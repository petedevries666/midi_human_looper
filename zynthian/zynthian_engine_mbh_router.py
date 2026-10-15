"""Register dedicated MBMF as a native Oram MIDI source, without MIDI feedback.

Only terminal synth chains may receive the virtual input. No direct synth JACK
fanout, and no edits to Zynthian's real-time router implementation.
"""
import logging
import re


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


def discover(context):
    """Extend Oram's input-device discovery, preserving unrelated devices."""
    current = sources(context)
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
        safe = mb_chain_count > 0
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
