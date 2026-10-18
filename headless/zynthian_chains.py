"""Host-only instrument links. Never changes JACK or ZynMidiRouter routes."""
import hashlib
import json
import logging
import math
import time
from pathlib import Path
import socket
import socketserver
import threading
import unicodedata
import uuid


def signature(chain):
    return [[int(p.id), str(p.eng_code)] for slot in chain.synth_slots for p in slot]


def at_rest(state):
    return not any((state.get('chainRunning'), state.get('chainRecording'),
                    state.get('chainArmed'), state.get('activeNotes'),
                    state.get('instances'), state.get('movements', {}).get('active'),
                    state.get('targetSnapshotId')))


class ChainLinks:
    def __init__(self, manager, source_id, control, saved=None, identities=None, mixer=None):
        self.manager, self.source_id, self.control = manager, source_id, control
        self.mixer = mixer
        self._mixer_sync = {}
        self.lock = threading.RLock()
        self.bindings = {}
        self.pending_identities = dict(identities or {})
        self.restore(saved or {})

    def restore(self, saved):
        if not isinstance(saved, dict) or len(saved) > 128:
            raise ValueError('Invalid host chain bindings')
        result = {}
        for key, value in saved.items():
            if not str(key).isdigit() or not 1 <= int(key) <= 16777215:
                raise ValueError('Invalid instrument identity')
            result[str(int(key))] = str(uuid.UUID(value))
        with self.lock:
            self.bindings = result

    def destinations(self):
        result = []
        for chain_id, chain in list(self.manager.chains.items()):
            if chain_id == self.source_id or not chain.synth_slots:
                continue
            if any(p.eng_code == 'MB' for slot in chain.midi_slots for p in slot):
                continue
            if self.manager.will_midi_howl(self.source_id, chain_id):
                continue
            identity = getattr(chain, '_mbmf_instrument_identity', None)
            prior = self.pending_identities.get(str(chain_id))
            if prior and prior.get('signature') == signature(chain):
                identity = prior['identity']
            if identity is None:
                identity = str(uuid.uuid4())
            if prior or not hasattr(chain, '_mbmf_instrument_identity'):
                uuid.UUID(identity)
                chain._mbmf_instrument_identity = identity
            # Consume once: a subsequently recycled chain ID never inherits it.
            self.pending_identities.pop(str(chain_id), None)
            channel = chain.midi_chan + 1 if type(chain.midi_chan) is int and 0 <= chain.midi_chan < 16 else None
            result.append(dict(identity=identity, chainId=chain_id, name=str(chain.get_title()),
                               channel=channel, signature=signature(chain)))
        return sorted(result, key=lambda c: c['chainId'])

    def identities(self):
        with self.lock:
            return {str(c['chainId']): {'identity': c['identity'], 'signature': c['signature']}
                    for c in self.destinations()}

    def snapshot(self):
        with self.lock:
            return dict(self.bindings)

    def status(self):
        with self.lock:
            chains = self.destinations()
            by_id = {c['identity']: c for c in chains}
            state = self.control.request()
            instruments = {str(i['id']): i for i in state.get('instruments', [])}
            links = {}
            for instrument_id, identity in self.bindings.items():
                chain = by_id.get(identity)
                instrument = instruments.get(instrument_id)
                if instrument is None:
                    status = 'instrument-unavailable'
                elif chain is None:
                    status = 'destination-unavailable'
                elif chain['channel'] is None:
                    status = 'fixed-channel-required'
                elif instrument['output'] != chain['channel'] or instrument['name'] != self.engine_name(chain):
                    status = 'pending'
                else:
                    status = 'synchronized'
                links[instrument_id] = dict(identity=identity, status=status,
                                           destination=chain, volume=self.chain_volume(chain), pan=self.chain_pan(chain))
            revision = hashlib.sha256(json.dumps(chains, sort_keys=True).encode()).hexdigest()
            return dict(version=1, routesManaged=False, inventoryRevision=revision,
                        chains=chains, bindings=links, engineRevision=state['revision'],
                        engineSessionId=state['engineSessionId'],
                        nativeSelectors=getattr(self, 'native_selectors', {}))

    def chain_volume(self, destination):return self.chain_mixer_value(destination, 'volume')

    def chain_pan(self, destination):return self.chain_mixer_value(destination, 'pan')

    def chain_mixer_value(self, destination, field):
        if self.mixer is None or destination is None:return None
        chain=self.manager.chains.get(destination['chainId'])
        index=getattr(chain,'mixer_chan',None)
        # Never allow the library's out-of-range clamp to target the main bus.
        if type(index) is not int or not 0<=index<self.mixer.MAX_NUM_CHANNELS-1:return None
        getter=getattr(self.mixer, 'get_level' if field=='volume' else 'get_balance',None)
        if not callable(getter):return None
        value=getter(index)
        return float(value) if type(value) in (int,float) and math.isfinite(value) and (0 if field=='volume' else -1)<=value<=1 else None

    def set_volume(self, instrument_id, identity, value, expected_volume, inventory_revision, session):
        return self.set_mixer_value('volume',instrument_id,identity,value,expected_volume,inventory_revision,session)

    def set_pan(self, instrument_id, identity, value, expected_pan, inventory_revision, session):
        return self.set_mixer_value('pan',instrument_id,identity,value,expected_pan,inventory_revision,session)

    def set_mixer_value(self, field, instrument_id, identity, value, expected_volume, inventory_revision, session):
        if type(instrument_id) is not int or any(type(v) not in (int,float) or not math.isfinite(v) or not (0 if field=='volume' else -1)<=v<=1 for v in (value,expected_volume)):
            raise ValueError('Invalid chain '+field)
        with self.lock:
            status=self.status()
            binding=status['bindings'].get(str(instrument_id))
            if status['engineSessionId']!=session or status['inventoryRevision']!=inventory_revision or not binding or binding['identity']!=identity or binding['status']!='synchronized':
                raise ValueError('Linked chain changed; refresh the volume control')
            actual=binding[field]
            if actual is None or abs(actual-expected_volume)>0.00001:raise ValueError('Chain '+field+' changed; refresh and try again')
            destination=binding['destination'];chain=self.manager.chains.get(destination['chainId'])
            index=getattr(chain,'mixer_chan',None)
            if type(index) is not int or not 0<=index<self.mixer.MAX_NUM_CHANNELS-1 or getattr(chain,'_mbmf_instrument_identity',None)!=identity:raise ValueError('Chain mixer unavailable')
            setter=self.mixer.set_level if field=='volume' else self.mixer.set_balance
            setter(index,float(value))
            readback=self.chain_mixer_value(destination,field)
            if readback is None or abs(readback-value)>0.00001:raise ValueError('Chain '+field+' was not confirmed')
            self.synchronize_mixer()
            return self.status()

    def synchronize_mixer(self):
        """Bridge native automation at control rate; never write audio from the callback."""
        if self.mixer is None:return
        with self.lock:
            if not self.bindings:
                self._mixer_sync.clear()
                return
            state=self.control.request();session=state['engineSessionId']
            destinations={d['identity']:d for d in self.destinations()};alive=set()
            for key,identity in sorted(self.bindings.items(),key=lambda item:int(item[0])):
                destination=destinations.get(identity)
                instrument=next((i for i in state['instruments'] if str(i['id'])==key),None)
                if destination is None or instrument is None or 'hostMixer' not in instrument:continue
                chain=self.manager.chains.get(destination['chainId'])
                if chain is None or instrument['output']!=destination['channel']:continue
                index=getattr(chain,'mixer_chan',None)
                if type(index) is not int or not 0<=index<self.mixer.MAX_NUM_CHANNELS-1:continue
                for field,kind in (('volume',25),('pan',26)):
                    actual=self.chain_mixer_value(destination,field)
                    if actual is None:continue
                    record_key=(session,key,identity,field);alive.add(record_key)
                    record=self._mixer_sync.get(record_key);native=instrument['hostMixer'];sequence=native[field+'Sequence']
                    if record is None or abs(actual-record['physical'])>0.000001:
                        # Startup and physical/Web fader moves are authoritative manual takeover.
                        response=self.control.request(op=32,target=int(key),arg=kind,macro=[0,actual],revision=state['revision'],session=session)
                        if response.get('status')!='ok':continue
                        state=response;instrument=next(i for i in state['instruments'] if str(i['id'])==key)
                        sequence=instrument['hostMixer'][field+'Sequence']
                    elif sequence!=record['sequence']:
                        value=native[field]
                        if self.manager.chains.get(destination['chainId']) is not chain or self.chain_mixer_value(destination,field)!=actual:
                            self._mixer_sync.pop(record_key,None);continue
                        setter=self.mixer.set_level if field=='volume' else self.mixer.set_balance
                        setter(index,float(value));actual=self.chain_mixer_value(destination,field)
                        if actual is None or abs(actual-value)>.00001:raise RuntimeError('Automated chain mixer readback failed')
                    self._mixer_sync[record_key]=dict(physical=actual,sequence=sequence)
            self._mixer_sync={key:value for key,value in self._mixer_sync.items() if key in alive}

    @staticmethod
    def engine_name(chain):
        text = unicodedata.normalize('NFKD', chain['name']).encode('ascii', 'ignore').decode()
        return ''.join(c for c in text if 32 <= ord(c) < 127)[:16] or 'CHAIN ' + str(chain['chainId'])

    def bind(self, instrument_id, identity, inventory_revision, revision, session):
        with self.lock:
            current = self.status()
            if (current['inventoryRevision'] != inventory_revision or
                    current['engineRevision'] != revision or current['engineSessionId'] != session):
                raise ValueError('State changed; refresh the chain selector')
            state = self.control.request()
            if not at_rest(state):
                raise ValueError('Stop MBMF and release all keys before linking an instrument')
            if type(instrument_id) is not int or not any(i['id'] == instrument_id for i in state['instruments']):
                raise ValueError('Instrument unavailable')
            if identity is None:
                self.bindings.pop(str(instrument_id), None)
            else:
                destination = next((c for c in current['chains'] if c['identity'] == identity), None)
                if destination is None:
                    raise ValueError('Destination unavailable')
                if destination['channel'] is None:
                    raise ValueError('Set a fixed MIDI channel on this Zynthian chain first')
                self.bindings[str(instrument_id)] = identity
            self.synchronize()
            return self.status()

    def relink_channels(self, inventory_revision, revision, session):
        """Explicit recovery only: preserve living links and never guess ties."""
        with self.lock:
            current=self.status()
            if (current['inventoryRevision']!=inventory_revision or current['engineRevision']!=revision or current['engineSessionId']!=session):
                raise ValueError('State changed; refresh before relinking')
            state=self.control.request()
            if state['revision']!=revision or state['engineSessionId']!=session or not at_rest(state):
                raise ValueError('Stop MBMF and release all keys before relinking')
            report=[]
            for instrument in state['instruments']:
                key=str(instrument['id']);old=current['bindings'].get(key)
                if old and old['destination'] is not None:
                    report.append(dict(instrumentId=instrument['id'],status='preserved'));continue
                matches=[c for c in current['chains'] if c['channel'] is not None and c['channel']==instrument['output']]
                if len(matches)==1:
                    self.bindings[key]=matches[0]['identity'];status='linked'
                else:status='ambiguous' if matches else 'missing'
                report.append(dict(instrumentId=instrument['id'],status=status))
            self.synchronize()
            result=self.status();result['relinkReport']=report
            return result

    def synchronize(self):
        with self.lock:
            if not self.bindings:return
            chains = {c['identity']: c for c in self.destinations()}
            for instrument_id, identity in list(self.bindings.items()):
                chain = chains.get(identity)
                if chain is None or chain['channel'] is None:
                    continue
                # Reobserve before every write: a user can start playing between updates.
                for field in ('output', 'name'):
                    state = self.control.request()
                    instrument = next((i for i in state['instruments'] if str(i['id']) == instrument_id), None)
                    if not at_rest(state) or instrument is None:
                        break
                    value = chain['channel'] if field == 'output' else self.engine_name(chain)
                    if instrument[field] == value:
                        continue
                    args = dict(op=9, target=int(instrument_id), arg=1, value=value) if field == 'output' else dict(op=36, target=int(instrument_id), arg=1, name=value)
                    result = self.control.request(revision=state['revision'], session=state['engineSessionId'], **args)
                    if result.get('status') != 'ok':
                        break


