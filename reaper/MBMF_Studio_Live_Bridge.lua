-- Run from REAPER's Actions list. Keep this file beside json.lua/phrase_bridge.lua.
-- Start the separately paired Python worker; no socket/HTTP code runs here.
local folder=debug.getinfo(1,'S').source:sub(2):match('^(.*[/\\])')
local J=dofile(folder..'json.lua')
local Phrase=dofile(folder..'phrase_bridge.lua')
local r=reaper
local spool=r.GetResourcePath()..'/Data/MIDI_Human_Looper/bridge'
r.RecursiveCreateDirectory(spool,0)
local function read(path)local f=io.open(path,'rb');if not f then return nil end;local s=f:read(16000001);f:close();return J.decode(s) end
local function write(path,value)
  local temp=path..'.tmp';local f=assert(io.open(temp,'wb'),'Cannot write bridge spool')
  f:write(J.encode(value));f:close();assert(os.rename(temp,path),'Cannot publish bridge job')
end
local function fail(e)r.ShowMessageBox(tostring(e),'MBMF bridge',0) end
local function safe(fn,...)
  local ok,result=pcall(fn,...);if not ok then fail(result) end;return ok,result
end
local function job(data,done,onerror)
  data.version=1
  local id=r.genGuid():gsub('[{}]',''):lower()
  local path=spool..'/'..id;write(path..'.job.json',data)
  local deadline=r.time_precise()+35
  local function poll()
    local ok,response=pcall(read,path..'.result.json')
    if not ok then fail(response);return end
    if response then
      os.remove(path..'.result.json')
      if response.ok then safe(done,response.result) elseif onerror then safe(onerror,response.error) else fail(response.error) end
    elseif r.time_precise()>deadline then
      -- Cancel a job that has not been claimed; a claimed remote transaction may
      -- already have committed. Do not retry automatically after ambiguous timeout.
      os.remove(path..'.job.json');fail('Bridge timeout. Inspect live state before retrying; start the Python bridge worker.')
    else r.defer(poll) end
  end
  poll()
end
local function engine_name(name,ident)
  return name:find('MIDI Human Looper',1,true) or name:find('MIDI BAD MOTHER',1,true) or ident:lower():find('midi_human_looper',1,true)
end
local function single_engine()
  assert(r.TrackFX_GetNamedConfigParm and r.TakeFX_GetNamedConfigParm,'PUSH/PULL requires REAPER FX identity APIs')
  local count,currentCount=0,0
  local current=r.EnumProjects(-1,'')
  local function track_fx(track,project)
    local function inspect(fx)
      local _,name=r.TrackFX_GetFXName(track,fx,'')
      local _,ident=r.TrackFX_GetNamedConfigParm(track,fx,'fx_ident')
      if engine_name(name,ident) then count=count+1;if project==current then currentCount=currentCount+1 end end
    end
    for fx=0,r.TrackFX_GetCount(track)-1 do inspect(fx) end
    for fx=0,r.TrackFX_GetRecCount(track)-1 do inspect(0x1000000+fx) end
  end
  -- gmem is shared across open project tabs, normal FX and input FX alike.
  local index=0
  while true do
    local project=r.EnumProjects(index,'');if not project then break end;index=index+1
    track_fx(r.GetMasterTrack(project),project)
    for t=0,r.CountTracks(project)-1 do track_fx(r.GetTrack(project,t),project) end
    for i=0,r.CountMediaItems(project)-1 do
      local item=r.GetMediaItem(project,i)
      for t=0,r.CountTakes(item)-1 do
        local take=r.GetTake(item,t)
        for fx=0,r.TakeFX_GetCount(take)-1 do
          local _,name=r.TakeFX_GetFXName(take,fx,'')
          local _,ident=r.TakeFX_GetNamedConfigParm(take,fx,'fx_ident')
          if engine_name(name,ident) then error('PUSH/PULL requires one track JSFX instance, not take FX') end
        end
      end
    end
  end
  assert(count==1 and currentCount==1,'PUSH/PULL requires one track JSFX in the current project and no other instance in any open project')
  assert(r.GetPlayState()==0,'STOP REAPER before PUSH/PULL')
end
local function mailbox(command,done)
  single_engine();r.gmem_attach('MIDI_HUMAN_LOOPER')
  assert(r.gmem_read(0)==0 and r.gmem_read(19)==0,'Patch I/O busy')
  local id=math.floor(r.time_precise()*1000)%16777214+1
  r.gmem_write(21,0);r.gmem_write(20,id);r.gmem_write(19,command)
  local deadline=r.time_precise()+5
  local function poll()
    if r.gmem_read(21)==id then
      if r.gmem_read(22)==1 then safe(done) else fail('JSFX refused: stop notes, playback and recording first') end
    elseif r.time_precise()>deadline then
      if r.gmem_read(20)==id then r.gmem_write(19,0) end
      fail('No JSFX acknowledgement. Use the updated effect and keep FX processing enabled while stopped.')
    else r.defer(poll) end
  end
  poll()
