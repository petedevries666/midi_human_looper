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
  if(s.chainMode)$('metrics').append(node('span',`Zynthian · two bars · ${s.chainBpm} BPM · ${s.chainError?'CLOCK / CAPACITY ERROR — stopped':s.chainRecording?'RECORDING':s.chainArmed?'WAITING FOR NEXT LOOP':s.chainRunning?'PLAYING':'STOPPED'}`));
  $('last-midi').textContent=`Last MIDI · sample ${s.lastEvent[0]} · status ${s.lastEvent[1]} · number ${s.lastEvent[2]} · value ${s.lastEvent[3]}`;
  for(const sw of s.switches){const el=document.querySelector(`[data-switch-id="${sw.id}"] .step`);if(el)el.textContent=`STEP ${sw.step} / ${sw.length}`;}
  renderControllers(s);
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
async function patch(action){if(pending)return;setPending(true);try{const data=await request(`/api/v1/patch/${action}`,{slot:Number($('patch-slot').value),expectedRevision:revision,expectedEngineSessionId:engineSession});$('patch-status').textContent=action==='save'?'PATCH SAVED':action==='export'?`EXPORTED ${data.file}`:'PATCH LOADED';if(data.revision)render(data);}catch(e){$('error').textContent=e.message;}finally{setPending(false);refresh();}}
$('panic').addEventListener('click',()=>command({action:'panic'}));
$('connect').addEventListener('click',()=>{clearTimeout(reconnect);loadDescriptors();refresh();connectStream();});
$('save-patch').addEventListener('click',()=>patch('save'));$('load-patch').addEventListener('click',()=>patch('load'));
loadDescriptors();refresh();connectStream();setInterval(()=>{if(!pending&&(!ws||ws.readyState!==WebSocket.OPEN))refresh();},1000);
// Browser timers only refresh telemetry; they never schedule MIDI.

