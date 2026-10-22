'use strict';
(()=>{
 const panel=document.createElement('fieldset');panel.id='patch-recall-options';
 panel.innerHTML='<legend>PATCHES / MIDI PROGRAM CHANGE</legend><label><input id="pc-enabled" type="checkbox"> MIDI RECALL</label> <label>CANAL <select id="pc-channel" aria-label="Program Change channel"></select></label> <label><input id="pc-snapshot" type="checkbox"> CHARGER LE SNAPSHOT ZYNTHIAN</label> <button id="pc-apply">APPLIQUER</button><p>PC 0 ignoré · PC 1 = PATCH 01 · Certains contrôleurs affichent les programmes avec un décalage de 1.</p><label>SNAPSHOT DU PATCH <select id="pc-link" aria-label="Linked Zynthian snapshot"></select></label> <button id="pc-associate">LIER</button> <button id="pc-unlink">DÉLIER</button><p><button id="pc-save-pair">SAUVER PATCH + SNAPSHOT ZYNTHIAN</button> <button id="pc-load-pair">RAPPELER PATCH</button></p><output id="pc-status" role="status"></output>';
 document.querySelector('#movement-config .group-content').append(panel);
 const chainPanel=node('fieldset');chainPanel.id='chain-recall-panel';chainPanel.append(node('legend','RAPPEL DES CHAÎNES'));
 const chainRows=node('div');chainRows.id='chain-recall-rows';chainPanel.append(chainRows,node('p','SAVE enregistre uniquement cette chaîne dans le snapshot lié : son réel, preset, effets et mixage. Les autres chaînes et les phrases restent inchangées.','chain-recall-help'));
 document.querySelector('#movement-config .group-content').append(chainPanel);
 let chainModel='';
 function chainDescription(values){return (values||[]).map(p=>`${p.role==='FX'?'FX · ':p.role==='MIDI'?'MIDI · ':''}${p.instrument} → ${p.preset}`).join('  ·  ');}
 function paintChains(data){
  const rows=data.chainRecalls||[],phase=data.phase;
  if(!rows.length&&!['ready','failed'].includes(phase)){for(const b of chainRows.querySelectorAll('button'))b.disabled=true;return;}
  const model=JSON.stringify([rows,phase,data.chainSaveError,slot(),busy,pending]);if(model===chainModel)return;chainModel=model;
  chainRows.replaceChildren();
  if(!rows.length){chainRows.append(node('p',data.chainSaveError||'Aucune chaîne instrument disponible.','chain-recall-help'));return;}
  for(const row of rows){
   const card=node('article',undefined,'chain-recall-row');card.dataset.chainId=row.chainId;
   const content=node('div'),heading=node('strong',`CHAÎNE ${String(row.chainId).padStart(2,'0')} · ${row.channel?'CH '+row.channel:'CANAL NON FIXE'}`);
   content.append(heading,node('div',chainDescription(row.current)||'Chaîne indisponible','chain-recall-program'));
   content.append(node('small','RÉFÉRENCE : '+(row.reference?chainDescription(row.reference.processors):'AUCUNE · lier / sauvegarder le snapshot complet')));
   const state=node('small',({saved:'RÉFÉRENCE ENREGISTRÉE',modified:'MODIFIÉ · SAVE POUR CONSERVER',reference:'RÉFÉRENCE DU SNAPSHOT',unlinked:'ABSENTE DU SNAPSHOT',unsupported:'CAPTURE INDISPONIBLE'}[row.state]||row.state),'chain-recall-state');
   state.title='Les changements faits dans la fenêtre interne d’un plugin ne sont pas toujours observables ici. SAVE capture son état réel, même si le nom ne change pas.';content.append(state);card.append(content);
   const save=button('SAVE',()=>send('save_chain',{slot:slot(),chainId:row.chainId,identity:row.identity,fingerprint:row.fingerprint,expectedEngineSessionId:row.engineSessionId}));
   save.setAttribute('aria-label',`SAVE chaîne ${row.chainId}`);save.disabled=busy||pending||!row.canSave||!['ready','failed'].includes(phase);
   save.title='Sauvegarder uniquement cette chaîne · arrêter la lecture et relâcher les notes';card.append(save);chainRows.append(card);
  }
 }
 for(let i=1;i<=16;i++){const o=new Option(String(i),String(i));$('pc-channel').add(o);}
 let busy=false,model='',lastSlot=0,lastPhase='',settingsDirty=false,linkDirty=false;
 const settingsInputs=['pc-enabled','pc-channel','pc-snapshot'];
 for(const id of settingsInputs)$(id).onchange=()=>{settingsDirty=true;$('pc-status').textContent='MODIFICATIONS EN ATTENTE · APPLIQUER';};
 $('pc-link').onchange=()=>{linkDirty=true;};
 function slot(){return Number($('patch-slot').value);}
 function paint(data,force=false){
  const s=data.settings,m=JSON.stringify([s,data.snapshots,slot()]);
  if(force||m!==model){
   model=m;if(!settingsDirty){$('pc-enabled').checked=s.enabled;$('pc-channel').value=s.channel;$('pc-snapshot').checked=s.withSnapshot;}
   const selected=linkDirty?$('pc-link').value:s.links[String(slot())]?.snapshot||'';
   $('pc-link').replaceChildren(new Option('AUCUN',''));for(const item of data.snapshots)$('pc-link').add(new Option(item.name,item.path));
   $('pc-link').value=selected;
  }
  $('pc-status').textContent=data.lastError||({ready:'PRÊT',failed:'ÉCHEC',queued:'EN ATTENTE',saving_chain:'SAUVEGARDE DE LA CHAÎNE',preflight:'VÉRIFICATION',stopping:'ARRÊT',snapshot:'CHARGEMENT ZYNTHIAN',restore:'RESTAURATION MBMF'}[data.phase]||data.phase);
  if(settingsDirty)$('pc-status').textContent+=' · MODIFICATIONS EN ATTENTE : APPLIQUER';
  if(data.selectedSlot&&data.selectedSlot!==lastSlot){lastSlot=data.selectedSlot;$('patch-slot').value=data.selectedSlot;loadedPatchSlot=data.selectedSlot;model='';refreshPatchSlots();refreshHostChains();}
  if(lastPhase!==data.phase&&data.phase==='ready'){refresh();refreshPatchSlots();}
  if(lastPhase!==data.phase&&lastPhase&&!['ready','failed'].includes(lastPhase))$('patch-status').textContent=data.phase==='failed'?data.lastError||'RAPPEL ÉCHOUÉ':data.phase==='ready'?'PATCH RAPPELÉ':$('pc-status').textContent;
  lastPhase=data.phase;
  paintChains(data);
 }
 async function send(operation,extra={}){
  if(busy)return;busy=true;
  const frozen=new Map([...panel.querySelectorAll('input,select,button'),...chainPanel.querySelectorAll('button')].map(control=>[control,control.disabled]));
  for(const control of frozen.keys())control.disabled=true;
  try{const data=await request('/api/v1/patch-recall',{action:'patch_recall',operation,...extra});if(operation==='configure')settingsDirty=false;if(operation==='link'||operation==='save_pair')linkDirty=false;paint(data,true);}
  catch(e){$('pc-status').textContent=e.message;}
  finally{busy=false;for(const [control,disabled] of frozen)control.disabled=disabled;}
 }
 $('pc-apply').onclick=()=>send('configure',{enabled:$('pc-enabled').checked,channel:Number($('pc-channel').value),withSnapshot:$('pc-snapshot').checked});
 $('pc-associate').onclick=()=>{if($('pc-link').value)send('link',{slot:slot(),snapshot:$('pc-link').value});};
 $('pc-unlink').onclick=()=>send('link',{slot:slot(),snapshot:null});
 $('pc-save-pair').onclick=()=>{if(confirm('Sauvegarder le patch courant et les chaînes Zynthian dans cet emplacement ? Le patch sauvegardé sera remplacé.'))send('save_pair',{slot:slot()});};
 $('pc-load-pair').onclick=()=>send('recall',{slot:slot()});
 async function poll(){if(document.hidden||busy||pending)return;try{paint(await request('/api/v1/patch-recall'));}catch(e){$('pc-status').textContent='RAPPEL MIDI INDISPONIBLE';}}
 $('patch-slot').addEventListener('change',()=>{model='';linkDirty=false;poll();});
 document.addEventListener('DOMContentLoaded',()=>{poll();setInterval(poll,3000);},{once:true});
})();
