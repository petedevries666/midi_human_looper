"""Host-side Smart Switch library. Never schedules MIDI or modifies phrase content."""
import copy,hashlib,json,math,re,secrets,threading,time,uuid
from pathlib import Path
from project_sync import atomic_json
from conductor import decode as decode_conductor, encode as encode_conductor
from controller_config import decode as decode_controllers

FIELDS=(0,2,3,4,12,13,6,7,8,9,10,11,14,15,16,17,18,19)
SW_BASE=165316;DS_BASE=166828;I_BASE=168366;SIZE=171649
GESTURES=('tap','double','hold','long_hold')
def digest(value):return hashlib.sha256(json.dumps(value,sort_keys=True,separators=(',',':'),allow_nan=False).encode()).hexdigest()
def default_library():return dict(version=1,revision=1,presets={},links={},activeSlot=0)
def text(value,limit):
 if not isinstance(value,str) or not value or len(value)>limit or any(ord(c)<32 or 127<=ord(c)<160 for c in value):raise ValueError('Printable name required')
 return value

def validate_config(config):
 if not isinstance(config,dict) or set(config)!={'settings','sequence','name','longHold'}:raise ValueError('Incomplete switch preset')
 s=config['settings'];seq=config['sequence'];lh=config['longHold']
 if not isinstance(s,list) or len(s)!=18 or any(type(v) is not int for v in s):raise ValueError('Switch settings required')
 ranges=[(0,1),(0,2),(0,15),(0,127),(0,127),(0,127),(0,1),(50,2000),(100,5000),(0,3),(0,1),(0,64)]+[(0,9)]*3+[(0,64)]*3
 if any(not a<=v<=b for v,(a,b) in zip(s,ranges)) or (s[1]==2 and s[4]==s[5]):raise ValueError('Invalid switch or MIDI settings')
 if any(s[12+i]>=7 and s[15+i]>=48 for i in range(3)):raise ValueError('Invalid module target')
 if not isinstance(seq,list) or len(seq)>64 or any(type(v) is not int or not 1<=v<=128 for v in seq):raise ValueError('Invalid phrase references')
 if not isinstance(config['name'],str) or len(config['name'])>16 or any(not 32<=ord(c)<127 for c in config['name']):raise ValueError('Switch name must fit 16 characters')
 if not isinstance(lh,dict) or set(lh)!={'milliseconds','action','target'} or any(type(v) is not int for v in lh.values()) or not(lh['milliseconds']==0 or s[8]<lh['milliseconds']<=30000) or not 0<=lh['action']<=9 or not 0<=lh['target']<=64:raise ValueError('Invalid LONG HOLD settings')
 result=copy.deepcopy(config);result['settings'][11]=len(result['sequence']);return result

def switches(patch):
 from native_capacity import layout
 cfg=layout(patch);size=cfg['PATCH_PAYLOAD_SIZE'];sw_base=cfg['SW_LEGACY_PAYLOAD'];ds_base=cfg['DS_LEGACY_PAYLOAD'];i_base=cfg['I_LEGACY_PAYLOAD']
 if patch.get('format')!='MIDI_HUMAN_LOOPER_PATCH' or patch.get('schema') not in (7,8) or len(patch.get('memory',[]))!=size:raise ValueError('Preset propagation requires schema 7 or 8; original preserved')
 mem=patch['memory']
 if mem[sw_base]!=3 or mem[ds_base]!=6 or mem[i_base]!=7:raise ValueError('Unknown switch layout; original preserved')
 result={}
 for index in range(cfg['SW_COUNT']):
  base=sw_base+1+index*128 if index<4 else ds_base+2+(index-4)*128
  if mem[base+20]:
   ident=int(mem[base+21]);n=int(mem[base+11]);config=dict(settings=[int(mem[base+j]) for j in FIELDS],sequence=[int(v)+1 for v in mem[base+48:base+48+n]],name=''.join(chr(int(v)) for v in mem[base+32:base+48] if v),longHold=dict(zip(('milliseconds','action','target'),(int(v) for v in mem[base+120:base+123]))))
   validate_config(config);result[ident]=dict(slot=index,base=base,config=config)
 return result

