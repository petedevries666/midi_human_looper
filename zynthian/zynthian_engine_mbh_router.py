"""Register dedicated MBMF as a native Oram MIDI source, without MIDI feedback.

Only terminal synth chains may receive the virtual input. No direct synth JACK
fanout, and no edits to Zynthian's real-time router implementation.
"""
import logging
import re
import json
import ctypes
from pathlib import Path

# Explicit opt-in: default Zynthian input routing is untouched.
CONFIG_PATH = Path("/zynthian/zynthian-my-data/midi-human-looper/install.json")


def sources(context):
    result = {}
    for chain in context.chain_manager.chains.values():
        if chain.synth_slots or not chain.midi_slots:
            continue
        for processor in chain.midi_slots[-1]:
            if processor.eng_code == 'MB':
                name = processor.engine.get_jackname()
                for port in context.jclient.get_ports(re.escape(name), is_midi=True, is_output=True):
                    if re.fullmatch(r'mbh_\d+:midi_out', port.name):
                        result[port.name] = port
    return result



def _read_exclusive_ports():
    """Exact JACK input port names, never an inferred keyboard or synth."""
    try:
        config = json.loads(CONFIG_PATH.read_text(encoding='utf-8'))
    except FileNotFoundError:
        return []
    ports = config.get('exclusive_midi_input_ports', [])
    if (not isinstance(ports, list) or any(not isinstance(p, str) or
            not p or p.startswith(('mbh_', 'ZynMidiRouter:')) for p in ports)
            or len(ports) != len(set(ports))):
        raise ValueError('invalid exclusive_midi_input_ports')
    return ports


def _native_output_count(context, index):
    # Oram's get_max_num_zmops() counts chain slots only (16 here).
    # The native getter returns -1 past the complete matrix, including
    # reserved and device outputs. Probe read-only, bounded, once per process.
    cached = getattr(context, '_mbmf_native_output_count', None)
    if cached is not None:
        return cached
    for output in range(256):
        value = context.lib_zyncore.zmop_get_route_from(output, index)
        if value == -1:
            if output <= context.state_manager.get_max_num_zmops():
                raise ValueError('Incomplete native output matrix')
            context._mbmf_native_output_count = output
            return output
        if value not in (0, 1):
            raise ValueError('Invalid native route readback')
    raise ValueError('Unbounded native output matrix')


def _quarantine_virtual(context):
    """Block native MB virtual source *before* restoring physical bypass routes.

    Native ZynMidiRouter matrices are invisible in jack_lsp. Closing the
    virtual source first makes rollback safe even when devN_in JACK remains
    connected until Oram reconciles its desired graph.
    """
    owned = getattr(context, '_mbmf_source_inputs', {})
    virtual = set(sources(context)) | {r['name'] for r in owned.values()}
    indices = {i for i,p in enumerate(context.devices_in)
               if p is not None and p.name in virtual}
    for record in owned.values():
        if record.get('learn_relay'):record['learn_relay'].allowed=()
    safe = True
    # Device and sequencer outputs also have native routes. Closing only
    # chain outputs leaves MIDI-thru / hardware return paths unguarded.
    try:
        count = _native_output_count(context, next(iter(indices))) if indices else 0
        if type(count) is not int or not 0 <= count <= 256:
            raise ValueError('Invalid native output count')
    except Exception:
        logging.exception('MBMF cannot enumerate native outputs; source blocked')
        return False
    # A removed chain can leave its JACK port and native slot alive for another
    # autoconnect pass. Do not forget its ownership just because sources() no
    # longer sees the processor. Never write a recycled unrelated device slot.
    for index, record in list(owned.items()):
        if index >= len(context.devices_in):
            logging.error('MBMF retired native slot unavailable; restore blocked')
            safe = False
        elif context.devices_in[index] is None:
            indices.add(index)
        elif context.devices_in[index].name != record['name']:
            # Oram may move MB to another input slot during USB hotplug or
            # snapshot recall. Retire old ownership only after JACK proves no
            # managed virtual source still feeds that recycled native input.
            # Never restore modes/flags/routes over the unrelated new device.
            try:
                connections=context.jclient.get_all_connections(f'ZynMidiRouter:dev{index}_in')
                if any(p.name in virtual for p in connections):
                    raise RuntimeError('virtual edge still connected to recycled slot')
                relay=record.get('learn_relay')
                drivers=getattr(getattr(getattr(context,'state_manager',None),'ctrldev_manager',None),'drivers',{})
                if relay is not None and drivers.get(index) is relay:
                    # end() writes flags at the old index, now owned by someone
                    # else. This relay has no external resources to release.
                    relay.allowed=();del drivers[index]
                del owned[index]
                logging.warning('MBMF retired disconnected recycled native input %s',index)
            except Exception:
                logging.error('MBMF native slot recycled; restore blocked pending graph reconciliation')
                safe = False
    for index in sorted(indices):
        destinations = set(range(count))
        destinations.update(owned.get(index, {}).get('routes', {}))
        for zmop in sorted(destinations):
            try:
                if context.lib_zyncore.zmop_set_route_from(zmop, index, 0) != 1:
                    raise RuntimeError('native quarantine setter failed')
                if context.lib_zyncore.zmop_get_route_from(zmop, index) != 0:
                    raise RuntimeError('native quarantine readback failed')
            except Exception:
                logging.exception('MBMF virtual input could NOT be quarantined')
                safe = False
    return safe


