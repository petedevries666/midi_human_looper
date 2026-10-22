"""Host-owned MIDI patch recall; no disk or snapshot work in the audio callback."""
import copy,json,logging,math,re,threading,time,uuid
from pathlib import Path
from project_sync import atomic_json

def slot_number(value):
    if type(value) is not int or not 1<=value<=127:raise ValueError('Patch number must be 1–127')
    return value

def checked_patch(path):
    from server import validate_patch_extensions
    if path.is_symlink() or not path.is_file() or path.stat().st_size>134217728:raise ValueError('Saved patch unavailable')
    patch=json.loads(path.read_text());validate_patch_extensions(patch)
    memory=patch.get('memory');globals_=patch.get('globals')
    if not isinstance(memory,list) or patch.get('work_mem_size')!=len(memory) or not 0<len(memory)<=2000000 or not isinstance(globals_,list) or len(globals_)!=9 or any(type(v) not in (int,float) or not math.isfinite(v) for v in memory+globals_):raise ValueError('Invalid saved patch')
    return patch

class RecallService:
    def __init__(self,state_manager,directory,library,entries):
        self.manager=state_manager;self.directory=Path(directory);self.library=Path(library);self.entries=entries
        self.path=self.directory/'patch-recall.json';self.lock=threading.RLock();self.wake=threading.Event()
        self.pending=None;self.active=None;self.phase='ready';self.error='';self.selected=0
        self.last_recalled=None
        self.settings=dict(version=1,enabled=False,channel=16,withSnapshot=True,links={})
        if self.path.exists():
            saved=json.loads(self.path.read_text());self.validate(saved);self.settings=saved
        self.recover_save()
        from switch_presets import Store
        self.selected=Store(self.library,None).read()['activeSlot']
        from chain_recall import ChainSaves
        self.chain_saves=ChainSaves(self)
        self.thread=threading.Thread(target=self.run,name='MBMF-patch-recall',daemon=True);self.thread.start()

    @staticmethod
    def validate(s):
        if not isinstance(s,dict) or set(s)!={'version','enabled','channel','withSnapshot','links'} or s['version']!=1 or type(s['enabled']) is not bool or type(s['withSnapshot']) is not bool or type(s['channel']) is not int or not 1<=s['channel']<=16 or not isinstance(s['links'],dict):raise ValueError('Invalid global MIDI recall configuration')
        for key,link in s['links'].items():
            if key not in {str(i) for i in range(1,128)} or not isinstance(link,dict) or set(link)!={'snapshot','bindings'} or not isinstance(link['snapshot'],str) or not isinstance(link['bindings'],dict):raise ValueError('Invalid snapshot association')

    def snapshot_path(self,relative):
        root=Path(self.manager.snapshot_dir).resolve();path=root/relative
        if not isinstance(relative,str) or path.is_symlink() or path.suffix!='.zss' or not path.resolve().is_relative_to(root):raise ValueError('Snapshot must belong to Zynthian')
        return path

    def one_entry(self):
        values=list(self.entries.values())
        if len(values)!=1:raise ValueError('Exactly one MBMF processor required')
        return values[0]

    def apply_reservation(self):
        entry=self.one_entry();c=entry['control'];state=c.request()
        result=c.request(op=53,value=self.settings['channel'] if self.settings['enabled'] else 0,revision=state['revision'],session=state['engineSessionId'])
        if result.get('status')!='ok':raise ValueError('Native Program Change reservation unavailable')

    def install_midi_hook(self):
        controls=self.manager.ctrldev_manager
        if getattr(controls,'_mbmf_recall_hook',False):return
        original=controls.midi_event
        def dispatch(device,event):
            return self.midi_event(device,event) or original(device,event)
        controls.midi_event=dispatch;controls._mbmf_recall_hook=True

    def midi_event(self,device,event):
        settings=self.settings
        # Oram's UI event queue pads every short MIDI event to three bytes;
        # actual JACK Program Change packets contain two bytes.
        if not settings['enabled'] or len(event) not in (2,3) or event[0]!=(0xc0|settings['channel']-1):return False
        # Restoring a snapshot must not recursively trigger another request.
        if 0<event[1]<128 and not (device==0xff and self.phase in ('snapshot','restore')):
            with self.lock:
                controls=[entry['control'] for entry in self.entries.values()]
                if self.active is None and self.pending is None and self.phase=='ready' and len(controls)==1 and self.last_recalled==(event[1],controls[0]) and self.selected==event[1]:return True
                if self.active==('recall',event[1]):self.pending=None
                else:self.pending=('recall',event[1]);self.wake.set()
        return True

    def status(self):
        if self.active is None:
            from switch_presets import Store
            self.selected=Store(self.library,None).read()['activeSlot']
        snapshots=[];root=Path(self.manager.snapshot_dir)
        for path in sorted(root.glob('*/*.zss')):
            if not path.is_symlink() and not path.name.startswith('.'):
                snapshots.append(dict(path=path.relative_to(root).as_posix(),name=path.stem))
        rows=[];chain_error=''
        if self.active is None and self.pending is None:
            try:rows=self.chain_saves.inventory()
            except (ValueError,OSError,KeyError,TypeError) as error:chain_error=str(error)
        phase='queued' if self.pending and not self.active else 'preflight' if self.active and self.phase=='ready' else self.phase
        return dict(settings=copy.deepcopy(self.settings),phase=phase,lastError=self.error,selectedSlot=self.selected,snapshots=snapshots,chainRecalls=rows,chainSaveError=chain_error)

    def request(self,request):
        action=request.get('operation')
        with self.lock:
            if action=='status':return self.status()
            if self.active or self.pending:raise ValueError('Patch operation in progress')
            if action=='configure':
                candidate={**self.settings,**{k:request[k] for k in ('enabled','channel','withSnapshot')}};self.validate(candidate)
                from zyngui import zynthian_gui_config
                if candidate['enabled'] and candidate['channel']==zynthian_gui_config.master_midi_channel+1:raise ValueError('Choose a channel different from the Zynthian master channel')
                previous=self.settings;self.settings=candidate
                try:self.apply_reservation();atomic_json(self.path,candidate)
                except Exception:self.settings=previous;self.apply_reservation();raise
            elif action=='link':
                slot=slot_number(request.get('slot'));relative=request.get('snapshot');candidate=copy.deepcopy(self.settings)
                if relative is None:candidate['links'].pop(str(slot),None)
                else:
                    path=self.snapshot_path(relative);self.validate_snapshot(path)
                    candidate['links'][str(slot)]=dict(snapshot=relative,bindings=self.one_entry()['host_chains'].links.snapshot())
                atomic_json(self.path,candidate);self.settings=candidate
            elif action=='save_chain':
                required={'action','operation','slot','chainId','identity','fingerprint','expectedEngineSessionId'}
                if set(request)!=required or slot_number(request['slot'])!=self.selected or type(request['chainId']) is not int or not 1<=request['chainId']<=255 or type(request['expectedEngineSessionId']) is not int or not re.fullmatch('[0-9a-f]{64}',str(request['fingerprint'])):
                    raise ValueError('Invalid chain-save request; refresh the active patch')
                uuid.UUID(request['identity'])
                self.pending=('save_chain',copy.deepcopy(request));self.wake.set()
            elif action in ('recall','save_pair'):
                slot=slot_number(request.get('slot'));self.pending=(action,slot);self.wake.set()
            else:raise ValueError('Unsupported patch recall operation')
            return self.status()

    def validate_snapshot(self,path):
        if not path.is_file() or path.stat().st_size>268435456:raise ValueError('Snapshot unavailable')
        document=json.loads(path.read_text())
        chains=document.get('chains');config=document.get('engine_config',{})
        if not isinstance(chains,dict) or not any(k.startswith('MB/') for k in config):raise ValueError('Snapshot must include an MBMF processor')
        # Actual Oram chain slots are dictionaries; engine config is authoritative
        # for current snapshots, and one engine/processor is required for recall.
        processors=[v.get('processors',{}) for k,v in config.items() if k.startswith('MB/')]
        if len(processors)!=1 or len(processors[0])!=1:raise ValueError('Snapshot requires exactly one MBMF processor')
        from chain_recall import validate_assets
        validate_assets(document,Path(self.manager.snapshot_dir).parent/'presets/lv2')
        return document

    @staticmethod
    def stop(entry):
        c=entry['control'];state=c.request();reply=c.request(op=2,revision=state['revision'],session=state['engineSessionId'])
        if reply.get('status')!='ok':raise ValueError('Could not stop MBMF')
        deadline=time.monotonic()+10
        while time.monotonic()<deadline:
            state=c.request()
            if not any(state.get(k) for k in ('activeNotes','instances','chainRunning','chainRecording','chainArmed')) and not state.get('pendingOutput'):return
            time.sleep(.02)
        raise ValueError('MBMF did not become idle')

    def load_patch(self,patch,slot,bindings=None):
        from switch_presets import Store
        entry=self.one_entry();c=entry['control'];presets=Store(self.library,c);presets.recover()
        patch=presets.materialize(patch,slot)
        state=c.request()
        result=c.request(op=5,target=patch['schema'],patch=patch,revision=state['revision'],session=state['engineSessionId'])
        if result.get('status')!='ok':raise ValueError('Native patch restoration rejected')
        if bindings is not None:
            links=entry['host_chains'].links;links.restore(bindings);links.synchronize()
            existing={str(i['id']) for i in c.request().get('instruments',[])}
            unresolved=[k for k,v in links.status()['bindings'].items() if k in existing and v.get('destination') is None]
            if unresolved:raise ValueError('Missing linked Zynthian destination for Instrument '+', '.join(unresolved))
        presets.on_patch(slot);self.selected=slot;self.apply_reservation()

    def recall(self,slot):
        patch=checked_patch(self.library/f'patch{slot}.json');link=self.settings['links'].get(str(slot));path=None
        if self.settings['withSnapshot']:
            if link is None:raise ValueError('No Zynthian snapshot linked to this patch; select patch-only or link a snapshot')
            path=self.snapshot_path(link['snapshot']);self.validate_snapshot(path)
        entry=self.one_entry();old=entry['control'].request();backup=entry['control'].request(op=4,revision=old['revision'],session=old['engineSessionId'])
        if backup.get('format')!='MIDI_HUMAN_LOOPER_PATCH':raise ValueError('Cannot retain current patch for recovery')
        from switch_presets import Store
        old_slot=Store(self.library,None).read()['activeSlot'];old_bindings=entry['host_chains'].links.snapshot()
        recovery=self.directory/'patch-recall-recovery.zss'
        prior_snapshot=getattr(self.manager,'last_snapshot_fpath',None)
        if path:
            try:
                if not self.manager.save_snapshot(str(recovery)):raise ValueError('Cannot retain current Zynthian rig for recovery')
            finally:self.manager.last_snapshot_fpath=prior_snapshot
        self.phase='stopping';self.stop(entry)
        try:
            if path:
                self.phase='snapshot'
                if not self.manager.load_snapshot(str(path)):raise ValueError('Zynthian snapshot load failed')
                deadline=time.monotonic()+45
                while time.monotonic()<deadline:
                    try:
                        fresh=self.one_entry();state=fresh['control'].request()
                        if state['engineSessionId']!=old['engineSessionId']:break
                    except (OSError,ValueError):pass
                    time.sleep(.1)
                else:raise ValueError('Restored MBMF engine not ready')
            self.phase='restore';self.load_patch(patch,slot,link['bindings'] if link else {})
            self.last_recalled=(slot,self.one_entry()['control'])
        except Exception as error:
            try:
                if path and not self.manager.load_snapshot(str(recovery)):raise ValueError('Previous Zynthian rig could not be restored')
                self.load_patch(backup,old_slot,old_bindings)
            except Exception as rollback:raise ValueError(f'{error}; RECOVERY FAILED: {rollback}') from error
            raise ValueError(f'{error}; previous patch restored') from error

    def recover_save(self):
        journal=self.directory/'patch-pair-journal.json'
        if not journal.exists():return
        data=json.loads(journal.read_text());slot=slot_number(data['slot']);stage=self.directory/'patch-pair-stage'
        # Accept old journals for recovery, but write new pairs in the native bank.
        prefixes=(f'MBMF/{slot:03}-',f'001-MBMF/{slot:03}-')
        if stage.is_symlink() or not data['snapshot'].startswith(prefixes) or set(data['existed'])-{'patch','snapshot','registry'}:raise ValueError('Invalid interrupted pair-save journal; originals preserved')
        target=self.snapshot_path(data['snapshot'])
        for destination,name in ((self.library/f'patch{slot}.json','patch'),(target,'snapshot'),(self.path,'registry')):
            backup=stage/(name+'.old')
            if name in data['existed']:destination.write_bytes(backup.read_bytes())
            else:destination.unlink(missing_ok=True)
        journal.unlink();self.settings=json.loads(self.path.read_text()) if self.path.exists() else self.settings

    def save_pair(self,slot):
        from patch_names import read
        from zynthian_chains import at_rest
        entry=self.one_entry();state=entry['control'].request()
        if not at_rest(state):raise ValueError('Stop MBMF and release keys before saving a pair')
        patch=entry['control'].request(op=4,revision=state['revision'],session=state['engineSessionId'])
        if patch.get('format')!='MIDI_HUMAN_LOOPER_PATCH':raise ValueError('Cannot export current patch')
        name=read(self.library).get(str(slot),'') or f'PATCH {slot:02}'
        safe=re.sub(r'[^\w .-]','_',name).strip(' .') or 'PATCH'
        relative=f'001-MBMF/{slot:03}-{safe}.zss';target=self.snapshot_path(relative);target.parent.mkdir(exist_ok=True)
        old_link=self.settings['links'].get(str(slot))
        if target.exists() and (old_link is None or old_link['snapshot']!=relative):raise ValueError('A snapshot with that name already exists; link it explicitly or choose another patch name')
        stage=self.directory/'patch-pair-stage'
        if stage.is_symlink():raise ValueError('Pair-save staging must not be a symlink')
        stage.mkdir(exist_ok=True)
        staged=stage/'snapshot.new'
        previous=getattr(self.manager,'last_snapshot_fpath',None)
        try:
            if not self.manager.save_snapshot(str(staged)):raise ValueError('Zynthian snapshot save failed; pair unchanged')
            self.validate_snapshot(staged)
        finally:self.manager.last_snapshot_fpath=previous
        candidate=copy.deepcopy(self.settings);candidate['links'][str(slot)]=dict(snapshot=relative,bindings=entry['host_chains'].links.snapshot())
        destinations=((self.library/f'patch{slot}.json','patch'),(target,'snapshot'),(self.path,'registry'))
        existed=[]
        for path,label in destinations:
            if path.exists():(stage/(label+'.old')).write_bytes(path.read_bytes());existed.append(label)
        journal=self.directory/'patch-pair-journal.json';atomic_json(journal,dict(slot=slot,snapshot=relative,existed=existed))
        try:
            atomic_json(destinations[0][0],patch);staged.replace(target);atomic_json(self.path,candidate);journal.unlink();self.settings=candidate
            self.manager.last_snapshot_fpath=str(target)
            from switch_presets import Store
            Store(self.library,entry['control']).on_patch(slot);self.selected=slot
        except Exception:self.recover_save();raise

    def run(self):
        while True:
            self.wake.wait();self.wake.clear()
            with self.lock:
                job=self.pending;self.pending=None;self.active=job
                if job is not None:self.phase='preflight';self.error=''
            if job is None:continue
            try:
                from patch_lock import library_lock
                with library_lock(self.library,wait=True):
                    if job[0]=='recall':self.recall(job[1])
                    elif job[0]=='save_chain':
                        self.phase='saving_chain';self.chain_saves.save(job[1])
                    else:self.save_pair(job[1])
            except Exception as error:self.error=str(error);logging.exception('MBMF patch operation failed')
            finally:
                with self.lock:self.active=None;self.phase='failed' if self.error else 'ready'
                if self.pending:self.wake.set()

def install(state_manager,directory,library,entries):
    service=getattr(state_manager,'_mbmf_patch_recall',None)
    if service is None:
        service=RecallService(state_manager,directory,library,entries);state_manager._mbmf_patch_recall=service;service.install_midi_hook()
    service.apply_reservation()
    return service