def conductor_ids(patch):
 return {s['switchId'] for s in decode_conductor(patch['conductor'])['switches']} if patch.get('conductor') else set()

def empty_conductor_ids(patch):
 # Only the exact blank default is replaceable by an existing utility preset.
 if not patch.get('conductor'):return set()
 result=set()
 for sw in decode_conductor(patch['conductor'])['switches']:
  if set(sw)!={'switchId','traversal','transition','gesture','steps'}:continue
  if (sw['traversal'],sw['transition'],sw['gesture'])!=('SEQUENTIAL','IMMEDIATE','INSTANT'):continue
  steps=sw['steps']
  if len(steps)!=1 or set(steps[0])!={'id','transition','layers'} or steps[0]['transition']!='INHERIT':continue
  layers=steps[0]['layers']
  if len(layers)==1 and layers[0]['block'] is None:result.add(sw['switchId'])
 return result

def snapshot_bound(patch,owner):
 wire=patch.get('globalSnapshots',{}).get('configuration',[])
 if not wire or wire[0]<2:return False
 index=4
 for _ in range(int(wire[3])):
  count=int(wire[index+4]);index+=54+6*count
 if len(wire)<index+192:raise ValueError('Unknown snapshot action layout preserved')
 return any(wire[i]==owner and wire[i+2]>0 for i in range(index,index+192,4))

def module_targets(patch):
 # Pinned schema-7 mapping: primary arrays for instruments 1..3, appended arrays for the remaining slots.
 import ast,operator
 constants={};ops={ast.Add:operator.add,ast.Sub:operator.sub,ast.Mult:operator.mul,ast.Div:operator.truediv}
 def val(n):
  if isinstance(n,ast.Constant):return n.value
  if isinstance(n,ast.Name):return constants[n.id]
  if isinstance(n,ast.BinOp):return ops[type(n.op)](val(n.left),val(n.right))
  raise ValueError()
 from native_capacity import layout
 constants=layout(patch)
 source=''
 i_base=constants['I_LEGACY_PAYLOAD']
 for name,expression in re.findall(r'\b([A-Z][A-Z0-9_]*)\s*=\s*([^;]+);',source):
  try:constants[name]=val(ast.parse(expression.strip(),mode='eval').body)
  except (ValueError,KeyError,SyntaxError,TypeError):pass
 mem=patch['memory'];out=[]
 for slot in range(8):
  if not mem[i_base+2+slot]:continue
  ident=int(mem[i_base+10+slot]);base=int(constants['INST_TRANSFORM_TYPE_BASE'])+slot*6 if slot<3 else i_base+int(constants['I_INST_TRANSFORM_TYPE_BASE']-constants['I_CFG_BASE'])+(slot-3)*6
  for kind in sorted({abs(int(v)) for v in mem[base:base+6]}-{0}):out.append(dict(value=slot*6+kind-1,instrumentId=ident,engineType=kind))
 return out

def metadata(config,patch,owner):
 sw=switches(patch);capacity=64 if patch['schema']==8 else 16;by_slot={v['slot']:key for key,v in sw.items()};modules={m['value']:m for m in module_targets(patch)};result={}
 for i,key in enumerate(GESTURES):
  action=config['settings'][12+i] if i<3 else config['longHold']['action'];target=config['settings'][15+i] if i<3 else config['longHold']['target']
  if action in (3,5):result[key]=dict(type='switch',id='SELF' if by_slot.get(target)==owner else 'ALL' if target==capacity else by_slot.get(target))
  elif action in (7,8,9):result[key]=dict(type='module',**{k:v for k,v in modules.get(target,{}).items() if k!='value'})
 return result

