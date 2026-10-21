"""Native schema 8: 128 phrase sources and 64 switches, legacy schema 7 frozen.

Generate the native EEL variant from the shared engine. Every structural rewrite
is checked, so changes to the shared engine fail generation instead of guessing.
No UI/gfx development is added to the frozen REAPER source.
"""
import ast
import copy
import math
import operator
import re
from functools import lru_cache
from pathlib import Path

PHRASES, SWITCHES = 128, 64
ROOT = Path(__file__).resolve().parents[1]

def build_source(source):
    def change(old, new):
        nonlocal source
        if old not in source:
            raise ValueError('Native capacity source contract changed: '+old[:72])
        source = source.replace(old, new)
    change('IO_SCHEMA = 7;', 'IO_SCHEMA = 8;')
    # Native VELOCITY has a wider gain; frozen REAPER bounds remain unchanged.
    change('kind==0 ? 3 : kind==3 ?', 'kind==0 ? 8 : kind==3 ?')
    change('LAYERS = 16;', 'LAYERS = 128;')
    change('2+12*SW_STRIDE', '2+60*SW_STRIDE')
    change('12*SW_RT_STRIDE', '60*SW_RT_STRIDE')
    change('12*SW_STEPS', '60*SW_STEPS')
    change('12*SW_STRIDE', '60*SW_STRIDE')
    change('SW_COUNT=16;', 'SW_COUNT=64;')
    change('SW_RELEASE_SIZE=32;', 'SW_RELEASE_SIZE=128;')
    # Keep due boundaries in sample order, but stop scanning when none is due.
    # The legacy fixed outer loop does 64*64 scans per idle audio block after
    # capacity expansion. A bounded rescan is needed only after executing work.
    change('loop(SW_COUNT,\n conductor_qsi=-1;conductor_qoffs=samplesblock;conductor_qscan=0;',
           'conductor_qbudget=SW_COUNT;conductor_qagain=1;\nwhile(conductor_qbudget>0 && conductor_qagain)(\n conductor_qbudget-=1;conductor_qagain=0;\n conductor_qsi=-1;conductor_qoffs=samplesblock;conductor_qscan=0;')
    change('conductor_qsi>=0?(\n  conductor_qg=',
           'conductor_qsi>=0?(\n  conductor_qagain=1;conductor_qg=')
    # Native runtime scratch and lookup pages must stay clear of enlarged banks.
    source = re.sub(r'\b3\d{6}\b', lambda m:str(int(m[0])+3000000), source)
    change('INSTANCE_BASE=6100000;', 'INSTANCE_BASE=7000000;')
    change('mem[1000000+', 'mem[24000000+')
    change('mem[1700000+', 'mem[26000000+')
    change('FREE_FINISHED_BASE=6007180;FREE_LOOP_ANCHOR_BASE=6007100;',
           'FREE_FINISHED_BASE=6100200;FREE_LOOP_ANCHOR_BASE=6100000;')
    change('6008000', '6200000')
    change('6040768', '6462144')
    change('loop(33024,', 'loop(LAYERS*2064,')
    # Clear contiguous runtime pages in the VM's native implementation. Expanded
    # phrase capacity made interpreted per-cell STOP/PANIC clears miss JACK's
    # deadline. Keep every address and sentinel; never touch serialized sources.
    for counter in ('pv_i', 'gi'):
        change(f'{counter}=0;loop(LAYERS*2064,mem[6200000+{counter}]=0;{counter}+=1;);',
               'memset(6200000,0,LAYERS*2064);')
    change('j=0;loop(2048,idx=gi*2048+j;mem[engine_addr(SW_LIVE_OUT_BASE,idx)]=0;mem[engine_addr(SW_PHRASE_OUT_BASE,idx)]=0;mem[engine_addr(SW_LOOP_INPUT_BASE,idx)]=0;mem[I_ONCE_OUT_BASE+idx]=0;\n mem[input_addr(gi*2048+j)]=0;mem[input_addr((INST_CAP+gi)*2048+j)]=0;j+=1;);',
           'memset(engine_addr(SW_LIVE_OUT_BASE,gi*2048),0,2048);memset(engine_addr(SW_PHRASE_OUT_BASE,gi*2048),0,2048);memset(engine_addr(SW_LOOP_INPUT_BASE,gi*2048),0,2048);memset(I_ONCE_OUT_BASE+gi*2048,0,2048);memset(input_addr(gi*2048),0,2048);memset(input_addr((INST_CAP+gi)*2048),0,2048);')
    change('j=0;loop(INST_CAP*4096,mem[input_addr(j)]=0;j+=1;);',
           'j=0;loop(INST_CAP*2,memset(input_addr(j*2048),0,2048);j+=1;);')
    change('ch=0;loop(INST_CAP*2048+INST_CAP,mem[I_QUARANTINE_BASE+ch]=0;ch+=1;);',
           'memset(I_QUARANTINE_BASE,0,INST_CAP*2048+INST_CAP);')
    change('ch=0;loop(INST_CAP, note=0;loop(2048,mem[engine_addr(SW_LIVE_OUT_BASE,ch*2048+note)]=0;mem[engine_addr(SW_PHRASE_OUT_BASE,ch*2048+note)]=0;mem[engine_addr(SW_LOOP_INPUT_BASE,ch*2048+note)]=0;mem[I_ONCE_OUT_BASE+ch*2048+note]=0;note+=1;);ch+=1;);',
           'ch=0;loop(INST_CAP,memset(engine_addr(SW_LIVE_OUT_BASE,ch*2048),0,2048);memset(engine_addr(SW_PHRASE_OUT_BASE,ch*2048),0,2048);memset(engine_addr(SW_LOOP_INPUT_BASE,ch*2048),0,2048);memset(I_ONCE_OUT_BASE+ch*2048,0,2048);ch+=1;);')
    change('ch=0;loop(4096,mem[I_FALLBACK_BASE+ch]=0;ch+=1;);',
           'memset(I_FALLBACK_BASE,0,4096);')
    change('ch=SW_PHRASE_OUT_BASE;loop(SW_MEMORY_END-SW_PHRASE_OUT_BASE,mem[ch]=0;ch+=1;);',
           'memset(SW_PHRASE_OUT_BASE,0,SW_MEMORY_END-SW_PHRASE_OUT_BASE);')
    change('gi=0;loop(INST_CAP*2048,mem[I_ONCE_OUT_BASE+gi]=0;gi+=1;);',
           'memset(I_ONCE_OUT_BASE,0,INST_CAP*2048);')
    change('v=0;loop(INSTANCE_OWNERS,j=0;loop(128,\n idx=(v*INST_CAP+gi)*128+j;mem[NATIVE_ARP_HELD_BASE+idx]=0;mem[NATIVE_ARP_SOURCE_BASE+idx]=0;mem[NATIVE_MONO_SOURCE_BASE+idx]=0;j+=1;);v+=1;);',
           'v=0;loop(INSTANCE_OWNERS,idx=(v*INST_CAP+gi)*128;memset(NATIVE_ARP_HELD_BASE+idx,0,128);memset(NATIVE_ARP_SOURCE_BASE+idx,0,128);memset(NATIVE_MONO_SOURCE_BASE+idx,0,128);v+=1;);')
    # Per-instrument deletion still clears its own strided instance rows. A
    # global reset can clear each complete plane once without the EEL row loop.
    change('native_phrase_contract>=2?(v=0;loop(INSTANCE_OWNERS,idx=',
           'native_phrase_contract>=2?(!native_runtime_bulk_clear?(v=0;loop(INSTANCE_OWNERS,idx=')
    change('v+=1;);mem[NATIVE_MONO_OWNER_BASE+gi]=-1;);',
           'v+=1;););mem[NATIVE_MONO_OWNER_BASE+gi]=-1;);')
    change('pv_i=0;loop(INST_CAP,i_clear_runtime(pv_i);pv_i+=1;);',
           'native_runtime_bulk_clear=1;native_phrase_contract>=2?(memset(NATIVE_ARP_HELD_BASE,0,NATIVE_TRANSFORM_CELLS);memset(NATIVE_ARP_SOURCE_BASE,0,NATIVE_TRANSFORM_CELLS);memset(NATIVE_MONO_SOURCE_BASE,0,NATIVE_TRANSFORM_CELLS););pv_i=0;loop(INST_CAP,i_clear_runtime(pv_i);pv_i+=1;);native_runtime_bulk_clear=0;')
    change('j=0;loop(128,mem[engine_addr(ARP_HELD_COUNT_BASE,gi*128+j)]=0;mem[engine_addr(ARP_SOURCE_COUNT_BASE,gi*128+j)]=0;\n mem[engine_addr(SW_ARP_PHRASE_BASE,gi*128+j)]=0;mem[engine_addr(SW_ARP_PHRASE_SOURCE_BASE,gi*128+j)]=0;\n mem[engine_addr(MONO_HELD_COUNT_BASE,gi*128+j)]=0;mem[engine_addr(SW_MONO_PHRASE_BASE,gi*128+j)]=0;j+=1;);',
           ''.join(f'memset(engine_addr({page},gi*128),0,128);' for page in ('ARP_HELD_COUNT_BASE','ARP_SOURCE_COUNT_BASE','SW_ARP_PHRASE_BASE','SW_ARP_PHRASE_SOURCE_BASE','MONO_HELD_COUNT_BASE','SW_MONO_PHRASE_BASE')))
    # The JACK host pre-binds and clears these exact same pages with libc.
    # Other entry points retain the complete standalone EEL reset.
    change('native_free_time?(memset(6200000,0,LAYERS*2064););',
           'native_free_time && !native_host_bulk_clear?(memset(6200000,0,LAYERS*2064););')
    change('native_runtime_bulk_clear=1;native_phrase_contract>=2?(',
           'native_runtime_bulk_clear=1;native_phrase_contract>=2 && !native_host_bulk_clear?(')
    change('loop(16,mem[FREE_LOOP_ANCHOR_BASE', 'loop(LAYERS,mem[FREE_LOOP_ANCHOR_BASE')
    change('loop(16,mem[FREE_FINISHED_BASE', 'loop(LAYERS,mem[FREE_FINISHED_BASE')
    change('CONDUCTOR_BASE-16;', 'CONDUCTOR_BASE-256;')
    change('CONDUCTOR_BASE-1024;', 'CONDUCTOR_BASE-4096;')
    # Phrase timing / trigger channel / output policy beyond legacy phrase 16.
    change('mem[I_CFG_BASE]=IO_SCHEMA;', 'mem[I_CFG_BASE]=7;')
    anchor='PATCH_PAYLOAD_SIZE=I_LEGACY_PAYLOAD+I_CFG_SIZE;'
    change(anchor, anchor+'''
NATIVE_LEGACY_PAYLOAD=I_LEGACY_PAYLOAD+I_CFG_SIZE;
NATIVE_META_BASE=CONDUCTOR_BASE-8192;NATIVE_META_SIZE=1+LAYERS*3;
NATIVE_TIME_BASE=NATIVE_META_BASE+1;NATIVE_OUTPUT_BASE=NATIVE_TIME_BASE+LAYERS;
NATIVE_CHANNEL_BASE=NATIVE_OUTPUT_BASE+LAYERS;
PATCH_PAYLOAD_SIZE=NATIVE_LEGACY_PAYLOAD+NATIVE_META_SIZE;
mem[NATIVE_META_BASE]=8;native_meta_i=0;loop(LAYERS,mem[NATIVE_TIME_BASE+native_meta_i]=1;mem[NATIVE_OUTPUT_BASE+native_meta_i]=0;mem[NATIVE_CHANNEL_BASE+native_meta_i]=0;native_meta_i+=1;);
NATIVE_RELEASE_FLAGS=CONDUCTOR_BASE-6144;NATIVE_STOP_FLAGS=NATIVE_RELEASE_FLAGS+128;
NATIVE_SWITCH_RELEASE_FLAGS=NATIVE_STOP_FLAGS+128;
NATIVE_SNAPSHOT_ACTION_BASE=CONDUCTOR_BASE-7168;
NATIVE_SNAPSHOT_PARAMETER_BASE=CONDUCTOR_BASE-12000;native_snapshot_pending=0;
''')
    change('I_RUNTIME_END+si*6', 'NATIVE_SNAPSHOT_ACTION_BASE+si*6')
    # Pending phrase mute/solo/mode edits must cover all phrase sources.
    # A separate region avoids the legacy voice cursors at I_RUNTIME_END+1024.
    change('I_RUNTIME_END+520', 'NATIVE_SNAPSHOT_PARAMETER_BASE')
    change('slot<120', 'slot<(24+LAYERS*3+INST_CAP*6)')
    change('loop(120,', 'loop(24+LAYERS*3+INST_CAP*6,')
    change('kind==24?72+gi*6+row', 'kind==24?(24+LAYERS*3)+gi*6+row')
    change('slot<72?floor((slot-24)/3):floor((slot-72)/6)',
           'slot<(24+LAYERS*3)?floor((slot-24)/3):floor((slot-(24+LAYERS*3))/6)')
    change('row=slot<72?slot%3:(slot-72)%6;',
           'row=slot<(24+LAYERS*3)?slot%3:(slot-(24+LAYERS*3))%6;')
    # Do not scan 456 pending descriptor slots on every idle audio block.
    # Apply marks work; a deferred descriptor keeps the flag until it is safe.
    change('mem[b]=value;mem[b+1]=kind;', 'native_snapshot_pending=1;mem[b]=value;mem[b+1]=kind;')
    change('snap_host_enabled ? (\n    slot=0;loop(24+LAYERS*3+INST_CAP*6,',
           'snap_host_enabled && native_snapshot_pending ? (\n    native_snapshot_pending=0;slot=0;loop(24+LAYERS*3+INST_CAP*6,')
    change('mem[b+1]=0;\n      );\n    );slot+=1;);',
           'mem[b+1]=0;\n      );mem[b+1]>0?native_snapshot_pending=1;\n    );slot+=1;);')


    change('native_hold_release_mask=0;conductor_release_mask=0;', 'native_hold_release_mask=0;conductor_release_mask=0;native_flag_i=0;loop(320,mem[NATIVE_RELEASE_FLAGS+native_flag_i]=0;native_flag_i+=1;);')
    change('(j>=I_LEGACY_PAYLOAD?', '(j>=NATIVE_LEGACY_PAYLOAD?NATIVE_META_BASE+j-NATIVE_LEGACY_PAYLOAD:j>=I_LEGACY_PAYLOAD?')
    change('(SW_CFG_BASE+1+floor(layer/4)*SW_STRIDE+112+layer%4;);',
           '(layer>=16?NATIVE_TIME_BASE+layer:SW_CFG_BASE+1+floor(layer/4)*SW_STRIDE+112+layer%4;);')
    change('(SW_CFG_BASE+1+floor(layer/4)*SW_STRIDE+116+layer%4;);',
           '(layer>=16?NATIVE_OUTPUT_BASE+layer:SW_CFG_BASE+1+floor(layer/4)*SW_STRIDE+116+layer%4;);')
    change('(sw_cfg(floor(layer/4))+27+layer%4;);',
           '(layer>=16?NATIVE_CHANNEL_BASE+layer:sw_cfg(floor(layer/4))+27+layer%4;);')
    # A JSFX bitmask cannot represent 128 sources. Use bounded per-source flags.
    change('native_hold_release_mask|=1<<layer;', 'mem[NATIVE_RELEASE_FLAGS+layer]=1;native_hold_release_mask=1;')
    change('native_hold_release_mask&(1<<native_hold_layer)', 'mem[NATIVE_RELEASE_FLAGS+native_hold_layer]>0')
    change('native_hold_release(native_hold_layer,0);', '(mem[NATIVE_RELEASE_FLAGS+native_hold_layer]=0;native_hold_release(native_hold_layer,0););')
    change('free_loop_stop_mask&(1<<free_stop_i)?(', 'mem[NATIVE_STOP_FLAGS+free_stop_i]>0?(mem[NATIVE_STOP_FLAGS+free_stop_i]=0;')
    change('conductor_release_mask&(1<<conductor_release_i)?conductor_release(conductor_release_i,0,0);',
           'mem[NATIVE_SWITCH_RELEASE_FLAGS+conductor_release_i]>0?(mem[NATIVE_SWITCH_RELEASE_FLAGS+conductor_release_i]=0;conductor_release(conductor_release_i,0,0););')
    # Fixed-address charge cleanup also needs the expanded runtime accessor.
    for index in ('pv_i','si','gi'):
        change(f'{index}<4?SW_RT_BASE+{index}*32:DS_RT_BASE+({index}-4)*32',
               f'{index}<4?SW_RT_BASE+{index}*32:DS_RT_BASE+({index}-4)*32')
    # RESET/STOP+RESET reset both the legacy traversal and native Conductor.
    change('mem[r+10]=-1;);', 'mem[r+10]=-1;mem[CONDUCTOR_BASE+si*8+3]=-1;mem[CONDUCTOR_BASE+si*8+4]=0;mem[CONDUCTOR_BASE+si*8+5]=0;mem[CONDUCTOR_BASE+si*8+6]=0;mem[r+22]=0;mem[r+27]=0;mem[r+29]=0;mem[r+31]=0;);')
    from native_phrase_retrigger import extend as phrase_retrigger
    source = phrase_retrigger(source)
    from native_arp import extend
    source = extend(source)
    from native_echo_sources import extend as echo_sources
    return echo_sources(source)

