'use strict';
function duplicateConductorStep(original,uuid){
 const copy=structuredClone(original),blocks=new Map();copy.id=uuid();
 for(const layer of copy.layers){layer.id=uuid();if(layer.block){const previous=layer.block.id;layer.block.id=uuid();blocks.set(previous,layer.block.id);}}
 for(const binding of copy.supercharge?.bindings||[])if(blocks.has(binding.blockId))binding.blockId=blocks.get(binding.blockId);
 return copy;
}
// C's versioned model, D's execution. Only the stopped, guarded native commit writes it.
let conductorView=null;
function paintConductorRuntime(state){
 if(!conductorView)return;
 const runtime=state.switches.find(s=>s.id===conductorView.switchId)?.conductor;
 const unchanged=state.engineSessionId===conductorView.session&&state.revision===conductorView.revision;
 conductorView.root.querySelectorAll('[data-step-position]').forEach(el=>{el.classList.toggle('active-step',unchanged&&Number(el.dataset.stepPosition)===runtime?.step);const queued=unchanged&&Number(el.dataset.stepPosition)===runtime?.queuedStep&&runtime.queuedStep>0;el.classList.toggle('queued-step',queued);const badge=el.querySelector('.queued-badge');if(badge)badge.hidden=!queued;});
 conductorView.status.textContent=!unchanged?'CONFIGURATION CHANGED · reopen before DONE':runtime?.result?({1:'MISSING SOURCE',2:'12 VOICES · REFUSED',3:'UNSAFE SOURCE',4:'UNSUPPORTED',5:'INSTANCE ID LIMIT'}[runtime.result]||'REFUSED'):runtime?.queuedStep?`STEP ${runtime.step} → ${runtime.queuedStep} EN ATTENTE`:`ACTIVE ${runtime?.step||'—'} / ${runtime?.steps||0}${runtime?.repeatTotal>1?` · REPEAT ${runtime.repeatCount}/${runtime.repeatTotal}`:''}`;
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
 const checkpoint=()=>{history.push(structuredClone({steps:sequence.steps,transition:sequence.transition,advance:sequence.advance,supercharge:model.supercharge}));editing=null;error.textContent='';};
 const change=fn=>{checkpoint();fn();paint();};
 function transitionSelect(label,current,inherit,onchange){
  const row=node('label',label,'conductor-option'),select=node('select');select.setAttribute('aria-label',label);
  for(const [value,text] of [...(inherit?[['INHERIT','HÉRITER']]:[]),['IMMEDIATE','IMMÉDIAT'],['END_OF_PHRASE','FIN DE PHRASE / CYCLE']]){const o=node('option',text);o.value=value;select.append(o);}
  select.value=current;select.onchange=()=>onchange(select.value);row.append(select);return row;
 }
 const globalTransition=transitionSelect('PASSAGE AU STEP SUIVANT',sequence.transition,false,value=>change(()=>sequence.transition=value));heading.append(globalTransition);
 const advanceRow=node('label','AVANCER AU','conductor-option'),advanceSelect=node('select');advanceSelect.setAttribute('aria-label','ADVANCE GESTURE');
 for(const [v,t] of [['PRESS','PRESS · à l’appui'],['RELEASE','RELEASE · tap ou charge']]){const o=node('option',t);o.value=v;advanceSelect.append(o);}advanceSelect.value=sequence.advance||'PRESS';advanceSelect.onchange=()=>change(()=>sequence.advance=advanceSelect.value);advanceRow.append(advanceSelect);heading.append(advanceRow);
 const chargeDefaults=()=>model.supercharge||{thresholdMs:600,fullMs:2000};
 const commonCharge=node('details');commonCharge.append(node('summary','SUPERCHARGE · TEMPS DU PATCH'));
 const commonInputs={};for(const [key,label,min,max] of [['thresholdMs','PATCH SEUIL CHARGE ms',0,30000],['fullMs','PATCH PLEINE CHARGE ms',1,120000]]){
  const row=node('label',label,'conductor-option'),input=node('input');input.type='number';input.min=min;input.max=max;input.step=1;input.value=chargeDefaults()[key];input.setAttribute('aria-label',label);input.onchange=()=>{checkpoint();model.supercharge={...chargeDefaults(),[key]:Number(input.value)};paint();};commonInputs[key]=input;row.append(input);commonCharge.append(row);
 }heading.append(commonCharge);


 const source=b=>b?.type==='MOVEMENT'?model.movements?.find(s=>s.id===b.sourceId):model.sources.find(s=>s.id===b?.sourceId&&s.type===b?.type);
 const phrase=b=>latest.phrases.find(p=>p.id===source(b)?.slot);
 const label=b=>{if(b.type==='ACTION')return `ACTION · ${b.action}`;if(b.type==='MOVEMENT'){const m=source(b);return m?`MOVEMENT · ${m.name}`:`MISSING · ${b.sourceId}`;}if(b.type!=='PHRASE')return `${b.type} · UNAVAILABLE · ${b.sourceId||''}`;const p=phrase(b);return p?`${String(p.id).padStart(2,'0')} · ${p.name||'PHRASE '+p.id}${p.events?'':' · EMPTY'}`:`MISSING · ${b.sourceId||b.type}`;};
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
  menu.append(movements);
  if(s.layers[0]!==l){const actions=node('details');actions.append(node('summary','ACTIONS'));
   for(const name of ['STOP','RESET_CURSOR','RESET_SHUFFLE_BAG','STOP_RESET','PANIC'])actions.append(action('ACTION '+name,()=>{change(()=>{ensure(s);l.block={id:uuid(),type:'ACTION',action:name,target:name.startsWith('RESET')||name==='STOP_RESET'?{type:'SWITCH',switchId:sw.id}:{type:'ALL_PHRASES'},trigger:'PRESS'};selected=s.id;});properties(s,l);}));menu.append(actions);
  }
  menu.append(action('CLOSE',removeMenu));anchor.parentElement.append(menu);
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
  el.ondragover=e=>{e.preventDefault();if(e.dataTransfer)e.dataTransfer.dropEffect=e.altKey||drag?.copy?'copy':'move';};
  el.ondrop=e=>{e.preventDefault();e.stopPropagation();if(committing||!drag)return;
   if(drag.layer&&l)transfer(drag.step,drag.layer,s,l,e.altKey?'DUPLICATE':e.ctrlKey?'SWAP':'REPLACE');
   else if(!drag.layer&&!l&&(e.altKey||drag.copy))change(()=>{const copy=duplicateConductorStep(drag.step,uuid),at=sequence.steps.indexOf(s);sequence.steps.splice(at<0?sequence.steps.length:at,0,copy);selected=copy.id;});
   else if(!drag.layer&&!l&&drag.step!==s&&sequence.steps.includes(s))change(()=>{const from=sequence.steps.indexOf(drag.step);sequence.steps.splice(from,1);sequence.steps.splice(sequence.steps.indexOf(s),0,drag.step);});
   drag=null;
  };
 }
 function chargeProperties(s){
  editing=null;side.replaceChildren();const index=sequence.steps.indexOf(s)+1;side.append(node('h3',`SUPERCHARGE · STEP ${index}`),node('p','Valeurs locales aux blocs démarrés au relâchement. AVANCER AU RELEASE prépare le prochain STEP pendant l’appui ; ses couches PRESS jouent à son entrée. Un release chargé remplace le court. Les paramètres d’instrument agissent au release chargé.'));
  const c=s.supercharge||{bindings:[]};
  const remember=()=>{if(!s.supercharge){checkpoint();s.supercharge=c;}if(model.version<2){model.version=2;model.movements??=[];model.ccRate??=25;}};
  function numeric(label,value,min,max,step,onchange){const row=node('label',label,'conductor-option'),input=node('input');input.type='number';input.min=min;input.max=max;input.step=step;input.value=value;input.setAttribute('aria-label',label);input.onchange=()=>{remember();checkpoint();onchange(Number(input.value));undo.disabled=false;};row.append(input);return row;}
  for(const [key,label,min,max] of [['thresholdMs','SEUIL CHARGE ms',0,30000],['fullMs','PLEINE CHARGE ms',1,120000]]){
   const row=node('label',label,'conductor-option'),policy=node('select'),input=node('input');policy.setAttribute('aria-label',`${label} inheritance`);
   for(const [v,t] of [['INHERIT',`HÉRITER · ${chargeDefaults()[key]} ms`],['OVERRIDE','OVERRIDE']]){const o=node('option',t);o.value=v;policy.append(o);}policy.value=Object.hasOwn(c,key)?'OVERRIDE':'INHERIT';input.type='number';input.min=min;input.max=max;input.step=1;input.value=c[key]??chargeDefaults()[key];input.disabled=policy.value==='INHERIT';input.setAttribute('aria-label',label);
   policy.onchange=()=>{remember();checkpoint();if(policy.value==='INHERIT')delete c[key];else c[key]=chargeDefaults()[key];paint();chargeProperties(s);};input.onchange=()=>{remember();checkpoint();c[key]=Number(input.value);undo.disabled=false;};row.append(policy,input);side.append(row);
  }
  const blocks=s.layers.map((l,i)=>({b:l.block,i})).filter(v=>['PHRASE','MOVEMENT'].includes(v.b?.type));
  const parameterTargets=[];for(const inst of latest.instruments){
    const add=(kind,moduleId=0)=>{const d=parameter(kind);if(d&&!d.assignment&&kind!==16)parameterTargets.push({type:'PARAMETER',instrumentId:inst.id,moduleId,kind,label:`I${inst.id} · ${inst.name||'INSTRUMENT'} · ${moduleId?'MODULE '+moduleId+' · ':''}${d.label}`});};
    if(hostChains?.bindings[String(inst.id)]){add(25);add(26);}else add(1);
    for(const tf of inst.transformers)for(const p of tf.parameters)if(!p.assignment)add(p.kind,tf.id);
  }
  c.bindings.forEach((a,i)=>{
   if(a.target){
    const box=node('section',undefined,'charge-binding'),dest=node('select');dest.setAttribute('aria-label',`CHARGE PARAMETER TARGET ${i+1}`);
    parameterTargets.forEach((t,j)=>{const o=node('option',t.label);o.value=j;dest.append(o);});const found=parameterTargets.findIndex(t=>t.instrumentId===a.target.instrumentId&&t.moduleId===a.target.moduleId&&t.kind===a.target.kind);dest.value=found;
    const d=parameter(a.target.kind);dest.onchange=()=>{checkpoint();const t=parameterTargets[Number(dest.value)];a.target={...t};delete a.target.label;const d=parameter(t.kind);a.from=d.min;a.to=d.max;paint();chargeProperties(s);};
    box.append(node('strong','PARAMÈTRE INSTRUMENT / TRANSFORMER'),dest,numeric(`CHARGE ${i+1} MIN`,a.from,d.min,d.max,d.step,v=>a.from=v),numeric(`CHARGE ${i+1} MAX`,a.to,d.min,d.max,d.step,v=>a.to=v),numeric(`CHARGE ${i+1} FACTOR`,a.factor,0,16,.01,v=>a.factor=v),action('REMOVE CHARGE BINDING',()=>{checkpoint();c.bindings.splice(i,1);paint();chargeProperties(s);}));side.append(box);return;
   }
   const box=node('section',undefined,'charge-binding'),dest=node('select');dest.setAttribute('aria-label',`CHARGE DESTINATION ${i+1}`);
   for(const {b,i:li} of blocks){const o=node('option',`LAYER ${li+1} · ${label(b)}`);o.value=b.id;dest.append(o);}dest.value=a.blockId;
   const b=blocks.find(v=>v.b.id===a.blockId)?.b,keys=b?.type==='MOVEMENT'?['movementDuration','movementAmplitude']:['phrase_base_velocity','phrase_time_decay','phrase_velocity_decay'];
   const ranges=k=>k==='movementDuration'?[.001,86400]:k==='movementAmplitude'?[0,1]:(()=>{const d=parameter({phrase_base_velocity:17,phrase_time_decay:14,phrase_velocity_decay:15}[k]);return [d.min,d.max];})();
   const names={movementDuration:'DURÉE MOVEMENT s',movementAmplitude:'AMPLITUDE MOVEMENT',phrase_base_velocity:'VÉLOCITÉ PHRASE',phrase_time_decay:'TIME DECAY PHRASE',phrase_velocity_decay:'VELOCITY DECAY PHRASE'};
   const param=node('select');param.setAttribute('aria-label',`CHARGE PARAMETER ${i+1}`);for(const k of keys){const o=node('option',names[k]);o.value=k;param.append(o);}param.value=a.parameter;
   function reset(key){const [lo,hi]=ranges(key);a.parameter=key;a.from=lo;a.to=hi;}
   dest.onchange=()=>{checkpoint();a.blockId=dest.value;reset(blocks.find(v=>v.b.id===a.blockId)?.b.type==='MOVEMENT'?'movementAmplitude':'phrase_base_velocity');paint();chargeProperties(s);};param.onchange=()=>{checkpoint();reset(param.value);paint();chargeProperties(s);};
   const [lo,hi]=ranges(a.parameter);box.append(dest,param,numeric(`CHARGE ${i+1} MIN`,a.from,lo,hi,.001,v=>a.from=v),numeric(`CHARGE ${i+1} MAX`,a.to,lo,hi,.001,v=>a.to=v),numeric(`CHARGE ${i+1} FACTOR`,a.factor,0,16,.01,v=>a.factor=v),action('REMOVE CHARGE BINDING',()=>{checkpoint();c.bindings.splice(i,1);paint();chargeProperties(s);}));side.append(box);
  });
  side.append(action('ADD PARAMETER CHARGE',()=>{const t=parameterTargets[0];if(!t)return;remember();checkpoint();const target={...t};delete target.label;const d=parameter(t.kind);c.bindings.push({target,parameter:'parameter',from:d.min,to:d.max,factor:1});paint();chargeProperties(s);}));
  side.append(action('ADD CHARGE BINDING',()=>{const b=blocks[0]?.b;if(!b)return;remember();checkpoint();const k=b.type==='MOVEMENT'?'movementAmplitude':'phrase_base_velocity',d=b.type==='MOVEMENT'?{min:0,max:1}:parameter(17);c.bindings.push({blockId:b.id,parameter:k,from:d.min,to:d.max,factor:1});paint();chargeProperties(s);}),node('small','Facteur × charge, limité à 0–100 %. Les bornes restent dans le range du paramètre. Amplitude MOVEMENT autour de REPOS ; durée PING-PONG = aller-retour complet.'),action('CLOSE PROPERTIES',()=>side.replaceChildren()));
 }
 function properties(s,l){
  editing=l.id;side.replaceChildren();const b=l.block;
  side.append(node('h3',label(b)),node('small','LOCAL · source unchanged'));
  if(b.type==='ACTION'){
   const select=(title,current,options,update)=>{const row=node('label',title,'conductor-option'),input=node('select');input.setAttribute('aria-label',title);
    if(!options.some(([value])=>value===String(current)))options.unshift([String(current),'MISSING / PRESERVED · '+current]);
    for(const [value,text] of options){const o=node('option',text);o.value=value;input.append(o);}input.value=current;input.onchange=()=>{checkpoint();update(input.value);paint();properties(s,l);};row.append(input);side.append(row);};
   const names=['STOP','RESET_CURSOR','RESET_SHUFFLE_BAG','STOP_RESET','PANIC'];
   select('ACTION TYPE',b.action,names.map(v=>[v,v]),value=>{b.action=value;b.target=value.startsWith('RESET')||value==='STOP_RESET'?{type:'SWITCH',switchId:sw.id}:{type:'ALL_PHRASES'};});
   select('ACTION TRIG',b.trigger,[['PRESS','PRESS'],['HOLD','HOLD'],['LONG_HOLD','LONG HOLD'],['RELEASE','RELEASE'],['SUPERCHARGE_RELEASE','SUPERCHARGE RELEASE']],value=>b.trigger=value);
   if(!names.includes(b.action)){side.append(node('p','Action conservée mais non exécutée par ce moteur.'));return;}
   const types=b.action==='STOP'?['PHRASE','MUTE_GROUP','ALL_PHRASES']:b.action==='PANIC'?['ALL_PHRASES']:['SWITCH'];
   select('ACTION TARGET',b.target.type,types.map(v=>[v,v]),type=>{b.target=type==='PHRASE'?{type,sourceId:model.sources[0]?.id||uuid()}:type==='MUTE_GROUP'?{type,id:1}:type==='SWITCH'?{type,switchId:sw.id}:{type};});
   if(b.target.type==='PHRASE')select('TARGET PHRASE',b.target.sourceId,model.sources.filter(v=>v.type==='PHRASE').map(v=>[v.id,latest.phrases.find(p=>p.id===v.slot)?.name||'PHRASE '+v.slot]),value=>b.target.sourceId=value);
   if(b.target.type==='SWITCH')select('TARGET SWITCH',String(b.target.switchId),latest.switches.map(v=>[String(v.id),v.name||'SWITCH '+v.id]),value=>b.target.switchId=Number(value));
   if(b.target.type==='MUTE_GROUP'){const row=node('label','TARGET MUTE GROUP','conductor-option'),input=node('input');input.type='number';input.min=1;input.max=16777215;input.step=1;input.value=b.target.id;input.setAttribute('aria-label','TARGET MUTE GROUP');input.onchange=()=>{if(!input.checkValidity())return;checkpoint();b.target.id=Number(input.value);paint();properties(s,l);};row.append(input);side.append(row);}
   side.append(node('small',b.action==='STOP'&&b.target.type!=='ALL_PHRASES'?'Arrête la cible avant les nouvelles phrases du step.':'STOP global, PANIC et RESET du switch courant doivent être seuls dans leur step.'),action('CLOSE PROPERTIES',()=>{editing=null;side.replaceChildren();}));return;
  }
  if(b.type==='PHRASE'||b.type==='MOVEMENT'){
   const row=node('label','TRIG','conductor-option'),policy=node('select'),value=node('select');row.title='Trigger gesture';policy.setAttribute('aria-label','TRIGGER inheritance');value.setAttribute('aria-label','TRIGGER override');
   for(const name of ['INHERIT','OVERRIDE']){const o=node('option',name);o.value=name;policy.append(o);}for(const name of ['PRESS','HOLD','LONG_HOLD','RELEASE','SUPERCHARGE_RELEASE']){const o=node('option',name.replace('_',' '));o.value=name;value.append(o);}policy.value=b.overrides.trigger?.mode||'INHERIT';value.value=b.overrides.trigger?.value||'PRESS';value.disabled=policy.value!=='OVERRIDE';
   const update=()=>{checkpoint();b.overrides.trigger=policy.value==='INHERIT'?{mode:'INHERIT'}:{mode:'OVERRIDE',value:value.value};paint();properties(s,l);};policy.onchange=value.onchange=update;row.append(policy,value);side.append(row);
  }
  if(b.overrides.trigger?.value==='LONG_HOLD'&&!sw.longHold?.milliseconds)side.append(node('p','LONG HOLD est désactivé : régler son seuil dans OPTIONS.','conductor-group-warning'));
  if(b.type==='MOVEMENT'){
   const m=source(b);if(!m){side.append(node('p','MISSING SOURCE · preserved'));return;}
   for(const [key,title,choices,fallback] of [['movementCycle','PLAY MODE',['ONCE','LOOP','PING_PONG'],m.cycleMode||'ONCE'],['movementPlayMode','MAINTIEN',['ONE_SHOT','GATED'],m.playMode||'ONE_SHOT'],['movementDuration','DURATION s',null,m.duration],['releaseSeconds','RELEASE s',null,m.releaseSeconds??.2],['restValue','REPOS 0–1',null,m.restValue??.5]]){
    const row=node('label',title,'conductor-option'),policy=node('select'),value=node(choices?'select':'input');
    policy.setAttribute('aria-label',`${title} inheritance`);value.setAttribute('aria-label',`${title} override`);
    for(const text of ['INHERIT','OVERRIDE']){const o=node('option',text);o.value=text;policy.append(o);}
    if(choices)for(const text of choices){const o=node('option',text==='GATED'?'MAINTENU':text);o.value=text;value.append(o);}
    else{value.type='number';value.min=key==='movementDuration'?.001:0;value.max=key==='movementDuration'?86400:key==='restValue'?1:60;value.step=.01;}
    policy.value=b.overrides[key]?.mode||'INHERIT';value.value=b.overrides[key]?.value??fallback;value.disabled=policy.value!=='OVERRIDE';
    const update=()=>{checkpoint();b.overrides[key]=policy.value==='INHERIT'?{mode:'INHERIT'}:{mode:'OVERRIDE',value:choices?value.value:Number(value.value)};paint();properties(s,l);};
    policy.onchange=value.onchange=update;row.append(policy,value);side.append(row);
   }
   side.append(previewCurve(m.points.map(p=>[p[0],p[1],p[2]??0]),m.interpolation==='HOLD'),node('output',`${m.duration}s · ${m.target.type==='CC'?`CH${m.target.channel} CC${m.target.number}`:'PARAMETER'}`));
   const row=node('label','RETRIGGER','conductor-option'),policy=node('select'),value=node('select');policy.setAttribute('aria-label','RETRIGGER inheritance');value.setAttribute('aria-label','RETRIGGER override');
   for(const v of ['INHERIT','OVERRIDE']){const o=node('option',v);o.value=v;policy.append(o);}for(const v of ['SOFT_RESTART','DIRECT']){const o=node('option',v);o.value=v;value.append(o);}policy.value=b.overrides.retrigger?.mode||'INHERIT';value.value=b.overrides.retrigger?.value||m.retrigger;value.disabled=policy.value!=='OVERRIDE';
   const update=()=>{checkpoint();b.overrides.retrigger=policy.value==='INHERIT'?{mode:'INHERIT'}:{mode:'OVERRIDE',value:value.value};paint();properties(s,l);};policy.onchange=value.onchange=update;row.append(policy,value);side.append(row,node('small','DURATION étire la courbe de ce bloc. MAINTENU rejoint REPOS au relâchement.'));return;
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
   for(const [key,title,fallback,max,stepSize] of [['revealCC','REVEAL CC',7,119,1],['revealFadeSeconds','FADE s',0,60,.01]]){
    const row=node('label',title,'conductor-option'),policy=node('select'),value=node('input');policy.setAttribute('aria-label',`${title} inheritance`);value.setAttribute('aria-label',`${title} override`);
    for(const text of ['INHERIT','OVERRIDE']){const o=node('option',text);o.value=text;policy.append(o);}
    value.type='number';value.min=0;value.max=max;value.step=stepSize;policy.value=b.overrides[key]?.mode||'INHERIT';value.value=b.overrides[key]?.value??fallback;value.disabled=policy.value!=='OVERRIDE';
    const update=()=>{checkpoint();b.overrides[key]=policy.value==='INHERIT'?{mode:'INHERIT'}:{mode:'OVERRIDE',value:Number(value.value)};paint();properties(s,l);};policy.onchange=value.onchange=update;row.append(policy,value);side.append(row);
   }
  }
  if(b.overrides.entry?.mode==='OVERRIDE'&&b.overrides.entry.value==='REVEAL'){
   const warning=node('small',b.overrides.trigger?.mode==='OVERRIDE'&&['HOLD','LONG_HOLD','RELEASE','SUPERCHARGE_RELEASE'].includes(b.overrides.trigger.value)?`CC${b.overrides.revealCC?.mode==='OVERRIDE'?b.overrides.revealCC.value:7} CHANNEL-WIDE`:'REVEAL NEEDS TRIG HOLD / LONG HOLD','conductor-group-warning');warning.title='REVEAL sends its configured CC: shared channels affect other layers and instruments. Use independent channels for isolation. A source phrase cannot also automate this same CC.';warning.setAttribute('role','status');side.append(warning);
  }
  for(const [key,title,kind] of [['phrase_tune','TUNE',null],['playMode','MODE',20],['phrase_base_velocity','VEL',17],['phrase_velocity_decay','V.DEC',15],['phrase_time_decay','T.DEC',14]]){
   const row=node('label',title,'conductor-option'),policy=node('select');policy.setAttribute('aria-label',`${title} inheritance`);
   for(const value of ['INHERIT','OVERRIDE']){const o=node('option',value);o.value=value;policy.append(o);}policy.value=b.overrides[key]?.mode||'INHERIT';
   const p=phrase(b),fallback=key==='phrase_tune'?(source(b)?.tune??0):key==='playMode'?['LOOP','ONCE','HOLD'][p?.mode]||'ONCE':p?.[{phrase_base_velocity:'baseVelocity',phrase_velocity_decay:'velocityDecay',phrase_time_decay:'timeDecay'}[key]]??1;
   let value;
   if(key==='playMode'){value=node('select');for(const text of ['LOOP','ONCE','HOLD']){const o=node('option',text);o.value=text;value.append(o);}value.value=b.overrides[key]?.value??fallback;}
   else{value=node('input');const d=key==='phrase_tune'?{min:-24,max:24,step:1}:parameter(kind);value.type='range';value.min=d.min;value.max=d.max;value.step=d.step;value.value=b.overrides[key]?.value??fallback;}
   value.setAttribute('aria-label',`${title} override`);value.disabled=policy.value!=='OVERRIDE';const output=node('output',value.value);
   const update=()=>{checkpoint();b.overrides[key]=policy.value==='INHERIT'?{mode:'INHERIT'}:{mode:'OVERRIDE',value:key==='playMode'?value.value:Number(value.value)};paint();properties(s,l);};
   policy.onchange=update;value.oninput=()=>output.value=value.value;value.onchange=update;row.append(policy,value,output);side.append(row);
  }
  const unsupported=Object.entries(b.overrides).filter(([k,v])=>v.mode==='OVERRIDE'&&!['trigger','entry','release','revealCC','revealFadeSeconds','playMode','phrase_tune','phrase_base_velocity','phrase_velocity_decay','phrase_time_decay'].includes(k));
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
    const duplicate=action('DUPLICATE STEP',()=>change(()=>{const copy=duplicateConductorStep(s,uuid);sequence.steps.splice(index+1,0,copy);selected=copy.id;}));duplicate.textContent='⧉';header.append(duplicate);
    for(const [name,delta] of [['MOVE STEP LEFT',-1],['MOVE STEP RIGHT',1]]){const control=action(name,()=>change(()=>{const other=index+delta;[sequence.steps[index],sequence.steps[other]]=[sequence.steps[other],sequence.steps[index]];}));control.textContent=delta<0?'←':'→';control.disabled=index+delta<0||index+delta>=sequence.steps.length;header.append(control);}
    const del=action('DELETE STEP',()=>change(()=>sequence.steps.splice(index,1)));del.textContent='×';header.append(del);
   }
   if(sequence.steps.includes(s)){header.draggable=true;header.title='Glisser pour déplacer · ALT + glisser pour dupliquer';header.ondragstart=e=>{drag={step:s,copy:e.altKey};e.dataTransfer.effectAllowed='copyMove';e.dataTransfer.setData('text/plain',s.id);};header.ondragend=()=>{drag=null;};}dropTarget(header,s);
   column.append(header);const badge=node('output','EN ATTENTE','queued-badge');badge.hidden=true;column.append(badge);
   if(sequence.steps.includes(s))column.append(transitionSelect(`PASSAGE STEP ${index+1}`,s.transition,true,value=>change(()=>s.transition=value)));
   if(sequence.steps.includes(s)){
    const controls=node('div',undefined,'conductor-step-controls'),charge=action(`SUPERCHARGE STEP ${index+1}`,()=>chargeProperties(s));charge.textContent='CHARGE';charge.title='SUPERCHARGE · réglages du STEP';
    const caption=node('label','REPEAT'),count=node('input');count.type='number';count.min=1;count.max=999;count.step=1;count.value=s.repeat??1;count.setAttribute('aria-label',`REPEAT STEP ${index+1}`);count.title='Nombre d’appuis jouant ce STEP avant de passer au suivant · ×1 par défaut';
    const update=value=>{if(!Number.isInteger(value)||value<1||value>999){error.textContent='REPEAT : entier de 1 à 999';count.value=s.repeat??1;return;}change(()=>{if(value===1)delete s.repeat;else s.repeat=value;});};
    const minus=action(`REDUCE REPEAT STEP ${index+1}`,()=>update((s.repeat??1)-1)),plus=action(`INCREASE REPEAT STEP ${index+1}`,()=>update((s.repeat??1)+1));minus.textContent='−';plus.textContent='+';minus.disabled=(s.repeat??1)<=1;plus.disabled=s.repeat>=999;count.onchange=()=>update(Number(count.value));count.onkeydown=e=>{if(e.key==='Enter'){e.preventDefault();count.blur();}};
    controls.append(charge,caption,minus,count,plus);column.append(controls);
   }
   const groups=new Map();for(const l of s.layers){const src=l.block?.type==='PHRASE'?source(l.block):null;if(src?.muteGroup){const ids=groups.get(src.muteGroup)||new Set();ids.add(src.slot);groups.set(src.muteGroup,ids);}}
   for(const [group,ids] of groups)if(ids.size>1){const warning=node('small',`GROUP ${group} · PHRASE ${Math.min(...ids)} wins`,'conductor-group-warning');warning.setAttribute('role','status');column.append(warning);}

   if(s.layers.some(l=>l.block?.type==='PHRASE'&&l.block.overrides.entry?.mode==='OVERRIDE'&&l.block.overrides.entry.value==='REVEAL')){
    const warning=node('small','REVEAL · CHANNEL-WIDE','conductor-group-warning');warning.setAttribute('role','status');warning.title='REVEAL affects every instrument on its MIDI channels. Shared channels are allowed; use independent channels for isolation.';column.append(warning);
   }
   s.layers.forEach((l,li)=>{
    const cell=node('div',undefined,'conductor-layer');cell.dataset.layerId=l.id;cell.append(node('small',li===0?'01 MASTER':String(li+1).padStart(2,'0')));
    if(l.block){const b=l.block;cell.dataset.blockId=b.id;cell.classList.toggle('missing-source',b.type!=='ACTION'&&!source(b));cell.append(node('strong',label(b)),node('output',b.type==='PHRASE'?`${mode(b)} · ${b.overrides?.trigger?.value||'PRESS'}${b.overrides.entry?.mode==='OVERRIDE'&&b.overrides.entry.value==='REVEAL'?' · REVEAL '+(b.overrides.release?.value||'LATCH'):''}`:b.type==='MOVEMENT'?`${b.overrides?.movementDuration?.mode==='OVERRIDE'?b.overrides.movementDuration.value:source(b)?.duration??'—'}s · ${b.overrides?.trigger?.value||'PRESS'} · ${(b.overrides?.movementPlayMode?.mode==='OVERRIDE'?b.overrides.movementPlayMode.value:source(b)?.playMode)==='GATED'?'MAINTENU':'ONE SHOT'}`:b.type==='ACTION'?`${b.trigger} · ${b.target.type}`:'UNSUPPORTED · preserved'));
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
  if(!['SEQUENTIAL'].includes(sequence.traversal)||!['IMMEDIATE','END_OF_PHRASE'].includes(sequence.transition)||sequence.gesture!=='INSTANT')error.textContent='Existing execution options unsupported by D · preserved';
  if(sequence.steps.some(s=>s.layers.filter(l=>l.block).length>12))error.textContent='More than 12 populated layers · D will refuse execution';
  paintConductorRuntime(latest);
 }
 const undo=action('UNDO',()=>{const previous=history.pop();sequence.steps=previous.steps;sequence.transition=previous.transition;if(previous.advance)sequence.advance=previous.advance;else delete sequence.advance;if(previous.supercharge)model.supercharge=previous.supercharge;else delete model.supercharge;for(const key of ['thresholdMs','fullMs'])commonInputs[key].value=chargeDefaults()[key];advanceSelect.value=sequence.advance||'PRESS';globalTransition.querySelector('select').value=sequence.transition;editing=null;paint();});
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
