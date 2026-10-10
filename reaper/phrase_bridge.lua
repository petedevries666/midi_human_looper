-- Pure REAPER API phrase adapter. No MIDI file export and no networking.
local M={}
function M.capture(r,take)
  assert(take and r.TakeIsMIDI(take),'Select a MIDI take')
  local item=r.GetMediaItemTake_Item(take)
  local start=r.GetMediaItemInfo_Value(item,'D_POSITION')
  local length=r.GetMediaItemInfo_Value(item,'D_LENGTH')
  assert(length>0 and length<=3600,'Phrase length must be 0..3600 seconds')
  local _,notes,cc,text=r.MIDI_CountEvts(take)
  assert(notes*2<=2048,'Phrase exceeds 2048 MIDI events')
  assert(cc<=16 and text==0,'First bridge supports notes only; CC/SysEx/text must be handled separately')
  local ok,raw=r.MIDI_GetAllEvts(take,'')
  assert(ok and #raw<=1048576,'Cannot read bounded source MIDI')
  local events={};local ppq=0;local position=1;local sourceEnd=0;local terminalCount=0;local terminalTime=nil;local lastNoteTime=0
  while position<=#raw do
    local delta,flags,message,nextPosition=string.unpack('i4Bs4',raw,position)
    ppq=ppq+delta;position=nextPosition
    local seconds=r.MIDI_GetProjTimeFromPPQPos(take,ppq)-start
    sourceEnd=math.max(sourceEnd,seconds)
    if #message>0 then
      local status=message:byte(1);local kind=status&240
      if #message==3 and kind==176 and message:byte(2)==123 and message:byte(3)==0 then
        -- REAPER may expose its synthetic source-end All Notes Off marker.
        -- Actual notes must still have real matching releases (worker validation).
        terminalCount=terminalCount+1
        assert(not terminalTime or terminalTime==seconds,'Non-terminal All Notes Off is unsupported')
        terminalTime=seconds
      else
        assert(#message==3 and (kind==128 or kind==144),'Only source note events are supported')
        assert(flags&2==0,'Muted source notes cannot be transferred silently')
        assert(seconds>=0 and seconds<=length,'Notes crossing the item boundary: transfer cancelled')
        events[#events+1]={seconds,status,message:byte(2),message:byte(3)}
        lastNoteTime=math.max(lastNoteTime,seconds)
      end
    end
  end
  assert(#events<=2048,'Phrase exceeds 2048 MIDI events')
  assert((cc==0 or cc==terminalCount) and terminalCount<=16,'Unsupported MIDI controllers')
  assert(not terminalTime or terminalTime>=lastNoteTime,'All Notes Off inside a phrase cannot be discarded')
  if r.GetMediaItemInfo_Value(item,'B_LOOPSRC')>.5 then
    assert(sourceEnd+0.000001>=length,'Looped source item: glue it before transfer')
  end
  return {events=events,lengthSeconds=length,terminalMarker=terminalCount>0}
end
function M.insert(r,phrase)
  local track=r.GetSelectedTrack(0,0);assert(track,'Select a destination track')
  local start=r.GetCursorPosition();local length=phrase.lengthSeconds
  assert(type(length)=='number' and length>0 and length<=3600,'Invalid phrase duration')
  assert(#phrase.events<=2048,'Oversized phrase')
  r.Undo_BeginBlock()
  local item=r.CreateNewMIDIItemInProj(track,start,start+length,false)
  assert(item,'Cannot create MIDI item');local take=r.GetActiveTake(item)
  local base=r.MIDI_GetPPQPosFromProjTime(take,start);local previous=0;local parts={}
  for _,e in ipairs(phrase.events) do
    local pos=math.floor(r.MIDI_GetPPQPosFromProjTime(take,start+e[1])-base+.5)
    assert(pos>=previous,'Unordered source MIDI')
    parts[#parts+1]=string.pack('i4Bs4',pos-previous,0,string.char(e[2],e[3],e[4]));previous=pos
  end
  local ending=math.floor(r.MIDI_GetPPQPosFromProjTime(take,start+length)-base+.5)
  parts[#parts+1]=string.pack('i4Bs4',math.max(0,ending-previous),0,'')
  local ok=r.MIDI_SetAllEvts(take,table.concat(parts))
  if not ok then r.DeleteTrackMediaItem(track,item);r.Undo_EndBlock('MBMF failed MIDI retrieval',-1);error('Cannot write MIDI events') end
  r.MIDI_Sort(take);r.UpdateArrange();r.Undo_EndBlock('MBMF retrieve live phrase',-1)
  return item
end
return M
