'use strict';
let activeCardMenu=null;
function closeCardMenu(){activeCardMenu?.remove();activeCardMenu=null;}
function openCardMenu(card,actions,x,y){
 closeCardMenu();const menu=document.createElement('div');menu.className='card-context-menu';menu.setAttribute('role','menu');
 for(const action of actions){if(action.hidden)continue;const b=document.createElement('button');b.type='button';b.textContent=action.label;b.setAttribute('role','menuitem');b.disabled=!!action.disabled;b.onclick=()=>{closeCardMenu();action.run();};menu.append(b);}
 ($('editor').open?$('editor'):document.body).append(menu);activeCardMenu=menu;
 const box=menu.getBoundingClientRect();menu.style.left=Math.max(4,Math.min(x,innerWidth-box.width-4))+'px';menu.style.top=Math.max(4,Math.min(y,innerHeight-box.height-4))+'px';
 menu.addEventListener('keydown',e=>{const buttons=[...menu.querySelectorAll('button:not(:disabled)')],i=buttons.indexOf(document.activeElement);if(e.key==='Escape'){e.preventDefault();closeCardMenu();card.focus();}else if(e.key==='ArrowDown'||e.key==='ArrowUp'){e.preventDefault();buttons[(i+(e.key==='ArrowDown'?1:-1)+buttons.length)%buttons.length]?.focus();}});
 menu.querySelector('button:not(:disabled)')?.focus();
}
function cardActions(card,actions,onactivate=null){
 card.tabIndex=0;card.title='Clic droit / appui long : actions du bloc';let timer=null,start=null,suppressUntil=0;
 const menu=(x,y)=>{suppressUntil=Date.now()+800;openCardMenu(card,typeof actions==='function'?actions():actions,x,y);};
 card.addEventListener('contextmenu',e=>{e.preventDefault();e.stopPropagation();menu(e.clientX,e.clientY);});
 card.addEventListener('keydown',e=>{if(e.target!==card)return;if(e.key==='ContextMenu'||(e.shiftKey&&e.key==='F10')){e.preventDefault();const r=card.getBoundingClientRect();menu(r.left,r.bottom);}else if(onactivate&&(e.key==='Enter'||e.key===' ')){e.preventDefault();onactivate();}});
 const cancel=()=>{clearTimeout(timer);timer=null;};
 card.addEventListener('pointerdown',e=>{if(e.pointerType!=='touch'||(e.target!==card&&e.target.closest('button,input,select,a')))return;start=[e.clientX,e.clientY];timer=setTimeout(()=>{timer=null;menu(...start);},600);});
 card.addEventListener('pointermove',e=>{if(start&&Math.hypot(e.clientX-start[0],e.clientY-start[1])>8)cancel();});
 for(const edge of ['pointerup','pointercancel','lostpointercapture'])card.addEventListener(edge,cancel);
 card.addEventListener('click',e=>{if(Date.now()<suppressUntil){e.preventDefault();e.stopImmediatePropagation();return;}if(onactivate&&!e.target.closest('button,input,select,a'))onactivate();},true);
}
document.addEventListener('pointerdown',e=>{if(activeCardMenu&&!activeCardMenu.contains(e.target)){e.preventDefault();e.stopImmediatePropagation();closeCardMenu();}},true);
document.addEventListener('keydown',e=>{if(e.key==='Escape'&&activeCardMenu){e.preventDefault();closeCardMenu();}});
window.addEventListener('blur',closeCardMenu);
let modulationLayoutFrame=0;
function positionModulationCurves(){
 if(modulationLayoutFrame)return;
 modulationLayoutFrame=requestAnimationFrame(()=>{
 modulationLayoutFrame=0;
 const updates=[];
 for(const svg of document.querySelectorAll('svg[data-modulation-preview]')){
  const rail=svg.mbmfRail,parent=svg.parentElement;if(!rail?.isConnected||!parent)continue;
  const r=rail.getBoundingClientRect(),p=parent.getBoundingClientRect();
  updates.push([svg,{left:(r.left-p.left-parent.clientLeft+1)+'px',top:(r.top-p.top-parent.clientTop+1)+'px',bottom:'auto',width:Math.max(0,r.width-2)+'px',height:Math.max(0,r.height-2)+'px'}]);
 }
 // Read all geometry first. Identical observer notifications never write styles
 // again: no read/write/read layout thrashing or resize feedback in Firefox.
 for(const [svg,styles] of updates)for(const [key,value] of Object.entries(styles))if(svg.style[key]!==value)svg.style[key]=value;
 });
}
window.addEventListener('resize',positionModulationCurves);
document.addEventListener('DOMContentLoaded',()=>{if(window.ResizeObserver)new ResizeObserver(positionModulationCurves).observe(document.querySelector('main'));});