class Bridge:
    """One bounded local endpoint per processor, owned by its native adapter."""
    def __init__(self, path, links, on_refresh=None, recall=None):
        self.path, self.links = Path(path), links
        self.on_refresh = on_refresh
        if self.path.exists() or self.path.is_symlink():
            raise RuntimeError('Host-chain socket already exists; inspect its owner')
        bridge = self

        class Handler(socketserver.StreamRequestHandler):
            def handle(self):
                self.connection.settimeout(3)
                try:
                    line = self.rfile.readline(4097)
                    if len(line) > 4096 or not line.endswith(b'\n'):
                        raise ValueError('Bounded JSON request required')
                    request = json.loads(line)
                    if not isinstance(request,dict):raise ValueError('JSON object required')
                    if request.get('action')=='patch_recall' and recall is not None:
                        result=recall.request(request)
                    elif request == {'action': 'status'}:
                        result = bridge.links.status()
                    elif set(request)=={'action','inventoryRevision','expectedRevision','expectedEngineSessionId'} and request['action']=='relink_channels':
                        result=bridge.links.relink_channels(request['inventoryRevision'],request['expectedRevision'],request['expectedEngineSessionId'])
                    elif set(request)=={'action','instrumentId','identity','value','expectedPan','inventoryRevision','expectedEngineSessionId'} and request['action']=='pan':
                        result=bridge.links.set_pan(request['instrumentId'],request['identity'],request['value'],request['expectedPan'],request['inventoryRevision'],request['expectedEngineSessionId'])
                    elif set(request)=={'action','instrumentId','identity','value','expectedVolume','inventoryRevision','expectedEngineSessionId'} and request['action']=='volume':
                        result=bridge.links.set_volume(request['instrumentId'],request['identity'],request['value'],request['expectedVolume'],request['inventoryRevision'],request['expectedEngineSessionId'])
                    elif set(request) == {'action', 'instrumentId', 'identity', 'inventoryRevision', 'expectedRevision', 'expectedEngineSessionId'} and request['action'] == 'bind':
                        result = bridge.links.bind(request['instrumentId'], request['identity'], request['inventoryRevision'], request['expectedRevision'], request['expectedEngineSessionId'])
                    else:
                        raise ValueError('Unsupported host chain request')
                except (ValueError, TypeError, KeyError, OSError) as error:
                    result = {'error': str(error)}
                self.wfile.write(json.dumps(result).encode() + b'\n')

        self.server = socketserver.ThreadingUnixStreamServer(str(self.path), Handler)
        self.server.daemon_threads = True
        self.path.chmod(0o600)
        self.stop_event = threading.Event()
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.worker = threading.Thread(target=self.run, daemon=True)
        self.worker.start()

    def run(self):
        slow=0;last_error=0
        while not self.stop_event.wait(.04):
            try:
                now=time.monotonic()
                if now>=slow:
                    self.links.synchronize()
                    if self.on_refresh:self.on_refresh()
                    slow=now+1
                self.links.synchronize_mixer()
            except Exception:
                now=time.monotonic()
                if now-last_error>=1:
                    logging.exception('MBMF host-chain synchronization deferred');last_error=now

    def close(self):
        self.stop_event.set()
        self.server.shutdown()
        self.server.server_close()
        self.worker.join(timeout=20)
        self.thread.join(timeout=5)
        self.path.unlink(missing_ok=True)


def bridge_request(path, request):
    with socket.socket(socket.AF_UNIX) as client:
        client.settimeout(20)
        client.connect(str(path))
        client.sendall(json.dumps(request).encode() + b'\n')
        with client.makefile('rb') as stream:
            line = stream.readline(131073)
        if len(line) > 131072 or not line.endswith(b'\n'):
            raise ValueError('Oversized host inventory')
        return json.loads(line)
