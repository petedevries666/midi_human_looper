'use strict';
let revision=1, engineSession=null, pending=false, renderedModel='', latest=null;
let catalog=null, ws=null, reconnect=null;
const $=id=>document.getElementById(id);
const node=(tag,text,cls)=>{const n=document.createElement(tag);if(text!==undefined)n.textContent=text;if(cls)n.className=cls;return n;};
function headers(){return {'Content-Type':'application/json','X-Engine-Token':$('token').value};}
async function request(path,body){const response=await fetch(path,{method:body?'POST':'GET',headers:headers(),body:body?JSON.stringify(body):undefined});const data=await response.json();if(!response.ok)throw new Error(data.error||data.status||'Request failed');return data;}
function button(label,action){const b=node('button',label);b.addEventListener('click',action);return b;}
function descriptor(type){return catalog?.modules.find(m=>m.engineType===type);}
function parameter(kind){return catalog?.parameters.find(p=>p.engineKind===kind);}
async function loadDescriptors(){try{catalog=await request('/api/v1/descriptors');renderedModel='';if(latest)render(latest);}catch(e){$('error').textContent=e.message;}}
function editInstrument(i){const d=descriptor(0);if(!d)return;edit(d,i,d.parameters.map(id=>{const p=catalog.parameters.find(p=>p.id===id);return {descriptor:p,value:i[p.engineField],assignment:0};}),null);}
function editModule(i,tf){const d=descriptor(tf.type);if(!d)return;edit(d,i,tf.parameters.map(p=>({descriptor:parameter(p.kind),...p})),tf);}
function edit(module,instrument,values,instance){
  const dialog=$('editor'),content=$('editor-content');if(dialog.open)return;
  const capturedRevision=revision,capturedSession=engineSession;
  let committing=false;
  const drafts=values.map(v=>({...v}));
  content.replaceChildren(node('h2',`${module.label} · ${instance?.id||instrument.id}`));
  const dismiss=()=>{if(!committing)dialog.close();};
  content.append(button('×',dismiss));
  for(const draft of drafts){
    const p=draft.descriptor;if(!p)continue;
    const label=node('label',p.label,'parameter');
    const number=node('input');number.type='number';number.min=p.min;number.max=p.max;number.step=p.step;number.value=draft.value;
    const rail=node('input');rail.type='range';rail.min=p.min;rail.max=p.max;rail.step=p.step;rail.value=draft.value;
    rail.disabled=number.disabled=!!draft.assignment;
    function update(value){draft.value=Number(value);number.value=draft.value;rail.value=draft.value;}
    number.addEventListener('input',()=>update(number.value));rail.addEventListener('input',()=>update(rail.value));rail.addEventListener('dblclick',()=>update(p.default));
    label.append(number,node('span',p.unit),rail);
    if(draft.assignment)label.append(node('small',`EXPRESSION ${draft.assignment} owns this target`));
    content.append(label);
  }
  const error=node('p','');error.setAttribute('role','alert');content.append(error);
  const done=button('DONE',async()=>{
    if(committing)return;
    if(engineSession!==capturedSession){error.textContent='Engine restarted. CANCEL and reopen this editor.';return;}
    const body=instance?{action:'module_commit',instrumentId:instrument.id,moduleId:instance.id,parameters:drafts.filter(d=>!d.assignment).map(d=>({kind:d.kind,value:d.value}))}:{action:'instrument_commit',instrumentId:instrument.id,...Object.fromEntries(drafts.map(d=>[d.descriptor.engineField,d.value]))};
    if(instance&&drafts.every(d=>d.assignment)){dialog.close();return;}
    committing=true;done.disabled=cancel.disabled=true;
    try{const state=await request('/api/v1/command',{protocolVersion:1,expectedRevision:capturedRevision,expectedEngineSessionId:capturedSession,...body});render(state);dialog.close();}
    catch(e){error.textContent=e.message==='conflict'?'Configuration changed. CANCEL and reopen this editor.':e.message;}
    finally{committing=false;done.disabled=cancel.disabled=false;}
  });
  const cancel=button('CANCEL',dismiss);content.append(done,cancel);
  dialog.oncancel=e=>{if(committing)e.preventDefault();};
  dialog.onclick=e=>{const r=dialog.getBoundingClientRect();if(e.target===dialog&&(e.clientX<r.left||e.clientX>r.right||e.clientY<r.top||e.clientY>r.bottom))dismiss();};
  dialog.showModal();
}
function render(s){
  if(engineSession===s.engineSessionId&&s.revision<revision)return;
  engineSession=s.engineSessionId;revision=s.revision;latest=s;
  $('connection').textContent='CONNECTED · Engine running';
  $('metrics').replaceChildren(...[`Backend ${s.backend} · ${s.sampleRate} Hz / ${s.blockSize}`,`Sample clock ${s.sampleClock}`,`MIDI messages ${s.midiCount}`,`Active notes ${s.activeNotes}`,`Maximum callback ${s.maxCallbackUs.toFixed(1)} µs`,`Late blocks ${s.lateBlocks}`,`Output overflow ${s.outputOverflow}`].map(v=>node('span',v)));
  $('last-midi').textContent=`Last MIDI · sample ${s.lastEvent[0]} · status ${s.lastEvent[1]} · number ${s.lastEvent[2]} · value ${s.lastEvent[3]}`;
  for(const sw of s.switches){const el=document.querySelector(`[data-switch-id="${sw.id}"] .step`);if(el)el.textContent=`STEP ${sw.step} / ${sw.length}`;}
  const model=JSON.stringify([s.phrases,s.instruments,s.switches.map(v=>({...v,step:0}))]);if(model===renderedModel)return;renderedModel=model;
  $('phrases').replaceChildren(...s.phrases.map(p=>{const n=node('div',`PHRASE ${p.id}`,'phrase');n.append(node('small',`${p.events} events · ${p.mode===0?'LOOP':'ONCE / HOLD'} · TIME ×${p.timeDecay.toFixed(2)}`));for(const [label,action] of [['PLAY','phrase_play'],['REC / OVERDUB','phrase_record'],['FINISH REC','phrase_finish']])n.append(button(label,()=>command({action,phraseId:p.id})));return n;}));
  $('instruments').replaceChildren(...s.instruments.map(i=>{
    const n=node('article',undefined,'instrument');n.dataset.instrumentId=i.id;
    n.append(node('h3',`${i.name||'INSTRUMENT'} · ID ${i.id} · ${i.enabled?'ON':'OFF'}`),node('div',`MIDI IN ${i.input||'ALL'} → OUT ${i.output||'ORIGINAL'}`,'routing'),node('p',`VOLUME ${i.level}`),button('EDIT',()=>editInstrument(i)));
    const rail=node('div',undefined,'rail'),fill=node('span');fill.style.width=`${i.level/127*100}%`;rail.append(fill);n.append(rail);
    const chain=node('div',undefined,'transformers');
    for(const tf of i.transformers||[]){
      const card=node('article',undefined,'module');card.dataset.moduleId=tf.id;
      card.append(node('h3',`${descriptor(tf.type)?.label||'MODULE'} · ID ${tf.id}`),node('p',tf.enabled?'ON':'BYPASS'),button('EDIT',()=>editModule(i,tf)));
      for(const [label,operation] of [['BYPASS','bypass'],['↑','up'],['↓','down'],['DELETE','delete']])card.append(button(label,()=>{if(operation==='delete'&&!confirm('Delete this Transformer?'))return;command({action:'module_structure',instrumentId:i.id,moduleId:tf.id,operation});}));
      chain.append(card);
    }
    const select=node('select');select.setAttribute('aria-label',`Transformer type for Instrument ${i.id}`);
    for(const d of catalog?.modules.filter(m=>m.engineType>0)||[]){const option=node('option',d.label);option.value=d.engineType;select.append(option);}
    n.append(chain,select,button('ADD TRANSFORMER',()=>command({action:'module_structure',instrumentId:i.id,operation:'add',engineType:Number(select.value)})));
    return n;
  }));
  $('switches').replaceChildren(...s.switches.map(sw=>{
    const n=node('article',undefined,'switch');n.dataset.switchId=sw.id;n.append(node('h3',sw.name||`SWITCH ${sw.id}`),node('p',`${sw.type===0?'PHRASE':'SPECIAL'} · ID ${sw.id}`),node('p',`${sw.kind===1?'NOTE':sw.kind===2?'CC':'UNASSIGNED'} ${sw.number} · CH ${sw.channel}`),node('p',`STEP ${sw.step} / ${sw.length}`,'step'));
    const tests=node('div',undefined,'tests');for(const gesture of ['tap','double','hold']){const b=button(`TEST ${gesture.toUpperCase()}`,()=>command({action:'test',switchId:sw.id,gesture}));b.dataset.valid=sw.enabled?'1':'0';b.disabled=!sw.enabled;tests.append(b);}
    const hardware=button('SIMULATE FOOTSWITCH',async()=>{if(await command({action:'midi',channel:sw.channel,note:sw.number,value:100}))await command({action:'midi',channel:sw.channel,note:sw.number,value:0});});hardware.className='hardware';hardware.dataset.valid=sw.kind===1?'1':'0';hardware.disabled=sw.kind!==1;n.append(tests,hardware);return n;
  }));
}
async function refresh(){try{render(await request('/api/v1/state'));}catch(e){$('connection').textContent='DISCONNECTED · Engine continues independently';$('error').textContent=e.message;}}
function setPending(value){pending=value;for(const b of document.querySelectorAll('main button')){if(value){b.dataset.pendingDisabled=b.disabled?'1':'0';b.disabled=true;}else if(b.dataset.pendingDisabled!==undefined){b.disabled=b.dataset.pendingDisabled==='1';delete b.dataset.pendingDisabled;}}}
async function command(value){if(pending)return false;setPending(true);try{render(await request('/api/v1/command',{protocolVersion:1,expectedRevision:revision,expectedEngineSessionId:engineSession,...value}));$('error').textContent='';return true;}catch(e){$('error').textContent=e.message;await refresh();return false;}finally{setPending(false);}}
function connectStream(){
  if(ws){ws.onclose=null;ws.close();}
  ws=new WebSocket(`${location.protocol==='https:'?'wss':'ws'}://${location.host}/api/v1/ws`);
  ws.onopen=()=>ws.send(JSON.stringify({token:$('token').value}));
  ws.onmessage=e=>{try{if(!pending)render(JSON.parse(e.data));}catch(err){$('error').textContent=err.message;}};
  ws.onclose=()=>{$('connection').textContent='DISCONNECTED · Engine continues independently';reconnect=setTimeout(connectStream,1000);};ws.onerror=()=>ws.close();
}
async function patch(action){if(pending)return;setPending(true);try{const data=await request(`/api/v1/patch/${action}`,{slot:Number($('patch-slot').value),expectedRevision:revision,expectedEngineSessionId:engineSession});$('patch-status').textContent=action==='save'?'PATCH SAVED':'PATCH LOADED';if(data.revision)render(data);}catch(e){$('error').textContent=e.message;}finally{setPending(false);refresh();}}
$('panic').addEventListener('click',()=>command({action:'panic'}));
$('connect').addEventListener('click',()=>{clearTimeout(reconnect);loadDescriptors();refresh();connectStream();});
$('save-patch').addEventListener('click',()=>patch('save'));$('load-patch').addEventListener('click',()=>patch('load'));
loadDescriptors();refresh();connectStream();setInterval(()=>{if(!pending&&(!ws||ws.readyState!==WebSocket.OPEN))refresh();},1000);
// Browser timers only refresh telemetry; they never schedule MIDI.
