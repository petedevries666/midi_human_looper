-- Small bounded JSON codec for the bridge's data-only job protocol.
local J={null={}}
function J.encode(v)
  local t=type(v)
  if v==J.null then return 'null' end
  if t=='number' then assert(v==v and math.abs(v)<math.huge,'Non-finite JSON');return ('%.17g'):format(v) end
  if t=='boolean' then return tostring(v) end
  if t=='string' then return '"'..v:gsub('[%z\1-\31\\"]',function(c)
    local e={['"']='\\"',['\\']='\\\\',['\n']='\\n',['\r']='\\r',['\t']='\\t'}
    return e[c] or ('\\u%04x'):format(c:byte()) end)..'"' end
  assert(t=='table','Invalid JSON value')
  local out={};local array=true
  for k in pairs(v) do if type(k)~='number' then array=false end end
  if array then for i=1,#v do out[#out+1]=J.encode(v[i]) end;return '['..table.concat(out,',')..']' end
  for k,x in pairs(v) do assert(type(k)=='string');out[#out+1]=J.encode(k)..':'..J.encode(x) end
  return '{'..table.concat(out,',')..'}'
end
function J.decode(s)
  assert(#s<=16000000,'Oversized JSON');local p=1
  local function ws()local _,b=s:find('^%s*',p);p=(b or p-1)+1 end
  local function str()
    assert(s:sub(p,p)=='"');p=p+1;local out={}
    while p<=#s do
      local c=s:sub(p,p);p=p+1
      if c=='"' then return table.concat(out) end
      assert(c:byte()>=32,'Invalid JSON string')
      if c=='\\' then
        c=s:sub(p,p);p=p+1
        local esc={['"']='"',['\\']='\\',['/']='/',b='\b',f='\f',n='\n',r='\r',t='\t'}
        if c=='u' then
          local h=s:sub(p,p+3);assert(h:match('^%x%x%x%x$'));local n=tonumber(h,16);p=p+4
          if n>=0xd800 and n<=0xdbff then
            assert(s:sub(p,p+1)=='\\u');p=p+2;h=s:sub(p,p+3);assert(h:match('^%x%x%x%x$'))
            local low=tonumber(h,16);assert(low>=0xdc00 and low<=0xdfff);p=p+4;n=0x10000+(n-0xd800)*1024+low-0xdc00
          else assert(n<0xdc00 or n>0xdfff) end
          c=utf8.char(n)
        else c=assert(esc[c],'Invalid JSON escape') end
      end
      out[#out+1]=c
    end
    error('Unterminated JSON string')
  end
  local value
  value=function(depth)
    assert(depth<=32,'JSON nesting');ws();local c=s:sub(p,p)
    if c=='"' then return str() end
    if c=='[' or c=='{' then
      p=p+1;ws();local result={};local close=c=='[' and ']' or '}'
      if s:sub(p,p)==close then p=p+1;return result end
      repeat
        local key
        if c=='{' then ws();key=str();assert(result[key]==nil,'Duplicate JSON key');ws();assert(s:sub(p,p)==':');p=p+1 else key=#result+1 end
        result[key]=value(depth+1);ws();local sep=s:sub(p,p);p=p+1
        if sep==close then return result end
        assert(sep==',','JSON delimiter')
      until false
    end
    for text,x in pairs({['true']=true,['false']=false,['null']=J.null}) do
      if s:sub(p,p+#text-1)==text then p=p+#text;return x end
    end
    local text=s:match('^-?%d+%.?%d*[eE]?[+-]?%d*',p)
    assert(text and #text>0,'Invalid JSON token');local x=assert(tonumber(text),'Invalid JSON number');p=p+#text;return x
  end
  local result=value(0);ws();assert(p>#s,'Trailing JSON');return result
end
return J
