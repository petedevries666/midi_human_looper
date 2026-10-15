'use strict';
let revision=1, engineSession=null, pending=false, renderedModel='', latest=null;
// Next insertion type is an editor choice, not a musical parameter. Preserve it
// by stable instrument ID when a pending native response rebuilds the rows.
const transformerChoices=new Map();
let selectedModule=null;
let catalog=null, ws=null, reconnect=null, renderedSnapshots='', renderedSnapshotSession=null;
const $=id=>document.getElementById(id);
const node=(tag,text,cls)=>{const n=document.createElement(tag);if(text!==undefined)n.textContent=text;if(cls)n.className=cls;return n;};
function headers(){return {'Content-Type':'application/json','X-Engine-Token':$('token').value};}
async function request(path,body){const response=await fetch(path,{method:body?'POST':'GET',headers:headers(),body:body?JSON.stringify(body):undefined});const data=await response.json();if(!response.ok)throw new Error(data.error||data.status||'Request failed');return data;}
const iconPaths={play:'M6 3l12 9-12 9z',stop:'M5 5h14v14H5z',record:'M12 4a8 8 0 1 0 0 16a8 8 0 1 0 0-16',mute:'M4 9h4l5-4v14l-5-4H4z M17 8l5 8m0-8-5 8',solo:'M12 3l3 6 7 1-5 5 1 7-6-3-6 3 1-7-5-5 7-1z',edit:'M4 20l1-6L17 2l5 5L10 19z',add:'M12 4v16M4 12h16',remove:'M5 5l14 14M19 5L5 19',prev:'M16 4l-8 8 8 8',next:'M8 4l8 8-8 8',save:'M4 3h14l3 3v15H3V3z M7 3v7h10V3 M7 21v-7h10v7',load:'M3 8h7l2 3h9l-3 10H3z M12 2v7m-3-3 3 3 3-3',midi:'M4 4h16v16H4z M8 4v9m4-9v9m4-9v9'};
function decorateButton(b,label){
  const key=/^(BYPASS|ENABLE)$/.test(label)?'record':/LEARN|MIDI/.test(label)?'midi':/^REC(?: |$)|FINISH/.test(label)?'record':/TRIGGER|TEST|RECALL/.test(label)?'play':/STOP/.test(label)?'stop':/MUTE/.test(label)?'mute':/SOLO/.test(label)?'solo':/LEARN|MIDI/.test(label)?'midi':/EDIT|OPTIONS|CONFIGURE/.test(label)?'edit':/ADD|CAPTURE/.test(label)?'add':/DELETE|FORGET|^×$/.test(label)?'remove':/SAVE/.test(label)?'save':/LOAD/.test(label)?'load':label==='←'?'prev':label==='→'?'next':null;
  if(!key)return;b.setAttribute('aria-label',label);b.title=label;if(/^(MUTE|SOLO)/.test(label))b.setAttribute('aria-pressed',String(label.endsWith(' ON')));
  const svg=document.createElementNS('http://www.w3.org/2000/svg','svg');svg.setAttribute('viewBox','0 0 24 24');svg.setAttribute('aria-hidden','true');svg.classList.add('action-icon');
  const path=document.createElementNS(svg.namespaceURI,'path');path.setAttribute('d',iconPaths[key]);svg.append(path);b.prepend(svg);
}
function button(label,action){const b=node('button',label);b.setAttribute('aria-label',label);b.title=label;decorateButton(b,label);compactAction(b,label);b.addEventListener('click',action);return b;}
function compactAction(b,label){
  const short={'BYPASS':'','ENABLE':'','SOLO':'S','SOLO ON':'S','MUTE':'M','MUTE ON':'M','FINISH REC':'END','MIDI LEARN':'LEARN','TRIGGER LEARN':'','CANCEL LEARN':'','ADD TRANSFORMER':'','ADD INSTRUMENT':'INST','ADD CONTROLLER SOURCE':'SOURCE','ADD MAPPING':'MAP','+ CAPTURE SNAPSHOT':'CAPTURE','CAPTURE STATE':'STATE','SIMULATE FOOTSWITCH':'MIDI','CONFIGURE A/B':'A/B','SAVE PATCH':'','LOAD PATCH':'','STOP':'','EDIT':'','PHRASE OPTIONS':'','OPTIONS':'','SNAPSHOTS':'SNAP','DELETE':'','FORGET':'','FORGET MIDI':'CLEAR MIDI','×':'','TRIGGER':'','REC / OVERDUB':'','RECALL':'','←':'','→':''};
  const text=Object.hasOwn(short,label)?short[label]:label.startsWith('TEST ')?label.slice(5):label.startsWith('LEARN ·')?'':null;
  if(text===null)return;if(label==='CANCEL LEARN')b.setAttribute('aria-pressed','true');if(label==='FINISH REC')b.querySelector('svg')?.remove();for(const child of [...b.childNodes])if(child.nodeType===Node.TEXT_NODE)child.remove();if(text)b.append(document.createTextNode(text));b.classList.toggle('icon-only',!text);}
