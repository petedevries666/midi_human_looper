#!/usr/bin/env python3
"""Reproduce ONCE choke through actual HTTP commands/native callback; not mock MIDI.

The EEL companion records raw MIDI. This adapter test verifies authoritative
phrase states and saved source data. --strict fails on the unmet contract.
"""
import base64
import json
import sys
import urllib.request
from test_native_free_capture import FreeCapture
from phrase_midi import write_smf

api=FreeCapture('runTest')
api.setUpClass()
try:
    api.command('panic')
    for phrase,pitch in ((1,48),(2,72)):
        api.command('phrase_clear',phraseId=phrase)
        api.command('parameter_set',targetId=phrase,kind=20,value=1)
        raw=write_smf(dict(lengthSeconds=10,bpm=120,events=[[0,144,pitch,91],[9,128,pitch,23]]))
        state=api.call()
        body=dict(file=base64.b64encode(raw).decode(),phraseId=phrase,mode='replace',
                  expectedRevision=state['revision'],expectedEngineSessionId=state['engineSessionId'])
        req=urllib.request.Request(api.base+'/api/v1/phrase/midi',data=json.dumps(body).encode(),
                                  headers={'Content-Type':'application/json'})
        with urllib.request.urlopen(req,timeout=5) as response:
            if response.status!=200:raise RuntimeError('fixture import failed')
    sources=[api.export(phrase) for phrase in (1,2)]
    api.command('phrase_play',phraseId=1)
    api.wait_for(lambda:api.call()['phrases'][0]['state']=='PLAYING','first ONCE native admission')
    api.command('phrase_play',phraseId=2)
    api.wait_for(lambda:api.call()['phrases'][1]['state']=='PLAYING','second ONCE native admission')
    state=api.call();playing=[p['id'] for p in state['phrases'] if p['state']=='PLAYING']
    if playing!=[2]:raise RuntimeError(f'Baseline changed: expected exact choke symptom, got {playing}')
    print('XFAIL NATIVE_ONCE_CROSS_SOURCE_CHOKE: authoritative PLAYING phrases =',playing)
    api.command('panic')
    if api.call()['activeNotes']!=0:raise RuntimeError('native PANIC did not clean up notes')
    api.patch('save');api.patch('load')
    if sources!=[api.export(phrase) for phrase in (1,2)]:raise RuntimeError('source data changed during SAVE/LOAD')
    print('PASS native adapter fixture import, first/second admission, PANIC and source SAVE/LOAD')
finally:
    api.tearDownClass()
if '--strict' in sys.argv:sys.exit(1)
