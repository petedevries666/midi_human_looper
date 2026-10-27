"""Non-realtime MIDI input configuration; audio routing belongs to Oram."""
import hashlib
import json
from midi_inputs import Store,channels,enroll,inventory,canonicalize


class Service:
    def __init__(self,path,control,refresh,legacy_ports=()):
        self.store=Store(path,legacy_ports)
        self.control=control
        self.refresh=refresh

    @staticmethod
    def fingerprint(registry):
        return hashlib.sha256(json.dumps(registry,sort_keys=True,separators=(',',':')).encode()).hexdigest()

    def status(self):
        state=self.control.request();registry=self.store.read()
        inputs=inventory(registry,state.get('physicalMidiInputs',[]))
        runtime=state.get('midiInputRuntime',{}).get('configuration',[1,0])
        from midi_thru_config import validate_inputs
        validate_inputs(runtime)
        ready={runtime[at+1] for at in range(2,len(runtime),19) if runtime[at+2]}
        for row in inputs:row['routingReady']=bool(state.get('midiThruEnabled') and row['enabled'] and row['id'] in ready)
        return {'available':bool(state.get('midiThruAvailable')),
                'enabled':bool(state.get('midiThruEnabled')),
                'engineSessionId':state['engineSessionId'],
                'revision':state.get('revision',1),
                'configurationRevision':self.fingerprint(registry),
                'inputs':inputs,
                'defaults':registry['defaults'],
                'patch':state.get('midiThru',{'version':1,'configuration':[1,0]})}

    def update_source(self,request):
        if set(request)!={'key','enabled','channels','expectedConfigurationRevision','expectedEngineSessionId'}:
            raise ValueError('Unsupported MIDI input edit')
        state=self.control.request()
        if not state.get('midiThruAvailable') or state['engineSessionId']!=request['expectedEngineSessionId']:
            raise ValueError('Engine changed or lacks MIDI THRU support; refresh')
        if not state.get('midiThruEnabled') and (state.get('activeNotes',0) or state.get('pendingOutput',0) or state.get('active',False)):
            raise ValueError('Arrêter la lecture et relâcher les notes avant la première activation MIDI THRU')
        registry=self.store.read()
        if request['expectedConfigurationRevision']!=self.fingerprint(registry):
            raise ValueError('MIDI input configuration changed; refresh before editing')
        modes=channels(request['channels'],True)
        row=next((r for r in inventory(registry,state.get('physicalMidiInputs',[])) if r['key']==request['key']),None)
        if row is None or row['ambiguous']:
            raise ValueError('MIDI source absent or ambiguous; no substitution allowed')
        if row['id'] is None and not row['present']:
            raise ValueError('Connect the MIDI source before enabling it')
        next_registry=canonicalize(registry,state.get('physicalMidiInputs',[]))
        if row['id'] is not None:
            row=next(r for r in inventory(next_registry,state.get('physicalMidiInputs',[])) if r['id']==row['id'])
        saved=enroll(next_registry,row['port'] or row['key'],row['name'],request['enabled'],identity=row['key'])
        saved['channels']=modes
        self.store.save(next_registry)
        # This requests one autoconnect pass. Never change TEACH's scoped relay
        # or connect JACK ports from an HTTP worker.
        self.refresh()
        return self.status()
