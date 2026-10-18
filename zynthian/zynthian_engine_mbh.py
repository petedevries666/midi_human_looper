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


def mbh_snapshot_config(engine_config, processor_id):
    """Oram saves multiple MB engines as MB/N, while slots retain code MB."""
    if not isinstance(engine_config, dict):return None
    matches = [value for key, value in engine_config.items()
               if isinstance(key, str) and key.startswith('MB/') and isinstance(value, dict)
               and isinstance(value.get('processors'), dict)
               and str(processor_id) in value['processors']]
    # Legacy adapters aggregate all processors into every MB/N entry. Accept
    # duplicate copies only when this processor and host identities agree.
    if matches and any(value['processors'][str(processor_id)] != matches[0]['processors'][str(processor_id)]
                       or value.get('hostChainIdentities', {}) != matches[0].get('hostChainIdentities', {})
                       for value in matches[1:]):
        raise ValueError('Ambiguous MBMF processor snapshot; refusing reassignment')
    return matches[0] if matches else None


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
        ['update_check', {'name':'CHECK UPDATE','value':0,'is_trigger':True,'midi_autolearn':False,'value_min':0,'value_max':1,'graph_path':'update_check'}],
        ['update_install', {'name':'INSTALL UPDATE','value':0,'is_trigger':True,'midi_autolearn':False,'value_min':0,'value_max':1,'graph_path':'update_install'}],
        ['update_rollback', {'name':'ROLLBACK','value':0,'is_trigger':True,'midi_autolearn':False,'value_min':0,'value_max':1,'graph_path':'update_rollback'}],
        ['update_status', {'name':'UPDATE STATUS','value':0,'is_trigger':True,'midi_autolearn':False,'value_min':0,'value_max':1,'graph_path':'update_status'}],
    ]
    _ctrl_screens = [['Looper',['phrase','play','record','stop']],['Patch',['finish','save','load']],['Update',['update_check','update_install','update_rollback','update_status']]]
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
        self._ctrls=[[name,{**values,**({'value_max':128} if name=='phrase' and self.config.get('expanded_capacity') else {})}] for name,values in self._ctrls]
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
        source=self.root/'midi_human_looper.jsfx'
        if self.config.get('expanded_capacity'):
            from native_capacity import build_source
            source=data/'native-expanded.jsfx'
            source.write_text(build_source((self.root/'midi_human_looper.jsfx').read_text(encoding='utf-8')),encoding='utf-8')
        command=[self.config['binary'],str(source),socket_path,'--jack','--chain','--chain-timing',str(self.chain_timing),'--client',name]
        if self.grid_capture:command.append('--chain-grid-capture')
        if self.config.get('performance_trace') is True:command+=['--rt-trace',str(data/'rt-trace.csv')]
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
            manager = getattr(self.state_manager, 'chain_manager', None)
            if manager is not None:
                from zynthian_chains import ChainLinks, Bridge
                links = ChainLinks(manager, processor.chain_id, entry['control'],
                    entry.get('host_chain_snapshot'), getattr(self, 'host_chain_identities', {}),
                    mixer=getattr(self.state_manager, 'zynmixer', None))
                entry['host_chains'] = Bridge(data/'host-chains.sock', links,
                    on_refresh=lambda: self._refresh_host_chain_selectors(processor))
            web=[sys.executable,str(self.root/'headless/server.py'),'--socket',socket_path,'--patch-dir',str(data),'--port',str(self.config.get('web_port_base',8765)+pid),'--bind',self.config.get('web_bind','127.0.0.1')]
            if entry.get('host_chains'):
                web += ['--host-chain-socket', str(data/'host-chains.sock')]
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
            if entry.get('host_chains'):entry['host_chains'].close()
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
        try:
            from zyngine import zynthian_engine_mbh_router
            filtered_source=True
        except ImportError:
            filtered_source=False
        if source is not None and not source.synth_slots and not filtered_source:
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
        host_controls = []
        bridge = self.instances.get(int(processor.id), {}).get('host_chains')
        if bridge:
            status = bridge.links.status()
            state = bridge.links.control.request()
            for instrument in state.get('instruments', []):
                key = str(instrument['id'])
                selected = status['bindings'].get(key, {}).get('identity')
                choices = [None] + [c['identity'] for c in status['chains']]
                labels = ['UNLINKED'] + [f"C{c['chainId']} {c['name']} CH{c['channel'] or 'ALL'}" for c in status['chains']]
                if selected and selected not in choices:
                    choices.append(selected);labels.append('DESTINATION MISSING')
                symbol = 'host_chain_%s' % instrument['id']
                self._ctrls.append([symbol, dict(name='I%s Zynthian' % key,
                    value=choices.index(selected), labels=labels, ticks=list(range(len(choices))),
                    value_min=0, value_max=len(choices)-1, is_integer=True, midi_autolearn=False,
                    graph_path=('host_chain', instrument['id'], choices, status['inventoryRevision']))])
                host_controls.append(symbol)
            for start in range(0, len(host_controls), 4):
                self._ctrl_screens.append(['Instrument links %s' % (start//4+1), host_controls[start:start+4]])
        controllers = super().get_controllers_dict(processor)
        for symbol in host_controls:
            controllers[symbol].get_state = lambda full=True: {}
        for symbol in routes:
            # Oram ZS3 already saves chain.midi_out. Do not replay a second,
            # possibly stale knob value over restored authoritative routing.
            controllers[symbol].get_state = lambda full=True: {}
        for symbol in ('update_check','update_install','update_rollback','update_status'):
            controllers[symbol].get_state = lambda full=True: {}
        return controllers

    def _refresh_host_chain_selectors(self, processor):
        """Refresh controller data in place, without rebuilding widgets or routes.

        MB controls are built before following synth chains finish restoring.
        Keep existing controller objects so the open native page sees new labels.
        """
        bridge = self.instances.get(int(processor.id), {}).get('host_chains')
        if not bridge:return
        status = bridge.links.status()
        choices = [None] + [c['identity'] for c in status['chains']]
        labels = ['UNLINKED'] + [f"C{c['chainId']} {c['name']} CH{c['channel'] or 'ALL'}" for c in status['chains']]
        diagnostics = {}
        for symbol, controller in list(getattr(processor, 'controllers_dict', {}).items()):
            if not symbol.startswith('host_chain_'):continue
            instrument = int(symbol.removeprefix('host_chain_'))
            selected = status['bindings'].get(str(instrument), {}).get('identity')
            options, names = list(choices), list(labels)
            if selected and selected not in options:
                options.append(selected);names.append('DESTINATION MISSING')
            value = options.index(selected)
            graph = ('host_chain', instrument, options, status['inventoryRevision'])
            if controller.labels != names or controller.value != value or controller.graph_path != graph:
                # set_options reconfigures the controller model, never emits MIDI.
                controller.set_options(dict(labels=names,ticks=list(range(len(options))),
                    value_min=0,value_max=len(options)-1,value=value,is_trigger=False,
                    graph_path=graph))
                controller.is_dirty = True
            diagnostics[str(instrument)] = names[value]
        bridge.links.native_selectors = diagnostics

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
        if isinstance(zctrl.graph_path, tuple) and zctrl.graph_path[0] == 'host_chain':
            _, instrument, choices, inventory_revision = zctrl.graph_path
            bridge = self.instances[int(zctrl.processor.id)]['host_chains']
            state = bridge.links.control.request()
            index = int(zctrl.value)
            if index < 0 or index >= len(choices):raise ValueError('Invalid chain selection')
            bridge.links.bind(instrument, choices[index], inventory_revision,
                              state['revision'], state['engineSessionId'])
            return
        if isinstance(zctrl.graph_path,str) and zctrl.graph_path.startswith('update_'):
            if zctrl.value:self.update_control(zctrl.graph_path[7:])
            zctrl.value=0
            return
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

    def update_control(self, action):
        # Physical local confirmation is administrative authorization. This root
        # Unix request is not exposed through the editor's HTTP envelope.
        sys.path.insert(0,str(self.root/'zynthian/update'))
        from backend import client
        from zyngui import zynthian_gui_config
        gui=zynthian_gui_config.zyngui
        try:
            status=client('status')
            if action=='status':
                candidate=status.get('available')
                available=('\nAVAILABLE '+candidate['name']+' '+candidate['revision'][:12]+'\n'+candidate['changes'][:180]) if candidate else '\nNo reviewed update checked'
                gui.show_info('INSTALLED V'+status.get('version','?')+' '+status['installed'][:12]+available+'\n'+status['progress']['phase']+'\n'+status['progress']['message']);return
            if action=='check':
                client('check',native=True)
                gui.show_info('Checking reviewed releases.\nUse UPDATE STATUS for result.');return
            candidate=status.get('available')
            if status.get('recoveryRequired'):action='recover'
            if action=='install' and not candidate:raise ValueError('CHECK UPDATE first; no reviewed release available')
            if action=='rollback' and not status['rollbackAvailable']:raise ValueError('No previous working version')
            label=('INSTALL '+candidate['name']+'\n'+candidate['revision'][:12]+'\n'+candidate['changes'][:180]) if action=='install' else action.upper()
            def confirmed():
                try:
                    client(action,native=True,confirm=True,revision=candidate['revision'] if candidate else None)
                    gui.show_info('Update accepted.\nUse UPDATE STATUS.\nUI may restart; JACK unchanged.')
                except (OSError,ValueError) as error:gui.show_info(str(error))
            gui.show_confirm(label+'\nStop playback and save snapshot.\nUI/audio may be interrupted. Proceed?',confirmed)
        except (OSError,ValueError) as error:gui.show_info('UPDATE unavailable\n'+str(error))
    def _restore(self, entry, state):
        if state.get('version')!=1:raise ValueError('unsupported MBH processor snapshot')
        entry['phrase']=state['phrase']
        now=entry['control'].request()
        patch=state['patch']
        result=entry['control'].request(op=5,target=patch['schema'],patch=patch,revision=now['revision'],session=now['engineSessionId'])
        if result.get('status')!='ok':raise RuntimeError('MBH snapshot load rejected')
        entry['host_chain_snapshot'] = state.get('hostChainBindings', {})
        if entry.get('host_chains'):
            entry['host_chains'].links.restore(entry['host_chain_snapshot'])
    def get_extended_config(self):
        result={}
        for pid,entry in self._live_entries.items():
            now=entry['control'].request()
            patch=entry['control'].request(op=4,revision=now['revision'],session=now['engineSessionId'])
            if patch.get('format')!='MIDI_HUMAN_LOOPER_PATCH':raise RuntimeError('MBH snapshot save rejected')
            result[str(pid)]=dict(version=1,phrase=entry['phrase'],patch=patch)
            if entry.get('host_chains'):
                result[str(pid)]['hostChainBindings'] = entry['host_chains'].links.snapshot()
        identities = {}
        for entry in self._live_entries.values():
            if entry.get('host_chains'):identities.update(entry['host_chains'].links.identities())
        return dict(version=1,processors=result,hostChainIdentities=identities)
    def set_extended_config(self, config):
        if config.get('version')!=1:raise ValueError('unsupported MBH engine snapshot')
        self.host_chain_identities = config.get('hostChainIdentities', {})
        for entry in self.instances.values():
            if entry.get('host_chains'):
                entry['host_chains'].links.pending_identities = dict(self.host_chain_identities)
        self.restored=config['processors']
        for pid,entry in self.instances.items():
            if str(pid) in self.restored:self._restore(entry,self.restored[str(pid)])
