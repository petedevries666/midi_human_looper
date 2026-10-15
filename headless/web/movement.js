'use strict';
// All authoring is a stopped native CAS transaction; drafts are never telemetry.
let movementModel=null,movementRevision=-1,movementSession=0,movementLoading=false;
function movementUUID(){const b=crypto.getRandomValues(new Uint8Array(16));b[6]=(b[6]&15)|64;b[8]=(b[8]&63)|128;const h=[...b].map(x=>x.toString(16).padStart(2,'0')).join('');return `${h.slice(0,8)}-${h.slice(8,12)}-${h.slice(12,16)}-${h.slice(16,20)}-${h.slice(20)}`;}
function upgradeMovementModel(model){const m=model?structuredClone(model):{version:1,sources:latest.phrases.map(p=>({id:movementUUID(),type:'PHRASE',slot:p.id})),switches:[]};m.version=2;m.movements??=[];m.ccRate??=25;return m;}
async function saveMovementModel(model,loaded){
 if(engineSession!==loaded.engineSessionId)throw new Error('Engine changed; reopen');
 render(await request('/api/v1/command',{protocolVersion:1,expectedRevision:loaded.revision,expectedEngineSessionId:loaded.engineSessionId,action:'conductor_commit',conductor:model}));
 const actual=await request('/api/v1/conductor');movementModel=actual.model;movementRevision=actual.revision;movementSession=actual.engineSessionId;paintMovementLibrary();return actual;
}
async function refreshMovements(state){
 const running=state.movements?.running||[];for(const row of $('movements').children){const v=running.find(v=>v.id===row.dataset.movementId);row.classList.toggle('movement-active',!!v);const o=row.querySelector('.movement-state');if(o)o.textContent=v?`${Math.round(v.progress*100)}%`:'STOPPED';}
 if(uiPointerHeld||pending||movementLoading||(state.revision===movementRevision&&state.engineSessionId===movementSession))return;
 movementLoading=true;try{const loaded=await request('/api/v1/conductor');if(engineSession===loaded.engineSessionId){movementModel=loaded.model;movementRevision=loaded.revision;movementSession=loaded.engineSessionId;paintMovementLibrary();}}catch(e){}finally{movementLoading=false;}
}
function paintMovementLibrary(){
 const root=$('movements');root.replaceChildren();$('movement-rate').value=movementModel?.ccRate||25;
 for(const m of movementModel?.movements||[]){const row=node('div',undefined,'movement-row');row.dataset.movementId=m.id;
  const preview=previewCurve(m.points.map(p=>[...p,0]),m.interpolation==='HOLD');preview.setAttribute('aria-label',`${m.name} curve`);
  row.append(node('strong',m.name),preview,node('output','STOPPED','movement-state'),node('output',`${m.duration}s · ${m.target.type==='CC'?`CH${m.target.channel} CC${m.target.number}`:'PARAM'}`),button('EDIT',()=>editMovement(m.id)),button('▶',()=>command({action:'movement_preview',movementId:m.id})),button('■',()=>command({action:'movement_stop',movementId:m.id})),button('×',async()=>{
   if(!confirm(`Delete ${m.name}? References will remain missing.`))return;try{const loaded=await request('/api/v1/conductor'),model=upgradeMovementModel(loaded.model);model.movements=model.movements.filter(v=>v.id!==m.id);await saveMovementModel(model,loaded);}catch(e){$('error').textContent=e.message;}
  }));const names=['PREVIEW MOVEMENT','STOP MOVEMENT','DELETE MOVEMENT'];[...row.querySelectorAll('button')].slice(1).forEach((b,i)=>{b.setAttribute('aria-label',`${names[i]} ${m.name}`);b.title=names[i];});root.append(row);
 }
}
async function editMovement(id=null){
 const dialog=$('editor');if(dialog.open)return;let loaded;try{loaded=await request('/api/v1/conductor');}catch(e){$('error').textContent=e.message;return;}
 const model=upgradeMovementModel(loaded.model),existing=model.movements.find(m=>m.id===id);if(id&&!existing)return;
 const draft=structuredClone(existing||{id:movementUUID(),name:'MOVEMENT',target:{type:'CC',channel:1,number:11},points:[[0,0],[1,1]],duration:2.5,interpolation:'LINEAR',retrigger:'SOFT_RESTART',glideSeconds:.2});
 const content=$('editor-content');content.replaceChildren();const root=node('div',undefined,'movement-editor');content.append(root);root.append(node('h2','MOVEMENT'));
 const row=(name,input)=>{const label=node('label',name);input.setAttribute('aria-label',name);label.append(input);root.append(label);return input;};
 const input=(type,value,min=null,max=null)=>{const i=node('input');i.type=type;i.value=value;if(min!==null)i.min=min;if(max!==null)i.max=max;if(type==='number')i.step=.01;return i;};
 const select=(values,value)=>{const i=node('select');for(const v of values){const o=node('option',v);o.value=v;i.append(o);}i.value=value;return i;};
 const name=row('NAME',input('text',draft.name));
 const kind=row('TARGET TYPE',select(['CC','PARAMETER'],draft.target.type));const targets=node('div',undefined,'movement-target');root.append(targets);
 const channel=input('number',draft.target.channel??1,1,16),number=input('number',draft.target.number??11,0,119);channel.step=number.step=1;
 const parameters=node('select');parameters.setAttribute('aria-label','MOVEMENT PARAMETER');const eligible=[];
 for(const p of latest.phrases)for(const k of [14,15,17])eligible.push({type:'PARAMETER',instrumentId:p.id,moduleId:0,kind:k,label:`P${p.id} ${parameter(k).label}`});
 for(const i of latest.instruments){eligible.push({type:'PARAMETER',instrumentId:i.id,moduleId:0,kind:1,label:`I${i.id} VOL`});for(const tf of i.transformers)for(const p of tf.parameters)if(!p.assignment)eligible.push({type:'PARAMETER',instrumentId:i.id,moduleId:tf.id,kind:p.kind,label:`I${i.id} ${tf.id} ${parameter(p.kind).label}`});}
 eligible.forEach((t,j)=>{const o=node('option',t.label);o.value=j;parameters.append(o);});parameters.value=Math.max(0,eligible.findIndex(t=>t.instrumentId===draft.target.instrumentId&&t.moduleId===draft.target.moduleId&&t.kind===draft.target.kind));
 function targetUI(){targets.replaceChildren();if(kind.value==='CC'){for(const [name,i] of [['CHANNEL',channel],['CC',number]]){const l=node('label',name);i.setAttribute('aria-label',name);l.append(i);targets.append(l);}targets.append(node('small','MAIN MIDI OUT'));}else targets.append(parameters);}
 kind.onchange=targetUI;targetUI();
 const duration=row('DURATION s',input('number',draft.duration,.001)),interpolation=row('INTERPOLATION',select(['LINEAR','HOLD'],draft.interpolation)),restart=row('RETRIGGER',select(['SOFT_RESTART','DIRECT'],draft.retrigger)),glide=row('GLIDE s',input('number',draft.glideSeconds,.001,60));
 const points=draft.points.map(p=>[...p,0]);const curve=curveEditor(points,{linearOnly:true,maximum:Infinity,hold:()=>interpolation.value==='HOLD'});root.append(curve);interpolation.onchange=()=>root.querySelector('.movement-curve')?.refreshCurve();
 const preset=node('div',undefined,'curve-presets');for(const [name,shape] of [['RAMP UP',[[0,0,0],[1,1,0]]],['RAMP DOWN',[[0,1,0],[1,0,0]]],['STAIRS',[[0,0,0],[.25,.25,0],[.5,.5,0],[.75,.75,0],[1,1,0]]]])preset.append(button(name,()=>{points.splice(0,points.length,...structuredClone(shape));if(name==='STAIRS')interpolation.value='HOLD';const next=curveEditor(points,{linearOnly:true,maximum:Infinity,hold:()=>interpolation.value==='HOLD'});root.querySelector('.movement-curve')?.replaceWith(next);next.classList.add('movement-curve');}));curve.classList.add('movement-curve');root.append(preset);
 const error=node('p','');error.setAttribute('role','alert');root.append(error);let committing=false;
 const done=button('DONE',async()=>{if(committing)return;committing=true;const controls=[...root.querySelectorAll('button,input,select')],disabled=controls.map(c=>c.disabled);controls.forEach(c=>c.disabled=true);
  try{Object.assign(draft,{name:name.value,duration:Number(duration.value),interpolation:interpolation.value,retrigger:restart.value,glideSeconds:Number(glide.value),points:points.map(p=>p.slice(0,2))});if(kind.value==='CC'){draft.target={type:'CC',channel:Number(channel.value),number:Number(number.value)};if(draft.target.number===64)throw new Error('CC64 is reserved for sustain safety');}else{const target=eligible[Number(parameters.value)];if(!target)throw new Error('No eligible parameter');draft.target={...target};delete draft.target.label;}
   if(existing)model.movements[model.movements.findIndex(m=>m.id===id)]=draft;else model.movements.push(draft);await saveMovementModel(model,loaded);dialog.close();
  }catch(e){error.textContent=e.message+' · STOP/PANIC before DONE; draft retained';}finally{committing=false;controls.forEach((c,i)=>c.disabled=disabled[i]);}
 });root.append(done,button('CANCEL',()=>{if(!committing)dialog.close();}));dialog.oncancel=e=>{if(committing)e.preventDefault();};dialog.onclick=e=>{const r=dialog.getBoundingClientRect();if(!committing&&e.target===dialog&&(e.clientX<r.left||e.clientX>r.right||e.clientY<r.top||e.clientY>r.bottom))dialog.close();};showEditor(dialog,true);
}
$('add-movement').onclick=()=>editMovement();
$('movement-rate').onchange=async e=>{const value=Number(e.target.value);e.target.disabled=true;try{const loaded=await request('/api/v1/conductor'),model=upgradeMovementModel(loaded.model);model.ccRate=value;await saveMovementModel(model,loaded);}catch(error){$('error').textContent=error.message;paintMovementLibrary();}finally{e.target.disabled=false;}};