def constants(source):
    """Resolve numeric allocation declarations, never execute EEL code."""
    values={};ops={ast.Add:operator.add,ast.Sub:operator.sub,ast.Mult:operator.mul,
                   ast.Div:operator.truediv,ast.Mod:operator.mod}
    def value(n):
        if isinstance(n,ast.Constant) and isinstance(n.value,(int,float)):return n.value
        if isinstance(n,ast.Name):return values[n.id]
        if isinstance(n,ast.BinOp):return ops[type(n.op)](value(n.left),value(n.right))
        if isinstance(n,ast.UnaryOp) and isinstance(n.op,ast.USub):return -value(n.operand)
        if isinstance(n,ast.Call) and isinstance(n.func,ast.Name) and n.func.id=='ceil':return math.ceil(value(n.args[0]))
        raise ValueError()
    for name,expr in re.findall(r'\b([A-Z][A-Z0-9_]*)\s*=\s*([^;]+);',source.split('function engine_addr')[0]):
        try:values[name]=value(ast.parse(expr.strip(),mode='eval').body)
        except (KeyError,ValueError,SyntaxError,TypeError):pass
    return {k:int(v) if int(v)==v else v for k,v in values.items()}

@lru_cache(maxsize=1)
def layouts():
    source=(ROOT/'midi_human_looper.jsfx').read_text(encoding='utf-8')
    return constants(source),constants(build_source(source))

