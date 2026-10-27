(()=>{
'use strict';
const panel=node('fieldset');panel.id='midi-thru-panel';
panel.append(node('legend','MIDI THRU / ENTRÉES'));
const scope=document.createElement('select');scope.setAttribute('aria-label','Portée des réglages MIDI THRU');
for(const [value,label] of [['global','GLOBAL'],['patch','PATCH ACTUEL']]){const option=node('option',label);option.value=value;scope.append(option);}
const scopeLabel=node('label','RÉGLAGES ');scopeLabel.append(scope);
const refreshButton=button('ACTUALISER',()=>{if(!dirty||confirm('Abandonner les réglages non appliqués ?'))load(true);});
const help=node('p','OFF : commandes et LEARN restent actifs. NON ASSIGNÉ : seules les notes non utilisées comme commandes passent. TOUT : les commandes peuvent aussi jouer. La capture LEARN reste silencieuse.');
const routingHelp=node('p','Le jeu direct passe ensuite par les canaux IN/OUT des INSTRUMENTS. Les phrases et Movements internes ne sont pas filtrés par MIDI THRU.');
const status=node('output');status.setAttribute('role','status');
const rows=node('div');rows.className='midi-thru-inputs';
panel.append(scopeLabel,refreshButton,help,routingHelp,status,rows);
document.querySelector('#movement-config .group-content').append(panel);
let data=null,model='',dirty=false,busy=false;
const patchRows=extension=>{const w=extension?.configuration||[1,0],result=[];for(let at=2;at<w.length;at+=17)result.push({source:w[at],channels:w.slice(at+1,at+17)});return result;};
function paint(){
 if(!data)return;
 const signature=JSON.stringify([scope.value,data.available,data.enabled,data.inputs,data.patch,data.activeSlot]);
 if(signature===model)return;model=signature;rows.replaceChildren();
 if(!data.available){status.textContent=data.reason||'Cette version du moteur ne propose pas encore MIDI THRU.';return;}
 status.textContent=data.enabled?'MIDI THRU actif.':'La première activation demande une lecture arrêtée et les notes relâchées.';
 if(!data.inputs.length){rows.append(node('p','Aucune entrée MIDI physique détectée.'));return;}
 const rules=patchRows(data.patch);
 for(const input of data.inputs){
  const card=node('article');card.className='midi-thru-input';
  card.append(node('strong',input.name),node('small',input.ambiguous?'AMBIGUË · CONNEXION REFUSÉE':input.present?'CONNECTÉE':'DÉCONNECTÉE'));
  const grid=node('div');grid.className='midi-thru-channels';
  const rule=rules.find(r=>r.source===input.id);
  const patchUnavailable=scope.value==='patch'&&(!input.id||!input.enabled||!data.enabled);
  const values=scope.value==='patch'?(rule?.channels||Array(16).fill(-1)):input.channels;
  const selects=[];
  for(let ch=0;ch<16;ch++){
   const label=node('label','CH '+(ch+1));const select=document.createElement('select');
   select.setAttribute('aria-label',`${input.name} canal ${ch+1}`);
   const inherited=scope.value==='patch'?(input.channels[ch]<0?data.defaults[ch]:input.channels[ch]):data.defaults[ch];
   const names=['OFF','NON ASSIGNÉ','TOUT'];
   for(const value of [-1,0,1,2]){const option=node('option',value<0?'HÉRITÉ · '+names[inherited]:names[value]);option.value=String(value);select.append(option);}
   select.value=String(values[ch]);select.disabled=input.ambiguous||patchUnavailable;
   select.onchange=()=>{dirty=true;status.textContent='Réglages modifiés · cliquer APPLIQUER pour les conserver.';};
   label.append(select);grid.append(label);selects.push(select);
  }
  const apply=button(scope.value==='patch'?'APPLIQUER AU PATCH':input.enabled?'APPLIQUER GLOBAL':'GÉRER CETTE ENTRÉE',async()=>{
   if(busy)return;busy=true;apply.disabled=true;
   try{
    const channels=selects.map(s=>Number(s.value));
    if(scope.value==='global'){
     await request('/api/v1/midi-inputs',{key:input.key,enabled:true,channels,expectedConfigurationRevision:data.configurationRevision,expectedEngineSessionId:data.engineSessionId});
    }else{
     const fresh=await request('/api/v1/midi-inputs');
     if(fresh.engineSessionId!==data.engineSessionId||fresh.activeSlot!==data.activeSlot||JSON.stringify(fresh.patch)!==JSON.stringify(data.patch))throw new Error('Le patch a changé · actualiser avant de modifier.');
     const next=patchRows(fresh.patch).filter(r=>r.source!==input.id);
     if(channels.some(v=>v!==-1))next.push({source:input.id,channels});
     const configuration=[1,next.length];for(const r of next)configuration.push(r.source,...r.channels);
     if(!await command({action:'midi_thru_commit',midiThru:{version:1,configuration},expectedRevision:fresh.revision,expectedEngineSessionId:fresh.engineSessionId}))throw new Error('Modification non appliquée · consulter le message de l’interface.');
    }
    dirty=false;model='';await load(true);status.textContent='Réglages enregistrés. Le routage Zynthian se synchronise.';
   }catch(error){status.textContent=error.message;}
   finally{busy=false;apply.disabled=input.ambiguous||patchUnavailable;}
  });
  apply.disabled=input.ambiguous||patchUnavailable;
  if(patchUnavailable)card.append(node('small','Activer la gestion de cette entrée dans GLOBAL avant de créer une surcharge par patch.'));
  card.append(grid,apply);rows.append(card);
 }
}
async function load(force=false){
 if(busy&&!force)return;
 if(dirty&&!force)return;
 try{data=await request('/api/v1/midi-inputs');if(force){dirty=false;model='';}paint();}
 catch(error){status.textContent=error.message;}
}
scope.onchange=()=>{if(dirty&&!confirm('Abandonner les réglages non appliqués ?')){scope.value=scope.value==='patch'?'global':'patch';return;}dirty=false;model='';paint();};
const section=document.getElementById('movement-config');section.addEventListener('toggle',()=>{if(section.open)load();});
setInterval(()=>{if(section.open&&!document.hidden&&!panel.contains(document.activeElement))load();},2000);
})();