def _restore_exclusive(context):
    """Restore owned physical routes only once virtual output is quarantined."""
    saved = getattr(context, '_mbmf_exclusive', None)
    if not saved:
        return True
    if not _quarantine_virtual(context):
        logging.error('MBMF leaves physical input isolated: unsafe restore')
        return False
    chains = context.chain_manager.chains
    restored = True
    for (zmop, index), (chain, port_name, previous) in saved['routes'].items():
        if chains.get(chain.chain_id) is not chain or chain.zmop_index != zmop:
            continue
        if port_name is not None and (index >= len(context.devices_in) or
                context.devices_in[index] is None or
                context.devices_in[index].name != port_name):
            continue
        try:
            if context.lib_zyncore.zmop_set_route_from(zmop, index, previous) != 1:
                raise RuntimeError('physical restore setter failed')
            if context.lib_zyncore.zmop_get_route_from(zmop, index) != previous:
                raise RuntimeError('physical restore readback failed')
        except Exception:
            restored = False
            logging.exception('MBMF failed restoring exclusive MIDI route')
    for index, (port_name, previous) in saved['modes'].items():
        if index >= len(context.devices_in) or context.devices_in[index] is None:
            continue
        if context.devices_in[index].name != port_name:
            continue
        try:
            if context.lib_zyncore.zmip_set_flag_active_chain(index, previous) != 1:
                raise RuntimeError('physical mode restore setter failed')
            if context.lib_zyncore.zmip_get_flag_active_chain(index) != previous:
                raise RuntimeError('physical mode restore readback failed')
            context.devices_in_mode[index] = previous
        except Exception:
            restored = False
            logging.exception('MBMF failed restoring exclusive MIDI input mode')
    if restored:
        context._mbmf_exclusive = None
    return restored


