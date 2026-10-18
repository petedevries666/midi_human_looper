"use strict";
async function editSwitchPresets(sw,draft=null){
 const dialog=$('editor');if(dialog.open)dialog.close();
 const content=$('editor-content');content.replaceChildren(node('h2','SMART SWITCH PRESETS'));
 const error=node('p','');error.setAttribute('role','alert');content.append(error);
 let inventory;try{inventory=await request('/api/v1/switch-presets');}catch(e){error.textContent=e.message;content.append(button('CLOSE',()=>dialog.close()));showEditor(dialog);return;}
 const config=structuredClone(draft||{name:sw.name,settings:sw.settings,sequence:sw.sequence,longHold:sw.longHold||{milliseconds:0,action:0,target:0}});
 const label=(text,control)=>{const row=node('label',text,'parameter');row.append(control);content.append(row);return control;};
 const name=node('input');name.value=sw.name||`SWITCH ${sw.id}`;name.maxLength=64;name.setAttribute('aria-label','Preset name');label('PRESET NAME',name);
 const patchIdentity=node('select');patchIdentity.setAttribute('aria-label','Current patch identity');for(const slot of [1,2,3,4]){const o=node('option',`PATCH ${slot}`);o.value=String(slot);patchIdentity.append(o);}patchIdentity.value=String(inventory.currentSlot||Number($('patch-slot').value));label('CURRENT PATCH',patchIdentity);
 const selection=node('select');selection.setAttribute('aria-label','Smart Switch preset');selection.append(node('option','SELECT PRESET'));
 for(const [id,p] of Object.entries(inventory.library.presets)){const o=node('option',p.name);o.value=id;selection.append(o);}label('PRESET',selection);
 const links=node('p',''),resolutions=node('div'),destinations=node('div'),preview=node('section',undefined,'preset-preview');content.append(links,resolutions,destinations,preview);
 let currentResolutions={},targets=[];
 function resolver(parent,available,preset){
  const resolved={};
  for(const [gesture,ref] of Object.entries(preset?.references||{})){
   const row=node('label',`${gesture.toUpperCase()} DESTINATION`,'parameter'),select=node('select');select.setAttribute('aria-label',`${gesture} destination`);const auto=node('option','AUTOMATIC');auto.value='';select.append(auto);
   if(ref.type==='switch'){
    for(const [value,title] of [['SELF','THIS SWITCH'],['ALL','ALL SWITCHES'],...(available.switches||[]).map(s=>[s.id,s.name||`SWITCH ${s.id}`])]){const o=node('option',title);o.value=String(value);select.append(o);}
   }else for(const m of available.modules||[]){const d=descriptor(m.engineType);const o=node('option',`I${m.instrumentId} · ${d?.label||d?.name||'MODULE '+m.engineType}`);o.value=String(m.value);select.append(o);}
   select.onchange=()=>{if(select.value==='')delete resolved[gesture];else resolved[gesture]=['SELF','ALL'].includes(select.value)?select.value:Number(select.value);};row.append(select);parent.append(row);
  }return resolved;
 }
 function choose(){
  const preset=inventory.library.presets[selection.value];resolutions.replaceChildren();destinations.replaceChildren();preview.replaceChildren();targets=[];
  if(!preset){links.textContent='';currentResolutions={};return;}
  const related=[];for(const [slot,bindings] of Object.entries(inventory.library.links))for(const [owner,id] of Object.entries(bindings))if(id===selection.value)related.push(`PATCH ${slot} / SWITCH ${owner}`);
  links.textContent=related.length?'LINKED: '+related.join(', '):'No linked patches';
  currentResolutions=resolver(resolutions,inventory.currentTargets,preset);
  destinations.append(node('h3','PROPAGATE TO SAVED PATCHES'));
  if(!inventory.patches.length)destinations.append(node('p','SAVE a patch first to make it available here.'));
  for(const p of inventory.patches){
   const box=node('fieldset'),legend=node('legend',`PATCH ${p.slot}`),enabled=node('input');enabled.type='checkbox';enabled.setAttribute('aria-label',`Select PATCH ${p.slot}`);legend.prepend(enabled);box.append(legend);if(p.error)box.append(node('p',p.error,'preset-error'));
   const owner=node('select');owner.setAttribute('aria-label',`Destination switch PATCH ${p.slot}`);
   for(const s of p.switches.filter(s=>!s.conductor&&!s.snapshot)){const o=node('option',s.name||`SWITCH ${s.id}`);o.value=String(s.id);owner.append(o);}if(!owner.options.length)enabled.disabled=true;
   if([...owner.options].some(o=>o.value===String(sw.id)))owner.value=String(sw.id);
   const link=node('input');link.type='checkbox';link.setAttribute('aria-label',`Link preset PATCH ${p.slot}`);const linkLabel=node('label','LINK TO GLOBAL PRESET');linkLabel.prepend(link);box.append(owner,linkLabel);
   const mapped=resolver(box,p,preset);targets.push({enabled,owner,link,mapped,slot:p.slot});destinations.append(box);
  }
 }
 selection.onchange=choose;
 async function propose(operation){
  error.textContent='';preview.replaceChildren();
  try{
   const data={action:'preview',operation,slot:Number(patchIdentity.value),switchId:sw.id,presetId:selection.value,name:name.value,config,expectedRevision:revision,expectedEngineSessionId:engineSession,resolutions:currentResolutions};
   if(operation==='propagate')data.targets=targets.filter(t=>t.enabled.checked).map(t=>({slot:t.slot,switchId:Number(t.owner.value),linked:t.link.checked,resolutions:t.mapped}));
   const p=await request('/api/v1/switch-presets',data);preview.append(node('h3','REVIEW CHANGES'));
   for(const line of p.summary)preview.append(node('p',line));for(const line of p.warnings)preview.append(node('p',line,'preset-warning'));for(const line of p.errors)preview.append(node('p',line,'preset-error'));
   const apply=button('APPLY REVIEWED CHANGES',async()=>{apply.disabled=true;try{await request('/api/v1/switch-presets',{action:'execute',previewId:p.previewId});await refresh();dialog.close();}catch(e){error.textContent=e.message;apply.disabled=false;}});apply.disabled=!!p.errors.length;preview.append(apply,button('DISMISS PREVIEW',()=>preview.replaceChildren()));
  }catch(e){error.textContent=e.message;}
 }
 const actions=node('div',undefined,'preset-actions');for(const [title,op] of [['SAVE NEW PRESET','save'],['UPDATE SELECTED PRESET','update'],['COPY TO THIS SWITCH','apply'],['LINK THIS SWITCH','link'],['DETACH THIS SWITCH','unlink'],['PROPAGATE…','propagate']])actions.append(button(title,()=>propose(op)));content.append(actions);
 content.append(node('p','A copy is independent. A global link follows preset updates and patch loading. Source NOTE/CC, channel, press/release values, thresholds and TAP/DOUBLE/HOLD/LONG HOLD actions are included. COPY and LINK save the current configuration to the selected patch, after the review.'));
 content.append(button('CLOSE',()=>dialog.close()));showEditor(dialog);choose();
}
