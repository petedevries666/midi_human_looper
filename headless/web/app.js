'use strict';
let revision=1, engineSession=null, pending=false, renderedModel='', latest=null;
let catalog=null, ws=null, reconnect=null, renderedSnapshots='', renderedSnapshotSession=null;
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
async function editSnapshot(record){
  const dialog=$('editor'),content=$('editor-content');if(dialog.open)return;
  try{record=await request(`/api/v1/snapshot/${record.id}`);}catch(e){$('error').textContent=e.message;return;}
  if(dialog.open)return;
  const capturedRevision=record.revision,capturedSession=record.engineSessionId;
  let committing=false;
  content.replaceChildren(node('h2',`SNAPSHOT · ${record.id}`));
  const dismiss=()=>{if(!committing)dialog.close();};content.append(button('×',dismiss));
  const field=(label,input)=>{const row=node('label',label,'parameter');row.append(input);content.append(row);return input;};
  const name=field('NAME',node('input'));name.value=record.name;name.maxLength=48;name.setAttribute('aria-label','Snapshot name');
  const seconds=field('MORPH SECONDS',node('input'));seconds.type='number';seconds.min=0;seconds.max=30;seconds.step=.1;seconds.value=record.seconds;seconds.setAttribute('aria-label','Morph seconds');
  const choices=(label,values,current)=>{const select=node('select');select.setAttribute('aria-label',label);for(const [value,text] of values){const option=node('option',text);option.value=value;select.append(option);}select.value=current;return field(label,select);};
  const ease=choices('CURVE',[[0,'LINEAR'],[1,'SMOOTH']],record.ease);
  const switching=choices('DISCRETE SWITCH',[[1,'AT START'],[2,'AT MIDPOINT'],[3,'AT END']],record.switching);
  content.append(node('small',`${record.parameterCount} captured targets. UPDATE recaptures current effective values.`));
  const inclusion=node('details');inclusion.append(node('summary','INCLUDED PARAMETERS'));
  for(const p of record.parameters||[]){
    const label=node('label',`${[14,15,17,18,19,20].includes(p.kind)?'PHRASE':'INSTRUMENT'} ${p.instrumentId}${p.moduleId?` · MODULE ${p.moduleId}`:''} · ${parameter(p.kind)?.label||p.kind} = ${p.value}${p.expression?' · LEGACY EXPRESSION':''}`,'snapshot-inclusion');
    const checkbox=node('input');checkbox.type='checkbox';checkbox.checked=p.included;checkbox.setAttribute('aria-label',`Include ${p.instrumentId}:${p.moduleId}:${p.kind}`);checkbox.onchange=()=>p.included=checkbox.checked;label.prepend(checkbox);inclusion.append(label);
  }
  content.append(inclusion);
  const error=node('p','');error.setAttribute('role','alert');content.append(error);
  const done=button('DONE',async()=>{
    if(committing)return;
    if(engineSession!==capturedSession){error.textContent='Engine restarted. CANCEL and reopen this editor.';return;}
    committing=true;done.disabled=cancel.disabled=true;
    try{const state=await request('/api/v1/command',{protocolVersion:1,expectedRevision:capturedRevision,expectedEngineSessionId:capturedSession,action:'snapshot_commit',snapshotId:record.id,name:name.value,seconds:Number(seconds.value),ease:Number(ease.value),switching:Number(switching.value),inclusions:(record.parameters||[]).map(p=>({instrumentId:p.instrumentId,moduleId:p.moduleId,kind:p.kind,included:p.included}))});dialog.close();renderedSnapshots='';render(state);}
    catch(e){error.textContent=e.message==='conflict'?'Configuration changed. CANCEL and reopen this editor.':e.message;}
    finally{committing=false;done.disabled=cancel.disabled=false;}
  });
  const cancel=button('CANCEL',dismiss);content.append(done,cancel);
  dialog.oncancel=e=>{if(committing)e.preventDefault();};
  dialog.onclick=e=>{const r=dialog.getBoundingClientRect();if(e.target===dialog&&(e.clientX<r.left||e.clientX>r.right||e.clientY<r.top||e.clientY>r.bottom))dismiss();};
  dialog.showModal();
}
function editSwitchSnapshots(sw){
  const dialog=$('editor'),content=$('editor-content');if(dialog.open)return;
  const capturedRevision=revision,capturedSession=engineSession;
  let committing=false;
  content.replaceChildren(node('h2',`${sw.name||'SMART SWITCH'} · SNAPSHOTS`));
  const dismiss=()=>{if(!committing)dialog.close();};content.append(button('×',dismiss));
  const field=(label,input)=>{const row=node('label',label,'parameter');row.append(input);content.append(row);return input;};
  const gesture=field('GESTURE',node('select'));gesture.setAttribute('aria-label','Switch gesture');
  ['TAP','DOUBLE','HOLD'].forEach((text,id)=>{const option=node('option',text);option.value=id;gesture.append(option);});
  const action=field('ACTION',node('select'));action.setAttribute('aria-label','Snapshot action');
  ['EXISTING SWITCH ACTION','SNAPSHOT NEXT','SNAPSHOT PREVIOUS','SNAPSHOT RECALL','SNAPSHOT MORPH','SNAPSHOT CYCLE','MORPH TO NEXT','MORPH TO PREVIOUS'].forEach((text,id)=>{const option=node('option',text);option.value=id;action.append(option);});
  const target=field('SNAPSHOT',node('select'));target.setAttribute('aria-label','Target snapshot');
  for(const r of latest.snapshots||[]){const option=node('option',r.name);option.value=r.id;target.append(option);}
  const load=()=>{const a=(latest.snapshotActions||[]).find(a=>a.switchId===sw.id&&a.gesture===Number(gesture.value));action.value=a?.action||0;if(a?.snapshotId)target.value=a.snapshotId;target.disabled=!['3','4'].includes(action.value);};
  gesture.onchange=load;action.onchange=()=>target.disabled=!['3','4'].includes(action.value);load();
  content.append(node('small','Navigation wraps in snapshot order. Morph uses the destination snapshot duration and curve. Existing MIDI assignment and gesture detection are preserved.'));
  const error=node('p','');error.setAttribute('role','alert');content.append(error);
  const done=button('DONE',async()=>{
    if(committing)return;if(engineSession!==capturedSession){error.textContent='Engine restarted. CANCEL and reopen.';return;}
    committing=true;done.disabled=cancel.disabled=true;
    try{const state=await request('/api/v1/command',{protocolVersion:1,expectedRevision:capturedRevision,expectedEngineSessionId:capturedSession,action:'snapshot_switch',switchId:sw.id,gesture:Number(gesture.value),snapshotAction:Number(action.value),snapshotId:['3','4'].includes(action.value)?Number(target.value):0});dialog.close();renderedModel='';render(state);}
    catch(e){error.textContent=e.message==='conflict'?'Configuration changed. CANCEL and reopen.':e.message;}
    finally{committing=false;done.disabled=cancel.disabled=false;}
  });
  const cancel=button('CANCEL',dismiss);content.append(done,cancel);
  dialog.oncancel=e=>{if(committing)e.preventDefault();};dialog.onclick=e=>{const r=dialog.getBoundingClientRect();if(e.target===dialog&&(e.clientX<r.left||e.clientX>r.right||e.clientY<r.top||e.clientY>r.bottom))dismiss();};dialog.showModal();
}
let renderedAB='',abDesired=null,abSendTimer=null;
function queueAB(position){
  abDesired={position,revision,session:engineSession,a:latest.snapshotAB?.a,b:latest.snapshotAB?.b};
  const send=async()=>{if(pending){abSendTimer=setTimeout(send,50);return;}const value=abDesired;abDesired=null;if(value.session!==engineSession||value.a!==latest.snapshotAB?.a||value.b!==latest.snapshotAB?.b)return;await command({action:'snapshot_ab_position',position:value.position,a:value.a,b:value.b,expectedRevision:value.revision,expectedEngineSessionId:value.session});if(abDesired!==null)abSendTimer=setTimeout(send,50);};
  clearTimeout(abSendTimer);abSendTimer=setTimeout(send,40);
}
async function learnAB(){
  let {sources,mappings}=controllerConfiguration();let mapping=mappings.find(m=>m.kind===16&&m.enabled);
  if(!mapping){
    const sourceId=freshId(sources.map(v=>v.id));
    if(!await command({action:'controller_source',sourceId,kind:0}))return;
    ({sources,mappings}=controllerConfiguration());
    mapping={id:freshId(mappings.map(v=>v.id)),sourceId,targetId:freshId(mappings.map(v=>v.targetId)),instrumentId:1,moduleId:0,kind:16,priority:0,takeover:2,returnMode:0,threshold:.02,glideSeconds:.2,slewPerSecond:1,idleSeconds:1,returnSeconds:.5,easing:0,enabled:1,points:[[0,0,0],[1,1,0]]};
    if(!await command({action:'mapping_commit',mapping}))return;
  }
  await command({action:'controller_learn',sourceId:mapping.sourceId});
}
function editAB(){
  const dialog=$('editor'),content=$('editor-content');if(dialog.open)return;
  const capturedRevision=revision,capturedSession=engineSession;let committing=false;
  content.replaceChildren(node('h2','SNAPSHOT A/B'));const dismiss=()=>{if(!committing)dialog.close();};content.append(button('×',dismiss));
  const choice=(label,current,values)=>{const row=node('label',label,'parameter'),select=node('select');select.setAttribute('aria-label',label);for(const [id,text] of values){const option=node('option',text);option.value=id;select.append(option);}select.value=current;row.append(select);content.append(row);return select;};
  const options=latest.snapshots.map(r=>[r.id,r.name]);
  const a=choice('SNAPSHOT A',latest.snapshotAB?.a||options[0][0],options),b=choice('SNAPSHOT B',latest.snapshotAB?.b||options[1][0],options),ease=choice('A/B CURVE',latest.snapshotAB?.ease||0,[[0,'LINEAR'],[1,'SMOOTH']]);
  content.append(node('small','Use shared included targets. Individual controller takeovers remain overridden until A/B is configured again. MIDI Learn uses the existing Controller Engine.'));
  const error=node('p','');error.setAttribute('role','alert');content.append(error);
  const done=button('DONE',async()=>{if(committing)return;committing=true;done.disabled=cancel.disabled=true;
    try{const state=await request('/api/v1/command',{protocolVersion:1,expectedRevision:capturedRevision,expectedEngineSessionId:capturedSession,action:'snapshot_ab_configure',a:Number(a.value),b:Number(b.value),ease:Number(ease.value),position:latest.snapshotAB?.position||0});dialog.close();renderedAB='';render(state);}catch(e){error.textContent=e.message;}finally{committing=false;done.disabled=cancel.disabled=false;}
  });const cancel=button('CANCEL',dismiss);content.append(done,cancel);dialog.oncancel=e=>{if(committing)e.preventDefault();};dialog.onclick=e=>{const r=dialog.getBoundingClientRect();if(e.target===dialog&&(e.clientX<r.left||e.clientX>r.right||e.clientY<r.top||e.clientY>r.bottom))dismiss();};dialog.showModal();
}
function renderAB(s){
  const macro=s.snapshotAB||{},key=JSON.stringify([s.engineSessionId,(s.snapshots||[]).map(r=>[r.id,r.name]),macro.a,macro.b,macro.ease]);
  if(key!==renderedAB){const open=$('snapshot-ab').querySelector('details')?.open;renderedAB=key;$('snapshot-ab').replaceChildren();
    if((s.snapshots||[]).length>=2){const details=node('details');details.open=!!open;details.append(node('summary','MANUAL A/B MORPH'));const row=node('div',undefined,'snapshot-row');row.append(button('CONFIGURE A/B',editAB));
      if(macro.a&&macro.b){const slider=node('input');slider.id='ab-position';slider.type='range';slider.min=0;slider.max=1;slider.step=.001;slider.value=macro.position;slider.setAttribute('aria-label','Snapshot A/B position');slider.oninput=()=>queueAB(Number(slider.value));row.append(slider,button('MIDI LEARN',learnAB));}
      details.append(row,node('small','','ab-feedback'));$('snapshot-ab').append(details);
    }
  }
  const slider=$('ab-position');if(slider&&document.activeElement!==slider&&abDesired===null)slider.value=macro.position||0;
  const feedback=document.querySelector('.ab-feedback');if(feedback){const {sources,mappings}=controllerConfiguration(s),mapping=mappings.find(m=>m.kind===16&&m.enabled),source=sources.find(v=>v.id===mapping?.sourceId),learn=s.controllerLearn||{};feedback.replaceChildren(node('span',`${Math.round((macro.position||0)*100)}% · ${macro.skipped||0} skipped · ${macro.overridden||0} overridden${source?.kind?` · ${source.kind===2?'CC':'NOTE'} ${source.number} CH ${source.channel+1}`:''}`));
    if(mapping&&learn.target===mapping.sourceId){feedback.append(node('span',learn.conflict<0?' · Assigned to a legacy controller: cancel and choose another input.':learn.conflict>0?' · Already assigned: deliberate reassignment required.':' · Waiting for MIDI…'),button('CANCEL LEARN',()=>command({action:'controller_cancel',sourceId:mapping.sourceId})));if(learn.conflict>0)feedback.append(button('REASSIGN',()=>command({action:'controller_confirm',sourceId:mapping.sourceId})));}
  }
}
function render(s){
  if(engineSession===s.engineSessionId&&s.revision<revision)return;
  engineSession=s.engineSessionId;revision=s.revision;latest=s;
  $('connection').textContent='CONNECTED · Engine running';
  $('metrics').replaceChildren(...[`Backend ${s.backend} · ${s.sampleRate} Hz / ${s.blockSize}`,`Sample clock ${s.sampleClock}`,`MIDI messages ${s.midiCount}`,`Active notes ${s.activeNotes}`,`Maximum callback ${s.maxCallbackUs.toFixed(1)} µs`,`Late blocks ${s.lateBlocks}`,`Output overflow ${s.outputOverflow}`].map(v=>node('span',v)));
  if(s.chainMode)$('metrics').append(node('span',`Zynthian · two bars · ${s.chainBpm} BPM · ${s.chainError?'CLOCK / CAPACITY ERROR — stopped':s.chainRecording?'RECORDING':s.chainArmed?'WAITING FOR NEXT LOOP':s.chainRunning?'PLAYING':'STOPPED'}`));
  $('last-midi').textContent=`Last MIDI · sample ${s.lastEvent[0]} · status ${s.lastEvent[1]} · number ${s.lastEvent[2]} · value ${s.lastEvent[3]}`;
  for(const sw of s.switches){const el=document.querySelector(`[data-switch-id="${sw.id}"] .step`);if(el)el.textContent=`STEP ${sw.step} / ${sw.length}`;}
  $('capture-snapshot').onclick=()=>command({action:'snapshot_capture'});
  const snapshotKey=JSON.stringify([s.engineSessionId,(s.snapshots||[]).map(r=>[r.id,r.name,r.seconds,r.ease,r.switching])]);
  if(renderedSnapshotSession!==s.engineSessionId || (snapshotKey!==renderedSnapshots && !document.activeElement?.hasAttribute('data-snapshot-name') && !document.querySelector('.snapshot-actions[open]'))) {
  renderedSnapshots=snapshotKey;renderedSnapshotSession=s.engineSessionId;
  const snapshotSession=s.engineSessionId;
  $('snapshots').replaceChildren(...(s.snapshots||[]).map((r,index)=>{
    const row=node('div',undefined,'snapshot-row');row.dataset.snapshotId=r.id;const name=node('input');name.value=r.name;name.maxLength=48;name.setAttribute('data-snapshot-name','');name.setAttribute('aria-label','Snapshot name');name.onchange=()=>{if(snapshotSession!==engineSession){$('error').textContent='Engine restarted; reopen the snapshot controls.';return;}if(name.value!==r.name)command({action:'snapshot_rename',snapshotId:r.id,name:name.value});};row.append(name,node('small','','snapshot-feedback'));
    const more=node('details');more.className='snapshot-actions';more.append(node('summary','•••'));const menu=node('div',undefined,'snapshot-menu');more.append(menu);
    for(const [label,action] of [['RECALL','snapshot_recall'],['MORPH','snapshot_morph'],['UPDATE','snapshot_update'],['DUPLICATE','snapshot_duplicate'],['↑','snapshot_move'],['↓','snapshot_move'],['DELETE','snapshot_delete']]) {
      const control=button(label,()=>{if(snapshotSession!==engineSession){$('error').textContent='Engine restarted; reopen the snapshot controls.';return;}if(action==='snapshot_delete'&&!confirm('Delete this snapshot?'))return;more.open=false;command({action,snapshotId:r.id,direction:label==='↓'?'down':'up'});});
      control.disabled=(label==='↑'&&index===0)||(label==='↓'&&index===(s.snapshots||[]).length-1);
      (['RECALL','MORPH','UPDATE'].includes(label)?row:menu).append(control);
    }
    menu.prepend(button('EDIT',()=>{more.open=false;const current=latest?.snapshots?.find(v=>v.id===r.id);if(current&&snapshotSession===engineSession)editSnapshot(current);}));
    row.append(more);
    return row;
  }));
  }
  for(const r of s.snapshots||[]) {
    const feedback=document.querySelector(`[data-snapshot-id="${r.id}"] .snapshot-feedback`);
    if(feedback)feedback.textContent=`${r.id===s.selectedSnapshotId?'SELECTED · ':''}${r.dirty?'MODIFIED':''}${r.id===s.selectedSnapshotId&&s.snapshotSkippedTargets?` · PARTIAL (${s.snapshotSkippedTargets} missing)`:''}${r.id===s.targetSnapshotId?` · MORPH ${Math.round(s.morphProgress*100)}%`:''}`;
  }
  renderAB(s);
  renderControllers(s);
  const model=JSON.stringify([s.controllerLearn,s.phrases,s.instruments,s.switches.map(v=>({...v,step:0})),s.snapshotActions]);if(model===renderedModel)return;renderedModel=model;
  compactPhrases(s);
  $('instruments').replaceChildren(...s.instruments.map(compactInstrument));
  $('switches').replaceChildren(...s.switches.map(sw=>{
    const n=node('article',undefined,'switch');n.dataset.switchId=sw.id;n.append(node('strong',sw.name||`SWITCH ${sw.id}`),node('small',`${sw.kind===1?'NOTE':sw.kind===2?'CC':'UNASSIGNED'} ${sw.number} · CH ${sw.channel}`),node('small',`STEP ${sw.step} / ${sw.length}`,'step'),button('OPTIONS',()=>editSwitchSnapshots(sw)));
    const tests=node('div',undefined,'tests');for(const gesture of ['tap','double','hold']){const b=button(`TEST ${gesture.toUpperCase()}`,()=>command({action:'test',switchId:sw.id,gesture}));b.dataset.valid=sw.enabled?'1':'0';b.disabled=!sw.enabled;tests.append(b);}
    const hardware=button('SIMULATE FOOTSWITCH',async()=>{if(await command({action:'midi',channel:sw.channel,note:sw.number,value:100}))await command({action:'midi',channel:sw.channel,note:sw.number,value:0});});hardware.className='hardware';hardware.dataset.valid=sw.kind===1?'1':'0';hardware.disabled=sw.kind!==1;n.append(tests,hardware);return n;
  }));
}
async function refresh(){try{render(await request('/api/v1/state'));}catch(e){$('connection').textContent='DISCONNECTED · Engine continues independently';$('error').textContent=e.message;}}
function setPending(value){pending=value;for(const b of document.querySelectorAll('main button')){if(value){b.dataset.pendingDisabled=b.disabled?'1':'0';b.disabled=true;}else if(b.dataset.pendingDisabled!==undefined){b.disabled=b.dataset.pendingDisabled==='1';delete b.dataset.pendingDisabled;}}}
async function command(value){if(pending)return false;setPending(true);try{render(await request('/api/v1/command',{protocolVersion:1,expectedRevision:revision,expectedEngineSessionId:engineSession,...value}));$('error').textContent='';return true;}catch(e){$('error').textContent=value.action?.startsWith('snapshot_')&&e.message==='unknown_target'?'Recall was not applied: a target is missing or has a legacy expression assignment.':e.message;await refresh();return false;}finally{setPending(false);}}
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
    if(learn.domain!=='phrase'&&learn.target===source.id){card.append(node('p',learn.conflict<0?'Already assigned to a legacy phrase/switch/controller. CANCEL and choose another input.':learn.conflict>0?`Already assigned to SOURCE ${learn.conflict}. Reassign deliberately?`:'Waiting for MIDI note or CC…'),button('CANCEL LEARN',()=>command({action:'controller_cancel',sourceId:source.id})));if(learn.conflict>0)card.append(button('REASSIGN',()=>command({action:'controller_confirm',sourceId:source.id})));}
    return card;
  }));
  $('mappings').replaceChildren(...mappings.map(m=>{
    const runtime=s.controllerRuntime[m.slot],card=node('article',undefined,'module');card.dataset.mappingId=m.id;
    card.append(node('h3',`SOURCE ${m.sourceId} → ${m.kind===16?'GLOBAL':[14,15,17,18,19,20].includes(m.kind)?'PHRASE':'I'}${m.instrumentId} / ${m.moduleId||parameter(m.kind)?.label||'PARAMETER'} / ${parameter(m.kind)?.label||m.kind}`),node('p',`${(runtime.effective*100).toFixed(1)}% · ${runtime.returning?'RETURNING':runtime.pickup?'PICKUP WAIT':runtime.owner?'CONTROLLED':'BASE'}`),button('EDIT',()=>editMapping(m)),button(m.enabled?'BYPASS':'ENABLE',()=>command({action:'mapping_commit',mapping:{...m,enabled:m.enabled?0:1}})),button('CAPTURE STATE',()=>command({action:'controller_capture',targetId:m.targetId})),button('RETURN',()=>command({action:'controller_return',targetId:m.targetId})),button('DELETE',()=>command({action:'mapping_delete',mappingId:m.id})));
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
  const targets=[{instrumentId:1,moduleId:0,kind:16,label:'GLOBAL SNAPSHOT A/B'}];for(const p of latest.phrases)for(const kind of [14,15,17,18,19,20])targets.push({instrumentId:p.id,moduleId:0,kind,label:`PHRASE ${p.id} / ${parameter(kind).label}`});for(const i of latest.instruments){for(const kind of [1,21,22,23])targets.push({instrumentId:i.id,moduleId:0,kind,label:`I${i.id} / ${parameter(kind).label}`});for(const tf of i.transformers){targets.push({instrumentId:i.id,moduleId:tf.id,kind:24,label:`I${i.id} / ${tf.id} ON/OFF`});for(const p of tf.parameters)if(!p.assignment && parameter(p.kind)?.assignmentEligible)targets.push({instrumentId:i.id,moduleId:tf.id,kind:p.kind,label:`I${i.id} / ${tf.id} / ${parameter(p.kind).label}`});}}
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

document.addEventListener('click',event=>{for(const menu of document.querySelectorAll('.snapshot-actions[open]'))if(!menu.contains(event.target))menu.open=false;});
document.addEventListener('keydown',event=>{if(event.key==='Escape')for(const menu of document.querySelectorAll('.snapshot-actions[open]'))menu.open=false;});
function phraseOptions(phraseId){
  const dialog=$('editor'),content=$('editor-content');if(dialog.open)return;
  let committing=false;
  const dismiss=()=>{if(!committing)dialog.close();};
  content.replaceChildren(node('h2',`PHRASE ${phraseId} · MIDI`),button('×',dismiss));
  const error=node('p','');error.setAttribute('role','alert');
  const file=node('input');file.type='file';file.accept='.mid,.midi,audio/midi';file.setAttribute('aria-label','MIDI file');
  content.append(button('IMPORT MIDI',()=>file.click()),file,button('EXPORT MIDI',async()=>{
    try{
      const response=await fetch(`/api/v1/phrase/${phraseId}/midi`,{headers:headers()});
      if(!response.ok)throw new Error((await response.json()).error);
      const url=URL.createObjectURL(await response.blob()),link=node('a');link.href=url;link.download=`mbmf-phrase-${String(phraseId).padStart(2,'0')}.mid`;link.click();setTimeout(()=>URL.revokeObjectURL(url),1000);
    }catch(e){error.textContent=e.message;}
  }));
  const preview=node('div');content.append(preview,error,button('CANCEL',dismiss));
  file.onchange=async()=>{
    preview.replaceChildren();error.textContent='';
    try{
      if(!file.files[0]||file.files[0].size>1048576)throw new Error('MIDI file limit: 1 MiB');
      const bytes=new Uint8Array(await file.files[0].arrayBuffer());let binary='';for(const b of bytes)binary+=String.fromCharCode(b);
      const encoded=btoa(binary),capturedRevision=revision,capturedSession=engineSession;
      const body={phraseId,file:encoded,mode:'preview'};
      const info=await request('/api/v1/phrase/midi',body);
      const initialTempo=info.tempos.filter(t=>t[0]===0).at(-1)?.[1]||120,meter=info.meters[0];
      preview.append(node('p',`${info.noteCount} notes · ${info.tracks} tracks · ${info.lengthSeconds.toFixed(3)} s`),node('small',`Initial ${initialTempo.toFixed(2)} BPM · ${meter?`${meter[1]}/${meter[2]}`:'4/4 (default)'}`),node('p',info.tempoPolicy),node('p','Replace stored source notes. Stop this processor first. Other processors are independent.'));
      const replace=button('REPLACE PHRASE',async()=>{
        committing=true;replace.disabled=true;
        try{await request('/api/v1/phrase/midi',{...body,mode:'replace',expectedRevision:capturedRevision,expectedEngineSessionId:capturedSession});dialog.close();await refresh();}
        catch(e){error.textContent=e.message;}finally{committing=false;replace.disabled=false;}
      });preview.append(replace);
    }catch(e){error.textContent=e.message;}
  };
  dialog.oncancel=e=>{if(committing)e.preventDefault();};dialog.onclick=e=>{const r=dialog.getBoundingClientRect();if(e.target===dialog&&(e.clientX<r.left||e.clientX>r.right||e.clientY<r.top||e.clientY>r.bottom))dismiss();};dialog.showModal();
}
let phrasePage=0;
function liveParameter(targetId,kind,value,moduleId=0){return command({action:'parameter_set',targetId,moduleId,kind,value});}
function inlineNumber(label,value,min,max,step,onchange){
  const wrap=node('label',label,'inline-control'),input=node('input');input.type='number';input.min=min;input.max=max;input.step=step;input.value=value;input.setAttribute('aria-label',label);input.onchange=()=>onchange(Number(input.value));wrap.append(input);return wrap;
}
function compactPhrases(s){
  const pages=Math.ceil(s.phrases.length/6);phrasePage=Math.min(phrasePage,pages-1);
  $('phrase-pagination').replaceChildren(button('←',()=>{phrasePage=Math.max(0,phrasePage-1);renderedModel='';render(latest);}),node('span',`${phrasePage+1} / ${pages}`),button('→',()=>{phrasePage=Math.min(pages-1,phrasePage+1);renderedModel='';render(latest);}));
  $('phrases').replaceChildren(...s.phrases.slice(phrasePage*6,phrasePage*6+6).map(p=>{
    const row=node('div',undefined,'phrase');row.dataset.phraseId=p.id;
    row.append(button('REC / OVERDUB',()=>command({action:'phrase_record',phraseId:p.id})),button('TRIGGER',()=>command({action:'phrase_play',phraseId:p.id})),node('strong',`PHRASE ${p.id}`));
    const learning=s.controllerLearn?.domain==='phrase'&&s.controllerLearn.target===p.id;
    const learn=button(learning?'CANCEL LEARN':p.triggerNote>=0?`LEARN · CH${p.triggerChannel||'ANY'} N${p.triggerNote}`:'TRIGGER LEARN',()=>command({action:learning?'phrase_learn_cancel':'phrase_learn',phraseId:p.id}));
    learn.title=p.triggerNote>=0?`NOTE ${p.triggerNote} · CH ${p.triggerChannel||'ANY'}`:'Unassigned phrase trigger';row.append(learn);
    if(learning&&s.controllerLearn.conflict){row.append(node('small',s.controllerLearn.conflict<0?'Already assigned to a phrase/switch. Cancel or choose a different note.':'Already assigned to a Controller source.'));
      if(s.controllerLearn.conflict>0)row.append(button('REASSIGN',()=>command({action:'phrase_learn_confirm',phraseId:p.id})));}
    row.append(button(p.solo?'SOLO ON':'SOLO',()=>liveParameter(p.id,19,p.solo?0:1)),button(p.mute?'MUTE ON':'MUTE',()=>liveParameter(p.id,18,p.mute?0:1)));
    const mode=node('select');mode.setAttribute('aria-label',`Play mode Phrase ${p.id}`);
    for(const [value,label] of [[1,'ONCE'],[0,'LOOP'],[2,'HOLD']]){const option=node('option',label);option.value=value;mode.append(option);}mode.value=p.mode;mode.disabled=!!s.chainMode;mode.title=s.chainMode?'Native chain prototype uses synchronized two-bar LOOP playback':'';mode.onchange=()=>liveParameter(p.id,20,Number(mode.value));row.append(mode);
    row.append(inlineNumber('BASE VEL',p.baseVelocity,.2,3,.01,value=>liveParameter(p.id,17,value)));
    if(p.mode===1)row.append(inlineNumber('VEL DECAY',p.velocityDecay,.2,1,.01,value=>liveParameter(p.id,15,value)),inlineNumber('TIME DECAY',p.timeDecay,.5,2,.01,value=>liveParameter(p.id,14,value)));
    const finish=button('FINISH REC',()=>command({action:'phrase_finish',phraseId:p.id}));finish.title='Finish record / overdub without discarding the take';row.append(finish,node('small',`${p.events} events`),button('PHRASE OPTIONS',()=>phraseOptions(p.id)));
    return row;
  }));
}
function compactInstrument(i){
  const n=node('article',undefined,'instrument');n.dataset.instrumentId=i.id;
  const main=node('div',undefined,'instrument-main');
  main.append(button(i.enabled?'ON':'OFF',()=>liveParameter(i.id,21,i.enabled?0:1)),node('strong',`${i.name||'INSTRUMENT'} · ${i.id}`));
  for(const [label,kind,current,zero] of [['MIDI IN',22,i.input,'ALL'],['MIDI OUT',23,i.output,'ORIGINAL']]){
    const wrap=node('label',label,'inline-control'),select=node('select');select.setAttribute('aria-label',`${label} Instrument ${i.id}`);
    for(let channel=0;channel<=16;channel++){const option=node('option',channel?String(channel):zero);option.value=channel;select.append(option);}select.value=current;select.onchange=()=>liveParameter(i.id,kind,Number(select.value));wrap.append(select);main.append(wrap);
  }
  main.append(inlineNumber('VOLUME',i.level,0,127,1,value=>liveParameter(i.id,1,value)),button('×',()=>{if(confirm(`Delete Instrument ${i.id} and its complete Transformer chain?`))command({action:'instrument_delete',instrumentId:i.id});}));n.append(main);
  const chain=node('div',undefined,'transformers');
  for(const tf of i.transformers||[]){
    const card=node('article',undefined,'module');card.dataset.moduleId=tf.id;
    card.append(node('strong',`${descriptor(tf.type)?.label||'MODULE'} · ${tf.id}`),node('small',tf.enabled?'ON':'BYPASS'),button('EDIT',()=>editModule(i,tf)));
    for(const [label,operation] of [['BYPASS','bypass'],['↑','up'],['↓','down'],['DELETE','delete']]){
      if(operation==='up'||operation==='down'){
        const index=i.transformers.indexOf(tf),other=i.transformers[index+(operation==='up'?-1:1)];
        if(!i.serialPitchOrder||![1,2].includes(tf.type)||!other||![1,2].includes(other.type))continue;
      }
      card.append(button(label,()=>{if(operation==='delete'&&!confirm('Delete this Transformer?'))return;command({action:'module_structure',instrumentId:i.id,moduleId:tf.id,operation});}));
    }chain.append(card);
  }
  const select=node('select');select.setAttribute('aria-label',`Transformer type for Instrument ${i.id}`);
  for(const d of catalog?.modules.filter(m=>m.engineType>0&&(catalog.runtimeCapabilities?.transformerTypes||[1,2,3,4,5,6]).includes(m.engineType))||[]){const option=node('option',d.label);option.value=d.engineType;select.append(option);}
  n.append(chain,node('small',i.serialPitchOrder?'Serial pitch order · Velocity → Polyphony → ARP; CC separate':'Legacy stages: Transpose → Range → Velocity → Polyphony → ARP; CC separate'),select,button('ADD TRANSFORMER',()=>command({action:'module_structure',instrumentId:i.id,operation:'add',engineType:Number(select.value)})),button('EDIT',()=>editInstrument(i)));return n;
}

$('add-instrument').onclick=()=>command({action:'instrument_add'});
