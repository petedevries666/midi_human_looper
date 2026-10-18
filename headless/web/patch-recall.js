'use strict';
(()=>{
 const panel=document.createElement('fieldset');panel.id='patch-recall-options';
 panel.innerHTML='<legend>PATCHES / MIDI PROGRAM CHANGE</legend><label><input id="pc-enabled" type="checkbox"> MIDI RECALL</label> <label>CANAL <select id="pc-channel" aria-label="Program Change channel"></select></label> <label><input id="pc-snapshot" type="checkbox"> CHARGER LE SNAPSHOT ZYNTHIAN</label> <button id="pc-apply">APPLIQUER</button><p>PC 0 ignoré · PC 1 = PATCH 01 · Certains contrôleurs affichent les programmes avec un décalage de 1.</p><label>SNAPSHOT DU PATCH <select id="pc-link" aria-label="Linked Zynthian snapshot"></select></label> <button id="pc-associate">LIER</button> <button id="pc-unlink">DÉLIER</button><p><button id="pc-save-pair">SAUVER PATCH + SNAPSHOT ZYNTHIAN</button> <button id="pc-load-pair">RAPPELER PATCH</button></p><output id="pc-status" role="status"></output>';
 document.querySelector('#movement-config .group-content').append(panel);
 for(let i=1;i<=16;i++){const o=new Option(String(i),String(i));$('pc-channel').add(o);}
 let busy=false,model='',lastSlot=0,lastPhase='';
 function slot(){return Number($('patch-slot').value);}
 function paint(data,force=false){
  const s=data.settings,m=JSON.stringify([s,data.snapshots,slot()]);
  if(force||m!==model){
   model=m;$('pc-enabled').checked=s.enabled;$('pc-channel').value=s.channel;$('pc-snapshot').checked=s.withSnapshot;
   $('pc-link').replaceChildren(new Option('AUCUN',''));for(const item of data.snapshots)$('pc-link').add(new Option(item.name,item.path));
   $('pc-link').value=s.links[String(slot())]?.snapshot||'';
  }
  $('pc-status').textContent=data.lastError||({ready:'PRÊT',failed:'ÉCHEC',preflight:'VÉRIFICATION',stopping:'ARRÊT',snapshot:'CHARGEMENT ZYNTHIAN',restore:'RESTAURATION MBMF'}[data.phase]||data.phase);
  if(data.selectedSlot&&data.selectedSlot!==lastSlot){lastSlot=data.selectedSlot;$('patch-slot').value=data.selectedSlot;loadedPatchSlot=data.selectedSlot;model='';refreshPatchSlots();refreshHostChains();}
  if(lastPhase!==data.phase&&data.phase==='ready'){refresh();refreshPatchSlots();}
  lastPhase=data.phase;
 }
 async function send(operation,extra={}){
  if(busy)return;busy=true;
  try{paint(await request('/api/v1/patch-recall',{action:'patch_recall',operation,...extra}),true);}
  catch(e){$('pc-status').textContent=e.message;}
  finally{busy=false;}
 }
 $('pc-apply').onclick=()=>send('configure',{enabled:$('pc-enabled').checked,channel:Number($('pc-channel').value),withSnapshot:$('pc-snapshot').checked});
 $('pc-associate').onclick=()=>{if($('pc-link').value)send('link',{slot:slot(),snapshot:$('pc-link').value});};
 $('pc-unlink').onclick=()=>send('link',{slot:slot(),snapshot:null});
 $('pc-save-pair').onclick=()=>{if(confirm('Sauvegarder le patch courant et les chaînes Zynthian dans cet emplacement ? Le patch sauvegardé sera remplacé.'))send('save_pair',{slot:slot()});};
 $('pc-load-pair').onclick=()=>send('recall',{slot:slot()});
 async function poll(){if(document.hidden||busy||pending)return;try{paint(await request('/api/v1/patch-recall'));}catch(e){$('pc-status').textContent='RAPPEL MIDI INDISPONIBLE';}}
 $('patch-slot').addEventListener('change',()=>{model='';poll();});
 document.addEventListener('DOMContentLoaded',()=>{poll();setInterval(poll,3000);},{once:true});
})();