def apply_config(patch,owner,config,refs=None,resolutions=None):
 result=copy.deepcopy(patch);sw=switches(result);refs=refs or {};resolutions=resolutions or {};warnings=[];errors=[]
 if owner not in sw:raise ValueError('Destination switch missing')
 if owner in conductor_ids(result):
  if owner not in empty_conductor_ids(result):raise ValueError('This switch owns a CONDUCTOR; preset application refused')
  document=decode_conductor(result['conductor']);document['switches']=[s for s in document['switches'] if s['switchId']!=owner];result['conductor']=encode_conductor(document)
  warnings.append('Replace the empty default Conductor with this utility preset; existing gestures retained')
 if snapshot_bound(result,owner):raise ValueError('SNAP has priority on this switch; use another switch or clear its SNAP actions first')
 config=validate_config(config);s=config['settings'];modules=module_targets(result)
 for i,key in enumerate(GESTURES):
  action=s[12+i] if i<3 else config['longHold']['action'];target=s[15+i] if i<3 else config['longHold']['target'];ref=refs.get(key,{})
  if action in (3,5):
   ident=resolutions.get(key,ref.get('id','SELF'))
   if ident=='SELF':ident=owner
   if ident=='ALL':target=64 if patch['schema']==8 else 16
   elif ident not in sw:errors.append(key+': destination switch missing')
   else:target=sw[ident]['slot']
  elif action in (7,8,9):
   choices=[m for m in modules if m.get('instrumentId')==ref.get('instrumentId') and m.get('engineType')==ref.get('engineType')]
   if key in resolutions:choices=[m for m in modules if m['value']==resolutions[key]]
   if len(choices)!=1:errors.append(key+': instrument/module target missing or ambiguous')
   else:target=choices[0]['value']
  if i<3:s[15+i]=target
  else:config['longHold']['target']=target
 for ident,other in sw.items():
  o=other['config']['settings']
  if ident!=owner and s[1] and o[1:4]==s[1:4]:errors.append('MIDI source already used by SWITCH '+str(ident))
 if patch.get('controllerEngine'):
  for source in decode_controllers(patch['controllerEngine'])['sources']:
   if s[1] and [source['kind'],source['channel'],source['number']]==s[1:4]:errors.append('MIDI source already used by CONTROLLER '+str(source['id']))
 base=sw[owner]['base'];mem=result['memory'];s[11]=len(config['sequence'])
 for j,value in zip(FIELDS,s):mem[base+j]=value
 mem[base+48:base+112]=[n-1 for n in config['sequence']]+[0]*(64-len(config['sequence']))
 mem[base+32:base+48]=[ord(c) for c in config['name']]+[0]*(16-len(config['name']))
 mem[base+120:base+123]=[config['longHold'][key] for key in ('milliseconds','action','target')]
 if config['sequence']:warnings.append('NEXT uses this patch’s phrase slots; verify their musical content')
 return result,config,warnings,errors