def _apply_exclusive(context, requested, virtual_names):
    """Keyboard -> MB -> native virtual input -> synth, without direct bypass.

    Explicit named physical inputs go to MB, not directly to other chains.
    ZynSMF/step/CV returns to MB are blocked to avoid a transport-time
    feedback path. All unrelated devices and their other routes are retained.
    """
    if not requested:
        # No explicit consent to native feedback-sensitive routing.
        # The caller blocks the virtual source; any saved keyboard matrix
        # may be restored only after native virtual quarantine.
        return _restore_exclusive(context)
    chains = context.chain_manager.chains
    mb_chains = [c for c in chains.values() if isinstance(c.zmop_index, int) and c.zmop_index >= 0 and _contains_mb(c)]
    if len(mb_chains) != 1 or len(virtual_names) != 1:
        _restore_exclusive(context)
        logging.error('MBMF exclusive input requires exactly one dedicated MB chain')
        return False

    # Zynthian's internal seq/step/CV input indices lie beyond device slots.
    limit = getattr(context, 'max_num_devs', None)
    if type(limit) is not int or limit < 1 or limit > len(context.devices_in):
        _restore_exclusive(context)
        logging.error('MBMF exclusive input: invalid native device-slot count')
        return False
    indexes = {}
    for index, port in enumerate(context.devices_in[:limit]):
        if port is not None and port.name in requested:
            if port.name in indexes:
                _restore_exclusive(context)
                logging.error('MBMF duplicate keyboard input %s', port.name)
                return False
            indexes[port.name] = index
    if not indexes or any(name in virtual_names for name in requested):
        _restore_exclusive(context)
        logging.error('MBMF configured exclusive keyboard port missing or unsafe')
        return False
    missing = set(requested) - set(indexes)
    if missing:
        # A disconnected explicitly selected controller must not mute another
        # selected controller. Never infer or substitute an unselected device.
        logging.warning('MBMF disconnected configured inputs skipped: %s', ', '.join(sorted(missing)))

    # If native slots or chain instances were recycled, restore only valid
    # old ownership and capture a fresh baseline for the new graph.
    old = getattr(context, '_mbmf_exclusive', None)
    if old:
        # A changed opt-in keyboard list must release every previously
        # owned input first; otherwise the old keyboard stays silently
        # excluded from synths and the new one is isolated as well.
        retargeted = set(old['modes']) != set(indexes.values())
        if retargeted and not _restore_exclusive(context):
            return False
        old = getattr(context, '_mbmf_exclusive', None)
    if old:
        stale = any((i >= len(context.devices_in) or
                     context.devices_in[i] is None or
                     context.devices_in[i].name != name)
                    for i, (name, _) in old['modes'].items())
        stale |= any(chains.get(chain.chain_id) is not chain or chain.zmop_index != zmop
                     for (zmop, _), (chain, _, _) in old['routes'].items())
        if stale and not _restore_exclusive(context):
            return False
    saved = getattr(context, '_mbmf_exclusive', None)
    if not saved:
        context._mbmf_exclusive = saved = {'routes': {}, 'modes': {}}

    mb = mb_chains[0]
    internal = []
    for getter in ('get_zmip_seq_index', 'get_zmip_step_index', 'get_zmip_int_index'):
        fn = getattr(context.state_manager, getter, None)
        if not callable(fn):
            _restore_exclusive(context)
            logging.error('MBMF exclusive input cannot identify internal route %s', getter)
            return False
        internal.append(fn())
    if any(type(i) is not int or i < limit for i in internal):
        _restore_exclusive(context)
        logging.error('MBMF exclusive internal MIDI indices invalid')
        return False

    changes = {}
    # Disable physical keyboard bypass to synth and other MIDI chains.
    # Do not change ttymidi/video or any other unselected device.
    for index in indexes.values():
        port = context.devices_in[index]
        changes[(mb.zmop_index, index)] = (mb, port.name, 1)
        for chain in chains.values():
            if isinstance(chain.zmop_index, int) and chain.zmop_index >= 0 and chain is not mb:
                changes[(chain.zmop_index, index)] = (chain, port.name, 0)
    # A virtual -> synth -> zynsmf -> seq_in -> MB return is possible even
    # when virtual -> MB is disabled. Break that separate internal path.
    for index in internal:
        changes[(mb.zmop_index, index)] = (mb, None, 0)

    try:
        for index in indexes.values():
            port_name = context.devices_in[index].name
            if index not in saved['modes']:
                saved['modes'][index] = (
                    port_name, context.lib_zyncore.zmip_get_flag_active_chain(index))
            if context.lib_zyncore.zmip_set_flag_active_chain(index, 0) != 1:
                raise RuntimeError('keyboard MULTI set failed')
            context.devices_in_mode[index] = 0
            if context.lib_zyncore.zmip_get_flag_active_chain(index) != 0:
                raise RuntimeError('keyboard MULTI readback failed')
        # Exclusions first, only then allow keyboard -> MB.
        for (zmop, index), (chain, name, enabled) in sorted(
                changes.items(), key=lambda item: item[1][2]):
            key = (zmop, index)
            if key not in saved['routes']:
                saved['routes'][key] = (chain, name,
                    context.lib_zyncore.zmop_get_route_from(zmop, index))
            if context.lib_zyncore.zmop_set_route_from(zmop, index, enabled) != 1:
                raise RuntimeError('exclusive route set failed')
            if context.lib_zyncore.zmop_get_route_from(zmop, index) != enabled:
                raise RuntimeError('exclusive route readback failed')
    except Exception:
        logging.exception('MBMF exclusive input failed; restoring prior MIDI matrix')
        _restore_exclusive(context)
        return False
    return True

