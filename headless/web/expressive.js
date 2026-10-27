(()=>{
'use strict';
const el=(tag,text,cls)=>{const n=document.createElement(tag);if(text!==undefined)n.textContent=text;if(cls)n.className=cls;return n;};
const btn=(text,fn)=>{const b=el('button',text);b.type='button';b.onclick=fn;return b;};
function decode(state){
 const w=state&&state.nativeExpressive&&state.nativeExpressive.configuration||[1,0],rows=[];let at=2;
 if(!Array.isArray(w)||w[0]!==1)return rows;
 for(let n=0;n<w[1]&&at+15<=w.length;n++){
  const a=w.slice(at,at+15);at+=15;const pts=[];
  for(let j=0;j<a[14]&&at+1<w.length;j++){pts.push({x:w[at],y:w[at+1]});at+=2;}
  rows.push({instrument:a[0],humanizerModule:a[1],humanizer:{enabled:!!a[2],timingMs:a[3],biasMs:a[4],velocityPercent:a[5],feel:a[6],variation:a[7],scope:a[8],seed:a[9],liveLookaheadMs:a[10]},curveModule:a[11],curve:{enabled:!!a[12],amount:a[13],points:pts}});
 }return rows;
}
const fresh=id=>({instrument:id,humanizerModule:0,humanizer:{enabled:false,timingMs:20,biasMs:0,velocityPercent:0,feel:1,variation:0,scope:0,seed:1,liveLookaheadMs:0},curveModule:0,curve:{enabled:false,amount:100,points:[{x:1,y:1},{x:127,y:127}]}});
function encode(rows){const w=[1,rows.length];for(const r of rows){const h=r.humanizer,c=r.curve;w.push(r.instrument,r.humanizerModule,+h.enabled,h.timingMs,h.biasMs,h.velocityPercent,h.feel,h.variation,h.scope,h.seed,h.liveLookaheadMs,r.curveModule,+c.enabled,c.amount,c.points.length);for(const p of c.points)w.push(p.x,p.y);}return {version:1,configuration:w};}
function current(state){const live=window.MBMF_CURRENT_STATE?.();return live?.engineSessionId===state?.engineSessionId?live:state;}
async function apply(state,id,update,send){const rows=decode(current(state));let r=rows.find(x=>x.instrument===id);if(!r){r=fresh(id);rows.push(r);}update(r);return send({action:'expressive_commit',expressive:encode(rows.filter(x=>x.humanizerModule||x.curveModule))});}
const moduleField=key=>key==='humanizer'?'humanizerModule':'curveModule';
async function add(i,state,key,send){return apply(state,i.id,r=>{r[moduleField(key)]=i.id;r[key].enabled=true;},send);}
function mount(i,state,send,ui){
 const r=decode(state).find(x=>x.instrument===i.id)||fresh(i.id),root=document.createDocumentFragment();
 const routed=(state.instruments||[]).filter(x=>x.enabled&&x.output===i.output&&x.output>0);
 [['HUMANIZER','humanizer'],['VELOCITY CURVES','curve']].forEach(([name,key])=>{if(!r[moduleField(key)])return;const c=r[key],card=el('article',undefined,'module expressive-module');card.dataset.instrumentId=i.id;card.dataset.moduleId=key;card.classList.toggle('bypassed',!c.enabled);card.classList.toggle('selected',ui.selected?.instrumentId===i.id&&ui.selected?.moduleId===key);ui.decorate?.(card,'TRANSFORMER',key+':'+i.id);card.append(el('strong',name),el('small',c.enabled?'ON':'BYPASS'));const feedback=el('div',undefined,'module-feedback');feedback.append(el('small',key==='humanizer'?'TIMING':'AMOUNT'),el('output',key==='humanizer'?c.timingMs+' ms':c.amount+'%'));card.append(feedback);if(!i.output||routed.length>1)card.append(el('small','MIDI OUT unique requis','expressive-routing-note'));const bypass=btn('BYPASS',()=>apply(state,i.id,x=>{x[key].enabled=!x[key].enabled;},send));bypass.setAttribute('aria-pressed',String(!c.enabled));card.append(bypass);ui.cardActions(card,[{label:'EDIT',run:()=>ui.edit(i,key)},{label:'DELETE',run:async()=>{if(!confirm('Supprimer '+name+' ?'))return;if(await apply(state,i.id,x=>{x[key]=fresh(i.id)[key];x[moduleField(key)]=0;},send))ui.deleted?.(i.id,key);}}],()=>ui.edit(i,key));root.append(card);});
 return root;
}
function edit(i,state,key,send,ui){
 const row=JSON.parse(JSON.stringify(decode(current(state)).find(x=>x.instrument===i.id)||fresh(i.id))),{dialog,content}=ui;if(!dialog||!content)return;
 let amountTouched=false;
 content.replaceChildren(el('h2',(i.name||'INSTRUMENT '+i.id)+' / '+(key==='humanizer'?'HUMANIZER':'VELOCITY CURVES')));
 const err=el('p','','expressive-error');err.setAttribute('role','alert');
 const ctl=(label,type,value,min,max,step,fn,opts)=>{const l=el('label',undefined,'expressive-control');l.append(el('span',label));let x;if(type==='select'){x=el('select');opts.forEach(([v,t])=>{const o=el('option',t);o.value=v;x.append(o);});x.value=value;}else{x=el('input');x.type=type;x.min=min;x.max=max;x.step=step;x.value=value;}x.setAttribute('aria-label',label);x.oninput=()=>fn(Number(x.value));l.append(x);return l;};
 if(key==='humanizer'){
  const h=row.humanizer,p=el('div',undefined,'expressive-presets');
  [['SUBTLE',{timingMs:12,velocityPercent:8,feel:1,variation:0,scope:0}],['LOOSE',{timingMs:85,velocityPercent:24,feel:1,variation:1,scope:1}],['DESTROY',{timingMs:650,velocityPercent:60,feel:0,variation:1,scope:1,liveLookaheadMs:700}]].forEach(([name,v])=>p.append(btn(name,()=>{Object.assign(h,v);renderControls();})));
  content.append(p,el('p','Negative offsets need output lookahead; without enough lookahead, attacks are clamped to the current sample.'));
  let controls;
  function renderControls(){controls?.remove();controls=el('div',undefined,'expressive-controls');controls.append(ctl('TIMING RANGE · ms','number',h.timingMs,0,2000,.1,v=>h.timingMs=Math.max(0,Math.min(2000,v))),ctl('TIMING BIAS · ms','number',h.biasMs,-2000,2000,.1,v=>h.biasMs=Math.max(-2000,Math.min(2000,v))),ctl('VELOCITY VARIATION · %','number',h.velocityPercent,0,100,.5,v=>h.velocityPercent=Math.max(0,Math.min(100,v))),ctl('DISTRIBUTION','select',h.feel,0,1,1,v=>h.feel=v,[[0,'UNIFORM'],[1,'GAUSSIAN']]),ctl('VARIATION','select',h.variation,0,1,1,v=>h.variation=v,[[0,'FIXED'],[1,'EVOLVING']]),ctl('CHORD TIMING','select',h.scope,0,1,1,v=>h.scope=v,[[0,'GROUP'],[1,'NOTES']]),ctl('OUTPUT LOOKAHEAD · ms','number',h.liveLookaheadMs,0,2000,.1,v=>h.liveLookaheadMs=Math.max(0,Math.min(2000,v))),ctl('SEED','number',h.seed,0,4294967295,1,v=>h.seed=Math.max(0,Math.min(4294967295,Math.round(v)))));content.append(controls);}
  renderControls();
 }else{
  const c=row.curve,points=()=>c.points.map(p=>({x:p.x,y:p.y})),presets=el('div',undefined,'expressive-presets'),samples={LINEAR:[[1,1],[127,127]],SOFT:[[1,1],[32,18],[80,66],[127,127]],HARD:[[1,1],[32,48],[80,105],[127,127]],INVERT:[[1,127],[127,1]],GATE:[[1,1],[55,1],[56,127],[127,127]]};
  Object.entries(samples).forEach(([n,v])=>presets.append(btn(n,()=>{c.points=v.map(([x,y])=>({x,y}));selected=-1;draw();})));content.append(presets);
  const amount=ctl('AMOUNT · %','range',c.amount,0,100,1,v=>{amountTouched=true;c.amount=v;out.value=v+'%';}),out=el('output',c.amount+'%','expressive-amount');amount.append(out);content.append(amount);
  const rail=amount.querySelector('input');
  if(decode(state).some(x=>x.instrument===i.id&&x.curveModule===row.curveModule)){
   window.MBMF_BIND_EXPRESSIVE_AMOUNT?.(rail,{instrumentId:i.id,moduleId:row.curveModule,kind:27},{openOnClick:false});
   rail.setEffective=value=>{if(amountTouched||document.activeElement===rail)return;c.amount=value;rail.value=value;out.value=Math.round(value)+'%';};
  }else content.append(el('small','Apply once to make AMOUNT available to expression controllers.'));
  const wrap=el('div',undefined,'velocity-graph-wrap'),svg=document.createElementNS('http://www.w3.org/2000/svg','svg');svg.setAttribute('viewBox','0 0 400 200');svg.setAttribute('role','img');svg.setAttribute('aria-label','Velocity curve, input and output 1 to 127');const grid=document.createElementNS(svg.namespaceURI,'path');grid.setAttribute('class','velocity-grid');grid.setAttribute('d','M12 12H388 M12 100H388 M12 188H388 M12 12V188 M200 12V188 M388 12V188');svg.append(grid);const line=document.createElementNS(svg.namespaceURI,'polyline');line.setAttribute('class','velocity-curve-line');svg.append(line);let selected=-1;
  const xy=p=>[12+(p.x-1)*376/126,188-(p.y-1)*176/126];
  function draw(){svg.querySelectorAll('circle').forEach(n=>n.remove());line.setAttribute('points',c.points.map(p=>xy(p).join(',')).join(' '));c.points.forEach((p,j)=>{const [x,y]=xy(p),d=document.createElementNS(svg.namespaceURI,'circle');d.setAttribute('cx',x);d.setAttribute('cy',y);d.setAttribute('r',selected===j?8:6);d.classList.toggle('selected',selected===j);d.setAttribute('tabindex','0');d.setAttribute('aria-label','Point '+(j+1)+' input '+p.x+' output '+p.y);d.onpointerdown=ev=>{ev.preventDefault();selected=j;d.setPointerCapture(ev.pointerId);const move=e=>{const r=svg.getBoundingClientRect(),xx=Math.round(1+(e.clientX-r.left)/r.width*126),yy=Math.round(1+(1-(e.clientY-r.top)/r.height)*126);p.x=j===0?1:j===c.points.length-1?127:Math.max(c.points[j-1].x+1,Math.min(c.points[j+1].x-1,xx));p.y=Math.max(1,Math.min(127,yy));const pos=xy(p);d.setAttribute('cx',pos[0]);d.setAttribute('cy',pos[1]);line.setAttribute('points',c.points.map(q=>xy(q).join(',')).join(' '));};d.onpointermove=move;d.onpointerup=()=>{d.onpointermove=null;};};d.onclick=()=>{selected=j;draw();};svg.append(d);});}
  svg.ondblclick=ev=>{if(c.points.length>=16)return;const r=svg.getBoundingClientRect(),x=Math.round(1+(ev.clientX-r.left)/r.width*126),y=Math.round(1+(1-(ev.clientY-r.top)/r.height)*126),at=c.points.findIndex(p=>p.x>x);if(at<=0)return;c.points.splice(at,0,{x,y});selected=at;draw();};
  wrap.append(svg);content.append(wrap);const actions=el('div',undefined,'expressive-presets');actions.append(btn('ADD POINT',()=>{if(c.points.length>=16){err.textContent='Maximum 16 points.';return;}let at=1,gap=0;for(let j=1;j<c.points.length;j++)if(c.points[j].x-c.points[j-1].x>gap){at=j;gap=c.points[j].x-c.points[j-1].x;}if(gap>1){c.points.splice(at,0,{x:Math.round((c.points[at-1].x+c.points[at].x)/2),y:Math.round((c.points[at-1].y+c.points[at].y)/2)});selected=at;draw();}}),btn('DELETE SELECTED',()=>{if(selected<=0||selected>=c.points.length-1){err.textContent='Endpoints stay fixed at 1 and 127.';return;}c.points.splice(selected,1);selected=-1;err.textContent='';draw();}),btn('RESET LINEAR',()=>{c.points=points().slice(0,1).map(()=>({x:1,y:1})).concat([{x:127,y:127}]);selected=-1;draw();}));content.append(actions);draw();
 }
 content.append(err,btn('APPLY',async()=>{if(key==='curve'){const p=row.curve.points;if(p.length<2||p[0].x!==1||p[p.length-1].x!==127||p.some((v,j)=>v.x<1||v.x>127||v.y<1||v.y>127||(j&&v.x<=p[j-1].x))){err.textContent='X must increase from 1 to 127; Y must stay in range.';return;}if(!amountTouched){const live=decode(current(state)).find(x=>x.instrument===i.id&&x.curveModule===row.curveModule);if(live)row.curve.amount=live.curve.amount;}}if(await apply(state,i.id,r=>{const enabled=r[key].enabled;r[key]=row[key];r[key].enabled=enabled;},send))dialog.close();else err.textContent='Apply failed; check engine connection.';}),btn('CANCEL',()=>dialog.close()));ui.show();
}
function paint(state){for(const row of decode(state)){const output=document.querySelector('.expressive-module[data-instrument-id="'+row.instrument+'"][data-module-id="curve"] output');if(output)output.textContent=Math.round(row.curve.amount)+'%';}}
window.MBMF_EXPRESSIVE={mount,edit,add,paint,rows:decode,amount:(state,instrument,module)=>decode(state).find(x=>x.instrument===instrument&&x.curveModule===module)?.curve.amount};
})();