const shortParameter=label=>({'BASE VEL':'VEL','VEL DECAY':'V.DEC','TIME DECAY':'T.DEC','VOLUME':'VOL','SEMITONES':'ST','LOW NOTE':'LOW','HIGH NOTE':'HIGH'}[label]||label);
function contextualHelp(text){const help=node('details',undefined,'context-help');help.append(node('summary','HELP'),node('p',text));return help;}
// Native range inputs provide pointer/touch capture and standard keyboard semantics.
function tactileSlider(label,value,min,max,step,oncommit,defaultValue=1,logarithmic=false,binding=null){
  const root=node('label',undefined,'tactile-slider'),caption=node('span',shortParameter(label.replace(/ (Phrase|Instrument) \d+$/,'')),'slider-caption'),rail=node('input'),readout=node('output');
  rail.type='range';rail.min=logarithmic?-1:min;rail.max=logarithmic?1:max;rail.step=logarithmic?.001:step;rail.value=logarithmic?Math.log2(value):value;rail.setAttribute('aria-label',label);
  const decode=()=>logarithmic?Math.pow(2,Number(rail.value)):Number(rail.value);
  const paint=()=>{const v=decode();root.style.setProperty('--position',`${100*(Number(rail.value)-Number(rail.min))/(Number(rail.max)-Number(rail.min))}%`);readout.value=(step===1||label.startsWith('TEST '))?String(Math.round(v)):label.startsWith('VEL DECAY')?`${Math.round(v*100)}%`:`×${v.toFixed(label.startsWith('BASE VEL')?1:2)}`;rail.setAttribute('aria-valuetext',readout.value);};
  let accepted=Number(value),desired=null,sending=false,dragging=false;
  rail.addEventListener('pointerdown',()=>dragging=true);for(const edge of ['pointerup','pointercancel','lostpointercapture'])rail.addEventListener(edge,()=>dragging=false);
  rail.setEffective=v=>{if(dragging||sending||desired!==null||rail.dataset.assignmentGesture)return;accepted=Number(v);rail.value=logarithmic?Math.log2(accepted):accepted;paint();};
  async function commit(){if(rail.dataset.assignmentGesture)return;desired=decode();if(sending)return;sending=true;try{while(desired!==null){const next=desired;desired=null;const ok=await oncommit(next);if(ok===false&&desired===null){rail.value=logarithmic?Math.log2(accepted):accepted;paint();}else if(ok!==false)accepted=next;}}finally{sending=false;}}
  rail.oninput=paint;rail.onchange=commit;rail.ondblclick=()=>{rail.value=logarithmic?Math.log2(defaultValue):defaultValue;paint();commit();};
  root.append(caption,rail,readout);paint();if(binding)bindModulation(rail,binding);return root;
}
function descriptor(type){return catalog?.modules.find(m=>m.engineType===type);}
function musicalValue(p,value){return p?.choices?.[Math.round(value)]??`${Number(value).toFixed(p?.step>=1?0:2)} ${p?.unit||''}`;}
function parameter(kind){return catalog?.parameters.find(p=>p.engineKind===kind);}
async function loadDescriptors(){try{catalog=await request('/api/v1/descriptors');$('app-version').textContent=`V ${catalog.applicationVersion||'UNKNOWN'}`;renderedModel='';if(latest)render(latest);}catch(e){$('error').textContent=e.message;}}
function mappingFor(binding){return controllerConfiguration().mappings.find(m=>m.instrumentId===binding.instrumentId&&m.moduleId===binding.moduleId&&m.kind===binding.kind&&m.enabled);}
function curveY(points,x,hold=false){let y=points.at(-1)[1];for(let i=1;i<points.length;i++)if(x<points[i][0]||(!hold&&x===points[i][0])){const a=points[i-1],b=points[i];let t=hold?0:(x-a[0])/(b[0]-a[0]),power=1+5*Math.abs(a[2]||0);t=a[2]>0?Math.pow(t,power):a[2]<0?1-Math.pow(1-t,power):t;return a[1]+(b[1]-a[1])*t;}return y;}
function previewCurve(points,hold=false){const svg=document.createElementNS('http://www.w3.org/2000/svg','svg');svg.setAttribute('viewBox','0 0 100 20');svg.classList.add('rail-curve');svg.setAttribute('aria-hidden','true');const path=document.createElementNS(svg.namespaceURI,'path');path.setAttribute('d',Array.from({length:101},(_,x)=>`${x?'L':'M'}${x},${20*(1-curveY(points,x/100,hold))}`).join(' '));svg.append(path);return svg;}
function closeAssignment(){document.getElementById('assignment-menu')?.remove();}
function bindModulation(control,binding){
 control.mbmfBinding=binding;
 const p=parameter(binding.kind);if(!p?.assignmentEligible)return;
 control.dataset.modulationTarget=JSON.stringify(binding);
 const mapping=mappingFor(binding),source=controllerConfiguration().sources.find(s=>s.id===mapping?.sourceId);
 if(mapping){control.classList.add('modulated');control.title=`${p.label} · ${source?.name||'SOURCE '+mapping.sourceId}`;control.parentElement?.append(previewCurve(mapping.points));}
 const open=(x,y)=>assignmentMenu(binding,x,y);
 control.oncontextmenu=e=>{e.preventDefault();e.stopPropagation();open(e.clientX,e.clientY);};
 control.addEventListener('keydown',e=>{if(e.key==='ContextMenu'||(e.shiftKey&&e.key==='F10')){e.preventDefault();const r=control.getBoundingClientRect();open(r.left,r.bottom);}});
 let timer;control.addEventListener('pointerdown',e=>{if(e.pointerType==='touch'){const value=control.value;timer=setTimeout(()=>{control.dataset.assignmentGesture='1';control.value=value;control.dispatchEvent(new Event('input'));open(e.clientX,e.clientY);setTimeout(()=>delete control.dataset.assignmentGesture,500);},600);}});for(const event of ['pointerup','pointercancel','pointermove'])control.addEventListener(event,()=>clearTimeout(timer));
 const access=button('EXP',()=>{const r=control.getBoundingClientRect();open(r.left,r.bottom);});access.className='modulation-access';access.setAttribute('aria-label',`Assign modulation ${p.label}`);access.title=source?.name||'Assign expression · right-click or long press';control.parentElement?.append(access);
}
async function assignmentMenu(binding,x,y){
 closeAssignment();const menu=node('div',undefined,'assignment-menu');menu.id='assignment-menu';menu.setAttribute('role','menu');menu.setAttribute('aria-label','Modulator assignment');
 const {sources,mappings}=controllerConfiguration();const matches=mappings.filter(m=>m.instrumentId===binding.instrumentId&&m.moduleId===binding.moduleId&&m.kind===binding.kind);
 const item=(label,action)=>{const b=button(label,async()=>{closeAssignment();try{await action();}catch(e){$('error').textContent=e.message;}});b.setAttribute('role','menuitem');menu.append(b);};
 item('NONE',async()=>{for(const m of matches)await command({action:'mapping_delete',mappingId:m.id});if(binding.kind<14){const data=await request('/api/v1/command',{protocolVersion:1,expectedRevision:revision,expectedEngineSessionId:engineSession,action:'parameter_curve',targetId:binding.instrumentId,moduleId:binding.moduleId,kind:binding.kind});if(data.legacyCurve.source)await command({action:'parameter_unassign',targetId:binding.instrumentId,moduleId:binding.moduleId,kind:binding.kind});}});
 for(const source of sources)item(source.name||`SOURCE ${source.id}`,()=>assignModulator(binding,source));
 item('+ SOURCE',()=>createNamedSource(binding));
 ($('editor').open?$('editor'):document.body).append(menu);const r=menu.getBoundingClientRect();menu.style.left=`${Math.max(4,Math.min(x,innerWidth-r.width-4))}px`;menu.style.top=`${Math.max(4,Math.min(y,innerHeight-r.height-4))}px`;menu.querySelector('button')?.focus();
 menu.onkeydown=e=>{const buttons=[...menu.querySelectorAll('button')];if(e.key==='Escape'){e.preventDefault();closeAssignment();}if(['ArrowDown','ArrowUp'].includes(e.key)){e.preventDefault();const index=buttons.indexOf(document.activeElement);buttons[(index+(e.key==='ArrowDown'?1:-1)+buttons.length)%buttons.length].focus();}};
}
function createNamedSource(binding){
 const dialog=$('editor');if(dialog.open)dialog.close();delete dialog.dataset.contextual;
 const content=$('editor-content');content.replaceChildren(node('h2','EXPRESSION SOURCE'));
 const input=node('input');input.maxLength=16;input.value='EXP 1 CODIE';input.setAttribute('aria-label','Controller name');content.append(input);
 const error=node('p');error.setAttribute('role','alert');content.append(error);
 content.append(button('DONE',async()=>{try{const sourceId=freshId(controllerConfiguration().sources.map(s=>s.id));const state=await request('/api/v1/command',{protocolVersion:1,expectedRevision:revision,expectedEngineSessionId:engineSession,action:'controller_rename',sourceId,name:input.value,create:true});render(state);dialog.close();await assignModulator(binding,controllerConfiguration().sources.find(s=>s.id===sourceId));}catch(e){error.textContent=e.message;}}),button('CANCEL',()=>dialog.close()));showEditor(dialog);input.focus();
}
async function assignModulator(binding,source){
 if($('editor').dataset.kind==='module')await window.mbmfModuleFlush?.();
 const {mappings}=controllerConfiguration();const existing=mappingFor(binding);let points=existing?.points||[[0,0,0],[1,1,0]],legacy=0;
 if(binding.kind<14){const state=await request('/api/v1/command',{protocolVersion:1,expectedRevision:revision,expectedEngineSessionId:engineSession,action:'parameter_curve',targetId:binding.instrumentId,moduleId:binding.moduleId,kind:binding.kind});legacy=state.legacyCurve.source;if(legacy){if(!confirm('Replace this legacy expression assignment with native Controller ownership? Other legacy targets remain unchanged.'))return;points=state.legacyCurve.points;}}
 const same=mappings.find(m=>m.instrumentId===binding.instrumentId&&m.moduleId===binding.moduleId&&m.kind===binding.kind);
 const mapping={...(existing||{}),...binding,id:existing?.id||freshId(mappings.map(m=>m.id)),targetId:same?.targetId||freshId(mappings.map(m=>m.targetId)),sourceId:source.id,enabled:1,points};
 const state=await request('/api/v1/command',{protocolVersion:1,expectedRevision:revision,expectedEngineSessionId:engineSession,action:'mapping_commit',mapping,replaceLegacy:!!legacy});render(state);
 if($('editor').open)$('editor').close();editMapping(controllerConfiguration().mappings.find(m=>m.id===mapping.id));
}
document.addEventListener('pointerdown',e=>{const menu=$('assignment-menu');if(menu&&!menu.contains(e.target)){e.preventDefault();e.stopImmediatePropagation();closeAssignment();}},true);
document.addEventListener('keydown',e=>{if(e.key==='Escape'){if(document.querySelector('.assignment-menu')){closeAssignment();e.preventDefault();return;}const dialog=document.querySelector('dialog[data-contextual][open]');if(dialog){const cancel=new Event('cancel',{cancelable:true});if(dialog.dispatchEvent(cancel))dialog.close();e.preventDefault();}}});
function showEditor(dialog,docked=false,kind=''){if(kind)dialog.dataset.kind=kind;else delete dialog.dataset.kind;if(docked){dialog.dataset.contextual='true';dialog.show();dialog.scrollIntoView({block:'nearest'});}else{delete dialog.dataset.contextual;dialog.showModal();}}
document.addEventListener('pointerdown',e=>{const d=$('editor');if(d.open&&d.dataset.contextual&&!d.contains(e.target)&&!e.target.closest('.module')&&!e.target.closest('#assignment-menu'))d.close();});
function editInstrument(i){const d=descriptor(0);if(!d)return;edit(d,i,d.parameters.map(id=>{const p=catalog.parameters.find(p=>p.id===id),canonical=parameter({enabled:21,input:22,output:23}[id]);const display=canonical?{...p,valueType:canonical.valueType,choices:canonical.choices}:p;return {descriptor:display,value:i[p.engineField],assignment:0};}),null);}
async function editModule(i,tf){
 if($('editor').open){if($('editor').dataset.kind!=='module')return;if(await window.mbmfModuleFlush?.()===false)return;$('editor').close();}
 try{render(await request('/api/v1/state'));}catch(e){$('error').textContent=e.message;return;}
 const fresh=latest.instruments.find(v=>v.id===i.id),current=fresh?.transformers.find(v=>v.id===tf.id);if(!fresh||!current)return;i=fresh;tf=current;
 selectedModule={instrumentId:i.id,moduleId:tf.id};for(const element of document.querySelectorAll('.module'))element.classList.toggle('selected',Number(element.dataset.moduleId)===tf.id);
 const dialog=$('editor'),content=$('editor-content'),session=engineSession;
 dialog.dataset.kind='module';content.replaceChildren(node('h2',`${i.name||'INSTRUMENT '+i.id} / ${descriptor(tf.type)?.label}`));
 const before=new Map(),applied=new Map(),desired=new Map();let queue=Promise.resolve(),draining=false,timer=null,cancelled=false,failed=false;const failures=new Set();
 const error=node('p');error.setAttribute('role','alert');
 const flush=()=>{
  clearTimeout(timer);timer=null;if(draining)return queue;draining=true;
  queue=(async()=>{while(desired.size){const changes=[...desired];desired.clear();
   for(const [kind,value] of changes){if(cancelled||session!==engineSession){failed=true;error.textContent='Engine changed; reopen editor.';return;}
    let ok=false;for(let attempt=0;attempt<3&&!ok;++attempt){while(pending)await new Promise(r=>setTimeout(r,10));try{render(await request('/api/v1/command',{protocolVersion:1,expectedRevision:revision,expectedEngineSessionId:session,action:'parameter_set',targetId:i.id,moduleId:tf.id,kind,value}));ok=true;}catch(e){$('error').textContent=e.message;if(e.message!=='conflict')break;await refresh();}}
    if(ok){applied.set(kind,value);failures.delete(kind);}else{failures.add(kind);error.textContent=$('error').textContent;}failed=failures.size>0;if(!failed)error.textContent='';
   }
  }})().finally(()=>draining=false);return queue;
 };
 const change=(kind,value)=>{desired.set(kind,value);if(!draining&&!timer)timer=setTimeout(flush,40);};
 window.mbmfModuleFlush=async()=>{await flush();return !failed;};
 for(const item of tf.parameters){const p=parameter(item.kind);if(!p)continue;before.set(item.kind,item.pendingValue??item.value);const binding={instrumentId:i.id,moduleId:tf.id,kind:item.kind};
  const row=node('label',shortParameter(p.label),'parameter');
  if(p.valueType==='toggle'){let value=item.value;const control=button(p.label,()=>{value=value?0:1;control.textContent=value?'ON':'OFF';control.setAttribute('aria-pressed',String(!!value));change(item.kind,value);});control.textContent=value?'ON':'OFF';control.setAttribute('aria-pressed',String(!!value));control.disabled=!!item.assignment;row.append(control);bindModulation(control,binding);}
  else if(p.valueType==='enum'){const control=node('select');control.setAttribute('aria-label',p.label);for(let v=p.min;v<=p.max;v+=p.step){const o=node('option',p.choices?.[v]??String(v));o.value=v;control.append(o);}control.value=item.value;control.disabled=!!item.assignment;control.onchange=()=>change(item.kind,Number(control.value));row.append(control);bindModulation(control,binding);}
  else{const slider=tactileSlider(p.label,item.value,p.min,p.max,p.step,value=>{change(item.kind,value);return true;},p.default,false,binding);const rail=slider.querySelector('input');rail.disabled=!!item.assignment;let touch=false;rail.addEventListener('pointerdown',e=>touch=e.pointerType==='touch');for(const edge of ['pointerup','pointercancel'])rail.addEventListener(edge,()=>touch=false);rail.addEventListener('input',()=>{if(!touch&&!rail.dataset.assignmentGesture)change(item.kind,Number(rail.value));});row.append(slider);}
  content.append(row);
 }
 content.append(error,button('DONE',async()=>{if(await window.mbmfModuleFlush()===false)return;dialog.close();renderedModel='';render(latest);}),button('CANCEL',async()=>{
  await window.mbmfModuleFlush();cancelled=true;
  try{render(await request('/api/v1/state'));}catch(e){error.textContent=e.message;return;}
  if(session===engineSession)for(const [kind,value] of applied){const item=latest.instruments.find(v=>v.id===i.id)?.transformers.find(v=>v.id===tf.id)?.parameters.find(p=>p.kind===kind),current=item?.pendingValue??item?.value;
   if(Math.abs(current-value)<1e-8){while(pending)await new Promise(r=>setTimeout(r,10));await command({action:'parameter_set',targetId:i.id,moduleId:tf.id,kind,value:before.get(kind)});}}
  dialog.close();
 }));
 dialog.oncancel=e=>{e.preventDefault();content.querySelector('[aria-label="CANCEL"]').click();};showEditor(dialog,true,'module');
}