class LearnedCCRelay:
    """Consume MB UI events before Oram's global commands; apply scoped learns only."""
    unroute_from_chains=False
    midiproc=None
    midiproc_jackname=None
    dev_zynpad=False
    dev_zynmixer=False
    dev_pated=False
    enabled=True
    driver_description='Scoped MBMF learned controllers'
    def __init__(self, context, index, name):
        self.context,self.index,self.name=context,index,name
        self.idev,self.idev_out=index,None
        self.state_manager=getattr(context,'state_manager',None)
        self.allowed=();self.applied=0;self.reported=set()
    @staticmethod
    def get_driver_name():return 'MBMF scoped learned CC'
    def get_state(self):return {}
    def set_state(self,state):pass
    def sleep_on(self):pass
    def sleep_off(self):pass
    def end(self):
        self.allowed=()
        ctx=self.context
        if self.index<len(ctx.devices_in) and ctx.devices_in[self.index] is not None and ctx.devices_in[self.index].name==self.name:
            flags=ctx.lib_zyncore.zmip_get_flags(self.index)
            if ctx.lib_zyncore.zmip_set_flags(self.index,flags&~1)!=1:logging.error('MBMF relay UI capture shutdown failed')
    def teach_cc(self,channel,cc,chain=None):
        """Learn only the armed control of an admitted, live destination chain."""
        if type(channel) is not int or not 0<=channel<16 or type(cc) is not int or cc in (0,32) or not 0<=cc<120:
            raise ValueError('CC réservé ou canal invalide')
        ctx=self.context;manager=ctx.chain_manager;state=self.state_manager
        target=getattr(state,'midi_learn_zctrl',None)
        processor=getattr(target,'processor',None)
        port=ctx.devices_in[self.index]
        if target is None:raise ValueError('Armer le contrôle Zynthian : appui long sur son potentiomètre, puis Chain learn…')
        if port is None or port.name!=self.name:raise ValueError('Source MIDI MBMF indisponible')
        for candidate in self.allowed:
            if chain is not None and candidate is not chain:continue
            if manager.chains.get(candidate.chain_id) is not candidate or candidate.midi_chan!=channel:continue
            if ctx.lib_zyncore.zmop_get_route_from(candidate.zmop_index,self.index)!=1:continue
            if getattr(processor,'chain_id',None)!=candidate.chain_id:continue
            if getattr(manager,'processors',{}).get(getattr(processor,'id',None)) is not processor:continue
            if not any(value is target for value in getattr(processor,'controllers_dict',{}).values()):continue
            if getattr(state,'midi_learn_zctrl',None) is not target:raise ValueError('La cible MIDI Learn a changé')
            manager.add_midi_learn(channel,cc,target)
            state.disable_learn_cc()
            # The scoped relay consumes the MIDI event, so the ordinary GUI CC
            # callback cannot end its own Learn display. Queue this on the GUI
            # thread rather than touching Tk widgets from the host/MIDI thread.
            if callable(getattr(state,'send_cuia',None)):state.send_cuia('DISABLE_MIDI_LEARN')
            return True
        raise ValueError('La cible Learn doit appartenir à la chaîne Zynthian liée à cet instrument')
    def midi_event(self,event):
        # Always consume, including PANIC, notes, master-channel and program events.
        try:
            if len(event)!=3 or event[0]&0xf0!=0xb0:return True
            channel,cc,value=event[0]&15,event[1],event[2]
            if cc in (0,32) or not 0<=cc<120 or not 0<=value<=127:return True
            ctx=self.context;manager=ctx.chain_manager
            port=ctx.devices_in[self.index]
            if port is None or port.name!=self.name:return False
            if getattr(self.state_manager,'midi_learn_zctrl',None) is not None:
                try:self.teach_cc(channel,cc)
                except ValueError:pass
            targets=[]
            for chain in self.allowed:
                if manager.chains.get(chain.chain_id) is not chain or chain.midi_chan!=channel:continue
                if ctx.lib_zyncore.zmop_get_route_from(chain.zmop_index,self.index)!=1:continue
                keys=((chain.chain_id<<16)|(channel<<8)|cc,(chain.chain_id<<16)|(255<<8)|cc)
                for key in keys:targets.extend(z for z in getattr(manager,'chain_midi_cc_binding',{}).get(key,()) if getattr(getattr(z,'processor',None),'chain_id',None)==chain.chain_id)
                key=(self.index<<16)|(channel<<8)|cc
                targets.extend(z for z in getattr(manager,'absolute_midi_cc_binding',{}).get(key,()) if getattr(getattr(z,'processor',None),'chain_id',None)==chain.chain_id)
            seen=set()
            for control in targets:
                if id(control) in seen:continue
                seen.add(id(control));control.midi_control_change(value);self.applied+=1
            if seen and (channel,cc) not in self.reported:
                self.reported.add((channel,cc));logging.warning('MBMF scoped learn applied: CH%s CC%s controls=%s',channel+1,cc,len(seen))
        except Exception:logging.exception('MBMF scoped learn deferred')
        return True