def layout(patch):
    old,new=layouts()
    return new if patch.get('schema')==8 else old

def address(patch,index):
    if patch.get('schema')!=8:return index
    old,new=layouts()
    if index<old['COUNT_BASE']:return index
    names=('COUNT_BASE','MUTE_BASE','SOLO_BASE','VEL_BASE','MODE_BASE','TRIG_BASE','ONCEPOS_BASE','LEN_BASE','DECAY_BASE','REPEAT_BASE','PHRASE_NAME_BASE','PHRASE_NOTE_BASE')
    for name in names:
        size=256 if name=='PHRASE_NAME_BASE' else 16
        if old[name]<=index<old[name]+size:return new[name]+index-old[name]
    spans=(('INST_IN_BASE','PHRASE_NAME_BASE'),('INSTR_NAME_BASE','PHRASE_NOTE_BASE'),('WORK_MEM_SIZE','SW_LEGACY_PAYLOAD'),('SW_LEGACY_PAYLOAD','CC_LEGACY_PAYLOAD'),('CC_LEGACY_PAYLOAD','TF_LEGACY_PAYLOAD'),('TF_LEGACY_PAYLOAD','DS_LEGACY_PAYLOAD'),('DS_LEGACY_PAYLOAD','I_LEGACY_PAYLOAD'),('I_LEGACY_PAYLOAD','PATCH_PAYLOAD_SIZE'))
    for first,last in spans:
        if old[first]<=index<old[last]:return new[first]+index-old[first]
    raise ValueError('Unknown legacy address')

