"""Non-realtime MIDI input configuration; audio routing belongs to Oram."""
import copy
import hashlib
import json
from midi_inputs import Store,channels,enroll,inventory


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
        return {'available':bool(state.get('midiThruAvailable')),
                'enabled':bool(state.get('midiThruEnabled')),
                'engineSessionId':state['engineSessionId'],
                'revision':state.get('revision',1),
                'configurationRevision':self.fingerprint(registry),
                'inputs':inventory(registry,state.get('physicalMidiInputs',[])),
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
        next_registry=copy.deepcopy(registry)
        saved=enroll(next_registry,row['port'] or row['key'],row['name'],request['enabled'])
        saved['channels']=modes
        self.store.save(next_registry)
        # This requests one autoconnect pass. Never change TEACH's scoped relay
        # or connect JACK ports from an HTTP worker.
        self.refresh()
        return self.status()