def _learned_cc_relay(context,index,name):
    manager=getattr(getattr(context,'state_manager',None),'ctrldev_manager',None)
    if manager is None:return None
    previous=manager.drivers.get(index)
    if previous is not None:
        if isinstance(previous,LearnedCCRelay) and previous.name==name:return previous
        raise RuntimeError('virtual source already has a control driver')
    relay=LearnedCCRelay(context,index,name);manager.drivers[index]=relay
    return relay


def _enable_panic_cc(context, chain):
    """Keep native synth CC filtering, but let terminal panic commands through."""
    index = chain.zmop_index
    table = (ctypes.c_uint8 * 128)()
    if context.lib_zyncore.zmop_get_cc_route(index, table) != 1:
        raise RuntimeError('cannot read terminal synth CC routes')
    saved = getattr(context, '_mbmf_panic_cc_routes', None)
    if saved is None:
        context._mbmf_panic_cc_routes = saved = {}
    if index not in saved or saved[index][0] is not chain:
        saved[index] = (chain, int(table[120]), int(table[123]))
    table[120] = table[123] = 1
    if context.lib_zyncore.zmop_set_cc_route(index, table) != 1:
        raise RuntimeError('cannot enable terminal synth panic CC')
    actual = (ctypes.c_uint8 * 128)()
    if context.lib_zyncore.zmop_get_cc_route(index, actual) != 1 or list(actual) != list(table):
        raise RuntimeError('terminal synth panic CC readback failed')


def _restore_panic_cc(context):
    saved = getattr(context, '_mbmf_panic_cc_routes', {})
    for index, (chain, cc120, cc123) in list(saved.items()):
        if context.chain_manager.chains.get(chain.chain_id) is chain and chain.zmop_index == index:
            table = (ctypes.c_uint8 * 128)()
            if context.lib_zyncore.zmop_get_cc_route(index, table) != 1:
                return False
            if table[120] == table[123] == 1:
                table[120], table[123] = cc120, cc123
                if context.lib_zyncore.zmop_set_cc_route(index, table) != 1:
                    return False
        del saved[index]
    return True


def discover(context):
    """Extend Oram's input-device discovery, preserving unrelated devices."""
    current = sources(context)
    owned = getattr(context, '_mbmf_source_inputs', {})
    if any(record['name'] not in current for record in owned.values()):
        if not _quarantine_virtual(context):
            return
    if not current and not _restore_exclusive(context):
        return
    if not current and not _restore_panic_cc(context):
        logging.error('MBMF cannot restore terminal panic CC routes')
        return
    for index, record in list(owned.items()):
        if record['name'] not in current:
            # Do not resurrect a still-live orphan MB port, or overwrite an
            # unrelated device that reused this slot. Retired virtual routing
            # stays closed; Oram owns the next device's routing configuration.
            if index < len(context.devices_in) and context.devices_in[index] is not None:
                continue
            try:
                if 'flags' in record:
                    if context.lib_zyncore.zmip_set_flags(index, record['flags']) != 1:
                        raise RuntimeError('retired input flags restore failed')
                if context.lib_zyncore.zmip_set_flag_active_chain(index, record['mode']) != 1:
                    raise RuntimeError('retired input mode restore failed')
                if context.lib_zyncore.zmip_get_flag_active_chain(index) != record['mode']:
                    raise RuntimeError('retired input mode readback failed')
                context.devices_in_mode[index] = record['mode']
                del owned[index]
            except Exception:
                logging.exception('MBMF failed retiring native source; ownership retained')
    known = {p.name for p in context.hw_midi_src_ports}
    context.hw_midi_src_ports.extend(p for name, p in current.items() if name not in known)