def migrate(patch):
    """Copy complete schema-7 source data to schema 8 without touching the input."""
    if patch.get('schema')==8:return patch
    if patch.get('schema') in range(1,7):patch=upgrade_legacy(patch)
    if patch.get('schema')!=7:raise ValueError('Unsupported legacy schema; original preserved')
    old,new=layouts();original=patch['memory']
    if len(original)!=old['PATCH_PAYLOAD_SIZE']:raise ValueError('Legacy patch dimensions changed; original preserved')
    result=copy.deepcopy(patch);memory=[0]*new['PATCH_PAYLOAD_SIZE']
    def span(a,b,n):memory[b:b+n]=original[a:a+n]
    span(0,0,old['COUNT_BASE'])
    for name in ('COUNT_BASE','MUTE_BASE','SOLO_BASE','VEL_BASE','MODE_BASE','TRIG_BASE','ONCEPOS_BASE','LEN_BASE','DECAY_BASE','REPEAT_BASE','PHRASE_NOTE_BASE'):
        default={'VEL_BASE':1,'MODE_BASE':1,'DECAY_BASE':.8,'PHRASE_NOTE_BASE':-1}.get(name,0)
        memory[new[name]:new[name]+PHRASES]=[default]*PHRASES
        span(old[name],new[name],16)
    for start,end in [('INST_IN_BASE','PHRASE_NAME_BASE'),('INSTR_NAME_BASE','PHRASE_NOTE_BASE')]:
        span(old[start],new[start],old[end]-old[start])
    span(old['PHRASE_NAME_BASE'],new['PHRASE_NAME_BASE'],16*16)
    for first,last in [('WORK_MEM_SIZE','SW_LEGACY_PAYLOAD'),('SW_LEGACY_PAYLOAD','CC_LEGACY_PAYLOAD'),('CC_LEGACY_PAYLOAD','TF_LEGACY_PAYLOAD'),('TF_LEGACY_PAYLOAD','DS_LEGACY_PAYLOAD'),('DS_LEGACY_PAYLOAD','I_LEGACY_PAYLOAD'),('I_LEGACY_PAYLOAD','PATCH_PAYLOAD_SIZE')]:
        span(old[first],new[first],old[last]-old[first])
    meta=new['NATIVE_LEGACY_PAYLOAD'];memory[meta]=8
    memory[meta+1:meta+1+PHRASES]=[1]*PHRASES
    # The former ALL SWITCHES sentinel moves from 16 to 64; slot identities stay.
    for i in range(16):
        b=new['SW_LEGACY_PAYLOAD']+1+i*128 if i<4 else new['DS_LEGACY_PAYLOAD']+2+(i-4)*128
        for action,target in ((14,17),(15,18),(16,19),(121,122)):
            if memory[b+action] in (3,5) and memory[b+target]==16:memory[b+target]=SWITCHES
    for i in range(16,SWITCHES):
        b=new['DS_LEGACY_PAYLOAD']+2+(i-4)*128
        for offset,v in {4:min(127,60+i),7:300,8:800,12:127,14:1,17:i,18:i,19:i}.items():memory[b+offset]=v
    result.update(schema=8,work_mem_size=len(memory),memory=memory)
    if 'conductor' in result:
        import uuid
        from conductor import decode,encode
        model=decode(result['conductor']);present={s['slot'] for s in model['sources']}
        for slot in range(1,PHRASES+1):
            if slot not in present:
                item=dict(id=str(uuid.uuid4()),type='PHRASE',slot=slot)
                if model['version']>=3:item['muteGroup']=0
                model['sources'].append(item)
        result['conductor']=encode(model)
    return result

