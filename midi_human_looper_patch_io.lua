-- MIDI Human Looper external patch I/O daemon
-- Run once in REAPER. It stays alive with reaper.defer().
-- Files: <REAPER resource>/Data/MIDI_Human_Looper/patch1.json and patch2.json

local GMEM = "MIDI_HUMAN_LOOPER"
local SCHEMA = 7
local PAYLOAD_BASE = 32
reaper.gmem_attach(GMEM)

local root = reaper.GetResourcePath() .. "/Data/MIDI_Human_Looper"
local sep = package.config:sub(1,1)
root = root:gsub("[/\\]", sep)

local function ensure_dir()
  reaper.RecursiveCreateDirectory(root, 0)
end

local function path_for(slot)
  return root .. sep .. "patch" .. tostring(slot) .. ".json"
end

local function num(v)
  if v ~= v or v == math.huge or v == -math.huge then return "0" end
  return string.format("%.17g", v)
end

local function headless_extension(txt)
  if not txt or not txt:match('"controllerEngine"%s*:') then return false end
  local body = txt:match('"configuration"%s*:%s*%[(.-)%]')
  if not body then return true end -- Unknown extensions must not be erased.
  local values = {}
  for token in body:gmatch("[^,%s]+") do values[#values+1] = tonumber(token) or -1 end
  if #values ~= 2177 or values[1] ~= 1 then return true end
  for i=0,15 do if values[2+4*i] ~= 0 then return true end end
  for i=0,31 do if values[66+66*i] ~= 0 then return true end end
  return false
end

local function refuse_headless()
  if reaper.ShowMessageBox then
    reaper.ShowMessageBox("This file contains headless Controller Engine configuration. Use EXPORT REAPER BASE in the web editor, then copy the separate patchN-reaper.json file to the REAPER patch slot. The original headless patch has been preserved.", "MIDI Human Looper", 0)
  end
  return false
end

local function save_patch(slot)
  ensure_dir()
  local n = math.floor(reaper.gmem_read(3) + 0.5)
  local schema = reaper.gmem_read(2)
  if (schema ~= 1 and schema ~= 2 and schema ~= 3 and schema ~= 4 and schema ~= 5 and schema ~= 6 and schema ~= SCHEMA) or n <= 0 or n > 1000000 then return false end
  local existing = io.open(path_for(slot), "rb")
  if existing then
    local txt = existing:read("*a"); existing:close()
    if headless_extension(txt) then return refuse_headless() end
  end
  local fh = io.open(path_for(slot), "wb")
  if not fh then return false end
  fh:write('{"format":"MIDI_HUMAN_LOOPER_PATCH","schema":', tostring(schema))
  fh:write(',"work_mem_size":', tostring(n))
  fh:write(',"globals":[')
  for i=4,12 do
    if i>4 then fh:write(",") end
    fh:write(num(reaper.gmem_read(i)))
  end
  fh:write('],"memory":[')
  for j=0,n-1 do
    if j>0 then fh:write(",") end
    fh:write(num(reaper.gmem_read(PAYLOAD_BASE+j)))
  end
  fh:write("]}\n")
  fh:close()
  return true
end

local function parse_array(txt, key)
  local body = txt:match('"'..key..'"%s*:%s*%[(.-)%]')
  if not body then return nil end
  local out = {}
  for token in body:gmatch("[^,%s]+") do
    local v = tonumber(token)
    if not v or v ~= v or v == math.huge or v == -math.huge then return nil end
    out[#out+1] = v
  end
  return out
end

local function load_patch(slot)
  local fh = io.open(path_for(slot), "rb")
  if not fh then return false end
  local txt = fh:read("*a")
  fh:close()
  if headless_extension(txt) then return refuse_headless() end
  local schema = tonumber(txt:match('"schema"%s*:%s*(%d+)'))
  local n = tonumber(txt:match('"work_mem_size"%s*:%s*(%d+)'))
  local globals = parse_array(txt, "globals")
  local memory = parse_array(txt, "memory")
  if (schema ~= 1 and schema ~= 2 and schema ~= 3 and schema ~= 4 and schema ~= 5 and schema ~= 6 and schema ~= SCHEMA) or not n or n <= 0 or n > 1000000 or not globals or #globals ~= 9 or not memory or #memory ~= n then
    return false
  end
  if not txt:match('"format"%s*:%s*"MIDI_HUMAN_LOOPER_PATCH"') then return false end
  reaper.gmem_write(2, schema)
  reaper.gmem_write(3, n)
  for i=1,9 do reaper.gmem_write(3+i, globals[i]) end
  for j=1,n do reaper.gmem_write(PAYLOAD_BASE+j-1, memory[j]) end
  return true
end

local function loop()
  reaper.gmem_write(15, 1) -- heartbeat/ready flag
  reaper.gmem_write(16, SCHEMA) -- advertised maximum patch schema
  local cmd = math.floor(reaper.gmem_read(0) + 0.5)
  local slot = math.floor(reaper.gmem_read(1) + 0.5)
  if slot < 1 or slot > 2 then slot = 1 end

  if cmd == 1 then
    reaper.gmem_write(0, save_patch(slot) and 4 or 5)
  elseif cmd == 2 then
    reaper.gmem_write(0, load_patch(slot) and 3 or 5)
  end
  reaper.defer(loop)
end

reaper.atexit(function() reaper.gmem_write(15, 0); reaper.gmem_write(16, 0) end)
loop()
