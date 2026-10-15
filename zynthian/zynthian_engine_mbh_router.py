"""Oram worker-side native MIDI source registration (never an audio callback).

Only dedicated, MB-last MIDI chains are sources. Insertion in a synth chain keeps
its internal route. ZynMidiRouter owns channel filtering; no synth JACK links.
"""
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
    """Extend Oram's native input-device enumeration, retaining unrelated devices."""
    current=sources(context)
    owned=getattr(context,'_mbmf_source_inputs',{})
    for index, record in list(owned.items()):
        if record['name'] not in current:
            context.lib_zyncore.zmip_set_flag_active_chain(index,record['mode'])
            context.devices_in_mode[index]=record['mode']
            for chain, enabled in record['routes'].values():
                if context.chain_manager.chains.get(chain.chain_id) is chain and chain.zmop_index is not None:
                    context.lib_zyncore.zmop_set_route_from(chain.zmop_index,index,enabled)
            del owned[index]
    known = {p.name for p in context.hw_midi_src_ports}
    context.hw_midi_src_ports.extend(p for name, p in current.items() if name not in known)


def configure(context, required_routes):
    """Called under Oram's own autoconnect lock, before applying its route graph.

    Reapply after every graph/snapshot refresh. MULTI makes routing independent
    of focus. All MB-containing chains are excluded to prevent recirculation.
    Other chains use their existing ZynMidiRouter channel filter unchanged.
    """
    names = sources(context)
    owned=getattr(context,'_mbmf_source_inputs',None)
    if owned is None:context._mbmf_source_inputs=owned={}
    for index, port in enumerate(context.devices_in):
        if port is None or port.name not in names:
            continue
        if index not in owned:
            owned[index]=dict(name=port.name,mode=context.lib_zyncore.zmip_get_flag_active_chain(index),routes={})
        record=owned[index]
        context.lib_zyncore.zmip_set_flag_active_chain(index, 0)
        context.devices_in_mode[index] = 0
        for chain in context.chain_manager.chains.values():
            zmop = chain.zmop_index
            if zmop is None or zmop < 0:
                continue
            if zmop not in record['routes'] or record['routes'][zmop][0] is not chain:
                record['routes'][zmop]=(chain,context.lib_zyncore.zmop_get_route_from(zmop,index))
            contains_mb = any(p.eng_code == 'MB' for slot in chain.midi_slots for p in slot)
            # A return route to an MB chain is another possible feedback path.
            pending=list(chain.midi_out);seen=set();returns_mb=False
            while pending:
                target=pending.pop()
                if not isinstance(target,int) or target in seen:continue
                seen.add(target);destination=context.chain_manager.chains.get(target)
                if destination is None:continue
                if any(p.eng_code=='MB' for slot in destination.midi_slots for p in slot):
                    returns_mb=True;break
                pending.extend(destination.midi_out)
            context.lib_zyncore.zmop_set_route_from(zmop, index, int(not contains_mb and not returns_mb))
        # Old #64 snapshots may still contain direct destinations. Suppress only
        # this dedicated source's shortcuts; preserve the snapshot and all other
        # routes. The sole output connection is its registered router device.
        expected = f'ZynMidiRouter:dev{index}_in'
        for destination, inputs in required_routes.items():
            if destination != expected:
                inputs.discard(port.name)
        required_routes.setdefault(expected, set()).add(port.name)
