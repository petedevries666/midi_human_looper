'use strict';
// Browser preferences only; never change musical module order or patch data.
(function(){
const container=document.getElementById('module-groups');if(!container)return;
const key='mbmf.module-layout.v1';let saved={};try{saved=JSON.parse(localStorage.getItem(key)||'{}');}catch(e){}
if(!saved||typeof saved!=='object'||Array.isArray(saved))saved={};
const savedOrder=Array.isArray(saved.order)?saved.order:[];
const groups=[...container.querySelectorAll(':scope > details.module-group')];
const ids=new Set(groups.map(g=>g.id));
for(const id of savedOrder)if(ids.has(id))container.append(document.getElementById(id));
for(const g of groups)if(!savedOrder.includes(g.id))container.append(g);
let dragging=null;
function update(){const order=[...container.children];for(const g of order){g.querySelector('[data-move="up"]').disabled=order.indexOf(g)===0;g.querySelector('[data-move="down"]').disabled=order.indexOf(g)===order.length-1;}}
function persist(){try{localStorage.setItem(key,JSON.stringify({order:[...container.children].map(g=>g.id),open:Object.fromEntries(groups.map(g=>[g.id,g.open]))}));}catch(e){}update();}
for(const group of groups){
 if(typeof saved.open?.[group.id]==='boolean')group.open=saved.open[group.id];
 const summary=group.querySelector(':scope > summary'),title=summary.querySelector('h2').textContent.trim();
 const controls=document.createElement('span');controls.className='group-layout-controls';
 const handle=document.createElement('button');handle.type='button';handle.className='group-drag-handle';handle.textContent='\u283f';handle.draggable=true;handle.title='Drag to reorder '+title;handle.setAttribute('aria-label','Drag '+title+' to reorder');
 handle.addEventListener('click',e=>{e.preventDefault();e.stopPropagation();});
 handle.addEventListener('dragstart',e=>{dragging=group;e.dataTransfer.effectAllowed='move';e.dataTransfer.setData('text/plain',group.id);});
 handle.addEventListener('dragend',()=>{dragging=null;for(const g of groups)delete g.dataset.drop;});controls.append(handle);
 for(const [direction,label] of [['up','\u2191'],['down','\u2193']]){const b=document.createElement('button');b.type='button';b.textContent=label;b.dataset.move=direction;b.setAttribute('aria-label','Move '+title+' '+direction);b.title='Move '+direction;b.addEventListener('click',e=>{e.preventDefault();e.stopPropagation();const other=direction==='up'?group.previousElementSibling:group.nextElementSibling;if(!other)return;if(direction==='up')container.insertBefore(group,other);else container.insertBefore(other,group);persist();b.focus();});controls.append(b);}
 summary.append(controls);group.addEventListener('toggle',persist);
 group.addEventListener('dragover',e=>{if(!dragging||dragging===group)return;e.preventDefault();group.dataset.drop='true';});
 group.addEventListener('dragleave',e=>{if(!group.contains(e.relatedTarget))delete group.dataset.drop;});
 group.addEventListener('drop',e=>{if(!dragging||dragging===group)return;e.preventDefault();const rect=summary.getBoundingClientRect();container.insertBefore(dragging,e.clientY>rect.top+rect.height/2?group.nextElementSibling:group);for(const g of groups)delete g.dataset.drop;dragging=null;persist();});
}
update();
for(const [id,kind] of [['add-instrument','INSTRUMENT'],['capture-snapshot','SNAPSHOT'],['add-controller','CONTROLLER'],['add-movement','MOVEMENT']]){const n=document.getElementById(id);if(n)window.MBMF_TILES?.decorate(n,kind,'add',true);}
})();