def upgrade_legacy(patch):
    """Run established legacy migration in a private worker, never the live engine."""
    import os,subprocess,tempfile,time
    from server import Control
    binary=os.environ.get('HEADLESS_BINARY',str(ROOT/'.build/midi-headless-engine'))
    with tempfile.TemporaryDirectory(prefix='mbmf-legacy-migrate-') as tmp:
        directory=Path(tmp);sock=directory/'control.sock'
        with (directory/'worker.log').open('w') as log:
            worker=subprocess.Popen([binary,str(ROOT/'midi_human_looper.jsfx'),str(sock)],stdout=log,stderr=log)
            try:
                for _ in range(300):
                    if worker.poll() is not None:raise ValueError('Legacy migration worker failed; original preserved')
                    if sock.exists():break
                    time.sleep(.01)
                else:raise ValueError('Legacy migration worker unavailable; original preserved')
                control=Control(str(sock));state=control.request()
                reply=control.request(op=5,target=patch['schema'],patch=patch,revision=state['revision'],session=state['engineSessionId'])
                if reply.get('status')!='ok':raise ValueError('Legacy patch refused; original preserved')
                state=control.request();result=control.request(op=4,revision=state['revision'],session=state['engineSessionId'])
                if result.get('schema')!=7:raise ValueError('Legacy migration did not yield schema 7')
                return result
            finally:
                worker.terminate()
                try:worker.wait(timeout=5)
                except subprocess.TimeoutExpired:worker.kill();worker.wait()

if __name__=='__main__':
    import sys
    output=Path(sys.argv[1]);output.write_text(build_source((ROOT/'midi_human_looper.jsfx').read_text(encoding='utf-8')),encoding='utf-8')
