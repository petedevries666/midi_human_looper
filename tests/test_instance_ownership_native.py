#!/usr/bin/env python3
"""Actual PR B native callback + HTTP; no browser API or MIDI engine mocks."""
import base64,json,urllib.request
from test_native_free_capture import FreeCapture
from phrase_midi import write_smf
api=FreeCapture('runTest');api.setUpClass()
try:
 api.command('panic')
 for id in (2,3):api.command('instrument_route',instrumentId=id,field='enabled',value=0)
 for phrase,pitch in ((1,48),(2,72)):
  api.command('parameter_set',targetId=phrase,kind=20,value=1)
  raw=write_smf(dict(lengthSeconds=10,bpm=120,events=[[0,144,pitch,91],[9,128,pitch,23]]))
  state=api.call();req=urllib.request.Request(api.base+'/api/v1/phrase/midi',data=json.dumps(dict(
   file=base64.b64encode(raw).decode(),phraseId=phrase,mode='replace',expectedRevision=state['revision'],expectedEngineSessionId=state['engineSessionId'])).encode(),headers={'Content-Type':'application/json'})
  with urllib.request.urlopen(req,timeout=5) as response:assert response.status==200
 original=[api.export(i) for i in (1,2)]
 api.command('phrase_play_independent',phraseId=1)
 api.wait_for(lambda:len(api.call()['instances'])==1 and api.call()['instances'][0]['ownedOutputs']==1,'first emitted owned attack')
 a=api.call()['instances'][0]
 api.command('phrase_play_independent',phraseId=2)
 api.wait_for(lambda:len(api.call()['instances'])==2,'independent admission')
 assert {i['phraseId'] for i in api.call()['instances']}=={1,2}
 api.command('instance_stop',instanceId=a['id'],generation=a['generation'])
 api.wait_for(lambda:len(api.call()['instances'])==1,'targeted instance cleanup')
 assert api.call()['instances'][0]['phraseId']==2
 api.command('phrase_play_independent',phraseId=1)
 api.wait_for(lambda:len(api.call()['instances'])==2,'replacement admission')
 api.command('instance_stop',instanceId=a['id'],generation=a['generation'],expected=400)
 assert len(api.call()['instances'])==2
 api.command('panic');assert not api.call()['instances'] and api.call()['activeNotes']==0
 for i in range(12):api.command('phrase_play_independent',phraseId=1)
 api.wait_for(lambda:len(api.call()['instances'])==12,'existing voice capacity admitted')
 before=[i['id'] for i in api.call()['instances']];midi=api.call()['midiCount']
 api.command('phrase_play_independent',phraseId=1,expected=400)
 after=api.call();assert [i['id'] for i in after['instances']]==before
 assert after['instanceError']==2 and after['midiCount']==midi
 api.command('panic');assert not api.call()['instances'] and api.call()['activeNotes']==0
 api.patch('save');api.patch('load')
 assert original==[api.export(i) for i in (1,2)]
 assert not api.call()['instances']
 print('PASS actual native instance IDs/generations, independent admission, targeted/stale STOP, bounded refusal, PANIC, source persistence')
finally:
 api.tearDownClass()