function controllerConfiguration(s=latest){
  const wire=s?.controllerEngine?.configuration;if(!wire)return {sources:[],mappings:[]};
  const sources=[],mappings=[];
  for(let i=0;i<16;i++){const [id,kind,channel,number]=wire.slice(1+4*i,5+4*i);if(id)sources.push({id,kind,channel:channel+1,number});}
  const fields=['id','sourceId','targetId','instrumentId','moduleId','kind','base','priority','takeover','returnMode','easing','threshold','glideSeconds','slewPerSecond','idleSeconds','returnSeconds','enabled','pointCount'];
  for(let i=0;i<32;i++){const record=wire.slice(65+66*i,131+66*i);if(!record[0])continue;const m=Object.fromEntries(fields.map((key,j)=>[key,record[j]]));m.points=Array.from({length:m.pointCount},(_,j)=>record.slice(18+3*j,21+3*j));m.slot=i;mappings.push(m);}
  return {sources,mappings};
}
function freshId(used){let id;do{id=crypto.getRandomValues(new Uint32Array(1))[0]&0xffffff;}while(!id||used.includes(id));return id;}
function renderControllers(s){
  const {sources,mappings}=controllerConfiguration(s),learn=s.controllerLearn||{};
  $('controllers').replaceChildren(...sources.map(source=>{
    const card=node('article',undefined,'module');card.dataset.sourceId=source.id;
    card.append(node('h3',`SOURCE ${source.id}`),node('p',source.kind?`${source.kind===1?'NOTE':'CC'} ${source.number} · CH ${source.channel}`:'UNASSIGNED'));
    card.append(button('MIDI LEARN',()=>command({action:'controller_learn',sourceId:source.id})),button('FORGET',()=>command({action:'controller_forget',sourceId:source.id})));
    if(learn.target===source.id){card.append(node('p',learn.conflict<0?'Already assigned to a legacy phrase/switch/controller. CANCEL and choose another input.':learn.conflict>0?`Already assigned to SOURCE ${learn.conflict}. Reassign deliberately?`:'Waiting for MIDI note or CC…'),button('CANCEL LEARN',()=>command({action:'controller_cancel',sourceId:source.id})));if(learn.conflict>0)card.append(button('REASSIGN',()=>command({action:'controller_confirm',sourceId:source.id})));}
    return card;
  }));
  $('mappings').replaceChildren(...mappings.map(m=>{
    const runtime=s.controllerRuntime[m.slot],card=node('article',undefined,'module');card.dataset.mappingId=m.id;
    card.append(node('h3',`SOURCE ${m.sourceId} → ${m.kind>=14?'PHRASE':'I'}${m.instrumentId} / ${m.kind>=14?'DECAY':m.moduleId||'VOLUME'} / ${parameter(m.kind)?.label||m.kind}`),node('p',`${(runtime.effective*100).toFixed(1)}% · ${runtime.returning?'RETURNING':runtime.pickup?'PICKUP WAIT':runtime.owner?'CONTROLLED':'BASE'}`),button('EDIT',()=>editMapping(m)),button(m.enabled?'BYPASS':'ENABLE',()=>command({action:'mapping_commit',mapping:{...m,enabled:m.enabled?0:1}})),button('CAPTURE STATE',()=>command({action:'controller_capture',targetId:m.targetId})),button('RETURN',()=>command({action:'controller_return',targetId:m.targetId})),button('DELETE',()=>command({action:'mapping_delete',mappingId:m.id})));
    return card;
  }));
}
function curveEditor(points){
  const root=node('div'),canvas=node('canvas');canvas.width=400;canvas.height=120;canvas.className='curve-preview';root.append(canvas);
  const controls=node('div');root.append(controls);
  function draw(){const c=canvas.getContext('2d');c.clearRect(0,0,400,120);c.strokeStyle='#ddd';c.beginPath();for(let pixel=0;pixel<=400;pixel++){const x=pixel/400;let y=points[points.length-1][1];for(let i=1;i<points.length;i++)if(x<=points[i][0]){const a=points[i-1],b=points[i];let t=(x-a[0])/(b[0]-a[0]),power=1+5*Math.abs(a[2]);t=a[2]>0?Math.pow(t,power):a[2]<0?1-Math.pow(1-t,power):t;y=a[1]+(b[1]-a[1])*t;break;}const sy=120*(1-y);if(pixel)c.lineTo(pixel,sy);else c.moveTo(pixel,sy);}c.stroke();}
  function rows(){controls.replaceChildren();points.forEach((p,index)=>{const row=node('div',undefined,'curve-point');['X','Y','BEND'].forEach((name,k)=>{const label=node('label',name),input=node('input');input.type='number';input.min=k===2?-.98:0;input.max=k===2?.98:1;input.step=.01;input.value=p[k];input.disabled=k===0&&(index===0||index===points.length-1);input.setAttribute('aria-label',`${name} point ${index+1}`);input.addEventListener('input',()=>{p[k]=Number(input.value);draw();});label.append(input);row.append(label);});if(index&&index<points.length-1)row.append(button('REMOVE POINT',()=>{points.splice(index,1);rows();draw();}));controls.append(row);});draw();}
  root.append(button('ADD POINT',()=>{if(points.length>=16)return;let at=1;for(let i=2;i<points.length;i++)if(points[i][0]-points[i-1][0]>points[at][0]-points[at-1][0])at=i;points.splice(at,0,[(points[at-1][0]+points[at][0])/2,(points[at-1][1]+points[at][1])/2,0]);rows();}));rows();return root;
}
function editMapping(existing){
  if(!catalog||!latest||$('editor').open)return;
  const {sources,mappings}=controllerConfiguration();if(!sources.length){$('error').textContent='Add a controller source first.';return;}
  const draft=structuredClone(existing||{id:freshId(mappings.map(m=>m.id)),sourceId:sources[0].id,enabled:1,points:[[0,0,0],[1,1,0]]});
  const capturedRevision=revision,capturedSession=engineSession,dialog=$('editor'),content=$('editor-content');let committing=false;
  const dismiss=()=>{if(!committing)dialog.close();};content.replaceChildren(node('h2','CONTROLLER MAPPING'),button('×',dismiss));
  const source=node('select');source.setAttribute('aria-label','Controller source');for(const s of sources){const o=node('option',`SOURCE ${s.id}`);o.value=s.id;source.append(o);}source.value=draft.sourceId;content.append(source);
  const target=node('select');target.setAttribute('aria-label','Controller target');
  const targets=[];for(const p of latest.phrases)for(const kind of [14,15])targets.push({instrumentId:p.id,moduleId:0,kind,label:`PHRASE ${p.id} / ${parameter(kind).label}`});for(const i of latest.instruments){targets.push({instrumentId:i.id,moduleId:0,kind:1,label:`I${i.id} VOLUME`});for(const tf of i.transformers)for(const p of tf.parameters)if(!p.assignment && parameter(p.kind)?.assignmentEligible)targets.push({instrumentId:i.id,moduleId:tf.id,kind:p.kind,label:`I${i.id} / ${tf.id} / ${parameter(p.kind).label}`});}
  targets.forEach((t,j)=>{const o=node('option',t.label);o.value=j;target.append(o);});let selection=targets.findIndex(t=>t.instrumentId===draft.instrumentId&&t.moduleId===draft.moduleId&&t.kind===draft.kind);target.value=selection<0?targets.findIndex(t=>t.kind===1):selection;content.append(target);
  const descriptor=descriptorForMapping();for(const id of descriptor.parameters){const p=catalog.parameters.find(p=>p.id===id),label=node('label',p.label,'parameter'),input=node('input');input.type='number';input.min=p.min;input.max=p.max;input.step=p.step;input.value=draft[p.policyField]??p.default;draft[p.policyField]=Number(input.value);input.addEventListener('input',()=>draft[p.policyField]=Number(input.value));label.append(input,node('span',p.unit));content.append(label);}
  content.append(node('p','TAKEOVER: 0 DIRECT · 1 PICKUP · 2 GLIDE · 3 SLEW. BACK TO STATE: 0 OFF · 1 IDLE · 2 RELEASE · 3 COMMAND. EASING: 0 LINEAR · 1 SMOOTH.'),curveEditor(draft.points));
  const error=node('p','');error.setAttribute('role','alert');content.append(error);
  const done=button('DONE',async()=>{if(committing)return;const t=targets[Number(target.value)];if(!t){error.textContent='No eligible target';return;}Object.assign(draft,t);delete draft.label;draft.sourceId=Number(source.value);const same=mappings.find(m=>m.instrumentId===t.instrumentId&&m.moduleId===t.moduleId&&m.kind===t.kind);draft.targetId=same?.targetId||freshId(mappings.map(m=>m.targetId));
    committing=true;done.disabled=cancel.disabled=true;
    try{render(await request('/api/v1/command',{protocolVersion:1,expectedRevision:capturedRevision,expectedEngineSessionId:capturedSession,action:'mapping_commit',mapping:draft}));dialog.close();}catch(e){error.textContent=e.message;}finally{committing=false;done.disabled=cancel.disabled=false;}});
  const cancel=button('CANCEL',dismiss);content.append(done,cancel);dialog.oncancel=e=>{e.preventDefault();dismiss();};dialog.onclick=e=>{const r=dialog.getBoundingClientRect();if(e.target===dialog&&(e.clientX<r.left||e.clientX>r.right||e.clientY<r.top||e.clientY>r.bottom))dismiss();};dialog.showModal();
}
function descriptorForMapping(){return catalog.modules.find(m=>m.typeId==='controller_mapping');}
$('add-controller').addEventListener('click',()=>{const {sources}=controllerConfiguration();command({action:'controller_source',sourceId:freshId(sources.map(s=>s.id))});});
$('add-mapping').addEventListener('click',()=>editMapping());

$('export-patch').addEventListener('click',()=>patch('export'));
