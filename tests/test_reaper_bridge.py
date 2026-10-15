"""Run shipped Lua against mocked REAPER APIs, with actual binary MIDI buffers."""
from pathlib import Path
import unittest
from lupa.lua54 import LuaRuntime
ROOT=Path(__file__).resolve().parents[1]
class ReaperBridgeTests(unittest.TestCase):
    def setUp(self):
        self.lua=LuaRuntime(unpack_returned_tuples=True)
        self.lua.globals().root=str(ROOT/'reaper')
        self.lua.execute("J=dofile(root..'/json.lua');P=dofile(root..'/phrase_bridge.lua')")
    def test_json_bounds_unicode_and_wire_roundtrip(self):
        self.lua.execute('''
          local value=J.decode('{"a":[1,2.5,false,null],"s":"\\\\u00e9\\\\ud83c\\\\udfb9"}')
          assert(value.s=='é🎹');assert(value.a[4]==J.null)
          assert(J.decode(J.encode(value)).s==value.s)
          assert(not pcall(J.decode,'{"a":1,"a":2}'))
          assert(not pcall(J.decode,'[1]garbage'))
        ''')
    def test_capture_retrieve_preserves_bytes_seconds_and_channel(self):
        self.lua.execute('''
          local events={{0,146,60,100},{120,146,64,91},{240,130,60,30},{480,130,64,20}}
          local parts={};local previous=0
          for _,e in ipairs(events) do parts[#parts+1]=string.pack('i4Bs4',e[1]-previous,0,string.char(e[2],e[3],e[4]));previous=e[1] end
          parts[#parts+1]=string.pack('i4Bs4',480,0,'')
          local raw=table.concat(parts);local written
          r={
            TakeIsMIDI=function()return true end, GetMediaItemTake_Item=function()return 1 end,
            GetMediaItemInfo_Value=function(_,key)if key=='D_POSITION' then return 10 elseif key=='D_LENGTH' then return 1 else return 0 end end,
            MIDI_CountEvts=function()return true,2,0,0 end,
            MIDI_GetAllEvts=function()return true,raw end,
            MIDI_GetProjTimeFromPPQPos=function(_,p)return 10+p/960 end,
            GetSelectedTrack=function()return 1 end,GetCursorPosition=function()return 10 end,
            Undo_BeginBlock=function()end,Undo_EndBlock=function()end,
            CreateNewMIDIItemInProj=function(_,a,b)assert(a==10 and b==11);return 1 end,
            GetActiveTake=function()return 1 end,
            MIDI_GetPPQPosFromProjTime=function(_,t)return (t-10)*960 end,
            MIDI_SetAllEvts=function(_,data)written=data;return true end,
            MIDI_Sort=function()end,UpdateArrange=function()end
          }
          local phrase=P.capture(r,1);assert(phrase.events[4][1]==.5 and phrase.events[3][4]==30)
          P.insert(r,phrase);assert(written==raw,'Byte-perfect source note round trip')
          r.MIDI_CountEvts=function()return true,2,1,0 end
          assert(not pcall(P.capture,r,1),'CC rejection')
          r.MIDI_GetAllEvts=function()return true,raw..string.pack('i4Bs4',0,0,string.char(176,123,0)) end
          local terminated=P.capture(r,1);assert(terminated.terminalMarker and #terminated.events==4)
          r.MIDI_GetAllEvts=function()return true,raw end
          r.MIDI_CountEvts=function()return true,2,0,0 end
          r.GetMediaItemInfo_Value=function(_,key)if key=='D_POSITION' then return 10 elseif key=='D_LENGTH' then return .1 else return 0 end end
          assert(not pcall(P.capture,r,1),'Boundary rejection')
        ''')
    def test_shared_gmem_scope_counts_input_fx_and_other_open_projects(self):
        source=(ROOT/'reaper/MBMF_Studio_Live_Bridge.lua').read_text().replace('local function single_engine()','function single_engine()').replace('safe(start)','')
        self.lua.globals().source=source
        self.lua.execute("""
          secondary=false;input_only=false;current=101
          reaper={GetResourcePath=function()return '/tmp' end,RecursiveCreateDirectory=function()end,
            EnumProjects=function(i)if i==-1 then return current elseif i==0 then return 101 elseif i==1 then return 102 else return nil end end,
            GetMasterTrack=function()return 0 end,
            CountTracks=function(project)return project==101 and 1 or (secondary and 1 or 0) end,
            GetTrack=function(project)return project==101 and 1 or 2 end,
            TrackFX_GetCount=function(track)return track==1 and not input_only and 1 or 0 end,
            TrackFX_GetRecCount=function(track)return (track==1 and input_only) or track==2 and 1 or 0 end,
            TrackFX_GetFXName=function()return true,'renamed' end,
            TrackFX_GetNamedConfigParm=function()return true,'midi_human_looper.jsfx' end,
            TakeFX_GetNamedConfigParm=function()return false,'' end,
            CountMediaItems=function()return 0 end,GetPlayState=function()return 0 end}
          -- Normalize the boolean branch of the input-FX count stub.
          reaper.TrackFX_GetRecCount=function(track)if track==1 then return input_only and 1 or 0 elseif track==2 then return 1 else return 0 end end
          assert(load(source,'@'..root..'/MBMF_Studio_Live_Bridge.lua'))()
          assert(pcall(single_engine))
          input_only=true;assert(pcall(single_engine),'one input FX is recognized')
          secondary=true;assert(not pcall(single_engine),'second input FX in another project is refused')
          secondary=false;current=102;assert(not pcall(single_engine),'wrong active project cannot capture shared gmem')
        """)

    def test_companion_lua_compiles_without_running_ui(self):
        self.lua.execute("assert(loadfile(root..'/MBMF_Studio_Live_Bridge.lua'))")
if __name__=='__main__':unittest.main()