def _contains_mb(chain):
    return any(p.eng_code == 'MB' for slot in chain.midi_slots for p in slot)


def _returns_to_mb(chain, chains):
    """Detect indirect native chain-to-chain routes back to an MB processor."""
    pending = list(chain.midi_out)
    seen = set()
    while pending:
        target = pending.pop()
        if not isinstance(target, int) or target in seen:
            continue
        seen.add(target)
        destination = chains.get(target)
        if destination is None:
            continue
        if _contains_mb(destination):
            return True
        pending.extend(destination.midi_out)
    return False


def _jack_returns_to_mb(required_routes, start, mb_input):
    """Detect graph paths from a receiver output back to the MB input."""
    graph = {}
    for destination, inputs in required_routes.items():
        for source in inputs:
            graph.setdefault(source, set()).add(destination)
    pending = [start]
    seen = set()
    while pending:
        port = pending.pop()
        if port == mb_input:
            return True
        if port in seen:
            continue
        seen.add(port)
        pending.extend(graph.get(port, ()))
    return False


def configure(context, required_routes):
    """Fail closed if the native router cannot prove its no-feedback routes.

    This runs inside Oram's autoconnect lock, not in the JACK audio callback.
    Channel filtering remains owned by ZynMidiRouter; only synth chains are
    admitted, and MB / MIDI-only / return paths are explicitly excluded.
    """
    names = sources(context)
    owned = getattr(context, '_mbmf_source_inputs', None)
    if owned is None:
        context._mbmf_source_inputs = owned = {}
    chains = context.chain_manager.chains
    # Scrub old virtual sources too: a chain may disappear before its JACK port.
    # Leave every unrelated source/connection untouched.
    managed_names = set(names) | {r['name'] for r in owned.values()}
    for inputs in required_routes.values():
        inputs.difference_update(managed_names)
    # Preserve the old matrix before quarantine, including refreshes of an
    # already connected source. No native setter may enable virtual destinations
    # until physical/internal isolation AND virtual exclusion readbacks pass.
    for index, port in enumerate(context.devices_in):
        if port is None or port.name not in names:
            continue
        expected = f'ZynMidiRouter:dev{index}_in'
        for inputs in required_routes.values():
            inputs.discard(port.name)
        required_routes.setdefault(expected, set())
        try:
            if index not in owned or owned[index]['name'] != port.name:
                owned[index] = dict(name=port.name,
                    mode=context.lib_zyncore.zmip_get_flag_active_chain(index), routes={})
            for chain in chains.values():
                zmop = chain.zmop_index
                if type(zmop) is int and zmop >= 0:
                    record = owned[index]['routes']
                    if zmop not in record or record[zmop][0] is not chain:
                        record[zmop] = (chain, context.lib_zyncore.zmop_get_route_from(zmop, index))
        except Exception:
            _quarantine_virtual(context)
            logging.exception('MBMF cannot snapshot native routing; source blocked')
            return
    quarantined = _quarantine_virtual(context)
    requested = []
    exclusive_safe = False
    try:
        requested = _read_exclusive_ports()
        if quarantined:
            exclusive_safe = _apply_exclusive(context, requested, names)
    except Exception:
        logging.exception('MBMF invalid exclusive MIDI input config; virtual source blocked')
        _restore_exclusive(context)
    for index, port in enumerate(context.devices_in):
        if port is None or port.name not in names:
            continue
        if index not in owned or owned[index]['name'] != port.name:
            owned[index] = dict(
                name=port.name,
                mode=context.lib_zyncore.zmip_get_flag_active_chain(index),
                routes={})
        record = owned[index]
        mb_input = port.name.replace(':midi_out', ':midi_in')
        routes = []
        mb_chain_count = 0
        for chain in chains.values():
            zmop = chain.zmop_index
            if zmop is None or zmop < 0:
                continue
            if zmop not in record['routes'] or record['routes'][zmop][0] is not chain:
                record['routes'][zmop] = (
                    chain, context.lib_zyncore.zmop_get_route_from(zmop, index))
            contains_mb = _contains_mb(chain)
            if contains_mb:
                mb_chain_count += 1
            enabled = bool(
                chain.synth_slots and not contains_mb
                and not _returns_to_mb(chain, chains)
                and not _jack_returns_to_mb(
                    required_routes, f'ZynMidiRouter:ch{zmop}_out', mb_input))
            routes.append((zmop, int(enabled)))

        expected = f'ZynMidiRouter:dev{index}_in'
        # Remove all legacy direct shortcuts, even if verification fails.
        for destination, inputs in required_routes.items():
            if destination != expected:
                inputs.discard(port.name)
        required_routes.setdefault(expected, set()).discard(port.name)

        # Exclude MB and all other unsafe destinations BEFORE admitting synths.
        # A failed readback leaves the source disconnected (no feedback storm).
        # Never reconnect MB virtual input without an explicit, verified
        # physical keyboard isolation policy. The previous implicit default
        # caused a real MIDI storm during REC on Kit V4.
        safe = mb_chain_count > 0 and bool(requested) and exclusive_safe
        try:
            if safe:
                for chain in chains.values():
                    if (chain.zmop_index, 1) in routes:
                        _enable_panic_cc(context, chain)
                # FLAG_ZMIP_UI is an out-of-band path, independent of the
                # output matrix: UI handles CC123 by emitting CC123 again.
                # Only a consuming scoped relay may capture MB events; it never
                # passes them to global UI/transport/PANIC handlers.
                relay=_learned_cc_relay(context,index,port.name)
                record['learn_relay']=relay
                ui_flags=1 if relay is not None else 0
                flags = context.lib_zyncore.zmip_get_flags(index)
                if type(flags) is not int or not 0 <= flags <= 0xffffffff:
                    raise RuntimeError('invalid native input flags')
                record.setdefault('flags', flags)
                if context.lib_zyncore.zmip_set_flags(index, (flags & ~1)|ui_flags) != 1:
                    raise RuntimeError('virtual UI capture disable failed')
                if context.lib_zyncore.zmip_get_flags(index) != ((flags & ~1)|ui_flags):
                    raise RuntimeError('virtual UI capture readback failed')
                if context.lib_zyncore.zmip_set_flag_active_chain(index, 0) != 1:
                    safe = False
                context.devices_in_mode[index] = 0
                if context.lib_zyncore.zmip_get_flag_active_chain(index) != 0:
                    safe = False
            # Quarantine already disabled ALL destinations. Verify exclusions
            # before any enable, and stop immediately on a failed prerequisite.
            for zmop, _ in routes:
                if context.lib_zyncore.zmop_get_route_from(zmop, index) != 0:
                    safe = False
            if safe:
                for zmop, enabled in routes:
                    if not enabled:
                        continue
                    if context.lib_zyncore.zmop_set_route_from(zmop, index, 1) != 1:
                        safe = False
                        break
                    if context.lib_zyncore.zmop_get_route_from(zmop, index) != 1:
                        safe = False
                        break
            if safe:
                count = _native_output_count(context, index)
                admitted = {zmop for zmop, enabled in routes if enabled}
                matrix = [context.lib_zyncore.zmop_get_route_from(zmop, index)
                          for zmop in range(count)]
                if any(value != int(zmop in admitted)
                       for zmop, value in enumerate(matrix)):
                    safe = False
                else:
                    if relay is not None:relay.allowed=tuple(chain for chain in chains.values() if chain.zmop_index in admitted and chain.synth_slots and not _contains_mb(chain))
                    evidence = (index, tuple(matrix),bool(relay))
                    if getattr(context, '_mbmf_verified_matrix', None) != evidence:
                        logging.warning('MBMF verified native matrix: input=%s outputs=%s admitted=%s mode=MULTI UI_CAPTURE=%s PANIC_CC=ON',
                                        index, count, sorted(admitted),'SCOPED_LEARN' if relay is not None else 'OFF')
                        context._mbmf_verified_matrix = evidence
        except Exception:
            logging.exception('MBMF native routing failed; source remains disconnected')
            safe = False

        if not safe:
            if record.get('learn_relay'):record['learn_relay'].allowed=()
            _restore_exclusive(context)
            # Stop every route from this source, including any previously admitted
            # receiver. Oram will disconnect the owned devN_in JACK connection.
            for zmop, _ in routes:
                try:
                    context.lib_zyncore.zmop_set_route_from(zmop, index, 0)
                except Exception:
                    logging.exception('MBMF failed to close native route %s', zmop)
            logging.error('MBMF native MIDI source %s blocked: unsafe routing', port.name)
        else:
            required_routes[expected].add(port.name)
