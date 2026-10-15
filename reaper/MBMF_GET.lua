-- Toolbar action; implementation stays in the shared companion.
local folder=debug.getinfo(1,'S').source:sub(2):match('^(.*[/\\])')
MBMF_BRIDGE_ACTION='GET'
dofile(folder..'MBMF_Studio_Live_Bridge.lua')
MBMF_BRIDGE_ACTION=nil
