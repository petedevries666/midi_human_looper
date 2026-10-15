"""Explicit versioned DSP compatibility fixture; normal tests use production source.
Legacy1 selects the retained pre-M0 DSP branch (native_hold_enabled=1,
native_phrase_contract=0), not a replacement renderer or a MIDI model.
"""
import atexit,os,tempfile
from pathlib import Path
legacy=os.environ.get('MBMF_TEST_PHRASE_CONTRACT','2')=='legacy1'
if os.environ.get('MBMF_TEST_PHRASE_CONTRACT','2') not in ('2','legacy1'):raise ValueError('unknown test contract')
_cached=None
def contract_source(root):
 global _cached
 source=Path(root)/'midi_human_looper.jsfx'
 if not legacy:return source
 if _cached is None:
  tmp=tempfile.TemporaryDirectory(prefix='mbmf-legacy-contract1-');atexit.register(tmp.cleanup)
  _cached=Path(tmp.name)/'legacy1.jsfx'
  text=source.read_text();assert text.count('\n@block\n')==1
  _cached.write_text(text.replace('\n@block\n','\n@block\n// Explicit legacy native DSP fixture; production default remains contract 2.\nnative_phrase_contract=0;native_hold_enabled=1;\n',1))
 return _cached
