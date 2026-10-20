'use strict';
// Offline expressive editor LAB. Deliberately isolated from the production
// transformer picker until native engine registration and ownership are proven.
(()=>{
 const drafts=new Map();
 window.MBMF_EXPRESSIVE={open(instrumentId,kind){
 const root=document.createElement('div');
 const key=instrumentId+':'+kind;
 const saved=drafts.get(key);
 const make=(tag,label)=>{const el=document.createElement(tag);if(label!=null)el.textContent=label;return el;};
 const status=make('p','LOCAL PREVIEW ONLY · not connected to the MIDI engine');
 status.setAttribute('role','status');
 const human=saved?.human?structuredClone(saved.human):{version:1,type:'humanizer',enabled:false,timingMs:0,biasMs:0,
   velocityPercent:0,distribution:'gaussian',variation:'fixed',scope:'group',seed:1};
 const curve=saved?.curve?structuredClone(saved.curve):{version:1,type:'velocity_curves',enabled:true,amount:100,points:[[1,1],[127,127]]};
 const layout=make('div');layout.className='expressive-lab-layout';
 const heading=make('h3','HUMANIZER');if(kind==='humanizer')layout.append(heading);
 const number=(label,key,min,max,step)=>{
  const row=make('label',label+' '),field=make('input');field.type='number';
  field.min=min;field.max=max;field.step=step;field.value=human[key];field.setAttribute('aria-label',label);
  field.addEventListener('change',()=>{
   const v=Number(field.value);
   if(!Number.isFinite(v)||v<min||v>max){field.value=human[key];status.textContent=label+' : valeur hors limites';return;}
   human[key]=v;update();
  });
  row.append(field);if(kind==='humanizer')layout.append(row);
 };
 const choice=(label,key,values)=>{
  const row=make('label',label+' '),field=make('select');
  for(const value of values){const option=make('option',value.toUpperCase());option.value=value;field.append(option);}
  field.value=human[key];field.addEventListener('change',()=>{human[key]=field.value;update();});
  row.append(field);layout.append(row);
 };
 const toggle=make('label','ENABLED '),checkbox=make('input');checkbox.type='checkbox';
 checkbox.addEventListener('change',()=>{human.enabled=checkbox.checked;update();});
 toggle.append(checkbox);layout.append(toggle);
 number('TIMING RANGE ±ms','timingMs',0,2000,1);
 number('BIAS ms','biasMs',-2000,2000,1);
 number('VELOCITY VARIATION %','velocityPercent',0,100,1);
 number('SEED','seed',0,4294967295,1);
 choice('DISTRIBUTION','distribution',['gaussian','uniform']);
 choice('VARIATION','variation',['fixed','evolving']);
 choice('SCOPE','scope',['group','notes']);
 if(kind==='velocity_curves')layout.append(make('h3','VELOCITY CURVES'));
 const amountLabel=make('label','AMOUNT % '),amount=make('input');
 amount.type='number';amount.min=0;amount.max=100;amount.step=1;amount.value=100;
 amount.addEventListener('change',()=>{
  const v=Number(amount.value);if(!Number.isFinite(v)||v<0||v>100){amount.value=curve.amount;return;}
  curve.amount=v;update();
 });
 amountLabel.append(amount);if(kind==='velocity_curves')layout.append(amountLabel);
 const presets=make('div');
 const preview=make('svg');preview.setAttribute('viewBox','0 0 260 260');
 preview.setAttribute('role','img');preview.setAttribute('aria-label','Velocity response 1 to 127');
 preview.style.cssText='display:block;max-width:320px;width:100%;height:auto;border:1px solid currentColor;touch-action:none';
 const pointsList=make('div');
 const controls=make('div');
 const patch=make('textarea');patch.rows=13;patch.readOnly=true;patch.setAttribute('aria-label','Validated local patch JSON');
 patch.style.cssText='display:block;width:100%;font-family:monospace';
 const safePoint=(x,y)=>[Math.max(1,Math.min(127,Math.round(x))),Math.max(1,Math.min(127,Math.round(y)))];
 const shape=points=>{
  if(points.length<2||points.length>16||points[0][0]!==1||points[points.length-1][0]!==127)return false;
  return points.every((p,i)=>Array.isArray(p)&&p.length===2&&p.every(v=>Number.isInteger(v)&&v>=1&&v<=127)&&(!i||p[0]>points[i-1][0]));
 };
 const interpolate=v=>{
  let i=1;while(i<curve.points.length-1&&v>curve.points[i][0])i++;
  const a=curve.points[i-1],b=curve.points[i];
  const target=a[1]+(b[1]-a[1])*(v-a[0])/(b[0]-a[0]);
  return Math.max(1,Math.min(127,Math.round(v+(target-v)*curve.amount/100)));
 };
 function update(){
  if(!shape(curve.points))throw Error('Invalid curve points');
  patch.value=JSON.stringify({expressiveVersion:1,modules:[human,curve]},null,2);
  preview.replaceChildren();
  const ns='http://www.w3.org/2000/svg';
  const line=document.createElementNS(ns,'line');Object.entries({x1:0,y1:260,x2:260,y2:0,stroke:'currentColor','stroke-opacity':'.18'}).forEach(([k,v])=>line.setAttribute(k,v));preview.append(line);
  const path=document.createElementNS(ns,'path');
  const d=Array.from({length:127},(_,i)=>{const v=i+1;return (i?'L':'M')+((v-1)*260/126).toFixed(2)+' '+(260-(interpolate(v)-1)*260/126).toFixed(2)}).join(' ');
  path.setAttribute('d',d);path.setAttribute('fill','none');path.setAttribute('stroke','#d7bd50');path.setAttribute('stroke-width','3');preview.append(path);
  for(const [index,p] of curve.points.entries()){
   const circle=document.createElementNS(ns,'circle');circle.setAttribute('cx',(p[0]-1)*260/126);
   circle.setAttribute('cy',260-(p[1]-1)*260/126);circle.setAttribute('r',6);
   circle.setAttribute('fill','#d7bd50');circle.setAttribute('tabindex','0');
   circle.setAttribute('aria-label','Point '+(index+1)+' '+p[0]+' '+p[1]);preview.append(circle);
  }
  pointsList.replaceChildren();
  curve.points.forEach((p,i)=>{
   const row=make('div');row.style.cssText='display:flex;gap:6px;align-items:center;margin:4px 0';
   row.append(make('span','P'+(i+1)+' '));
   [0,1].forEach(axis=>{
    const field=make('input');field.type='number';field.min=1;field.max=127;field.step=1;field.value=p[axis];field.style.width='70px';
    field.setAttribute('aria-label','Point '+(i+1)+' '+(axis?'output':'input'));
    if(!axis&&(i===0||i===curve.points.length-1))field.disabled=true;
    field.addEventListener('change',()=>{
     const candidate=curve.points.map(x=>[...x]);candidate[i][axis]=Number(field.value);
     if(!shape(candidate)){field.value=p[axis];status.textContent='Points : X strictement croissants, Y de 1 à 127';return;}
     curve.points=candidate;update();
    });row.append(field);
   });
   if(i>0&&i<curve.points.length-1){const del=make('button','REMOVE');del.type='button';del.addEventListener('click',()=>{curve.points.splice(i,1);update();});row.append(del);}
   pointsList.append(row);
  });
 }
 const setPreset=(name,points)=>{
  const b=make('button',name);b.type='button';b.addEventListener('click',()=>{curve.points=points.map(p=>[...p]);update();});
  presets.append(b);
 };
 setPreset('LINEAR',[[1,1],[127,127]]);
 setPreset('INVERT',[[1,127],[127,1]]);
 setPreset('SOFT',[[1,35],[64,82],[127,127]]);
 setPreset('HARD',[[1,1],[64,38],[127,127]]);
 setPreset('CRUSH',[[1,64],[127,64]]);
 const add=make('button','ADD POINT');add.type='button';
 add.addEventListener('click',()=>{
  if(curve.points.length>=16){status.textContent='Maximum 16 points';return;}
  let index=1;
  while(index<curve.points.length&&curve.points[index][0]-curve.points[index-1][0]<=1)index++;
  if(index>=curve.points.length){status.textContent='No space between existing X points';return;}
  const a=curve.points[index-1],b=curve.points[index],x=Math.floor((a[0]+b[0])/2);
  curve.points.splice(index,0,safePoint(x,Math.round((a[1]+b[1])/2)));update();
 });controls.append(add);
 const copy=make('button','COPY JSON');copy.type='button';
 copy.addEventListener('click',async()=>{
  try{await navigator.clipboard.writeText(patch.value);status.textContent='Copied local JSON · NOT APPLIED to MIDI engine';}
  catch(e){patch.select();status.textContent='Clipboard unavailable; select and copy JSON manually';}
 });controls.append(copy);
 const download=make('button','EXPORT JSON');download.type='button';
 download.addEventListener('click',()=>{
  const blob=new Blob([patch.value+'\n'],{type:'application/json'});
  const url=URL.createObjectURL(blob),a=make('a');a.href=url;a.download='mbmf-expressive-draft.json';
  a.click();URL.revokeObjectURL(url);status.textContent='Exported local JSON · NOT APPLIED';
 });controls.append(download);
 if(kind==='velocity_curves')layout.append(presets,preview,pointsList);
 layout.append(controls,patch,status);
 const save=make('button','KEEP DRAFT');save.type='button';
 save.addEventListener('click',()=>{drafts.set(key,{human:structuredClone(human),curve:structuredClone(curve)});status.textContent='Draft kept for this instrument in this browser session. NOT SAVED TO PATCH / NOT ACTIVE IN ENGINE.';});
 layout.append(save);root.append(layout);update();return root;
 },has(instrumentId,kind){return drafts.has(instrumentId+':'+kind);}};
})();