function edit(module,instrument,values,instance){
  const dialog=$('editor'),content=$('editor-content');if(dialog.open)return;
  const capturedRevision=revision,capturedSession=engineSession;
  let committing=false;
  const drafts=values.map(v=>({...v}));
  const heading=node('h2',instance?`${instrument.name||'INSTRUMENT '+instrument.id} / ${module.label}`:instrument.name||`${module.label} ${instrument.id}`);heading.title=`Stable target ${instance?.id||instrument.id}`;content.replaceChildren(heading);if(!instance)content.append(contextualHelp(instrument.serialPitchOrder?'Serial pitch order · Velocity → Polyphony → ARP; CC separate':'Legacy stages: Transpose → Range → Velocity → Polyphony → ARP; CC separate'));
  const dismiss=()=>{if(!committing)dialog.close();};
  content.append(button('×',dismiss));
  for(const draft of drafts){
    const p=draft.descriptor;if(!p)continue;
    const label=node('label',shortParameter(p.label),'parameter');
    if(p.valueType==='toggle'||p.valueType==='enum'){
      const control=p.valueType==='toggle'?button(draft.value?'ON':'OFF',()=>{draft.dirty=true;draft.value=draft.value?0:1;control.textContent=draft.value?'ON':'OFF';control.setAttribute('aria-pressed',String(!!draft.value));}):node('select');
      control.setAttribute('aria-label',p.label);control.title=p.label;control.disabled=!!draft.assignment;
      if(p.valueType==='toggle')control.setAttribute('aria-pressed',String(!!draft.value));
      else{const names=p.choices;for(let v=p.min;v<=p.max;v+=p.step){const o=node('option',names?.[v]||String(v));o.value=v;control.append(o);}control.value=draft.value;control.onchange=()=>{draft.dirty=true;draft.value=Number(control.value);};}
      label.append(control);if(draft.assignment)label.append(node('small',`EXP ${draft.assignment}`));content.append(label);bindModulation(control,{instrumentId:instrument.id,moduleId:instance?.id||0,kind:p.engineKind});continue;
    }
    const number=node('input');number.type='number';number.min=p.min;number.max=p.max;number.step=p.step;number.value=draft.value;
    const rail=node('input');rail.type='range';rail.min=p.min;rail.max=p.max;rail.step=p.step;rail.value=draft.value;
    rail.disabled=number.disabled=!!draft.assignment;
    function update(value){draft.dirty=true;draft.value=Number(value);number.value=draft.value;rail.value=draft.value;}
    number.addEventListener('input',()=>update(number.value));rail.addEventListener('input',()=>update(rail.value));rail.addEventListener('dblclick',()=>update(p.default));
    const paintRail=()=>rail.style.setProperty('--position',`${100*(Number(rail.value)-p.min)/(p.max-p.min||1)}%`);rail.addEventListener('input',paintRail);number.addEventListener('input',paintRail);rail.addEventListener('dblclick',paintRail);paintRail();rail.setAttribute('aria-label',p.label);label.append(number,node('span',p.unit),rail);
    if(draft.assignment)label.append(node('small',`EXP ${draft.assignment}`));
    content.append(label);bindModulation(rail,{instrumentId:instrument.id,moduleId:instance?.id||0,kind:p.engineKind});
  }
  const error=node('p','');error.setAttribute('role','alert');content.append(error);
  const done=button('DONE',async()=>{
    if(committing)return;
    if(engineSession!==capturedSession){error.textContent='Engine restarted. CANCEL and reopen this editor.';return;}
    const body=instance?{action:'module_commit',instrumentId:instrument.id,moduleId:instance.id,parameters:drafts.filter(d=>!d.assignment && (d.dirty || !mappingFor({instrumentId:instrument.id,moduleId:instance.id,kind:d.kind}))).map(d=>({kind:d.kind,value:d.value}))}:{action:'instrument_commit',instrumentId:instrument.id,...Object.fromEntries(drafts.map(d=>[d.descriptor.engineField,d.value]))};
    if(instance&&!body.parameters.length){dialog.close();return;}
    committing=true;done.disabled=cancel.disabled=true;
    try{const state=await request('/api/v1/command',{protocolVersion:1,expectedRevision:capturedRevision,expectedEngineSessionId:capturedSession,...body});render(state);dialog.close();}
    catch(e){error.textContent=e.message==='conflict'?'Configuration changed. CANCEL and reopen this editor.':e.message;}
    finally{committing=false;done.disabled=cancel.disabled=false;}
  });
  const cancel=button('CANCEL',dismiss);content.append(done,cancel);
  dialog.oncancel=e=>{if(committing)e.preventDefault();};
  dialog.onclick=e=>{const r=dialog.getBoundingClientRect();if(e.target===dialog&&(e.clientX<r.left||e.clientX>r.right||e.clientY<r.top||e.clientY>r.bottom))dismiss();};
  showEditor(dialog,!!instance);
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
  content.append(contextualHelp(`${record.parameterCount} captured targets. UPDATE recaptures current effective values.`));
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
  showEditor(dialog);
}
function editSwitchSequence(sw){
 const dialog=$('editor');if(dialog.open)return;const content=$('editor-content');content.replaceChildren(node('h2','SMART SWITCH / SEQUENCE'));
 const settings=[...sw.settings],sequence=[...sw.sequence],session=engineSession,rev=revision;
 const name=node('input');name.value=sw.name;name.maxLength=16;name.setAttribute('aria-label','Smart Switch name');content.append(name);
 const choice=(label,index,options)=>{const row=node('label',label,'parameter'),select=node('select');select.setAttribute('aria-label',label);for(const [value,text] of options){const o=node('option',text);o.value=value;select.append(o);}select.value=settings[index];select.onchange=()=>settings[index]=Number(select.value);row.append(select);content.append(row);return select;};
 choice('ENABLED',0,[[0,'OFF'],[1,'ON']]);choice('TRAVERSAL',9,[[0,'FORWARD'],[1,'REVERSE'],[2,'PING-PONG'],[3,'RANDOM']]);choice('RESET ON RE-ENTRY',10,[[0,'CONTINUE'],[1,'RESTART']]);
 const list=node('div',undefined,'sequence-list');content.append(list);
 const paint=()=>{list.replaceChildren(...sequence.map((id,index)=>{const row=node('div',undefined,'sequence-step');row.append(node('span',`${index+1} → ${latest.phrases.find(p=>p.id===id)?.name||'PHRASE '+id}`));for(const [text,delta] of [['←',-1],['→',1]]){const b=button(text,()=>{const other=index+delta;[sequence[index],sequence[other]]=[sequence[other],sequence[index]];paint();});b.disabled=index+delta<0||index+delta>=sequence.length;row.append(b);}row.append(button('DELETE',()=>{sequence.splice(index,1);paint();}));return row;}));};paint();
 const phrase=node('select');phrase.setAttribute('aria-label','Sequence phrase');for(const p of latest.phrases){const o=node('option',`${p.id} · ${p.name||'PHRASE '+p.id}${p.events?'':' · EMPTY'}`);o.value=p.id;phrase.append(o);}content.append(phrase,button('ADD STEP',()=>{if(sequence.length<64){sequence.push(Number(phrase.value));paint();}}));
 const actions=[[0,'NONE'],[1,'NEXT PHRASE'],[2,'STOP PHRASES'],[3,'RESET SEQUENCE'],[4,'RESET ALL'],[5,'STOP + RESET'],[6,'PANIC']];
 for(const [index,label] of [[12,'TAP ACTION'],[13,'DOUBLE ACTION'],[14,'HOLD ACTION']]){
   // Preserve existing module actions without silently translating them.
   const override=(latest.snapshotActions||[]).find(a=>a.switchId===sw.id && a.gesture===index-12 && a.action>0);
   const select=choice(label,index,override?[[settings[index],'SNAPSHOT ACTION · SNAP EDIT']]:settings[index]>6?[...actions,[settings[index],'EXISTING MODULE ACTION']]:actions);
   if(override){select.disabled=true;select.title='Configured Snapshot action takes precedence. Use SNAP to change or remove it.';}
 }
 choice('ADVANCE',6,[[0,'ON PRESS'],[1,'GESTURE CLASSIFIED']]);
 const input=node('details');input.append(node('summary','MIDI / GESTURE TIMING'));content.append(input);
 const midiType=choice('MIDI TYPE',1,[[0,'UNASSIGNED'],[1,'NOTE'],[2,'CC']]);input.append(midiType.parentElement);
 for(const [label,index,min,max] of [['MIDI CHANNEL (1–16)',2,1,16],['NOTE / CC',3,0,127],['CC PRESS',4,0,127],['CC RELEASE',5,0,127],['DOUBLE MS',7,50,2000],['HOLD MS',8,100,5000]]){const row=node('label',label,'parameter'),n=node('input');n.type='number';n.min=min;n.max=max;n.value=settings[index]+(index===2?1:0);n.setAttribute('aria-label',label);n.onchange=()=>settings[index]=Number(n.value)-(index===2?1:0);row.append(n);input.append(row);}
 content.append(contextualHelp('Each NEXT gesture advances one step. Authored MIDI channels route the phrase to matching Instruments. LOOP layers continue until STOP; ONCE/HOLD retain their established lifecycle. RANDOM uses the existing shuffle bag. Empty steps remain valid and generate no notes.'));
 const error=node('p');error.setAttribute('role','alert');content.append(error);
 content.append(button('DONE',async()=>{if(session!==engineSession){error.textContent='Engine restarted; reopen editor.';return;}if(await command({action:'switch_commit',switchId:sw.id,settings,sequence,name:name.value,expectedRevision:rev})){dialog.close();renderedModel='';render(latest);}else error.textContent=$('error').textContent;}),button('CANCEL',()=>dialog.close()));showEditor(dialog);
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
  content.append(contextualHelp('Navigation wraps in snapshot order. Morph uses the destination snapshot duration and curve. Existing MIDI assignment and gesture detection are preserved.'));
  const error=node('p','');error.setAttribute('role','alert');content.append(error);
  const done=button('DONE',async()=>{
    if(committing)return;if(engineSession!==capturedSession){error.textContent='Engine restarted. CANCEL and reopen.';return;}
    committing=true;done.disabled=cancel.disabled=true;
    try{const state=await request('/api/v1/command',{protocolVersion:1,expectedRevision:capturedRevision,expectedEngineSessionId:capturedSession,action:'snapshot_switch',switchId:sw.id,gesture:Number(gesture.value),snapshotAction:Number(action.value),snapshotId:['3','4'].includes(action.value)?Number(target.value):0});dialog.close();renderedModel='';render(state);}
    catch(e){error.textContent=e.message==='conflict'?'Configuration changed. CANCEL and reopen.':e.message;}
    finally{committing=false;done.disabled=cancel.disabled=false;}
  });
  const cancel=button('CANCEL',dismiss);content.append(done,cancel);
  dialog.oncancel=e=>{if(committing)e.preventDefault();};dialog.onclick=e=>{const r=dialog.getBoundingClientRect();if(e.target===dialog&&(e.clientX<r.left||e.clientX>r.right||e.clientY<r.top||e.clientY>r.bottom))dismiss();};showEditor(dialog);
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
  content.append(contextualHelp('Use shared included targets. Individual controller takeovers remain overridden until A/B is configured again. MIDI Learn uses the existing Controller Engine.'));
  const error=node('p','');error.setAttribute('role','alert');content.append(error);
  const done=button('DONE',async()=>{if(committing)return;committing=true;done.disabled=cancel.disabled=true;
    try{const state=await request('/api/v1/command',{protocolVersion:1,expectedRevision:capturedRevision,expectedEngineSessionId:capturedSession,action:'snapshot_ab_configure',a:Number(a.value),b:Number(b.value),ease:Number(ease.value),position:latest.snapshotAB?.position||0});dialog.close();renderedAB='';render(state);}catch(e){error.textContent=e.message;}finally{committing=false;done.disabled=cancel.disabled=false;}
  });const cancel=button('CANCEL',dismiss);content.append(done,cancel);dialog.oncancel=e=>{if(committing)e.preventDefault();};dialog.onclick=e=>{const r=dialog.getBoundingClientRect();if(e.target===dialog&&(e.clientX<r.left||e.clientX>r.right||e.clientY<r.top||e.clientY>r.bottom))dismiss();};showEditor(dialog);
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
function paintEffectiveRails(s){for(const rail of document.querySelectorAll('.tactile-slider input[type=range]')){const b=rail.mbmfBinding;if(!b||!rail.setEffective)continue;const p=[14,15,17].includes(b.kind)?s.phrases.find(p=>p.id===b.instrumentId):s.instruments.find(i=>i.id===b.instrumentId);if(!p)continue;const field={1:'level',14:'timeDecay',15:'velocityDecay',17:'baseVelocity'}[b.kind];if(field)rail.setEffective(p[field]);}}
function render(s){
  if(engineSession===s.engineSessionId&&s.revision<revision)return;
  if(engineSession!==s.engineSessionId)transformerChoices.clear();
  for(const id of transformerChoices.keys())if(!s.instruments.some(i=>i.id===id))transformerChoices.delete(id);
  engineSession=s.engineSessionId;revision=s.revision;latest=s;
  $('connection').textContent='CONNECTED · Engine running';
  $('stop-native').hidden=!s.chainMode;paintPhraseStates(s);paintEffectiveRails(s);paintConductorRuntime(s);if(typeof refreshMovements==='function')refreshMovements(s);
  $('transport-state').textContent=s.chainMode?`NATIVE · ${s.chainRecording?'RECORDING':s.chainArmed?'RECORD ARMED':s.chainRunning?'PLAYING':'STOPPED'} · ${s.activeNotes} ACTIVE NOTES`:`ENGINE RUNNING · ${s.activeNotes} ACTIVE NOTES`;
  $('metrics').replaceChildren(...[`Build ${s.buildRevision||'unknown'}`,`Backend ${s.backend} · ${s.sampleRate} Hz / ${s.blockSize}`,`Sample clock ${s.sampleClock}`,`MIDI messages ${s.midiCount}`,`Active notes ${s.activeNotes}`,`Maximum callback ${s.maxCallbackUs.toFixed(1)} µs`,`JACK XRUN notifications ${s.lateBlocks}`,`Output overflow ${s.outputOverflow}`].map(v=>node('span',v)));
  if(s.chainMode)$('metrics').append(node('span',`Zynthian · ${s.chainCaptureMode==='free-time'?'FREE TIME':'TWO BARS'} · ${s.chainBpm} BPM · ${s.chainError?'CLOCK / CAPACITY ERROR — stopped':s.chainRecording?'RECORDING':s.chainArmed?(s.chainCaptureMode==='free-time'?'WAITING FOR FIRST NOTE':'WAITING FOR NEXT LOOP'):s.chainRunning?'PLAYING':'STOPPED'}`));
  $('last-midi').textContent=`Last MIDI · sample ${s.lastEvent[0]} · status ${s.lastEvent[1]} · number ${s.lastEvent[2]} · value ${s.lastEvent[3]}`;
  for(const sw of s.switches){const el=document.querySelector(`[data-switch-id="${sw.id}"] .step`);if(el)el.textContent=`STEP ${sw.conductor?.steps?sw.conductor.step:sw.step} / ${sw.conductor?.steps||sw.length}`;}
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
  if(!document.activeElement?.closest('#controllers .name-input'))renderControllers(s);
  if(uiPointerHeld||document.activeElement?.tagName==='SELECT'||document.activeElement?.classList.contains('name-input')||document.activeElement?.type==='range'||document.querySelector('[data-live-release=held]'))return;
  const model=JSON.stringify([s.controllerEngine,s.controllerLearn,s.phrases.map(p=>({...p,state:undefined,events:0})),s.instruments,s.switches.map(v=>({...v,step:0,actionCount:0,lastAction:0,result:0,conductor:undefined})),s.snapshotActions]);if(model===renderedModel)return;renderedModel=model;
  compactPhrases(s);
  paintPhraseStates(s);
  $('instruments').replaceChildren(...s.instruments.map(compactInstrument));
  const openSwitchTests=new Set([...document.querySelectorAll('.switch-test[open]')].map(e=>e.closest('[data-switch-id]').dataset.switchId));
  $('switches').replaceChildren(...s.switches.map(sw=>{
    const n=node('article',undefined,'switch');n.dataset.switchId=sw.id;n.append(node('strong',sw.name||`SWITCH ${sw.id}`),node('small',`${sw.kind===1?'NOTE':sw.kind===2?'CC':'UNASSIGNED'} ${sw.number} · CH ${sw.channel}`),node('small',`STEP ${sw.conductor?.steps?sw.conductor.step:sw.step} / ${sw.conductor?.steps||sw.length}`,'step'),button('OPTIONS',()=>editSwitchSequence(sw)),button('CONDUCTOR',()=>editConductor(sw)),button('SNAPSHOTS',()=>editSwitchSnapshots(sw)));
    const tests=node('div',undefined,'tests');for(const gesture of ['tap','double','hold']){const b=button(`TEST ${gesture.toUpperCase()}`,()=>testSwitch(sw.id,gesture));b.dataset.valid='1';b.title=`${gesture.toUpperCase()} preview · no MIDI assignment required`;tests.append(b);}
    const hardware=button('SIMULATE FOOTSWITCH',async()=>{if(await command({action:'midi',channel:sw.channel,note:sw.number,value:100}))await command({action:'midi',channel:sw.channel,note:sw.number,value:0});});hardware.className='hardware';hardware.dataset.valid=sw.kind===1?'1':'0';hardware.disabled=sw.kind!==1;const tools=node('details',undefined,'switch-test');tools.open=openSwitchTests.has(String(sw.id));tools.append(node('summary','TEST'),tests,hardware);n.append(tools,node('output',switchTestFeedback.get(sw.id)||'','switch-test-feedback'));return n;
  }));
}
const switchTestFeedback=new Map();
async function testSwitch(id,gesture){
 const before=latest.switches.find(v=>v.id===id)?.actionCount;
 if(!await command({action:'test',switchId:id,gesture}))return;
 await refresh();
 const sw=latest.switches.find(v=>v.id===id);
 const message=sw.conductor?.steps?`STEP ${sw.conductor.step} / ${sw.conductor.steps} · ${sw.conductor.result?({1:'MISSING SOURCE',2:'12 VOICES · REFUSED',3:'UNSAFE SOURCE',4:'UNSUPPORTED',5:'INSTANCE ID LIMIT'}[sw.conductor.result]||'REFUSED'):'ADMITTED '+sw.conductor.admitted}`:sw.actionCount===before?'NO ACTION · OPTIONS':sw.result===2?'EMPTY SEQUENCE / PHRASE · OPTIONS':sw.result===4?'MISSING MODULE TARGET':sw.result===5?'ACTION QUEUE FULL':`ACTION ${sw.lastAction>=101?'SNAPSHOT':({1:'NEXT',2:'STOP',3:'RESET',4:'RESET ALL',5:'STOP + RESET',6:'PANIC'}[sw.lastAction]||'MODULE')} · STEP ${sw.step}`;
 switchTestFeedback.set(id,`${gesture.toUpperCase()} · ${message}`);
 const output=document.querySelector(`[data-switch-id="${id}"] .switch-test-feedback`);if(output)output.textContent=switchTestFeedback.get(id);
}
async function refresh(){try{render(await request('/api/v1/state'));}catch(e){$('connection').textContent='DISCONNECTED · Engine continues independently';$('error').textContent=e.message;}}
function setPending(value){pending=value;for(const b of document.querySelectorAll('main button:not([data-live-release=held])')){if(value){b.dataset.pendingDisabled=b.disabled?'1':'0';b.disabled=true;}else if(b.dataset.pendingDisabled!==undefined){b.disabled=b.dataset.pendingDisabled==='1';delete b.dataset.pendingDisabled;}}}
let commandQueue=Promise.resolve(),uiPointerHeld=false,uiPointerEpoch=0;
document.addEventListener('pointerdown',()=>{++uiPointerEpoch;uiPointerHeld=true;},true);
for(const event of ['pointerup','pointercancel'])document.addEventListener(event,()=>{
  // Keep the real target alive through mouseup/click, not just pointerup.
  // A queued telemetry repaint can otherwise detach it before its action runs.
  const epoch=uiPointerEpoch;
  requestAnimationFrame(()=>requestAnimationFrame(()=>{
    if(epoch!==uiPointerEpoch)return; // A newer gesture owns the guard now.
    uiPointerHeld=false;if(latest&&!pending)render(latest);
  }));
},true);
window.addEventListener('blur',()=>{++uiPointerEpoch;uiPointerHeld=false;});
function command(value){const session=engineSession;const job=commandQueue.then(()=>executeCommand(value,session));commandQueue=job.catch(()=>{});return job;}
async function executeCommand(value,session){while(pending)await new Promise(resolve=>setTimeout(resolve,10));if(session!==engineSession){$('error').textContent='Engine restarted; action cancelled.';return false;}setPending(true);try{render(await request('/api/v1/command',{protocolVersion:1,expectedRevision:revision,expectedEngineSessionId:engineSession,...value}));$('error').textContent='';return true;}catch(e){$('error').textContent=value.action?.startsWith('snapshot_')&&e.message==='unknown_target'?'Recall was not applied: a target is missing or has a legacy expression assignment.':e.message;await refresh();return false;}finally{setPending(false);}}
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
$('clear-patch').onclick=async()=>{if(confirm('Clear the current MBMF patch, including phrases, Controllers, Smart Switch configuration and MBMF snapshots? Saved files and other Zynthian chains stay unchanged.')){if(await command({action:'patch_clear',confirm:true})){renderedModel='';renderedSnapshots='';render(latest);$('patch-status').textContent='CLEARED · SAVE to keep this patch';}}};
$('save-patch').addEventListener('click',()=>patch('save'));$('load-patch').addEventListener('click',()=>patch('load'));
loadDescriptors();refresh();connectStream();setInterval(()=>{if(!pending&&(!ws||ws.readyState!==WebSocket.OPEN))refresh();},1000);
window.addEventListener('blur',()=>window.mbmfHeldRelease?.());
document.addEventListener('visibilitychange',()=>{if(document.hidden)window.mbmfHeldRelease?.();});
// Browser timers only refresh telemetry; they never schedule MIDI.

let decodedControllerWire=null,decodedController=null;
function controllerConfiguration(s=latest){
  const wire=s?.controllerEngine?.configuration;if(!wire)return {sources:[],mappings:[],presets:[]};if(wire===decodedControllerWire)return decodedController;
  const sources=[],mappings=[];
  for(let i=0;i<16;i++){const [id,kind,channel,number]=wire.slice(1+4*i,5+4*i);if(id)sources.push({id,kind,channel:channel+1,number,name:s.controllerEngine.version===2?String.fromCharCode(...wire.slice(2177+i*16,2193+i*16).filter(Boolean)):null});}
  const fields=['id','sourceId','targetId','instrumentId','moduleId','kind','base','priority','takeover','returnMode','easing','threshold','glideSeconds','slewPerSecond','idleSeconds','returnSeconds','enabled','pointCount'];
  for(let i=0;i<32;i++){const record=wire.slice(65+66*i,131+66*i);if(!record[0])continue;const m=Object.fromEntries(fields.map((key,j)=>[key,record[j]]));m.points=Array.from({length:m.pointCount},(_,j)=>record.slice(18+3*j,21+3*j));m.slot=i;mappings.push(m);}
  const presets=s.controllerEngine.version===2?Array.from({length:4},(_,i)=>{const r=wire.slice(2433+i*49,2482+i*49);return Array.from({length:r[0]},(_,j)=>r.slice(1+j*3,4+j*3));}):[];
  decodedControllerWire=wire;return decodedController={sources,mappings,presets};
}
function freshId(used){let id;do{id=crypto.getRandomValues(new Uint32Array(1))[0]&0xffffff;}while(!id||used.includes(id));return id;}
function editControllerSource(source){
 const dialog=$('editor');if(dialog.open)return;const content=$('editor-content');
 content.replaceChildren(node('h2','CONTROLLER'));
 const name=node('input');name.value=source.name||`SOURCE ${source.id}`;name.maxLength=16;name.setAttribute('aria-label','Controller name');content.append(name);
 const error=node('p');error.setAttribute('role','alert');content.append(error);
 content.append(button('DONE',async()=>{if(await command({action:'controller_rename',sourceId:source.id,name:name.value}))dialog.close();else error.textContent=$('error').textContent;}),button('CANCEL',()=>dialog.close()));
 showEditor(dialog);name.focus();
}
const controllerTestValues=new Map();let controllerTestSession=null;
function controllerTestSlider(source){
 const session=engineSession;let desired=null,running=false,timer=null;
 const send=async()=>{clearTimeout(timer);timer=null;if(running)return;running=true;
  try{while(desired!==null){const value=desired;desired=null;controllerTestValues.set(source.id,value);
   for(let attempt=0;attempt<3;++attempt){while(pending)await new Promise(r=>setTimeout(r,10));if(session!==engineSession)return;
    try{render(await request('/api/v1/command',{protocolVersion:1,expectedRevision:revision,expectedEngineSessionId:session,action:'controller_test',sourceId:source.id,value}));break;}
    catch(e){$('error').textContent=e.message;if(e.message!=='conflict')break;await refresh();}
   }
  }}finally{running=false;}
 };
 const change=value=>{desired=value;if(!timer&&!running)timer=setTimeout(send,40);return true;};
 const slider=tactileSlider(`TEST ${source.name||'SOURCE '+source.id}`,controllerTestValues.get(source.id)||0,0,127,source.kind===1?127:1,change,0);
 const rail=slider.querySelector('input'),paint=rail.oninput;rail.oninput=()=>{paint();change(Number(rail.value));};
 rail.title='Manual source test · existing mappings and takeover · no MIDI Learn or assignment changes';slider.classList.add('controller-test-slider');return slider;
}
let renderedControllers='';
function renderControllers(s){
  if(controllerTestSession!==s.engineSessionId){controllerTestSession=s.engineSessionId;controllerTestValues.clear();switchTestFeedback.clear();}
  const key=JSON.stringify([s.engineSessionId,s.controllerEngine,s.controllerLearn]);
  if(key===renderedControllers){for(const m of controllerConfiguration(s).mappings){const feedback=document.querySelector(`[data-mapping-id="${m.id}"] .controller-feedback`),runtime=s.controllerRuntime[m.slot];if(feedback&&runtime)feedback.textContent=`${(runtime.effective*100).toFixed(1)}% · ${runtime.returning?'RETURNING':runtime.pickup?'PICKUP WAIT':runtime.owner?'CONTROLLED':'BASE'}`;}return;}
  renderedControllers=key;
  const {sources,mappings}=controllerConfiguration(s),learn=s.controllerLearn||{};
  $('controllers').replaceChildren(...sources.map(source=>{
    const card=node('article',undefined,'module');card.dataset.sourceId=source.id;
    card.append(editableName('Controller',source.id,source.name,`SOURCE ${source.id}`),node('p',source.kind?`${source.kind===1?'NOTE':'CC'} ${source.number} · CH ${source.channel}`:'UNASSIGNED'));
    card.append(button('EDIT',()=>editControllerSource(source)),button('REMOVE',()=>{if(confirm('Remove this Controller and only its mappings?'))command({action:'controller_remove',sourceId:source.id});}),button('MIDI LEARN',()=>command({action:'controller_learn',sourceId:source.id})));
    if(source.kind){const clear=button('FORGET MIDI',()=>command({action:'controller_forget',sourceId:source.id}));clear.title='Clear physical MIDI assignment only · keep Controller and parameter mappings';card.append(clear);}
    card.append(controllerTestSlider(source));
    if(learn.domain!=='phrase'&&learn.target===source.id){card.append(node('p',learn.conflict<0?'Already assigned to a legacy phrase/switch/controller. CANCEL and choose another input.':learn.conflict>0?`Already assigned to SOURCE ${learn.conflict}. Reassign deliberately?`:'Waiting for MIDI note or CC…'),button('CANCEL LEARN',()=>command({action:'controller_cancel',sourceId:source.id})));if(learn.conflict>0)card.append(button('REASSIGN',()=>command({action:'controller_confirm',sourceId:source.id})));}
    return card;
  }));
  $('mappings').replaceChildren(...mappings.map(m=>{
    const runtime=s.controllerRuntime[m.slot],card=node('article',undefined,'module');card.dataset.mappingId=m.id;
    card.append(node('h3',`SOURCE ${m.sourceId} → ${m.kind===16?'GLOBAL':[14,15,17,18,19,20].includes(m.kind)?'PHRASE':'I'}${m.instrumentId} / ${m.moduleId||parameter(m.kind)?.label||'PARAMETER'} / ${parameter(m.kind)?.label||m.kind}`),node('p',`${(runtime.effective*100).toFixed(1)}% · ${runtime.returning?'RETURNING':runtime.pickup?'PICKUP WAIT':runtime.owner?'CONTROLLED':'BASE'}`,'controller-feedback'),button('EDIT',()=>editMapping(m)),button(m.enabled?'BYPASS':'ENABLE',()=>command({action:'mapping_commit',mapping:{...m,enabled:m.enabled?0:1}})),button('CAPTURE STATE',()=>command({action:'controller_capture',targetId:m.targetId})),button('RETURN',()=>command({action:'controller_return',targetId:m.targetId})),button('REMOVE MAPPING',()=>{if(confirm('Remove only this parameter mapping? The Controller source remains.'))command({action:'mapping_delete',mappingId:m.id});}));
    return card;
  }));
}
function curveEditor(points,options={}){
  const maximum=options.maximum??16;
  const root=node('div'),canvas=node('canvas');canvas.width=400;canvas.height=120;canvas.className='curve-preview';root.append(canvas);
  const precision=node('details');precision.className='curve-precision';precision.append(node('summary','POINTS / PRECISION'));const controls=node('div');precision.append(controls);root.append(precision);
  function draw(){const c=canvas.getContext('2d');c.clearRect(0,0,400,120);c.strokeStyle='#ffe34d';c.beginPath();for(let pixel=0;pixel<=400;pixel++){const x=pixel/400;let y=points[points.length-1][1];for(let i=1;i<points.length;i++)if(x<points[i][0]||(!options.hold?.()&&x===points[i][0])){const a=points[i-1],b=points[i];let t=options.hold?.()?0:(x-a[0])/(b[0]-a[0]),power=1+5*Math.abs(a[2]||0);t=a[2]>0?Math.pow(t,power):a[2]<0?1-Math.pow(1-t,power):t;y=a[1]+(b[1]-a[1])*t;break;}const sy=120*(1-y);if(pixel)c.lineTo(pixel,sy);else c.moveTo(pixel,sy);}c.stroke();c.fillStyle='#ffe34d';for(const p of points){c.beginPath();c.arc(p[0]*400,(1-p[1])*120,4,0,Math.PI*2);c.fill();}}
  function rows(){controls.replaceChildren();points.forEach((p,index)=>{const row=node('div',undefined,'curve-point');(options.linearOnly?['X','Y']:['X','Y','BEND']).forEach((name,k)=>{const label=node('label',name),input=node('input');input.type='number';input.min=k===2?-.98:0;input.max=k===2?.98:1;input.step=.01;input.value=p[k];input.disabled=k===0&&(index===0||index===points.length-1);input.setAttribute('aria-label',`${name} point ${index+1}`);input.addEventListener('input',()=>{p[k]=Number(input.value);draw();});label.append(input);row.append(label);});if(index&&index<points.length-1)row.append(button('REMOVE POINT',()=>{points.splice(index,1);rows();draw();}));controls.append(row);});draw();}
  let dragged=-1;canvas.setAttribute('aria-label','Drag curve points; numeric controls below provide keyboard editing');canvas.style.touchAction='none';
  canvas.onpointerdown=e=>{const r=canvas.getBoundingClientRect(),x=(e.clientX-r.left)/r.width,y=1-(e.clientY-r.top)/r.height;dragged=points.reduce((best,p,i)=>Math.hypot(p[0]-x,p[1]-y)<Math.hypot(points[best][0]-x,points[best][1]-y)?i:best,0);canvas.setPointerCapture(e.pointerId);};
  canvas.onpointermove=e=>{if(dragged<0)return;const r=canvas.getBoundingClientRect(),p=points[dragged];p[1]=Math.max(0,Math.min(1,1-(e.clientY-r.top)/r.height));if(dragged>0&&dragged<points.length-1)p[0]=Math.max(points[dragged-1][0]+.001,Math.min(points[dragged+1][0]-.001,(e.clientX-r.left)/r.width));rows();};canvas.onpointerup=canvas.onpointercancel=()=>dragged=-1;
  root.append(button('ADD POINT',()=>{if(points.length>=maximum)return;let at=1;for(let i=2;i<points.length;i++)if(points[i][0]-points[i-1][0]>points[at][0]-points[at-1][0])at=i;points.splice(at,0,[(points[at-1][0]+points[at][0])/2,(points[at-1][1]+points[at][1])/2,0]);rows();}));rows();
  const presets=node('div',undefined,'curve-presets');root.append(presets);
  const choose=shape=>{points.splice(0,points.length,...structuredClone(shape));rows();};
  for(const preset of (catalog?.curvePresets||[]).filter(p=>!options.linearOnly||p.points.every(p=>!p[2]))){const b=button(preset.name,()=>choose(preset.points));b.prepend(previewCurve(preset.points));presets.append(b);}
  for(let slot=0;!options.linearOnly&&slot<4;slot++){
    const shape=controllerConfiguration().presets[slot];const load=button(`CUSTOM ${slot+1}`,()=>choose(controllerConfiguration().presets[slot]));load.disabled=!shape?.length;presets.append(load);
    presets.append(button(`STORE CUSTOM ${slot+1}`,async()=>{if(await command({action:'curve_preset_store',slot,points:structuredClone(points)})){load.disabled=false;}}));
  }
  canvas.oncontextmenu=e=>e.preventDefault();
  let segment=-1,origin=null;canvas.onpointerdown=e=>{
    const r=canvas.getBoundingClientRect(),x=(e.clientX-r.left)/r.width,y=1-(e.clientY-r.top)/r.height;
    let closest=0;for(let i=1;i<points.length;i++)if(Math.hypot((points[i][0]-x)*r.width,(points[i][1]-y)*r.height)<Math.hypot((points[closest][0]-x)*r.width,(points[closest][1]-y)*r.height))closest=i;
    const distance=Math.hypot((points[closest][0]-x)*r.width,(points[closest][1]-y)*r.height);
    if(e.button===2){e.preventDefault();if(distance<14&&closest>0&&closest<points.length-1){points.splice(closest,1);rows();}return;}
    if((e.altKey||e.shiftKey)&&!options.linearOnly){segment=Math.max(0,points.findIndex(p=>p[0]>x)-1);origin={y:e.clientY,bend:points[segment][2],a:points[segment][1],b:points[segment+1][1],shift:e.shiftKey};dragged=-1;}
    else{segment=-1;if(distance>14&&points.length<maximum&&x>.001&&x<.999){closest=points.findIndex(p=>p[0]>x);points.splice(closest,0,[x,Math.max(0,Math.min(1,y)),0]);}dragged=closest;}
    canvas.setPointerCapture(e.pointerId);rows();
  };
  canvas.onpointermove=e=>{const r=canvas.getBoundingClientRect();if(segment>=0&&origin){const delta=(origin.y-e.clientY)/r.height;if(origin.shift){const offset=Math.max(-Math.min(origin.a,origin.b),Math.min(1-Math.max(origin.a,origin.b),delta));points[segment][1]=origin.a+offset;points[segment+1][1]=origin.b+offset;}else points[segment][2]=Math.max(-.98,Math.min(.98,origin.bend+delta*1.96));rows();}else if(dragged>=0){const p=points[dragged];p[1]=Math.max(0,Math.min(1,1-(e.clientY-r.top)/r.height));if(dragged>0&&dragged<points.length-1)p[0]=Math.max(points[dragged-1][0]+.001,Math.min(points[dragged+1][0]-.001,(e.clientX-r.left)/r.width));rows();}};
  canvas.onpointerup=canvas.onpointercancel=()=>{dragged=-1;segment=-1;origin=null;};
  root.refreshCurve=draw;
  if(!options.linearOnly)root.append(contextualHelp('Click to add · drag points · right-click a point to remove · ALT drag bends a segment · SHIFT drag moves a segment. Numeric point controls support keyboard editing.'));

  return root;
}
function editMapping(existing){
  if(!catalog||!latest||$('editor').open)return;
  const {sources,mappings}=controllerConfiguration();if(!sources.length){$('error').textContent='Add a controller source first.';return;}
  const draft=structuredClone(existing||{id:freshId(mappings.map(m=>m.id)),sourceId:sources[0].id,enabled:1,points:[[0,0,0],[1,1,0]]});
  const capturedRevision=revision,capturedSession=engineSession,mappingFingerprint=JSON.stringify(mappings),dialog=$('editor'),content=$('editor-content');let committing=false;
  const dismiss=()=>{if(!committing)dialog.close();};content.replaceChildren(node('h2',`${parameter(draft.kind)?.label||'MODULATION'} / ${sources.find(s=>s.id===draft.sourceId)?.name||'CONTROLLER'}`),button('×',dismiss));
  const source=node('select');source.setAttribute('aria-label','Controller source');for(const s of sources){const o=node('option',s.name||`SOURCE ${s.id}`);o.value=s.id;source.append(o);}source.value=draft.sourceId;content.append(source);
  const target=node('select');target.setAttribute('aria-label','Controller target');
  const targets=[{instrumentId:1,moduleId:0,kind:16,label:'GLOBAL SNAPSHOT A/B'}];for(const p of latest.phrases)for(const kind of [14,15,17,18,19,20])targets.push({instrumentId:p.id,moduleId:0,kind,label:`PHRASE ${p.id} / ${parameter(kind).label}`});for(const i of latest.instruments){for(const kind of [1,21,22,23])targets.push({instrumentId:i.id,moduleId:0,kind,label:`I${i.id} / ${parameter(kind).label}`});for(const tf of i.transformers){targets.push({instrumentId:i.id,moduleId:tf.id,kind:24,label:`I${i.id} / ${tf.id} ON/OFF`});for(const p of tf.parameters)if(!p.assignment && parameter(p.kind)?.assignmentEligible)targets.push({instrumentId:i.id,moduleId:tf.id,kind:p.kind,label:`I${i.id} / ${tf.id} / ${parameter(p.kind).label}`});}}
  targets.forEach((t,j)=>{const o=node('option',t.label);o.value=j;target.append(o);});let selection=targets.findIndex(t=>t.instrumentId===draft.instrumentId&&t.moduleId===draft.moduleId&&t.kind===draft.kind);target.value=selection<0?targets.findIndex(t=>t.kind===1):selection;content.append(target);
  const advanced=node('details');advanced.append(node('summary','ADVANCED OPTIONS'));
  const descriptor=descriptorForMapping();for(const id of descriptor.parameters){const p=catalog.parameters.find(p=>p.id===id),label=node('label',shortParameter(p.label),'parameter'),input=node(p.choices?'select':'input');if(p.choices){p.choices.forEach((text,value)=>{const option=node('option',text);option.value=value;input.append(option);});}else{input.type='number';input.min=p.min;input.max=p.max;input.step=p.step;}input.setAttribute('aria-label',p.label);input.value=draft[p.policyField]??p.default;draft[p.policyField]=Number(input.value);input.addEventListener('input',()=>draft[p.policyField]=Number(input.value));label.append(input,node('span',p.unit));(p.choices?content:advanced).append(label);}
  content.append(button('MIDI LEARN',()=>command({action:'controller_learn',sourceId:Number(source.value)})),button('CANCEL LEARN',()=>command({action:'controller_cancel',sourceId:Number(source.value)})),advanced,curveEditor(draft.points));
  const error=node('p','');error.setAttribute('role','alert');content.append(error);
  const done=button('DONE',async()=>{if(committing)return;const t=targets[Number(target.value)];if(!t){error.textContent='No eligible target';return;}Object.assign(draft,t);delete draft.label;draft.sourceId=Number(source.value);const same=mappings.find(m=>m.instrumentId===t.instrumentId&&m.moduleId===t.moduleId&&m.kind===t.kind);draft.targetId=same?.targetId||freshId(mappings.map(m=>m.targetId));
    committing=true;done.disabled=cancel.disabled=true;
    try{if(engineSession!==capturedSession||JSON.stringify(controllerConfiguration().mappings)!==mappingFingerprint)throw new Error('Configuration changed. CANCEL and reopen.');render(await request('/api/v1/command',{protocolVersion:1,expectedRevision:revision,expectedEngineSessionId:capturedSession,action:'mapping_commit',mapping:draft}));dialog.close();}catch(e){error.textContent=e.message;}finally{committing=false;done.disabled=cancel.disabled=false;}});
  const cancel=button('CANCEL',dismiss);content.append(done,cancel);dialog.oncancel=e=>{e.preventDefault();dismiss();};dialog.onclick=e=>{const r=dialog.getBoundingClientRect();if(e.target===dialog&&(e.clientX<r.left||e.clientX>r.right||e.clientY<r.top||e.clientY>r.bottom))dismiss();};showEditor(dialog,true);
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
  const outputWrap=node('label','OUTPUT CHANNEL','inline-control'),output=node('select');
  output.setAttribute('aria-label',`OUTPUT CHANNEL Phrase ${phraseId}`);output.title='Playback only · applies on the next trigger';
  for(const [value,label] of [[0,'ORIGINAL'],[17,'ALL'],...Array.from({length:16},(_,i)=>[i+1,`CH${i+1}`])]){const option=node('option',label);option.value=value;output.append(option);}
  output.value=latest.phrases.find(p=>p.id===phraseId)?.outputChannel??0;
  output.onchange=async()=>{if(committing)return;committing=true;output.disabled=true;try{if(!await command({action:'phrase_output',phraseId,channel:Number(output.value)}))output.value=latest.phrases.find(p=>p.id===phraseId)?.outputChannel??0;}finally{committing=false;output.disabled=false;}};
  outputWrap.append(output);content.append(outputWrap);
  const file=node('input');file.type='file';file.accept='.mid,.midi,audio/midi';file.setAttribute('aria-label','MIDI file');
  content.append(button('IMPORT MIDI',()=>file.click()),file,button('EXPORT MIDI',async()=>{
    try{
      const response=await fetch(`/api/v1/phrase/${phraseId}/midi`,{headers:headers()});
      if(!response.ok)throw new Error((await response.json()).error);
      const url=URL.createObjectURL(await response.blob()),link=node('a');link.href=url;link.download=`mbmf-phrase-${String(phraseId).padStart(2,'0')}.mid`;link.click();setTimeout(()=>URL.revokeObjectURL(url),1000);
    }catch(e){error.textContent=e.message;}
  }));
  content.append(button('CLEAR MIDI',async()=>{
    if(committing||!confirm(`Clear MIDI content of Phrase ${phraseId}? Settings are preserved. STOP playback and finish recording first.`))return;
    committing=true;
    try{if(await command({action:'phrase_clear',phraseId}))dialog.close();else error.textContent='Stop playback and finish recording before clearing MIDI.';}
    finally{committing=false;}
  }));
  if(latest.chainMode&&['ARMED','RECORDING','OVERDUB ARMED','OVERDUB ACTIVE'].includes(latest.phrases.find(p=>p.id===phraseId)?.state))content.append(button('CANCEL REC',async()=>{if(!confirm('Discard this recording/overdub take and restore the previous MIDI content?'))return;if(await command({action:'phrase_cancel',phraseId}))dialog.close();}));
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
  dialog.oncancel=e=>{if(committing)e.preventDefault();};dialog.onclick=e=>{const r=dialog.getBoundingClientRect();if(e.target===dialog&&(e.clientX<r.left||e.clientX>r.right||e.clientY<r.top||e.clientY>r.bottom))dismiss();};showEditor(dialog);
}
let phrasePage=0;
function liveParameter(targetId,kind,value,moduleId=0){return command({action:'parameter_set',targetId,moduleId,kind,value});}
function editableName(domain,id,value,fallback){
  const control=button(value||fallback,()=>{
    if(pending)return;
    const input=node('input');input.value=value||'';input.maxLength=16;
    input.className='name-input';input.setAttribute('aria-label',`${domain} ${id} name`);
    const capturedSession=engineSession,capturedRevision=revision;
    control.replaceWith(input);input.focus();input.select();
    let finished=false;
    const cancel=()=>{if(finished)return;finished=true;input.replaceWith(control);control.focus();};
    input.onkeydown=async event=>{
      if(event.key==='Escape'){event.preventDefault();cancel();}
      if(event.key==='Enter'){
        event.preventDefault();if(finished)return;
        if([...input.value].some(c=>c.charCodeAt(0)<32||c.charCodeAt(0)>126)){
          $('error').textContent='Names use up to 16 printable ASCII characters, matching REAPER.';return;
        }
        finished=true;input.disabled=true;input.blur();
        const ok=await command({action:domain==='Controller'?'controller_rename':domain==='Phrase'?'phrase_rename':'instrument_rename',
          [domain==='Controller'?'sourceId':domain==='Phrase'?'phraseId':'instrumentId']:id,name:input.value,
          expectedRevision:capturedRevision,expectedEngineSessionId:capturedSession});
        if(!ok){finished=false;input.disabled=false;input.focus();}
        else document.querySelector(`[data-${domain.toLowerCase()}-id="${id}"] .editable-name`)?.focus();
      }
    };
    input.onblur=()=>{if(!finished)cancel();};
  });
  control.replaceChildren(node('span',value||fallback,'name-text'));
  control.className='editable-name';control.setAttribute('aria-label',`Edit ${domain} ${id} name`);
  control.title='Click to rename · Enter saves · Escape cancels · 16 characters';return control;
}
async function finishRecording(phraseId){return command({action:'phrase_finish',phraseId});}
let recordingShortcutBusy=false;
document.addEventListener('keydown',event=>{
 if(!['Enter',' '].includes(event.key)||event.altKey||event.ctrlKey||event.metaKey||event.shiftKey||event.isComposing||event.defaultPrevented)return;
 if(document.querySelector('dialog[open],.assignment-menu')||event.target.closest('input,textarea,select,button,summary,[contenteditable]:not([contenteditable="false"]),[role="button"]'))return;
 const candidates=(latest?.phrases||[]).filter(p=>['RECORDING','OVERDUB ACTIVE'].includes(p.state));
 const active=latest?.chainMode?candidates.find(p=>p.id===latest.chainPhraseId):candidates.length===1?candidates[0]:null;
 if(!active)return;
 event.preventDefault();if(event.repeat||recordingShortcutBusy)return;
 recordingShortcutBusy=true;const session=engineSession;
 (async()=>{try{while(pending)await new Promise(r=>setTimeout(r,10));if(session===engineSession&&['RECORDING','OVERDUB ACTIVE'].includes(latest.phrases.find(p=>p.id===active.id)?.state))await finishRecording(active.id);}finally{recordingShortcutBusy=false;}})();
});
function paintPhraseStates(s){for(const p of s.phrases||[]){const row=document.querySelector(`[data-phrase-id="${p.id}"]`);if(!row)continue;row.dataset.state=p.state||'IDLE';const play=row.querySelector('[data-phrase-play]');if(play){const stop=p.state==='PLAYING' && p.mode===0;play.dataset.running=String(stop);const scoped=s.chainMode&&(p.mode===2||s.chainCaptureMode==='free-time');play.setAttribute('aria-label',stop?(scoped?'STOP PHRASE':'GLOBAL STOP'):'TRIGGER');play.title=stop?(scoped?'Stop this phrase':'Legacy grid: stop this processor'):p.mode===2?(s.nativePhraseContract>=2?'HOLD: sustain notes; press again to cut and restart; release ignored':'Hold to repeat; release stops'):'Play phrase';const path=play.querySelector('path');if(path)path.setAttribute('d',iconPaths[stop?'stop':'play']);}const state=row.querySelector('.phrase-state');if(state)state.textContent=p.state||'IDLE';const rec=row.querySelector('[aria-label="REC / OVERDUB"]');if(rec){rec.dataset.state=p.state;rec.title=`REC / OVERDUB · ${p.state||'IDLE'}`;rec.setAttribute('aria-pressed',String(['ARMED','RECORDING','OVERDUB ARMED','OVERDUB ACTIVE'].includes(p.state)));}}}
function compactPhrases(s){
  const pages=Math.ceil(s.phrases.length/6);phrasePage=Math.min(phrasePage,pages-1);
  $('phrase-pagination').replaceChildren(button('←',()=>{phrasePage=Math.max(0,phrasePage-1);renderedModel='';render(latest);}),node('span',`${phrasePage+1} / ${pages}`),button('→',()=>{phrasePage=Math.min(pages-1,phrasePage+1);renderedModel='';render(latest);}));
  if(!$('phrase-columns')){const head=node('div',undefined,'phrase-columns');head.id='phrase-columns';for(const text of ['#','NAME','PLAY','REC','M','S','MODE','VEL','V.DEC','T.DEC','MIDI','END','EDIT'])head.append(node('span',text));$('phrases').before(head);}
  $('phrases').replaceChildren(...s.phrases.slice(phrasePage*6,phrasePage*6+6).map(p=>{
    const row=node('div',undefined,'phrase');row.dataset.phraseId=p.id;row.dataset.state=p.state||'IDLE';row.classList.toggle('empty',!p.events);row.classList.toggle('muted',!!p.mute);row.classList.toggle('soloed',!!p.solo);row.append(node('span',String(p.id).padStart(2,'0'),'phrase-number'));
    const heldMode=!!s.chainMode&&!!s.nativeHeldRelease&&p.mode===2;
    const trigger=button('TRIGGER',()=>{if(!heldMode)command({action:latest.phrases.find(v=>v.id===p.id)?.state==='PLAYING'&&p.mode===0?(latest.chainMode&&latest.chainCaptureMode==='free-time'?'phrase_stop':latest.chainMode?'chain_stop':'panic'):'phrase_play',phraseId:p.id});});trigger.dataset.phrasePlay='true';
    if(heldMode){
      let held=false,edge=Promise.resolve();
      const send=action=>{edge=edge.then(async()=>{while(pending)await new Promise(resolve=>setTimeout(resolve,10));return command({action,phraseId:p.id});});};
      let stopping=false;const press=()=>{if(latest.phrases.find(v=>v.id===p.id)?.state==='PLAYING'){stopping=true;send('phrase_stop');return;}stopping=false;if(!held){held=true;trigger.dataset.liveRelease='held';window.mbmfHeldRelease=release;send('phrase_play');}};
      const release=()=>{if(stopping){stopping=false;return;}if(held){held=false;if(window.mbmfHeldRelease===release)window.mbmfHeldRelease=null;delete trigger.dataset.liveRelease;send('phrase_release');}};
      trigger.onpointerdown=e=>{if(e.button!==0)return;e.preventDefault();trigger.setPointerCapture(e.pointerId);press();};
      trigger.onpointerup=release;trigger.onpointercancel=release;trigger.onlostpointercapture=release;
      trigger.onkeydown=e=>{if([' ','Enter'].includes(e.key)){e.preventDefault();press();}};
      trigger.onkeyup=e=>{if([' ','Enter'].includes(e.key)){e.preventDefault();release();}};trigger.onblur=release;
      trigger.title='HOLD: repeat while pressed; release stops owned phrase notes';
    }
    trigger.disabled=!!s.chainMode&&!s.nativeHeldRelease&&!(s.nativePhraseContract>=2)&&p.mode===2;
    if(trigger.disabled)trigger.title='Legacy HOLD data is preserved. STOP and choose LOOP or ONCE; native held release is not implemented.';
    row.append(button('REC / OVERDUB',()=>command({action:'phrase_record',phraseId:p.id})),trigger,editableName('Phrase',p.id,p.name,`PHRASE ${p.id}`));
    const learning=s.controllerLearn?.domain==='phrase'&&s.controllerLearn.target===p.id;
    const learn=button(learning?'CANCEL LEARN':p.triggerNote>=0?`LEARN · CH${p.triggerChannel||'ANY'} N${p.triggerNote}`:'TRIGGER LEARN',()=>command({action:learning?'phrase_learn_cancel':'phrase_learn',phraseId:p.id}));
    learn.title=learning?'Cancel Learn · waiting for MIDI note':p.triggerNote>=0?`NOTE ${p.triggerNote} · CH ${p.triggerChannel||'ANY'}`:'Unassigned phrase trigger';row.append(learn);
    if(learning&&s.controllerLearn.conflict){row.append(node('small',s.controllerLearn.conflict<0?'Already assigned to a phrase/switch. Cancel or choose a different note.':'Already assigned to a Controller source.'));
      if(s.controllerLearn.conflict>0)row.append(button('REASSIGN',()=>command({action:'phrase_learn_confirm',phraseId:p.id})));}
    row.append(button(p.solo?'SOLO ON':'SOLO',()=>liveParameter(p.id,19,p.solo?0:1)),button(p.mute?'MUTE ON':'MUTE',()=>liveParameter(p.id,18,p.mute?0:1)));
    const mode=node('select');mode.setAttribute('aria-label',`Play mode Phrase ${p.id}`);
    for(const [value,label] of [[1,'ONCE'],[0,'LOOP'],[2,'HOLD']]){const option=node('option',label);option.value=value;option.disabled=!!s.chainMode&&!s.nativeHeldRelease&&!(s.nativePhraseContract>=2)&&value===2;if(option.disabled)option.textContent='HOLD (UNAVAILABLE)';if(option.disabled)option.title='Native held-trigger release is not supported yet';mode.append(option);}mode.value=p.mode;mode.title=s.chainMode?'LOOP: press to play / stop · ONCE: independent one-shot · HOLD: sustain; press again cuts and restarts; release ignored (polyphonic, no ARP)':'REAPER legacy HOLD sustains notes until STOP / next phrase';bindModulation(mode,{instrumentId:p.id,moduleId:0,kind:20});mode.onchange=async()=>{if(await liveParameter(p.id,20,Number(mode.value))&&latest.chainMode&&latest.chainRunning)$('error').textContent='Mode change queued. STOP this processor to apply safely.';};row.append(mode);
    row.append(tactileSlider(`BASE VEL Phrase ${p.id}`,p.baseVelocity,.2,3,.01,value=>liveParameter(p.id,17,value),1,false,{instrumentId:p.id,moduleId:0,kind:17}));
    if(p.mode===1)row.append(tactileSlider(`VEL DECAY Phrase ${p.id}`,p.velocityDecay,.2,1,.01,value=>liveParameter(p.id,15,value),.8,false,{instrumentId:p.id,moduleId:0,kind:15}),tactileSlider(`TIME DECAY Phrase ${p.id}`,p.timeDecay,.5,2,.01,value=>liveParameter(p.id,14,value),1,true,{instrumentId:p.id,moduleId:0,kind:14}));
    const finish=button('FINISH REC',()=>finishRecording(p.id));finish.title='Finish record / overdub without discarding the take';row.append(finish,node('small',`${p.events} events`),button('PHRASE OPTIONS',()=>phraseOptions(p.id)));
    const buttons=[...row.querySelectorAll('button')],find=label=>buttons.find(b=>b.getAttribute('aria-label')===label),rails=[...row.querySelectorAll('.tactile-slider')];
    for(const rail of rails){rail.dataset.shortLabel=rail.querySelector('.slider-caption').textContent;rail.querySelector('.slider-caption').remove();}
    const empty=()=>{const n=node('span','—','decay-empty');n.title='Decay controls are available in ONCE mode';return n;};
    const cells=[row.querySelector('.phrase-number'),row.querySelector('.editable-name'),trigger,find('REC / OVERDUB'),buttons.find(b=>/^MUTE/.test(b.getAttribute('aria-label'))),buttons.find(b=>/^SOLO/.test(b.getAttribute('aria-label'))),mode,rails[0],rails[1]||empty(),rails[2]||empty(),learn,finish,find('PHRASE OPTIONS')];
    const notices=[...row.children].filter(n=>!cells.includes(n)&&n.tagName==='SMALL'&&!n.textContent.endsWith(' events'));
    const grouped=node('div',undefined,'phrase-rails');grouped.append(...cells.slice(7,10));row.replaceChildren(...cells.slice(0,7),grouped,...cells.slice(10));row.querySelector('.phrase-number').title=`Phrase ${p.id} · ${p.events} source events`;row.querySelector('.phrase-number').setAttribute('aria-label',row.querySelector('.phrase-number').title);for(const notice of notices){notice.classList.add('phrase-alert');row.append(notice);}const reassign=find('REASSIGN');if(reassign){reassign.classList.add('phrase-alert');row.append(reassign);}
    const state=node('small',p.state||'IDLE','phrase-state');row.querySelector('.editable-name').append(state);
    return row;
  }));
}
// A blank is a transactional editor draft, not an unsupported engine type.
function addEmptyTransformer(i){
 const dialog=$('editor');if(dialog.open)return;const session=engineSession;
 const content=$('editor-content');content.replaceChildren(node('h2',`${i.name||'INSTRUMENT '+i.id} / EMPTY TRANSFORMER`));
 const select=node('select');select.setAttribute('aria-label','Blank Transformer type');
 const blank=node('option','CHOOSE TYPE');blank.value='';select.append(blank);
 for(const d of catalog.modules.filter(m=>m.engineType>0&&(catalog.runtimeCapabilities?.transformerTypes||[1,2,3,4,5,6]).includes(m.engineType))){const o=node('option',d.label);o.value=d.engineType;select.append(o);}
 const error=node('p');error.setAttribute('role','alert');
 const done=button('DONE',async()=>{if(session!==engineSession){error.textContent='Engine restarted; CANCEL and reopen.';return;}const before=new Set(latest.instruments.find(v=>v.id===i.id)?.transformers.map(t=>t.id)||[]);
  if(await command({action:'module_structure',instrumentId:i.id,operation:'add',engineType:Number(select.value)})){
   const instrument=latest.instruments.find(v=>v.id===i.id),module=instrument?.transformers.find(t=>!before.has(t.id));dialog.close();if(module)await editModule(instrument,module);
  }else error.textContent=$('error').textContent;
 });done.disabled=true;select.onchange=()=>done.disabled=!select.value;
 content.append(select,error,done,button('CANCEL',()=>dialog.close()));showEditor(dialog);select.focus();
}
function compactInstrument(i){
  const n=node('article',undefined,'instrument');n.dataset.instrumentId=i.id;
  const main=node('div',undefined,'instrument-main');
  const enable=button(i.enabled?'ON':'OFF',()=>liveParameter(i.id,21,i.enabled?0:1));enable.setAttribute('aria-pressed',String(!!i.enabled));bindModulation(enable,{instrumentId:i.id,moduleId:0,kind:21});main.append(enable,editableName('Instrument',i.id,i.name,`INSTRUMENT ${i.id}`));
  for(const [label,kind,current,zero] of [['MIDI IN',22,i.input,'ALL'],['MIDI OUT',23,i.output,'ORIGINAL']]){
    const wrap=node('label',label==='MIDI IN'?'IN':'OUT','inline-control'),select=node('select');select.setAttribute('aria-label',`${label} Instrument ${i.id}`);
    for(let channel=0;channel<=16;channel++){const option=node('option',channel?String(channel):zero);option.value=channel;select.append(option);}select.value=current;select.onchange=()=>liveParameter(i.id,kind,Number(select.value));wrap.append(select);main.append(wrap);bindModulation(select,{instrumentId:i.id,moduleId:0,kind});
  }
  main.append(tactileSlider(`VOLUME Instrument ${i.id}`,i.level,0,127,1,value=>liveParameter(i.id,1,value),parameter(1)?.default??127,false,{instrumentId:i.id,moduleId:0,kind:1}),button('×',()=>{if(confirm(`Delete Instrument ${i.id} and its complete Transformer chain?`))command({action:'instrument_delete',instrumentId:i.id});}));n.append(main);
  const chain=node('div',undefined,'transformers');
  for(const tf of i.transformers||[]){
    const card=node('article',undefined,'module');card.dataset.moduleId=tf.id;card.classList.toggle('bypassed',!tf.enabled);card.classList.toggle('selected',selectedModule?.instrumentId===i.id&&selectedModule.moduleId===tf.id);
    card.append(node('strong',`${descriptor(tf.type)?.label||'MODULE'}`),node('small',tf.enabled?'ON':'BYPASS'),button('EDIT',()=>editModule(i,tf)));
    for(const p of tf.parameters||[]){const d=parameter(p.kind);if(!d)continue;if(p!==tf.parameters[0])continue;const meter=node('meter');meter.min=d.min;meter.max=d.max;meter.value=p.value;meter.title=`${d.label}: ${p.value}${p.assignment?' · EXPRESSION '+p.assignment:''}`;meter.setAttribute('aria-label',meter.title);const feedback=node('div',undefined,'module-feedback');feedback.append(node('small',shortParameter(d.label)),meter,node('output',tf.type===6?`CC${tf.parameters.find(v=>v.kind===13)?.value??0}`:musicalValue(d,p.value)));card.append(feedback);}
    for(const [label,operation] of [['BYPASS','bypass'],['↑','up'],['↓','down'],['DELETE','delete']]){
      if(operation==='up'||operation==='down'){
        const index=i.transformers.indexOf(tf),other=i.transformers[index+(operation==='up'?-1:1)];
        if(!i.serialPitchOrder||![1,2].includes(tf.type)||!other||![1,2].includes(other.type))continue;
      }
      card.append(button(label,()=>{if(operation==='delete'&&!confirm('Delete this Transformer?'))return;command({action:'module_structure',instrumentId:i.id,moduleId:tf.id,operation});}));
    }card.querySelector('[aria-label="BYPASS"]')?.setAttribute('aria-pressed',String(!tf.enabled));chain.append(card);
  }
  const select=node('select');select.setAttribute('aria-label',`Transformer type for Instrument ${i.id}`);
  const blank=node('option','+ ADD EMPTY TRANSFORMER');blank.value='empty';select.append(blank);
  for(const d of catalog?.modules.filter(m=>m.engineType>0&&(catalog.runtimeCapabilities?.transformerTypes||[1,2,3,4,5,6]).includes(m.engineType))||[]){const option=node('option',d.label);option.value=d.engineType;select.append(option);}
  select.value=catalog?.modules.find(m=>m.engineType>0&&(catalog.runtimeCapabilities?.transformerTypes||[1,2,3,4,5,6]).includes(m.engineType))?.engineType??'empty';
  const chosen=transformerChoices.get(i.id);
  if([...select.options].some(option=>option.value===chosen))select.value=chosen;
  select.onchange=()=>transformerChoices.set(i.id,select.value);
  chain.title=i.serialPitchOrder?'Serial pitch order · Velocity → Polyphony → ARP; CC separate':'Legacy stages: Transpose → Range → Velocity → Polyphony → ARP; CC separate';chain.append(select,button('ADD TRANSFORMER',async()=>{if(select.value==='empty'){addEmptyTransformer(i);return;}await command({action:'module_structure',instrumentId:i.id,operation:'add',engineType:Number(select.value)});}),button('EDIT',()=>editInstrument(i)));n.append(chain);return n;
}

$('add-instrument').onclick=()=>command({action:'instrument_add'});

// Explicit inspection avoids extra state-copy work on every websocket update.
let projectAuthority=null;
async function inspectProject(){
  projectAuthority=await request('/api/v1/project/status');
  const state=projectAuthority;
  $('project-status').textContent=(state.savedRevisionId?`RESTART ${state.savedRevisionId.slice(0,8)}`:'NO COMMITTED RESTART STATE')+
    (state.liveMatchesRestart===true?' · SAVED':state.liveMatchesRestart===false?' · LIVE NOT COMMITTED':' · CHECK DEFERRED UNTIL STOP')+
    ' · Zynthian snapshot overrides';
  return state;
}
$('inspect-project').onclick=async()=>{try{await inspectProject();}catch(e){$('error').textContent=e.message;}};
$('commit-project').onclick=async()=>{
  if(pending)return;setPending(true);
  try{
    const state=await inspectProject();
    await request('/api/v1/project/checkpoint',{expectedActiveRevisionId:state.savedRevisionId,expectedRevision:state.engineRevision??revision,expectedEngineSessionId:state.engineSessionId??engineSession});
    await inspectProject();$('patch-status').textContent='RESTART STATE COMMITTED';
  }catch(e){$('error').textContent=e.message;}finally{setPending(false);}
};

$('stop-native').onclick=()=>command({action:'chain_stop'});

for(const id of ['stop-native','save-patch','load-patch','add-instrument','add-controller','add-mapping'])decorateButton($(id),$(id).textContent);

for(const id of ['stop-native','save-patch','load-patch','add-instrument','add-controller','add-mapping']){const b=$(id);compactAction(b,b.getAttribute('aria-label')||b.textContent);}
