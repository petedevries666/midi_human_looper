"""Native Zynthian MIDI Tool adapter. The chain manager owns graph connections.
One isolated existing JSFX/JACK processor per Zynthian processor ID, not a new MIDI engine.
"""
import json
import os
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
        engine = subprocess.Popen([self.config['binary'],str(self.root/'midi_human_looper.jsfx'),socket_path,'--jack','--chain','--client',name],stdout=log,stderr=log)
        entry = dict(engine=engine,web=None,log=log,control=self.Control(socket_path),phrase=0,data=data)
        self.instances[pid] = entry
        self._live_entries[pid] = entry
        self.jackname = '^'+name+':'
        try:
            deadline=time.monotonic()+30
            while time.monotonic()<deadline:
                if engine.poll() is not None:raise RuntimeError('MBH engine failed; see '+str(data/'engine.log'))
                if Path(socket_path).is_socket():break
                time.sleep(.05)
            else:raise TimeoutError('MBH engine startup timeout')
            if entry['control'].request().get('status')!='ok':raise RuntimeError('MBH engine not ready')
            web=[sys.executable,str(self.root/'headless/server.py'),'--socket',socket_path,'--patch-dir',str(data),'--port',str(self.config.get('web_port_base',8765)+pid),'--bind',self.config.get('web_bind','127.0.0.1')]
            if self.config.get('token_file'):web+=['--token-file',self.config['token_file']]
            entry['web']=subprocess.Popen(web,stdout=log,stderr=log)
            processor.jackname=self.jackname
            self.processors.append(processor)
            processor.refresh_controllers()
            state=self.restored.get(str(pid))
            if state:self._restore(entry,state)
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
    def send_controller_value(self, zctrl):
        entry=self.instances[int(zctrl.processor.id)]
        action=zctrl.graph_path
        if action=='phrase':entry['phrase']=int(zctrl.value)-1;return
        if not zctrl.value:return
        control=entry['control'];state=control.request()
        common=dict(revision=state['revision'],session=state['engineSessionId'])
        if action in ('play','record','stop','finish'):
            response=control.request(op=20,target=entry['phrase'],arg={'stop':0,'play':1,'record':2,'finish':3}[action],**common)
        elif action=='save':
            patch=control.request(op=4,**common)
            if patch.get('format')!='MIDI_HUMAN_LOOPER_PATCH':raise RuntimeError('MBH save rejected; previous file retained')
            temporary=entry['data']/'patch1.json.tmp';temporary.write_text(json.dumps(patch));temporary.replace(entry['data']/'patch1.json');return
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
