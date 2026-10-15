"""Register dedicated MBMF as a native Oram MIDI source, without MIDI feedback.

Only terminal synth chains may receive the virtual input. No direct synth JACK
fanout, and no edits to Zynthian's real-time router implementation.
"""
import logging
import re
import json
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


def _quarantine_virtual(context):
    """Block native MB virtual source *before* restoring physical bypass routes.

    Native ZynMidiRouter matrices are invisible in jack_lsp. Closing the
    virtual source first makes rollback safe even when devN_in JACK remains
    connected until Oram reconciles its desired graph.
    """
    virtual = sources(context)
    indices = [i for i, p in enumerate(context.devices_in)
               if p is not None and p.name in virtual]
    for index in indices:
        for chain in context.chain_manager.chains.values():
            zmop = chain.zmop_index
            if not isinstance(zmop, int) or zmop < 0:
                continue
            try:
                if context.lib_zyncore.zmop_set_route_from(zmop, index, 0) != 1:
                    raise RuntimeError('native quarantine setter failed')
                if context.lib_zyncore.zmop_get_route_from(zmop, index) != 0:
                    raise RuntimeError('native quarantine readback failed')
            except Exception:
                logging.exception('MBMF virtual input could NOT be quarantined')
                return False
    return True


def _restore_exclusive(context):
    """Restore owned physical routes only once virtual output is quarantined."""
    saved = getattr(context, '_mbmf_exclusive', None)
    if not saved:
        return True
    if not _quarantine_virtual(context):
        logging.error('MBMF leaves physical input isolated: unsafe restore')
        return False
    chains = context.chain_manager.chains
    for (zmop, index), (chain, port_name, previous) in saved['routes'].items():
        if chains.get(chain.chain_id) is not chain or chain.zmop_index != zmop:
            continue
        if port_name is not None and (index >= len(context.devices_in) or
                context.devices_in[index] is None or
                context.devices_in[index].name != port_name):
            continue
        try:
            context.lib_zyncore.zmop_set_route_from(zmop, index, previous)
        except Exception:
            logging.exception('MBMF failed restoring exclusive MIDI route')
    for index, (port_name, previous) in saved['modes'].items():
        if index >= len(context.devices_in) or context.devices_in[index] is None:
            continue
        if context.devices_in[index].name != port_name:
            continue
        try:
            context.lib_zyncore.zmip_set_flag_active_chain(index, previous)
            context.devices_in_mode[index] = previous
        except Exception:
            logging.exception('MBMF failed restoring exclusive MIDI input mode')
    context._mbmf_exclusive = None
    return True


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
    if len(indexes) != len(requested) or any(name in virtual_names for name in requested):
        _restore_exclusive(context)
        logging.error('MBMF configured exclusive keyboard port missing or unsafe')
        return False

    # If native slots or chain instances were recycled, restore only valid
    # old ownership and capture a fresh baseline for the new graph.
    old = getattr(context, '_mbmf_exclusive', None)
    if old:
        stale = any((i >= len(context.devices_in) or
                     context.devices_in[i] is None or
                     context.devices_in[i].name != name)
                    for i, (name, _) in old['modes'].items())
        stale |= any(chains.get(chain.chain_id) is not chain or chain.zmop_index != zmop
                     for (zmop, _), (chain, _, _) in old['routes'].items())
        if stale:
            _restore_exclusive(context)
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

def discover(context):
    """Extend Oram's input-device discovery, preserving unrelated devices."""
    current = sources(context)
    if not current:
        _restore_exclusive(context)
    owned = getattr(context, '_mbmf_source_inputs', {})
    for index, record in list(owned.items()):
        if record['name'] not in current:
            context.lib_zyncore.zmip_set_flag_active_chain(index, record['mode'])
            context.devices_in_mode[index] = record['mode']
            for chain, enabled in record['routes'].values():
                if (context.chain_manager.chains.get(chain.chain_id) is chain
                        and chain.zmop_index is not None):
                    context.lib_zyncore.zmop_set_route_from(chain.zmop_index, index, enabled)
            del owned[index]
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
    try:
        requested = _read_exclusive_ports()
        exclusive_safe = _apply_exclusive(context, requested, names)
    except Exception:
        logging.exception('MBMF invalid exclusive MIDI input config; virtual source blocked')
        _restore_exclusive(context)
        exclusive_safe = False
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
            if context.lib_zyncore.zmip_set_flag_active_chain(index, 0) != 1:
                safe = False
            context.devices_in_mode[index] = 0
            if context.lib_zyncore.zmip_get_flag_active_chain(index) != 0:
                safe = False
            for zmop, enabled in sorted(routes, key=lambda pair: pair[1]):
                if context.lib_zyncore.zmop_set_route_from(zmop, index, enabled) != 1:
                    safe = False
                if context.lib_zyncore.zmop_get_route_from(zmop, index) != enabled:
                    safe = False
        except Exception:
            logging.exception('MBMF native routing failed; source remains disconnected')
            safe = False

        if not safe:
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
