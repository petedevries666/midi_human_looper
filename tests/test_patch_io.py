"""Run the shipped Lua daemon with REAPER API adapters and real temporary files."""
import json
import os
from pathlib import Path
import tempfile
import unittest
from lupa.lua54 import LuaRuntime

SOURCE = (Path(__file__).resolve().parents[1] / 'midi_human_looper_patch_io.lua').read_text()

class PatchIO(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name) / 'Data/MIDI_Human_Looper'
        self.root.mkdir(parents=True)
        self.lua = LuaRuntime(unpack_returned_tuples=True)
        self.lua.globals().resource_path = self.tmp.name
        self.lua.execute('''
          mem={}
          reaper={
            gmem_attach=function(name) assert(name=='MIDI_HUMAN_LOOPER') end,
            GetResourcePath=function() return resource_path end,
            RecursiveCreateDirectory=function() end,
            gmem_read=function(i) return mem[i] or 0 end,
            gmem_write=function(i,v) mem[i]=v end,
            defer=function(fn) tick=fn end,
            atexit=function(fn) shutdown=fn end
          }
        ''')
        self.lua.execute(SOURCE)
        self.mem = self.lua.globals().mem

    def tick(self, command, slot):
        self.mem[0], self.mem[1] = command, slot
        self.lua.globals().tick()
        return self.mem[0]

    def test_schema_and_slots_roundtrip(self):
        for schema in (1, 2, 3, 4):
            for slot in (1, 2):
                with self.subTest(schema=schema, slot=slot):
                    # Include a prefix and an extension-sized tail; Lua preserves all entries.
                    memory = [0, 144, 60, 100, -12.5, 0.125] + [slot * schema] * 424
                    globals_ = list(range(4, 13))
                    self.mem[2], self.mem[3] = schema, len(memory)
                    for i, value in enumerate(globals_, 4): self.mem[i] = value
                    for i, value in enumerate(memory, 32): self.mem[i] = value
                    self.assertEqual(self.tick(1, slot), 4)
                    data = json.loads((self.root / f'patch{slot}.json').read_text())
                    self.assertEqual(data['schema'], schema)
                    self.assertEqual(data['memory'], memory)
                    self.assertEqual(data['globals'], globals_)
                    for i in range(32, 32 + len(memory)): self.mem[i] = 999
                    self.assertEqual(self.tick(2, slot), 3)
                    self.assertEqual(self.mem[2], schema)
                    self.assertEqual([self.mem[i] for i in range(32, 32 + len(memory))], memory)

    def test_smart_switch_save_tail(self):
        fixture = os.environ.get('NATIVE_PATCH_FIXTURE')
        if fixture:
            data = json.loads(Path(fixture).read_text())
            memory, globals_ = data['memory'], data['globals']
            offset = data['switch_tail_offset']
        else:
            offset = 424
            memory, globals_ = [0] * (offset + 513), [0] * 9
            memory[offset] = 3
            for switch, number in ((0, 74), (1, 73)):
                b = offset + 1 + switch * 128
                memory[b:b+5] = [1, 0, 1, 2, number]
                memory[b+11], memory[b+14] = 2, 1
                memory[b+48:b+50] = [0, 6] if switch == 0 else [6, 0]
        self.mem[2], self.mem[3] = data['schema'] if fixture else 3, len(memory)
        for i, value in enumerate(globals_, 4): self.mem[i] = value
        for i, value in enumerate(memory, 32): self.mem[i] = value
        self.assertEqual(self.tick(1, 1), 4)
        saved = json.loads((self.root / 'patch1.json').read_text())
        self.assertEqual(saved['memory'], memory)
        if fixture:
            self.assertEqual(saved['schema'], 4)
            cc = data['cc_tail_offset'] + 2 + 3
            self.assertEqual(saved['memory'][cc:cc+4], [50, 71, 64, 12])
            self.assertEqual(saved['memory'][cc+4+2+12], .25)
        for switch, number in ((0, 74), (1, 73)):
            b = offset + 1 + switch * 128
            self.assertEqual(saved['memory'][b+4], number)
            self.assertEqual(saved['memory'][b+11], 2)
            self.assertEqual(saved['memory'][b+48:b+50], [0, 6] if switch == 0 else [6, 0])
        self.lua.execute('for i=32,32+mem[3]-1 do mem[i]=0 end')
        self.assertEqual(self.tick(2, 1), 3)
        self.assertEqual([self.mem[i] for i in range(32,32+len(memory))], memory)

    def test_rejects_invalid_without_payload_writes(self):
        valid = dict(format='MIDI_HUMAN_LOOPER_PATCH', schema=1, work_mem_size=2,
                     globals=list(range(9)), memory=[144, 60])
        cases = [dict(valid, schema=5), dict(valid, work_mem_size=3),
                 dict(valid, globals=[0]), dict(valid, format='other'),
                 dict(valid, work_mem_size=1000001), dict(valid, memory=['invalid', 60]),
                 dict(valid, memory=[1e309, 60])]
        self.mem[32] = 123
        for data in cases:
            with self.subTest(data=data):
                (self.root / 'patch1.json').write_text(json.dumps(data))
                self.assertEqual(self.tick(2, 1), 5)
                self.assertEqual(self.mem[32], 123)
        (self.root / 'patch1.json').write_text('not json')
        self.assertEqual(self.tick(2, 1), 5)
        self.assertEqual(self.tick(2, 2), 5)

    def test_invalid_save_and_heartbeat(self):
        self.assertEqual(self.mem[15], 1)
        self.assertEqual(self.mem[16], 4)
        self.mem[2], self.mem[3] = 2, 0
        self.assertEqual(self.tick(1, 1), 5)
        self.mem[2], self.mem[3] = 5, 2
        self.assertEqual(self.tick(1, 1), 5)
        self.lua.globals().shutdown()
        self.assertEqual(self.mem[15], 0)
        self.assertEqual(self.mem[16], 0)

if __name__ == '__main__':
    unittest.main()
