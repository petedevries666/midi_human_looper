'use strict';
// C's versioned model, D's execution. Only the stopped, guarded native commit writes it.
let conductorView=null;
function paintConductorRuntime(state){
 if(!conductorView)return;
 const runtime=state.switches.find(s=>s.id===conductorView.switchId)?.conductor;
 const unchanged=state.engineSessionId===conductorView.session&&state.revision===conductorView.revision;
 conductorView.root.querySelectorAll('[data-step-position]').forEach(el=>el.classList.toggle('active-step',unchanged&&Number(el.dataset.stepPosition)===runtime?.step));
 conductorView.status.textContent=!unchanged?'CONFIGURATION CHANGED · reopen before DONE':runtime?.result?({1:'MISSING SOURCE',2:'12 VOICES · REFUSED',3:'UNSAFE SOURCE',4:'UNSUPPORTED',5:'INSTANCE ID LIMIT'}[runtime.result]||'REFUSED'):`ACTIVE ${runtime?.step||'—'} / ${runtime?.steps||0}`;
}
async function editConductor(sw){
 const dialog=$('editor');if(dialog.open)return;
 let loaded;try{loaded=await request('/api/v1/conductor');}catch(e){$('error').textContent=e.message;return;}
 if(dialog.open)return;
 const session=loaded.engineSessionId,rev=loaded.revision;
 const uuid=()=>{const bytes=crypto.getRandomValues(new Uint8Array(16));bytes[6]=(bytes[6]&15)|64;bytes[8]=(bytes[8]&63)|128;const hex=[...bytes].map(b=>b.toString(16).padStart(2,'0'));return [hex.slice(0,4),hex.slice(4,6),hex.slice(6,8),hex.slice(8,10),hex.slice(10)].map(part=>part.join('')).join('-');};
 const model=loaded.model?structuredClone(loaded.model):{version:1,sources:latest.phrases.map(p=>({id:uuid(),type:'PHRASE',slot:p.id})),switches:[]};
 let sequence=model.switches.find(s=>s.switchId===sw.id);
 if(!sequence){sequence={switchId:sw.id,traversal:'SEQUENTIAL',transition:'IMMEDIATE',gesture:'INSTANT',steps:[]};model.switches.push(sequence);}
 const content=$('editor-content');content.replaceChildren();
 const root=node('div',undefined,'conductor-editor');content.append(root);
 const heading=node('div',undefined,'conductor-toolbar');heading.append(node('h2',`${sw.name||'SWITCH '+sw.id} / CONDUCTOR`));root.append(heading);
 const status=node('output','','conductor-status'),error=node('p','','conductor-error');error.setAttribute('role','alert');root.append(status,error);
 const board=node('div',undefined,'conductor-board'),side=node('aside',undefined,'conductor-properties');root.append(board,side);
 let selected=null,editing=null,committing=false,history=[],drag=null;
 const layer=()=>({id:uuid(),block:null}),step=()=>({id:uuid(),transition:'INHERIT',layers:[layer(),layer()]});
 let empty=step();
 const checkpoint=()=>{history.push(structuredClone(sequence.steps));editing=null;error.textContent='';};
 const change=fn=>{checkpoint();fn();paint();};
 const source=b=>b?.type==='MOVEMENT'?model.movements?.find(s=>s.id===b.sourceId):model.sources.find(s=>s.id===b?.sourceId&&s.type===b?.type);
 const phrase=b=>latest.phrases.find(p=>p.id===source(b)?.slot);
 const label=b=>{if(b.type==='MOVEMENT'){const m=source(b);return m?`MOVEMENT · ${m.name}`:`MISSING · ${b.sourceId}`;}if(b.type!=='PHRASE')return `${b.type} · UNAVAILABLE · ${b.sourceId||''}`;const p=phrase(b);return p?`${String(p.id).padStart(2,'0')} · ${p.name||'PHRASE '+p.id}${p.events?'':' · EMPTY'}`:`MISSING · ${b.sourceId||b.type}`;};
 const mode=b=>b.overrides?.playMode?.mode==='OVERRIDE'?b.overrides.playMode.value:['LOOP','ONCE','HOLD'][phrase(b)?.mode]||'—';
 const ensure=s=>{if(!sequence.steps.includes(s))sequence.steps.push(s);};
 const action=(name,fn)=>{const control=button({'EDIT BLOCK':'EDIT','REMOVE BLOCK':'DELETE'}[name]||name,()=>{if(!committing)fn();});control.setAttribute('aria-label',name);control.title=name;return control;};
 const removeMenu=()=>root.querySelector('.conductor-add-menu')?.remove();
 function choose(s,l,anchor){
  removeMenu();const menu=node('div',undefined,'conductor-add-menu');menu.setAttribute('role','menu');menu.setAttribute('aria-label','Add source');
  const category=node('details');category.open=true;category.append(node('summary','PHRASES'));category.onpointerenter=()=>category.open=true;category.querySelector('summary').onclick=e=>{e.preventDefault();category.open=true;};
  for(const p of latest.phrases){const src=model.sources.find(v=>v.type==='PHRASE'&&v.slot===p.id);if(!src)continue;
   category.append(action(`PHRASE ${String(p.id).padStart(2,'0')} · ${p.name||'PHRASE '+p.id}${p.events?'':' · EMPTY'}`,()=>change(()=>{ensure(s);l.block={id:uuid(),type:'PHRASE',sourceId:src.id,overrides:{}};selected=s.id;})));
  }
  menu.append(category);
  const movements=node('details');movements.append(node('summary','MOVEMENTS'));movements.onpointerenter=()=>movements.open=true;movements.querySelector('summary').onclick=e=>{e.preventDefault();movements.open=true;};
  if(s.layers[0]!==l){for(const m of model.movements||[])movements.append(action(`MOVEMENT · ${m.name}`,()=>change(()=>{ensure(s);l.block={id:uuid(),type:'MOVEMENT',sourceId:m.id,overrides:{}};selected=s.id;})));if(!model.movements?.length)movements.append(node('small','Create a source in MOVEMENTS'));}else movements.append(node('small','LAYER 01 is PHRASE MASTER'));
  menu.append(movements,action('CLOSE',removeMenu));anchor.parentElement.append(menu);
  menu.onkeydown=e=>{if(e.key==='Escape'){e.preventDefault();e.stopPropagation();removeMenu();anchor.focus();}};
  menu.querySelector('button')?.focus();
 }
 function transfer(fromStep,fromLayer,toStep,toLayer,operation){
  if(fromLayer===toLayer||!fromLayer.block)return;
  const a=fromLayer.block,b=toLayer.block;
  if((toStep.layers[0]===toLayer&&a.type!=='PHRASE')||(operation==='SWAP'&&fromStep.layers[0]===fromLayer&&b&&b.type!=='PHRASE')){error.textContent='LAYER 01 accepts PHRASE or EMPTY only';return;}
  change(()=>{ensure(toStep);toLayer.block=operation==='DUPLICATE'?{...structuredClone(a),id:uuid()}:a;if(operation!=='DUPLICATE')fromLayer.block=operation==='SWAP'?b:null;});
 }
 function dropTarget(el,s,l=null){
  el.ondragover=e=>{e.preventDefault();};
  el.ondrop=e=>{e.preventDefault();e.stopPropagation();if(!drag)return;
   if(drag.layer&&l)transfer(drag.step,drag.layer,s,l,e.altKey?'DUPLICATE':e.ctrlKey?'SWAP':'REPLACE');
   else if(!drag.layer&&!l&&drag.step!==s&&sequence.steps.includes(s))change(()=>{const from=sequence.steps.indexOf(drag.step);sequence.steps.splice(from,1);sequence.steps.splice(sequence.steps.indexOf(s),0,drag.step);});
   drag=null;
  };
 }
 function properties(s,l){
  editing=l.id;side.replaceChildren();const b=l.block;
  side.append(node('h3',label(b)),node('small','LOCAL · source unchanged'));
  if(b.type==='PHRASE'||b.type==='MOVEMENT'){
   const row=node('label','TRIG','conductor-option'),policy=node('select'),value=node('select');row.title='Trigger gesture';policy.setAttribute('aria-label','TRIGGER inheritance');value.setAttribute('aria-label','TRIGGER override');
   for(const name of ['INHERIT','OVERRIDE']){const o=node('option',name);o.value=name;policy.append(o);}for(const name of ['PRESS','HOLD']){const o=node('option',name);o.value=name;value.append(o);}policy.value=b.overrides.trigger?.mode||'INHERIT';value.value=b.overrides.trigger?.value||'PRESS';value.disabled=policy.value!=='OVERRIDE';
   const update=()=>{checkpoint();b.overrides.trigger=policy.value==='INHERIT'?{mode:'INHERIT'}:{mode:'OVERRIDE',value:value.value};paint();properties(s,l);};policy.onchange=value.onchange=update;row.append(policy,value);side.append(row);
  }
  if(b.type==='MOVEMENT'){
   const m=source(b);if(!m){side.append(node('p','MISSING SOURCE · preserved'));return;}
   side.append(previewCurve(m.points.map(p=>[...p,0]),m.interpolation==='HOLD'),node('output',`${m.duration}s · ${m.target.type==='CC'?`CH${m.target.channel} CC${m.target.number}`:'PARAMETER'}`));
   const row=node('label','RETRIGGER'),policy=node('select'),value=node('select');policy.setAttribute('aria-label','RETRIGGER inheritance');value.setAttribute('aria-label','RETRIGGER override');
   for(const v of ['INHERIT','OVERRIDE']){const o=node('option',v);o.value=v;policy.append(o);}for(const v of ['SOFT_RESTART','DIRECT']){const o=node('option',v);o.value=v;value.append(o);}policy.value=b.overrides.retrigger?.mode||'INHERIT';value.value=b.overrides.retrigger?.value||m.retrigger;value.disabled=policy.value!=='OVERRIDE';
   const update=()=>{checkpoint();b.overrides.retrigger=policy.value==='INHERIT'?{mode:'INHERIT'}:{mode:'OVERRIDE',value:value.value};paint();properties(s,l);};policy.onchange=value.onchange=update;row.append(policy,value);side.append(row,node('small','ONE_SHOT · source curve edited in MOVEMENTS'));return;
  }
  if(b.type!=='PHRASE'){side.append(node('p','UNSUPPORTED · preserved'));return;}
  for(const [key,title,choices,fallback] of [['entry','ENTRY',['TRIGGER','REVEAL'],'TRIGGER'],['release','REL',['LATCH','GATE'],'LATCH']]){
   if(key==='release'&&b.overrides.entry?.value!=='REVEAL'&&b.overrides.release?.mode!=='OVERRIDE')continue;
   const row=node('label',title,'conductor-option'),policy=node('select'),value=node('select');policy.setAttribute('aria-label',`${title} inheritance`);value.setAttribute('aria-label',`${title} override`);
   for(const name of ['INHERIT','OVERRIDE']){const o=node('option',name);o.value=name;policy.append(o);}for(const name of choices){const o=node('option',name);o.value=name;value.append(o);}
   policy.value=b.overrides[key]?.mode||'INHERIT';value.value=b.overrides[key]?.value||fallback;value.disabled=policy.value!=='OVERRIDE';
   const update=()=>{checkpoint();b.overrides[key]=policy.value==='INHERIT'?{mode:'INHERIT'}:{mode:'OVERRIDE',value:value.value};paint();properties(s,l);};policy.onchange=value.onchange=update;row.append(policy,value);side.append(row);
  }
  if(b.overrides.entry?.mode==='OVERRIDE'&&b.overrides.entry.value==='REVEAL'){
   const warning=node('small',b.overrides.trigger?.mode==='OVERRIDE'&&b.overrides.trigger.value==='HOLD'?'CC7 CHANNEL-WIDE':'REVEAL NEEDS TRIG HOLD','conductor-group-warning');warning.title='REVEAL sends CC7: shared channels affect other layers and instruments. Use independent channels for isolation. Source phrases containing CC7 are not supported.';warning.setAttribute('role','status');side.append(warning);
  }
  for(const [key,title,kind] of [['playMode','MODE',20],['phrase_base_velocity','VEL',17],['phrase_velocity_decay','V.DEC',15],['phrase_time_decay','T.DEC',14]]){
   const row=node('label',title,'conductor-option'),policy=node('select');policy.setAttribute('aria-label',`${title} inheritance`);
   for(const value of ['INHERIT','OVERRIDE']){const o=node('option',value);o.value=value;policy.append(o);}policy.value=b.overrides[key]?.mode||'INHERIT';
   const p=phrase(b),fallback=key==='playMode'?['LOOP','ONCE','HOLD'][p?.mode]||'ONCE':p?.[{phrase_base_velocity:'baseVelocity',phrase_velocity_decay:'velocityDecay',phrase_time_decay:'timeDecay'}[key]]??1;
   let value;
   if(key==='playMode'){value=node('select');for(const text of ['LOOP','ONCE','HOLD']){const o=node('option',text);o.value=text;value.append(o);}value.value=b.overrides[key]?.value??fallback;}
   else{value=node('input');const d=parameter(kind);value.type='range';value.min=d.min;value.max=d.max;value.step=d.step;value.value=b.overrides[key]?.value??fallback;}
   value.setAttribute('aria-label',`${title} override`);value.disabled=policy.value!=='OVERRIDE';const output=node('output',value.value);
   const update=()=>{checkpoint();b.overrides[key]=policy.value==='INHERIT'?{mode:'INHERIT'}:{mode:'OVERRIDE',value:key==='playMode'?value.value:Number(value.value)};paint();properties(s,l);};
   policy.onchange=update;value.oninput=()=>output.value=value.value;value.onchange=update;row.append(policy,value,output);side.append(row);
  }
  const unsupported=Object.entries(b.overrides).filter(([k,v])=>v.mode==='OVERRIDE'&&!['trigger','playMode','phrase_base_velocity','phrase_velocity_decay','phrase_time_decay'].includes(k));
  if(unsupported.length)side.append(node('small','Other existing options preserved · '+unsupported.map(([k])=>k).join(', ')));
  const moves=node('details');moves.append(node('summary','MOVE / REPLACE'));
  const destination=node('select');destination.setAttribute('aria-label','Block destination');
  for(const target of sequence.steps)for(const targetLayer of target.layers){if(targetLayer===l)continue;const o=node('option',`STEP ${sequence.steps.indexOf(target)+1} / LAYER ${target.layers.indexOf(targetLayer)+1}`);o.value=targetLayer.id;destination.append(o);}
  const operation=node('select');operation.setAttribute('aria-label','Block transfer');for(const text of ['REPLACE','SWAP','DUPLICATE']){const o=node('option',text);o.value=text;operation.append(o);}
  const move=action('APPLY MOVE',()=>{const target=sequence.steps.find(t=>t.layers.some(v=>v.id===destination.value));if(target)transfer(s,l,target,target.layers.find(v=>v.id===destination.value),operation.value);});move.disabled=!destination.options.length;moves.append(destination,operation,move);side.append(moves);
  side.append(action('CLOSE PROPERTIES',()=>{editing=null;side.replaceChildren();}));
 }
 function paint(){
  removeMenu();side.replaceChildren();board.replaceChildren();
  const columns=[...sequence.steps];if(!columns.length||columns.at(-1).layers.some(l=>l.block)){empty=step();columns.push(empty);}
  columns.forEach((s,index)=>{
   const column=node('section',undefined,'conductor-step');column.dataset.stepId=s.id;column.dataset.stepPosition=sequence.steps.includes(s)?index+1:0;column.classList.toggle('selected-step',selected===s.id);
   const header=node('div',undefined,'conductor-step-header');header.append(action(`STEP ${String(index+1).padStart(2,'0')}`,()=>{selected=s.id;paint();}));
   if(sequence.steps.includes(s)){
    for(const [name,delta] of [['MOVE STEP LEFT',-1],['MOVE STEP RIGHT',1]]){const control=action(name,()=>change(()=>{const other=index+delta;[sequence.steps[index],sequence.steps[other]]=[sequence.steps[other],sequence.steps[index]];}));control.textContent=delta<0?'←':'→';control.disabled=index+delta<0||index+delta>=sequence.steps.length;header.append(control);}
    const del=action('DELETE STEP',()=>change(()=>sequence.steps.splice(index,1)));del.textContent='×';header.append(del);
   }
   if(sequence.steps.includes(s)){header.draggable=true;header.ondragstart=e=>{drag={step:s};e.dataTransfer.setData('text/plain',s.id);};dropTarget(header,s);}
   column.append(header);
   const groups=new Map();for(const l of s.layers){const src=l.block?.type==='PHRASE'?source(l.block):null;if(src?.muteGroup){const ids=groups.get(src.muteGroup)||new Set();ids.add(src.slot);groups.set(src.muteGroup,ids);}}
   for(const [group,ids] of groups)if(ids.size>1){const warning=node('small',`GROUP ${group} · PHRASE ${Math.min(...ids)} wins`,'conductor-group-warning');warning.setAttribute('role','status');column.append(warning);}

   if(s.layers.some(l=>l.block?.type==='PHRASE'&&l.block.overrides.entry?.mode==='OVERRIDE'&&l.block.overrides.entry.value==='REVEAL')){
    const warning=node('small','CC7 CHANNEL-WIDE','conductor-group-warning');warning.setAttribute('role','status');warning.title='REVEAL affects every instrument on its MIDI channels. Shared channels are allowed; use independent channels for isolation.';column.append(warning);
   }
   s.layers.forEach((l,li)=>{
    const cell=node('div',undefined,'conductor-layer');cell.dataset.layerId=l.id;cell.append(node('small',li===0?'01 MASTER':String(li+1).padStart(2,'0')));
    if(l.block){const b=l.block;cell.dataset.blockId=b.id;cell.classList.toggle('missing-source',!source(b));cell.append(node('strong',label(b)),node('output',b.type==='PHRASE'?`${mode(b)} · ${b.overrides?.trigger?.value||'PRESS'}${b.overrides.entry?.mode==='OVERRIDE'&&b.overrides.entry.value==='REVEAL'?' · REVEAL '+(b.overrides.release?.value||'LATCH'):''}`:b.type==='MOVEMENT'?`${source(b)?.duration??'—'}s · ${b.overrides?.trigger?.value||'PRESS'}`:'UNSUPPORTED · preserved'));
     cell.append(action('EDIT BLOCK',()=>properties(s,l)),action('REMOVE BLOCK',()=>change(()=>l.block=null)),action('REPLACE BLOCK',()=>choose(s,l,cell.lastElementChild)));
    }else{const add=action(`Add PHRASE STEP ${index+1} LAYER ${li+1}`,()=>choose(s,l,add));add.textContent='+';add.className='conductor-add';cell.append(add,node('small','EMPTY'));}
    if(sequence.steps.includes(s)){
     for(const [name,delta] of [['MOVE LAYER UP',-1],['MOVE LAYER DOWN',1]]){const other=li+delta,control=action(name,()=>change(()=>[s.layers[li],s.layers[other]]=[s.layers[other],s.layers[li]]));control.textContent=delta<0?'↑':'↓';const first=other===0?l.block:li===0?s.layers[other]?.block:null;control.disabled=other<0||other>=s.layers.length||(first&&first.type!=='PHRASE');cell.append(control);}
     const del=action('DELETE LAYER',()=>change(()=>s.layers.splice(li,1)));del.textContent='−';del.disabled=s.layers.length===1||(li===0&&s.layers[1]?.block&&s.layers[1].block.type!=='PHRASE');cell.append(del);
    }
    if(l.block){cell.draggable=true;cell.ondragstart=e=>{e.stopPropagation();drag={step:s,layer:l};e.dataTransfer.setData('text/plain',l.id);};}dropTarget(cell,s,l);
    column.append(cell);
   });
   column.append(action('ADD LAYER',()=>change(()=>{ensure(s);s.layers.push(layer());})));board.append(column);
  });
  undo.disabled=!history.length;
  if(!['SEQUENTIAL'].includes(sequence.traversal)||sequence.transition!=='IMMEDIATE'||sequence.gesture!=='INSTANT')error.textContent='Existing execution options unsupported by D · preserved';
  if(sequence.steps.some(s=>s.layers.filter(l=>l.block).length>12))error.textContent='More than 12 populated layers · D will refuse execution';
  paintConductorRuntime(latest);
 }
 const undo=action('UNDO',()=>{sequence.steps=history.pop();editing=null;paint();});
 const addStep=action('ADD STEP',()=>change(()=>{sequence.steps.push(step());selected=sequence.steps.at(-1).id;}));
 const done=action('DONE',async()=>{
  if(engineSession!==session||revision!==rev){error.textContent='Configuration changed. CANCEL and reopen; draft retained.';return;}
  if(!sequence.steps.length)sequence.steps.push(empty); // C requires one valid EMPTY STEP, never an invalid zero-step document.
  committing=true;const controls=[...root.querySelectorAll('button,input,select')],wasDisabled=controls.map(control=>control.disabled);controls.forEach(control=>control.disabled=true);
  try{await request('/api/v1/command',{protocolVersion:1,expectedRevision:rev,expectedEngineSessionId:session,action:'conductor_commit',conductor:model});render(await request('/api/v1/state'));dialog.close();}
  catch(e){error.textContent=e.message==='conflict'?'Configuration changed. CANCEL and reopen; draft retained.':`${e.message} · STOP/PANIC before DONE; draft retained.`;}
  finally{committing=false;controls.forEach((control,index)=>control.disabled=wasDisabled[index]);}
 });
 const cancel=action('CANCEL',()=>dialog.close());heading.append(undo,addStep,done,cancel);
 dialog.oncancel=e=>{if(committing)e.preventDefault();};dialog.onclick=e=>{const r=dialog.getBoundingClientRect();if(!committing&&e.target===dialog&&(e.clientX<r.left||e.clientX>r.right||e.clientY<r.top||e.clientY>r.bottom))dialog.close();};
 dialog.addEventListener('close',()=>{conductorView=null;drag=null;},{once:true});
 conductorView={root,status,switchId:sw.id,session,revision:rev};paint();showEditor(dialog,false,'conductor');
}
