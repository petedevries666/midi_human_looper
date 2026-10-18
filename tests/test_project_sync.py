"""Real HTTP/native engine activation, conflicts, phrase bridge and restart."""
import copy
import json
from pathlib import Path
import sys
import subprocess
import unittest
import uuid
import urllib.request
from test_headless_mvp import HeadlessTests, ROOT, BINARY
sys.path.insert(0,str(ROOT/'headless'))
from reaper_bridge import Bridge
from project_sync import ProjectStore, Conflict
from server import Control
import portable_project as portable

class SyncTests(HeadlessTests):
    def test_sync_bridge(self):
        bridge=Bridge(self.base,'',Path(self.temp.name)/'spool')
        phrase={'events':[[0,146,60,100],[.125,146,64,91],[.25,130,60,30],[.5,130,64,20]],'lengthSeconds':1}
        preview=bridge.execute(dict(version=1,action='send_preview',phraseId=4,phrase=phrase))
        bridge.execute(dict(version=1,action='send',phraseId=4,phrase=phrase,expected=preview['expected']))
        retrieved=bridge.execute(dict(version=1,action='get',phraseId=4))['phrase']
        self.assertEqual(retrieved['events'],phrase['events'])
        control=Control(self.sock);state=self.call()
        local=control.request(op=4,arg=1,revision=state['revision'],session=state['engineSessionId'])
        # A REAPER-compatible base has no native-only extensions.
        local.pop('controllerEngine');local.pop('globalSnapshots')
        push=dict(version=1,action='push',patch=local,sampleRate=state['sampleRate'],confirmInitialReplace=True,reaperProjectId=str(uuid.uuid4()))
        applied=bridge.execute(push);self.assertEqual(applied['status'],'active')
        again=bridge.execute(push);self.assertEqual(again['status'],'active')
        with self.assertRaises(Conflict):bridge.execute({**push,'reaperProjectId':str(uuid.uuid4())})
        self.command('parameter_set',targetId=1,kind=1,value=77)
        with self.assertRaises(Conflict):bridge.execute(push)
        pulled=bridge.execute(dict(version=1,action='pull',patch=local,sampleRate=state['sampleRate'],reaperProjectId=push['reaperProjectId'],confirmLocalReplace=True))
        self.assertIn('memory',pulled['patch'])
        bridge.execute(dict(version=1,action='pull_commit',pendingId=pulled['pendingId']))
        # Dirty local state is refused unless deliberately replaced.
        dirty=copy.deepcopy(local);dirty['globals'][7]=.5
        with self.assertRaises(Conflict):bridge.execute(dict(version=1,action='pull',patch=dirty,sampleRate=state['sampleRate'],reaperProjectId=push['reaperProjectId']))
        self.command('phrase_play',phraseId=4)
        with self.assertRaises(Conflict):bridge.remote('/api/v1/project/capture')
        self.command('panic')
        store=ProjectStore(Path(self.temp.name)/'patches',control)
        old=store.manifest();current=bridge.remote('/api/v1/project/capture')
        project=current['project'];project['payload']['name']='tampered'
        with self.assertRaises(Conflict):bridge.remote('/api/v1/project/stage',dict(project=project,expectedActiveRevisionId=current['activeRevisionId']))
        self.assertEqual(store.manifest(),old)
        # A persistence failure rolls back the engine without publishing a new
        # active pointer. This executes the actual native load/rollback path.
        from unittest.mock import patch as mock_patch
        import project_sync
        clean=store.capture()
        # Re-capture with a changed parameter and valid parent/hash.
        candidate_patch=portable.materialize(clean['project'],state['sampleRate'])
        candidate_patch['globals'][7]=.8
        candidate=portable.capture(candidate_patch,state['sampleRate'],clean['project']['projectId'],clean['activeRevisionId'])
        store.stage(dict(project=candidate,expectedActiveRevisionId=clean['activeRevisionId']))
        staged_path=store.directory/(candidate['revisionId']+'.json')
        staged_bytes=staged_path.read_bytes();future=copy.deepcopy(candidate);future['unknownFutureData']=True
        staged_path.write_text(json.dumps(future));preserved=staged_path.read_bytes()
        with self.assertRaises(ValueError):store.stage(dict(project=candidate,expectedActiveRevisionId=clean['activeRevisionId']))
        self.assertEqual(staged_path.read_bytes(),preserved)
        staged_path.write_bytes(staged_bytes)
        save_json=project_sync.atomic_json
        def fail_manifest(path,value):
            if Path(path).name=='active.json':raise OSError('simulated disk failure')
            return save_json(path,value)
        with mock_patch('project_sync.atomic_json',side_effect=fail_manifest):
            with self.assertRaises(OSError):store.activate(dict(revisionId=candidate['revisionId'],expectedActiveRevisionId=clean['activeRevisionId'],
                expectedRevision=clean['engineRevision'],expectedEngineSessionId=clean['engineSessionId'],expectedFingerprint=clean['fingerprint']))
        self.assertEqual(store.manifest(),old)
        self.assertEqual(store.capture()['fingerprint'],clean['fingerprint'])
        restored=store.restore();self.assertEqual(restored['revisionId'],old['revisionId'])
        self.assertEqual(self.call()['activeNotes'],0)
        # Restart the actual process, restore without a browser or running web worker.
        self.stop_web();self.engine.terminate();self.engine.communicate(timeout=5)
        type(self).engine=subprocess.Popen([BINARY,str(ROOT/'midi_human_looper.jsfx'),self.sock],stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True)
        self.wait_for(lambda: Path(self.sock).exists(),'restarted engine')
        store.restore()
        recovered=control.request(op=35,target=3,revision=-1)['phraseData']
        self.assertEqual(recovered['events'],phrase['events'])
        self.start_web()
        # Exercise asynchronous spool through real HTTP instead of direct calls.
        from project_sync import atomic_json
        id=str(uuid.uuid4());atomic_json(bridge.spool/(id+'.job.json'),dict(version=1,action='get',phraseId=4))
        self.assertEqual(bridge.once(),1)
        self.assertTrue(json.loads((bridge.spool/(id+'.result.json')).read_text())['ok'])
        # Drive the shipped companion's defer/job protocol through this actual
        # HTTP server, with only REAPER UI/item APIs mocked.
        from lupa.lua54 import LuaRuntime
        import time
        resource=Path(self.temp.name)/'reaper-resource'
        ui_bridge=Bridge(self.base,'',resource/'Data/MIDI_Human_Looper/bridge')
        lua=LuaRuntime(unpack_returned_tuples=True)
        lua.globals().resource=str(resource);lua.globals().root=str(ROOT/'reaper')
        lua.globals().new_guid=lambda: str(uuid.uuid4())
        lua.globals().clock=time.monotonic
        lua.execute("""
          pending={};messages={};created=false;written=nil
          reaper={GetResourcePath=function()return resource end,RecursiveCreateDirectory=function()end,
            GetUserInputs=function()return true,'4' end,GetExtState=function()return '' end,SetExtState=function()end,
            genGuid=function()return new_guid() end,time_precise=function()return clock() end,
            defer=function(fn)pending[#pending+1]=fn end,
            ShowMessageBox=function(text)messages[#messages+1]=text;return 6 end,
            GetSelectedTrack=function()return 1 end,GetCursorPosition=function()return 20 end,
            Undo_BeginBlock=function()end,Undo_EndBlock=function()end,
            CreateNewMIDIItemInProj=function(_,a,b)assert(a==20 and b==21);created=true;return 1 end,
            GetActiveTake=function()return 1 end,
            MIDI_GetPPQPosFromProjTime=function(_,t)return (t-20)*960 end,
            MIDI_SetAllEvts=function(_,raw)written=raw;return true end,MIDI_Sort=function()end,UpdateArrange=function()end}
          MBMF_BRIDGE_ACTION='GET';dofile(root..'/MBMF_Studio_Live_Bridge.lua')
        """)
        tick=lua.eval('function()local f=table.remove(pending,1);if f then f() end end')
        for _ in range(10):
            ui_bridge.once();tick()
            if lua.eval('#pending')==0:break
        self.assertTrue(lua.eval('created and #messages==0'))
        lua.execute("""
          reaper.GetSelectedMediaItem=function()return 1 end;reaper.TakeIsMIDI=function()return true end
          reaper.GetMediaItemTake_Item=function()return 1 end
          reaper.GetMediaItemInfo_Value=function(_,key)if key=='D_POSITION' then return 20 elseif key=='D_LENGTH' then return 1 else return 0 end end
          reaper.MIDI_CountEvts=function()return true,2,0,0 end
          reaper.MIDI_GetAllEvts=function()return true,written end
          reaper.MIDI_GetProjTimeFromPPQPos=function(_,ppq)return 20+ppq/960 end
          MBMF_BRIDGE_ACTION='SEND';dofile(root..'/MBMF_Studio_Live_Bridge.lua')
        """)
        for _ in range(10):
            ui_bridge.once();tick()
            if lua.eval('#pending')==0:break
        self.assertTrue(lua.eval("#messages==2 and messages[2]=='Phrase sent.'"))
        self.assertEqual(bridge.execute(dict(version=1,action='get',phraseId=4))['phrase']['events'],phrase['events'])

if __name__=='__main__':
    result=unittest.TextTestRunner().run(unittest.TestSuite([SyncTests('test_sync_bridge')]))
    sys.exit(not result.wasSuccessful())
