"""Native Zynthian MIDI Tool adapter. The chain manager owns graph connections.
One isolated existing JSFX/JACK processor per Zynthian processor ID, not a new MIDI engine.
"""
import json
import os
import tempfile
from pathlib import Path
import subprocess
import sys
import time
from zyngine.zynthian_engine import zynthian_engine

class zynthian_engine_mbh(zynthian_engine):
    _live_entries = {}  # Control-thread snapshot aggregation for the MB engine nickname.
    _ctrls = [
        ['phrase', {'value':1,'value_min':1,'value_max':16,'graph_path':'phrase'}],
        ['play', {'value':0,'is_trigger':True,'value_min':0,'value_max':1,'graph_path':'play'}],
        ['record', {'value':0,'is_trigger':True,'value_min':0,'value_max':1,'graph_path':'record'}],
        ['stop', {'value':0,'is_trigger':True,'value_min':0,'value_max':1,'graph_path':'stop'}],
        ['finish', {'value':0,'is_trigger':True,'value_min':0,'value_max':1,'graph_path':'finish'}],
        ['save', {'value':0,'is_trigger':True,'value_min':0,'value_max':1,'graph_path':'save'}],
        ['load', {'value':0,'is_trigger':True,'value_min':0,'value_max':1,'graph_path':'load'}],
    ]
    _ctrl_screens = [['Looper',['phrase','play','record','stop']],['Patch',['finish','save','load']]]
    def __init__(self, state_manager=None):
        super().__init__(state_manager)
        self.name = 'MIDI Bad Mother Fucker'
        self.nickname = 'MB'
        self.type = 'MIDI Tool'
        self.options['replace'] = False
        self.instances = {}
        self.restored = {}
        config_path = Path(os.environ.get('MBH_CONFIG', self.my_data_dir+'/midi-human-looper/install.json'))
        self.config = json.loads(config_path.read_text())
        if self.config.get('version') != 1:raise ValueError('unsupported MBH installation')
        self.chain_timing=self.config.get('chain_timing_version',1)
        if type(self.chain_timing) is not int or self.chain_timing not in (1,2):raise ValueError('unsupported chain timing version')
        self.grid_capture=self.config.get('chain_grid_capture',False)
        if type(self.grid_capture) is not bool:raise ValueError('invalid chain_grid_capture')
        self.root = Path(self.config['repository'])
        sys.path.insert(0, str(self.root/'headless'))
        from server import Control
        self.Control = Control
    def add_processor(self, processor):
        pid = int(processor.id)
        if pid < 0 or pid > 512 or self.instances or pid in self._live_entries:raise ValueError('invalid/duplicate processor ID')
        data = Path(self.my_data_dir)/'midi-human-looper'/f'processor-{pid}'
        data.mkdir(parents=True, exist_ok=True)
        socket_path = str(data/'control.sock')
        if Path(socket_path).exists() or Path(socket_path).is_symlink():
            raise RuntimeError('stale/occupied MBH socket: '+socket_path+'; check process ownership before cleanup')
        name = f'mbh_{pid}'
        log = (data/'engine.log').open('ab')
        command=[self.config['binary'],str(self.root/'midi_human_looper.jsfx'),socket_path,'--jack','--chain','--chain-timing',str(self.chain_timing),'--client',name]
        if self.grid_capture:command.append('--chain-grid-capture')
        engine = subprocess.Popen(command,stdout=log,stderr=log)
        entry = dict(engine=engine,web=None,log=log,control=self.Control(socket_path),phrase=0,data=data)
        self.instances[pid] = entry
        self._live_entries[pid] = entry
        # Oram treats this as both a regex source and an escaped literal destination.
        # A caret works for source discovery but breaks routes into this processor.
        self.jackname = name+':'
        try:
            deadline=time.monotonic()+30
            while time.monotonic()<deadline:
                if engine.poll() is not None:raise RuntimeError('MBH engine failed; see '+str(data/'engine.log'))
                if Path(socket_path).is_socket():break
                time.sleep(.05)
            else:raise TimeoutError('MBH engine startup timeout')
            if entry['control'].request().get('status')!='ok':raise RuntimeError('MBH engine not ready')
            state=self.restored.get(str(pid))
            if state:self._restore(entry,state)
            else:
                from project_sync import ProjectStore
                ProjectStore(data,entry['control']).restore()
            web=[sys.executable,str(self.root/'headless/server.py'),'--socket',socket_path,'--patch-dir',str(data),'--port',str(self.config.get('web_port_base',8765)+pid),'--bind',self.config.get('web_bind','127.0.0.1')]
            if self.config.get('token_file'):web+=['--token-file',self.config['token_file']]
            entry['web']=subprocess.Popen(web,stdout=log,stderr=log)
            processor.jackname=self.jackname
            self.processors.append(processor)
            processor.refresh_controllers()
        except BaseException:
            self.remove_processor(processor)
            raise
    def remove_processor(self, processor):
        entry=self.instances.pop(int(processor.id),None)
        if entry:self._live_entries.pop(int(processor.id),None)
        if entry:
            # Native SIGTERM runs owned-note PANIC and drains output before JACK deactivation.
            for child in (entry['web'],entry['engine']):
                if child and child.poll() is None:
                    child.terminate()
                    try:child.wait(timeout=10)
                    except subprocess.TimeoutExpired:child.kill();child.wait()
            entry['log'].close()
        if processor in self.processors:self.processors.remove(processor)
        processor.jackname=None
    def stop(self):
        for processor in list(self.processors):self.remove_processor(processor)
    def _routing_context(self, processor):
        manager = getattr(self.state_manager, 'chain_manager', None)
        if manager is None:
            return None, None
        return manager, manager.get_chain(processor.chain_id)

    def get_controllers_dict(self, processor):
        """Native chain destinations, not a second JACK connection manager.

        Oram owns routes and stores them in its snapshot. Portable MBMF projects
        contain MIDI channels, never these host-local chain IDs.
        """
        manager, source = self._routing_context(processor)
        self._ctrls = list(type(self)._ctrls)
        self._ctrl_screens = [[name, list(symbols)] for name, symbols in type(self)._ctrl_screens]
        routes = []
        if source is not None and not source.synth_slots:
            for chain_id, destination in sorted(manager.chains.items()):
                # Only instrument chains. Never route back to MBMF, main or self.
                if chain_id == source.chain_id or not destination.synth_slots:
                    continue
                if manager.will_midi_howl(source.chain_id, chain_id):
                    continue
                symbol = 'destination_%s' % chain_id
                title = destination.get_title()
                channel = destination.midi_chan
                label = '%s CH%s' % (title, channel+1 if isinstance(channel, int) and 0 <= channel < 16 else 'ALL')
                self._ctrls.append([symbol, dict(name=label, value=int(chain_id in source.midi_out),
                    value_min=0, value_max=1, is_toggle=True, midi_autolearn=False,
                    graph_path=('midi_destination', chain_id, destination))])
                routes.append(symbol)
            for start in range(0, len(routes), 4):
                self._ctrl_screens.append(['MIDI OUT %s' % (start//4+1), routes[start:start+4]])
        return super().get_controllers_dict(processor)

    def _set_destination(self, zctrl):
        manager, source = self._routing_context(zctrl.processor)
        _, chain_id, generation = zctrl.graph_path
        destination = manager.get_chain(chain_id) if manager else None
        if (source is None or source.synth_slots or destination is None or
            destination is not generation or not destination.synth_slots or
            source.chain_id == chain_id):
            raise ValueError('MIDI destination unavailable; reopen MBMF controls')
        enabled = bool(zctrl.value)
        if enabled and manager.will_midi_howl(source.chain_id, chain_id):
            raise ValueError('MIDI destination would create a feedback loop')
        if enabled == (chain_id in source.midi_out):
            return
        # Configure routes only at rest. Native PANIC also emits channel-mode
        # messages: invoking it implicitly could silence unrelated synth notes.
        # Refuse rather than disconnect sounding voices or silently stop music.
        control = self.instances[int(zctrl.processor.id)]['control']
        now = control.request()
        if now.get('status') != 'ok':
            raise RuntimeError('MBMF state unavailable; MIDI route retained')
        if (now.get('activeNotes', 0) or now.get('instances') or
            now.get('movements', {}).get('active', 0) or now.get('chainRunning') or
            now.get('chainRecording')):
            raise RuntimeError('Stop MBMF and release held notes before changing MIDI routes')
        source.toggle_midi_out(chain_id)

    def send_controller_value(self, zctrl):
        if isinstance(zctrl.graph_path, tuple) and zctrl.graph_path[0] == 'midi_destination':
            try:
                self._set_destination(zctrl)
            except BaseException:
                # Rejected knob changes must not pretend the route was committed.
                _, source = self._routing_context(zctrl.processor)
                zctrl.value = int(source is not None and zctrl.graph_path[1] in source.midi_out)
                raise
            return
        entry=self.instances[int(zctrl.processor.id)]
        action=zctrl.graph_path
        if action=='phrase':entry['phrase']=int(zctrl.value)-1;return
        if not zctrl.value:return
        control=entry['control'];state=control.request()
        common=dict(revision=state['revision'],session=state['engineSessionId'])
        if action in ('play','record','stop','finish'):
            response=control.request(op=40,target=entry['phrase'],arg={'stop':0,'play':1,'record':2,'finish':3}[action],**common)
        elif action=='save':
            from server import validate_patch_extensions
            target=entry['data']/'patch1.json'
            if target.exists():validate_patch_extensions(json.loads(target.read_text()))
            patch=control.request(op=4,**common)
            if patch.get('format')!='MIDI_HUMAN_LOOPER_PATCH':raise RuntimeError('MBH save rejected; previous file retained')
            from project_sync import atomic_json
            atomic_json(target,patch)
            return
        elif action=='load':
            patch=json.loads((entry['data']/'patch1.json').read_text());response=control.request(op=5,target=patch['schema'],patch=patch,**common)
        else:raise ValueError('unknown MBH action')
        if response.get('status')!='ok':raise RuntimeError('MBH rejected command: '+response.get('status','unknown'))
    def _restore(self, entry, state):
        if state.get('version')!=1:raise ValueError('unsupported MBH processor snapshot')
        entry['phrase']=state['phrase']
        now=entry['control'].request()
        patch=state['patch']
        result=entry['control'].request(op=5,target=patch['schema'],patch=patch,revision=now['revision'],session=now['engineSessionId'])
        if result.get('status')!='ok':raise RuntimeError('MBH snapshot load rejected')
    def get_extended_config(self):
        result={}
        for pid,entry in self._live_entries.items():
            now=entry['control'].request()
            patch=entry['control'].request(op=4,revision=now['revision'],session=now['engineSessionId'])
            if patch.get('format')!='MIDI_HUMAN_LOOPER_PATCH':raise RuntimeError('MBH snapshot save rejected')
            result[str(pid)]=dict(version=1,phrase=entry['phrase'],patch=patch)
        return dict(version=1,processors=result)
    def set_extended_config(self, config):
        if config.get('version')!=1:raise ValueError('unsupported MBH engine snapshot')
        self.restored=config['processors']
        for pid,entry in self.instances.items():
            if str(pid) in self.restored:self._restore(entry,self.restored[str(pid)])
