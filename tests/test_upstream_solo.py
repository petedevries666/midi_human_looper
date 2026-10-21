"""Execute real upstream method ASTs with deterministic mixer/controller adapters.

Usage: python tests/test_upstream_solo.py path/to/zynthian_engine_audio_mixer.py
No hardware access, imports or writes to the upstream source.
"""
import ast,pathlib,sys,types,unittest
source=pathlib.Path(sys.argv.pop(1)).read_text()
tree=ast.parse(source);cls=next(n for n in tree.body if isinstance(n,ast.ClassDef))
methods=[n for n in cls.body if isinstance(n,ast.FunctionDef) and n.name in ('set_solo','set_state','get_state')]
env={'zynsigman':types.SimpleNamespace(S_AUDIO_MIXER=0,send=lambda *a,**k:None)}
exec(compile(ast.Module(body=methods,type_ignores=[]),'<upstream methods>','exec'),env)

class Controller:
 is_toggle=True;value_default=0;midi_cc_momentary_switch=0;symbol='solo'
 def __init__(self,owner,index):self.owner=owner;self.index=index;self.value=0
 def set_value(self,value,send=True):
  if value==self.value:return
  self.value=value
  if send:self.owner.set_solo(self.index,value,False)
 def reset_value(self):self.set_value(0)

class Mixer:
 MAX_NUM_CHANNELS=17;SS_ZCTRL_SET_VALUE=0
 set_solo=env['set_solo'];set_state=env['set_state'];get_state=env['get_state']
 def __init__(self):
  self.audio=[0]*17;self.zctrls=[{'solo':Controller(self,i)} for i in range(17)]
  self.learned_cc=[{} for _ in range(16)]
  self.lib_zynmixer=types.SimpleNamespace(setSolo=self.native)
 def native(self,ch,value):
  if ch==16:self.audio[:16]=[0]*16
  else:self.audio[ch]=value
 def midi_unlearn_all(self):pass

class SoloTests(unittest.TestCase):
 def test_main_clear_keeps_cache_and_native_equal_including_last_strip(self):
  m=Mixer()
  for i in (0,15):m.set_solo(i,1)
  m.set_solo(16,1)
  self.assertEqual(m.audio,[v['solo'].value for v in m.zctrls])
 def test_restore_preserves_intentional_solos_despite_main_flag(self):
  m=Mixer();m.set_state({'chan_00':{'solo':1},'chan_15':{'solo':1},'chan_16':{'solo':1}})
  self.assertEqual(m.audio[:16],[1]+[0]*14+[1]);self.assertEqual(m.zctrls[16]['solo'].value,0)
 def test_roundtrip_non_solo_and_momentary_flags(self):
  m=Mixer();m.set_state({'chan_02':{'solo':3},'chan_16':{'solo':1}})
  saved=m.get_state();n=Mixer();n.set_state(saved)
  self.assertEqual(n.audio,m.audio);self.assertEqual(n.audio[2],1)
  self.assertEqual(n.zctrls[2]['solo'].midi_cc_momentary_switch,1)

if __name__=='__main__':unittest.main()
