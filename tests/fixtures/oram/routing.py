# Native Oram chain and autoconnect excerpts, commit
# 11d4e858367db465a431c701d9035432742a5a7d, GPL-3.0-or-later.
import re

class NativeChain:
    def __init__(self, chain_id, midi_slots=(), synth_slots=(), midi_chan=None):
        self.chain_id=chain_id;self.midi_slots=list(midi_slots);self.synth_slots=list(synth_slots)
        self.audio_slots=[];self.midi_in=[];self.midi_out=[];self.midi_routes={}
        self.midi_thru=True;self.midi_chan=midi_chan;self.zmop_index=chain_id
    def is_midi(self): return True
    def is_audio(self): return False
    def get_processors(self, type=None, slot=None):
        slots=self.midi_slots if type=='MIDI Tool' else self.synth_slots
        return [p for group in (slots if slot is None else slots[slot:slot+1]) for p in group]

    def rebuild_midi_graph(self):
        """Build dictionary of lists of sources mapped by destination"""

        if not zynautoconnect.acquire_lock():
            return

        self.midi_routes = {}
        for i, slot in enumerate(self.midi_slots):
            if i == 0:
                continue  # Chain inputs are handled by autoconnect
            for processor in slot:
                sources = []
                for prev_proc in self.midi_slots[i - 1]:
                    sources.append(prev_proc.get_jackname())
                self.midi_routes[processor.get_jackname()] = sources

        sources = []
        if len(self.midi_slots):
            for prev_proc in self.midi_slots[-1]:
                sources.append(prev_proc.get_jackname())
        if self.synth_slots:
            for proc in self.synth_slots[0]:
                # TODO: Should always use engine's get_jackname? => proc.get_jackname(True)
                dst_jackname = proc.engine.get_jackname()
                self.midi_routes[dst_jackname] = sources
                # Special Engines can generate MIDI output too!!
                if proc.type == "Special":
                    sources = [dst_jackname]
        elif len(self.midi_slots) == 0 and self.midi_thru:
            sources = self.midi_in
        for output in self.midi_out:
            self.midi_routes[output] = sources
        # Feed output of MIDI chain to all audio processors - ideally this should only feed processors with
        # MIDI inputs but it is probably as simple to let autoconnect deal with that.
        for slot in self.audio_slots:
            for proc in slot:
                self.midi_routes[proc.engine.jackname] = sources

        zynautoconnect.release_lock()

    def get_midi_out(self):
        return self.midi_out

    def toggle_midi_out(self, dest):
        """ Set/unset a MIDI output route
        dest : destination ID. A jack port name/alias (string) or a chain ID (integer)
        """

        if dest not in self.midi_out:
            self.midi_out.append(dest)
        else:
            self.midi_out.remove(dest)

        self.rebuild_midi_graph()
        zynautoconnect.request_midi_connect(True)

    def get_type(self):
        if self.synth_slots:
            return "MIDI Synth"
        elif self.is_audio():
            return "Audio Effect"
        elif self.is_midi():
            return "MIDI Tool"
        else:
            return "Empty"

def resolve_routes(chain_manager, jclient):
    required_routes={p.name:set() for p in jclient.get_ports(is_midi=True,is_input=True)}
    for chain_id, chain in chain_manager.chains.items():
        # Add chain internal routes
        routes = chain_manager.get_chain_midi_routing(chain_id)
        for dst in list(routes):
            if isinstance(dst, int):
                # Destination is a chain
                route = routes.pop(dst)
                dst_chain = chain_manager.get_chain(dst)
                if dst_chain:
                    if dst_chain.midi_slots:
                        for proc in dst_chain.midi_slots[0]:
                            routes[proc.engine.get_jackname()] = route
                    elif dst_chain.synth_slots:
                        proc = dst_chain.synth_slots[0][0]
                        routes[proc.engine.get_jackname()] = route

        for dst_name in routes:
            dst_ports = jclient.get_ports(re.escape(dst_name), is_input=True, is_midi=True)
            if not dst_ports:
                # Try to get destiny port by alias
                try:
                    dst_ports = [jclient.get_port_by_name(dst_name)]
                except:
                    pass
            if dst_ports:
                for src_name in routes[dst_name]:
                    src_ports = jclient.get_ports(src_name, is_output=True, is_midi=True)
                    if src_ports:
                        required_routes[dst_ports[0].name].add(src_ports[0].name)

        if chain.is_midi():
            # Add chain MIDI outputs => Route chain's MIDI output to other chains
            if chain.midi_thru:
                dests = []
                for out in chain.midi_out:
                    if out in chain_manager.chains:
                        chain_midi_first_procs = chain_manager.get_processors(out, "MIDI Tool", 0)
                        if not chain_midi_first_procs:
                            chain_midi_first_procs = chain_manager.get_processors(out, "Synth", 0)
                        for processor in chain_midi_first_procs:
                            for dst in jclient.get_ports(processor.get_jackname(True), is_midi=True, is_input=True):
                                dests.append(dst.name)
                    else:
                        pass
                        # dests.append(out)
                # ... from last MIDI processor (MIDI2MIDI)
                if chain.midi_slots:
                    for processor in chain.midi_slots[-1]:
                        src_ports = jclient.get_ports(processor.get_jackname(True), is_midi=True, is_output=True)
                        if src_ports:
                            for dst in dests:
                                required_routes[dst].add(src_ports[0].name)
                # ... from last audio processor, if it's an audio2MIDI processor
                if chain.audio_slots:
                    for processor in chain.audio_slots[-1]:
                        src_ports = jclient.get_ports(processor.get_jackname(True), is_midi=True, is_output=True)
                        if src_ports:
                            for dst in dests:
                                required_routes[dst].add(src_ports[0].name)

            # Add MIDI router outputs => Connects zmop to chain's input
            src_ports = jclient.get_ports(f"ZynMidiRouter:ch{chain.zmop_index}_out", is_midi=True, is_output=True)
            if src_ports:
                # Connect to first slot, excluding clippy
                procs = chain.get_processors(type="MIDI Tool", slot=0)
                if not procs:
                    procs = chain.get_processors(type="Synth", slot=0)
                for dst_proc in procs:
                    if dst_proc.eng_code == "CL":
                        continue
                    dst_ports = jclient.get_ports(dst_proc.get_jackname(True), is_midi=True, is_input=True)
                    if dst_ports:
                        src = src_ports[0]
                        dst = dst_ports[0]
                        required_routes[dst.name].add(src.name)
    return required_routes

class ChainManager:
    def __init__(self,chains): self.chains=chains
    def get_chain(self,id): return self.chains.get(id)
    def get_processors(self,id,type,slot): return self.chains[id].get_processors(type=type,slot=slot)
    def get_chain_midi_routing(self,id): return dict(self.chains[id].midi_routes)
    def will_midi_howl(self, src_id, dst_id, node_list=None):
        """Checks if adding a connection will cause a MIDI howl-round loop

        src_id : Chain ID of the source chain
        dst_id : Chain ID of the destination chain
        node_list : Do not use - internal function parameter
        Returns : True if adding the route will cause howl-round feedback loop
        """

        if dst_id not in self.chains:
            return False
        if src_id is not None:
            # src_id only provided on first call (not re-entrant cycles)
            if src_id not in self.chains:
                return False
            node_list = [src_id]  # Init node_list on first call
        if dst_id in node_list:
            return True
        node_list.append(dst_id)
        for chain_id in self.chains[dst_id].midi_out:
            if chain_id in self.chains:
                if self.will_midi_howl(None, chain_id, node_list):
                    return True
                node_list.append(chain_id)
        return False