class Store:
 def __init__(self,directory,control,lock=None):
  self.directory=Path(directory);self.path=self.directory/'smart-switch-presets.json';self.control=control;self.lock=lock or threading.RLock();self.plans={};self.active_slot=0
 def read(self):
  if not self.path.exists():return default_library()
  if self.path.stat().st_size>2000000:raise ValueError('Preset library oversized')
  data=json.loads(self.path.read_text(encoding='utf-8'))
  if set(data)!={'version','revision','presets','links','activeSlot'} or data['version']!=1:raise ValueError('Unknown preset library preserved')
  if type(data['activeSlot']) is not int or not 0<=data['activeSlot']<=127:raise ValueError('Invalid saved active patch slot')
  for ident,p in data['presets'].items():uuid.UUID(ident);text(p['name'],64);validate_config(p['config'])
  return data
 def current(self):
  state=self.control.request()
  if state.get('activeNotes') or state.get('instances') or state.get('chainRunning') or state.get('chainArmed') or state.get('chainRecording') or state.get('movements',{}).get('active') or state.get('switchLearn',{}).get('target') or state.get('controllerLearn',{}).get('target'):raise ValueError('Stop MBMF and release keys before editing switch presets')
  p=self.control.request(op=4,revision=state['revision'],session=state['engineSessionId'])
  if p.get('format')!='MIDI_HUMAN_LOOPER_PATCH':raise ValueError('Engine configuration changed')
  return state,p
 def inventory(self):
  with self.lock:
   data=self.read();saved=[]
   for slot in range(1,128):
    path=self.directory/f'patch{slot}.json'
    if not path.exists():continue
    try:
     if path.stat().st_size>134217728:raise ValueError('Saved patch oversized')
     p=json.loads(path.read_text());owners=conductor_ids(p)-empty_conductor_ids(p)
     saved.append(dict(slot=slot,switches=[dict(id=k,name=v['config']['name'],conductor=k in owners,snapshot=snapshot_bound(p,k)) for k,v in switches(p).items()],modules=module_targets(p)))
    except (ValueError,KeyError,TypeError) as error:saved.append(dict(slot=slot,switches=[],modules=[],error=str(error)))
   try:
    _,p=self.current();current=dict(switches=[dict(id=k,slot=v['slot'],name=v['config']['name']) for k,v in switches(p).items()],modules=module_targets(p))
   except ValueError:current=dict(switches=[],modules=[])
   return dict(library=data,patches=saved,currentTargets=current,currentSlot=self.active_slot)
 def preview(self,request):
  with self.lock,self.control.lock:
   state,patch=self.current();data=self.read();data['activeSlot']=self.active_slot;operation=request.get('operation');owner=request.get('switchId')
   if type(owner) is not int or owner not in switches(patch):raise ValueError('Switch required')
   if state['revision']!=request.get('expectedRevision') or state['engineSessionId']!=request.get('expectedEngineSessionId'):raise ValueError('Engine changed; reopen preview')
   if operation not in ('save','update','apply','link','propagate','unlink','delete'):raise ValueError('Unknown preset operation')
   if operation in ('update','propagate','unlink') and 'slot' in request:
    if type(request['slot']) is not int or not 1<=request['slot']<=127:raise ValueError('Choose the current patch identity')
    data['activeSlot']=request['slot']
   ident=request.get('presetId');preset=data['presets'].get(ident);files={};summary=[];warnings=[];errors=[];current_config=None;current_owner=owner
   if operation in ('save','update'):
    config=validate_config(request.get('config'));name=text(request.get('name'),64)
    if owner in conductor_ids(patch)-empty_conductor_ids(patch):raise ValueError('Save only switches without a CONDUCTOR')
    if snapshot_bound(patch,owner):raise ValueError('SNAP actions use patch-specific snapshots; save a classic switch instead')
    if operation=='save':ident=str(uuid.uuid4())
    elif not preset:raise ValueError('Preset missing')
    preset=dict(name=name,config=config,references=metadata(config,patch,owner));data['presets'][ident]=preset;summary.append('Save preset '+name+' (MIDI source, thresholds and four actions included)')
   elif not preset:raise ValueError('Preset missing')
   if operation in ('apply','link'):
    _,current_config,w,e=apply_config(patch,owner,preset['config'],preset.get('references'),request.get('resolutions'));warnings+=w;errors+=e;summary.append('Apply to current SWITCH '+str(owner))
    active=request.get('slot',self.active_slot or 1)
    if type(active) is not int or not 1<=active<=127:raise ValueError('Choose the current patch slot')
    data['activeSlot']=active;path=self.directory/f'patch{active}.json'
    previous=json.loads(path.read_text()) if path.exists() else None
    if previous is not None:
     if set(previous)-{'format','schema','work_mem_size','globals','memory','controllerEngine','globalSnapshots','conductor'}:raise ValueError('Unknown saved patch fields preserved')
     switches(previous)
    changed,_,_,_=apply_config(patch,owner,preset['config'],preset.get('references'),request.get('resolutions'))
    files[str(path)]=dict(old=previous,new=changed);summary.append(f'SAVE current configuration to PATCH {active} (replaces its saved version)')
    if operation=='link':data['links'].setdefault(str(active),{})[str(owner)]=ident
    else:data['links'].get(str(active),{}).pop(str(owner),None)
   if operation=='unlink':data['links'].get(str(data.get('activeSlot',0)),{}).pop(str(owner),None);summary.append('Detach current switch; its settings stay unchanged')
   targets=request.get('targets',[]) if operation=='propagate' else []
   if operation=='update':
    targets=[dict(slot=int(slot),switchId=int(key),linked=True) for slot,links in data['links'].items() for key,value in links.items() if value==ident]
   if operation=='propagate' and (not isinstance(targets,list) or not targets or len(targets)>64):raise ValueError('Select at least one saved patch destination')
   for item in targets:
    slot,key=item.get('slot'),item.get('switchId')
    if type(slot) is not int or not 1<=slot<=127 or type(key) is not int:raise ValueError('Select saved patch destinations')
    path=self.directory/f'patch{slot}.json'
    if not path.exists():errors.append('PATCH '+str(slot)+' is not saved');continue
    old=files.get(str(path),{}).get('new') or json.loads(path.read_text());new,resolved,w,e=apply_config(old,key,preset['config'],preset.get('references'),item.get('resolutions'))
    warnings += [f'PATCH {slot}: '+x for x in w];errors += [f'PATCH {slot}: '+x for x in e]
    if str(path) not in files:files[str(path)]=dict(old=json.loads(path.read_text()))
    files[str(path)]['new']=new
    if item.get('linked'):data['links'].setdefault(str(slot),{})[str(key)]=ident
    else:data['links'].get(str(slot),{}).pop(str(key),None)
    summary.append(f'PATCH {slot} / SWITCH {key}'+(' · LINKED' if item.get('linked') else ' · COPY'))
    if data.get('activeSlot')==slot:current_config=resolved;current_owner=key
   if operation=='delete':
    if any(ident in links.values() for links in data['links'].values()):raise ValueError('Unlink preset destinations before deleting')
    del data['presets'][ident];summary.append('Delete preset '+preset['name'])
   if preset and operation not in ('delete','unlink'):
    cfg=preset['config'];s=cfg['settings'];lh=cfg['longHold'];summary.append(f"SOURCE {('UNASSIGNED','NOTE','CC')[s[1]]} {s[3]} / CH {s[2]+1} / PRESS {s[4]} / RELEASE {s[5]}");summary.append(f"DOUBLE {s[7]} ms / HOLD {s[8]} ms / LONG HOLD {lh['milliseconds']} ms")
    names=('NONE','NEXT PHRASE','STOP PHRASES','RESET SEQUENCE','RESET ALL','STOP + RESET','PANIC','TOGGLE MODULE','ENABLE MODULE','DISABLE MODULE')
    summary.append(' / '.join(k.upper().replace('_',' ')+': '+names[s[12+i] if i<3 else lh['action']] for i,k in enumerate(GESTURES)))
   data['revision']+=1;token=secrets.token_hex(16);self.plans={k:v for k,v in self.plans.items() if v['expires']>time.monotonic()}
   old_patch=new_patch=None
   if current_config and current_owner in empty_conductor_ids(patch):
    old_patch=patch
    new_patch,_,_,conversion_errors=apply_config(patch,current_owner,current_config,metadata(current_config,patch,current_owner))
    errors+=conversion_errors
   self.plans[token]=dict(oldPatch=old_patch,newPatch=new_patch,expires=time.monotonic()+180,oldLibrary=self.read(),library=data,files=files,config=current_config,owner=current_owner,oldConfig=switches(patch)[current_owner]['config'],revision=state['revision'],session=state['engineSessionId'],errors=errors)
   return dict(previewId=token,summary=summary,warnings=warnings,errors=errors,presetId=ident)
 def execute(self,token):
  with self.lock,self.control.lock:
   plan=self.plans.pop(token,None)
   if not plan or plan['expires']<time.monotonic():raise ValueError('Preview expired; preview again')
   if plan['errors']:raise ValueError('Resolve missing destinations and MIDI conflicts before applying')
   state,_=self.current()
   if state['revision']!=plan['revision'] or state['engineSessionId']!=plan['session'] or digest(self.read())!=digest(plan['oldLibrary']):raise ValueError('Configuration changed since preview')
   for name,entry in plan['files'].items():
    if (json.loads(Path(name).read_text()) if Path(name).exists() else None)!=entry['old']:raise ValueError('Saved patch changed since preview')
   journal=self.directory/'smart-switch-preset-transaction.json';atomic_json(journal,dict(version=1,files=plan['files'],library=plan['library'],oldLibrary=plan['oldLibrary']))
   written=[];native_changed=False
   try:
    for name,entry in plan['files'].items():atomic_json(name,entry['new']);written.append(name)
    config=plan['config']
    if config:
     s=list(config['settings']);s[11]=len(config['sequence']);lh=config['longHold'];wire=s+[n-1 for n in config['sequence']]+[0]*(64-len(config['sequence']))+[ord(c) for c in config['name']]+[0]*(16-len(config['name']))+[lh[k] for k in ('milliseconds','action','target')]
     if plan.get('newPatch'):
      result=self.control.request(op=5,arg=1,target=plan['newPatch']['schema'],patch=plan['newPatch'],revision=state['revision'],session=state['engineSessionId'])
     else:result=self.control.request(op=41,target=plan['owner'],settings=wire,revision=state['revision'],session=state['engineSessionId'])
     if result.get('status')!='ok':raise ValueError('Engine refused preset; saved patches restored')
     native_changed=True
    atomic_json(self.path,plan['library']);self.active_slot=plan['library']['activeSlot'];journal.unlink();return dict(status='ok',library=plan['library'])
   except Exception:
    if native_changed:
     old=plan['oldConfig'];s=list(old['settings']);s[11]=len(old['sequence']);lh=old['longHold'];wire=s+[n-1 for n in old['sequence']]+[0]*(64-len(old['sequence']))+[ord(c) for c in old['name']]+[0]*(16-len(old['name']))+[lh[k] for k in ('milliseconds','action','target')]
     fresh=self.control.request()
     if plan.get('oldPatch'):self.control.request(op=5,arg=1,target=plan['oldPatch']['schema'],patch=plan['oldPatch'],revision=fresh['revision'],session=fresh['engineSessionId'])
     else:self.control.request(op=41,target=plan['owner'],settings=wire,revision=fresh['revision'],session=fresh['engineSessionId'])
    for name in written:
     if plan['files'][name]['old'] is None:Path(name).unlink(missing_ok=True)
     else:atomic_json(name,plan['files'][name]['old'])
    atomic_json(self.path,plan['oldLibrary']);journal.unlink(missing_ok=True);raise
 def recover(self):
  journal=self.directory/'smart-switch-preset-transaction.json'
  if not journal.exists():self.active_slot=self.read()['activeSlot'];return
  p=json.loads(journal.read_text())
  for name in p['files']:
   if Path(name).resolve().parent!=self.directory.resolve() or not re.fullmatch(r'patch(?:[1-9]|[1-9][0-9]|1[01][0-9]|12[0-7])\.json',Path(name).name):raise ValueError('Invalid preset recovery path')
  all_new=all(Path(name).exists() and digest(json.loads(Path(name).read_text()))==digest(entry['new']) for name,entry in p['files'].items())
  if all_new:atomic_json(self.path,p['library'])
  else:
   for name,entry in p['files'].items():
    if Path(name).resolve().parent!=self.directory.resolve():raise ValueError('Invalid preset recovery path')
    if entry['old'] is None:Path(name).unlink(missing_ok=True)
    else:atomic_json(name,entry['old'])
   atomic_json(self.path,p['oldLibrary'])
  journal.unlink()
  self.active_slot=self.read()['activeSlot']
 def on_patch(self,slot):
  with self.lock:
   data=self.read();data['activeSlot']=slot;self.active_slot=slot;data['revision']+=1;atomic_json(self.path,data)
 def materialize(self,patch,slot):
  with self.lock:
   data=self.read();out=patch
   for owner,ident in data['links'].get(str(slot),{}).items():
    if int(owner) not in switches(out):continue # Deleted switches stay deleted.
    preset=data['presets'].get(ident)
    if not preset:raise ValueError('Linked switch preset missing; original patch preserved')
    out,_,_,errors=apply_config(out,int(owner),preset['config'],preset.get('references'))
    if errors:raise ValueError('; '.join(errors))
   return out

