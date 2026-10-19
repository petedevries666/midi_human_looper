'use strict';
// Detached worker clipboards; the browser never holds patch/event payloads.
const blockClipboards=new Map();
async function blockOperation(action,kind,source=null,target=null,mode='empty'){
 if(pending)return;
 if(action==='paste'&&$('editor').open){$('error').textContent='Fermer l’éditeur avant PASTE pour conserver son brouillon.';return;}
 setPending(true);
 try{
  const reply=await request('/api/v1/blocks',{action,kind,source,target,mode,clipboardId:blockClipboards.get(kind),expectedRevision:revision,expectedEngineSessionId:engineSession});
  if(action==='copy'){blockClipboards.set(kind,reply.clipboardId);$('patch-status').textContent=`${kind.toUpperCase()} COPIED`;}
  else{renderedModel='';renderedSnapshots='';movementRevision=-1;await refresh();$('patch-status').textContent=`${kind.toUpperCase()} ${mode==='swap'?'SWAPPED':'PASTED'} · SAVE PATCH pour conserver`;}
  $('error').textContent='';
 }catch(e){$('error').textContent=e.message;}
 finally{setPending(false);}
}
function blockCopyAction(kind,id){return {label:'COPY',disabled:pending,run:()=>blockOperation('copy',kind,id)};}
function blockPasteActions(kind,target=null,occupied=false){
 return [{label:'PASTE',disabled:pending||!blockClipboards.has(kind),run:()=>{
  if(kind==='phrase'&&occupied)phrasePasteChoice(target);
  else blockOperation('paste',kind,null,target);
 }}];
}
function phrasePasteChoice(target){
 const dialog=$('editor');if(dialog.open)return;
 const content=$('editor-content');content.replaceChildren(node('h2',`PASTE · PHRASE ${target}`),node('p','Emplacement occupé : OVERWRITE remplace son contenu. SWAP échange les contenus avec la phrase copiée dans ce patch. Les numéros et leurs liens restent en place.'));
 for(const mode of ['overwrite','swap'])content.append(button(mode.toUpperCase(),()=>{dialog.close();blockOperation('paste','phrase',null,target,mode);}));
 content.append(button('CANCEL',()=>dialog.close()));showEditor(dialog);
}
function emptyBlockActions(card,kind){if(card.dataset.blockEmptyBound)return;card.dataset.blockEmptyBound=kind;cardActions(card,()=>blockPasteActions(kind));}

// This is a browser layout preference per loaded patch, never a musical reorder.
let blockDragging=null;
function blockLayoutKey(kind){return `mbmf.blocks.v1.${loadedPatchSlot}.${kind}`;}
function blockCards(kind){const ids={snapshot:'snapshots',switch:'switches',movement:'movements'};return [...$(ids[kind]).children].filter(n=>n.dataset.blockId);}
function rememberBlockLayout(kind){try{localStorage.setItem(blockLayoutKey(kind),JSON.stringify(blockCards(kind).map(n=>n.dataset.blockId)));}catch(e){$('patch-status').textContent='Disposition appliquée ; stockage navigateur indisponible';}}
function applyBlockLayout(kind){
 if(blockDragging)return;
 let saved=[];try{saved=JSON.parse(localStorage.getItem(blockLayoutKey(kind))||'[]');}catch(e){}
 if(!Array.isArray(saved))return;
 saved=[...new Set(saved.filter(id=>typeof id==='string'))];
 const cards=blockCards(kind);if(!cards.length)return;
 const ordered=[...saved.map(id=>cards.find(n=>n.dataset.blockId===id)).filter(Boolean),...cards.filter(n=>!saved.includes(n.dataset.blockId))];
 // Do not detach/reinsert an unchanged live test button on every telemetry frame.
 if(ordered.every((n,i)=>n===cards[i]))return;
 const parent=cards[0].parentElement,tail=[...parent.children].find(n=>!n.dataset.blockId)||null;
 for(const n of ordered)parent.insertBefore(n,tail);
}
function moveBlock(card,kind,delta){const cards=blockCards(kind),i=cards.indexOf(card),other=cards[i+delta];if(!other)return;card.parentElement.insertBefore(delta<0?card:other,delta<0?other:card);rememberBlockLayout(kind);}
function blockMoveActions(card,kind){return [{label:'← DÉPLACER',disabled:!card.previousElementSibling?.dataset.blockId,run:()=>moveBlock(card,kind,-1)},{label:'DÉPLACER →',disabled:!card.nextElementSibling?.dataset.blockId,run:()=>moveBlock(card,kind,1)}];}
function movableBlock(card,kind,id){
 card.dataset.blockId=String(id);card.dataset.blockKind=kind;
 const handle=node('button','⠿','block-drag-handle');handle.type='button';handle.draggable=true;handle.title='Glisser pour déplacer · flèches au clavier';handle.setAttribute('aria-label',`Déplacer ${kind} ${id}`);
 handle.onclick=e=>{e.preventDefault();e.stopPropagation();};
 handle.onkeydown=e=>{if(['ArrowLeft','ArrowUp','ArrowRight','ArrowDown'].includes(e.key)){e.preventDefault();e.stopPropagation();moveBlock(card,kind,['ArrowLeft','ArrowUp'].includes(e.key)?-1:1);handle.focus();}};
 handle.ondragstart=e=>{e.stopPropagation();closeCardMenu();blockDragging={card,kind};e.dataTransfer.effectAllowed='move';e.dataTransfer.setData('text/plain',String(id));};
 const finish=()=>{if(blockDragging){rememberBlockLayout(blockDragging.kind);blockDragging.card.classList.remove('block-dragging');}blockDragging=null;};
 handle.ondragend=finish;
 const place=e=>{if(!blockDragging||blockDragging.kind!==kind||blockDragging.card===card)return;e.preventDefault();e.stopPropagation();const r=card.getBoundingClientRect();const after=e.clientY>r.top+r.height*.7||e.clientX>r.left+r.width/2;card.parentElement.insertBefore(blockDragging.card,after?card.nextSibling:card);};
 card.addEventListener('dragover',e=>{if(blockDragging?.kind===kind){e.preventDefault();e.stopPropagation();}});card.addEventListener('drop',e=>{place(e);finish();});
 // Touch drag uses only the small handle, leaving card long-press menus intact.
 handle.onpointerdown=e=>{if(e.pointerType!=='touch')return;e.preventDefault();handle.setPointerCapture(e.pointerId);blockDragging={card,kind};card.classList.add('block-dragging');};
 handle.onpointermove=e=>{if(e.pointerType!=='touch'||blockDragging?.card!==card)return;const target=document.elementFromPoint(e.clientX,e.clientY)?.closest('[data-block-id]');if(target&&target!==card&&target.dataset.blockKind===kind){const r=target.getBoundingClientRect();target.parentElement.insertBefore(card,e.clientY>r.top+r.height/2?target.nextSibling:target);}};
 for(const edge of ['pointerup','pointercancel','lostpointercapture'])handle.addEventListener(edge,e=>{if(e.pointerType==='touch')finish();});
 card.append(handle);
}