end
local function capture_patch(done)
  mailbox(1,function()
    local n=r.gmem_read(3);assert(n==171649 and r.gmem_read(2)==7,'Schema-7 JSFX required')
    local globals,memory={},{}
    for i=1,9 do globals[i]=r.gmem_read(3+i) end
    for i=1,n do memory[i]=r.gmem_read(31+i) end
    done({format='MIDI_HUMAN_LOOPER_PATCH',schema=7,work_mem_size=n,globals=globals,memory=memory},r.gmem_read(17))
  end)
end
local function start()
  local action=MBMF_BRIDGE_ACTION
  if not action then
    local ok;ok,action=r.GetUserInputs('MBMF STUDIO / LIVE',1,'SEND / GET / PUSH / PULL:',r.GetExtState('MBMFBridge','action'))
    if not ok then return end
  end
  action=action:upper();r.SetExtState('MBMFBridge','action',action,true)
  if action=='SEND' or action=='GET' then
    local yes,text=r.GetUserInputs('Live phrase target',1,'Phrase ID (1..16):',r.GetExtState('MBMFBridge','phrase')~='' and r.GetExtState('MBMFBridge','phrase') or '1')
    if not yes then return end;local target=tonumber(text);assert(target and target%1==0 and target>=1 and target<=16,'Invalid phrase')
    r.SetExtState('MBMFBridge','phrase',text,true)
    if action=='GET' then job({action='get',phraseId=target},function(result)Phrase.insert(r,result.phrase) end)
    else
      local item=r.GetSelectedMediaItem(0,0);local phrase=Phrase.capture(r,item and r.GetActiveTake(item))
      job({action='send_preview',phraseId=target,phrase=phrase},function(preview)
        if r.ShowMessageBox('Replace live phrase '..target..' with '..#phrase.events..' source events?\nExisting target data will be replaced.','MBMF SEND',4)==6 then
          job({action='send',phraseId=target,phrase=phrase,expected=preview.expected},function()r.ShowMessageBox('Phrase sent.','MBMF',0) end)
        end
      end)
    end
  elseif action=='PUSH' or action=='PULL' then
    local project=r.EnumProjects(-1,'')
    local projectId=r.GetProjectGUID(project):gsub('[{}]',''):lower()
    capture_patch(function(patch,sampleRate)
      if action=='PUSH' then
        local initial=read(spool..'/baseline.json')==nil
        if initial and r.ShowMessageBox('First PUSH replaces the stopped live project. Continue?','MBMF initial pairing',4)~=6 then return end
        job({action='push',patch=patch,sampleRate=sampleRate,reaperProjectId=projectId,confirmInitialReplace=initial},function()r.ShowMessageBox('Live revision activated and persisted.','MBMF PUSH',0) end)
      else
        local function apply(result)
          -- Re-capture to protect edits made while the network worker was busy.
          capture_patch(function(current)
            assert(r.GetProjectGUID(r.EnumProjects(-1,'')):gsub('[{}]',''):lower()==projectId,'Current REAPER project changed during PULL')
            assert(J.encode(current)==J.encode(patch),'Local state changed during PULL; cancelled')
            single_engine();r.gmem_attach('MIDI_HUMAN_LOOPER')
            assert(r.gmem_read(0)==0 and r.gmem_read(19)==0,'Patch I/O busy')
            local nextPatch=result.patch
            r.gmem_write(2,nextPatch.schema);r.gmem_write(3,nextPatch.work_mem_size)
            for i,v in ipairs(nextPatch.globals) do r.gmem_write(3+i,v) end
            for i,v in ipairs(nextPatch.memory) do r.gmem_write(31+i,v) end
            mailbox(2,function()r.MarkProjectDirty(project);job({action='pull_commit',pendingId=result.pendingId},function()r.ShowMessageBox('Local project retrieved.','MBMF PULL',0) end) end)
          end)
        end
        local function duplicate()
          job({action='pull_duplicate'},function(result)r.ShowMessageBox('Portable copy saved in bridge spool: '..result.file,'MBMF duplicate',0) end)
        end
        job({action='pull',patch=patch,sampleRate=sampleRate,reaperProjectId=projectId},apply,function(message)
          if message:find('Local edits',1,true) then
            local choice=r.ShowMessageBox('Unsynchronized local configuration.\nYES: replace local JSFX\nNO: duplicate portable live project only\nCANCEL: leave both unchanged','MBMF PULL conflict',3)
            if choice==6 then job({action='pull',patch=patch,sampleRate=sampleRate,reaperProjectId=projectId,confirmLocalReplace=true},apply)
            elseif choice==7 then duplicate() end
          elseif message:find('REAPER',1,true) then
            if r.ShowMessageBox(message..'\nSave a portable copy without applying it?','MBMF capability limit',4)==6 then duplicate() end
          else fail(message) end
        end)
      end
    end)
  else error('Choose SEND, GET, PUSH or PULL') end
end
safe(start)
