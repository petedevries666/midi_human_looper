'use strict';
window.MBMF_RANDOM={
 defaults:{startJitter:{amount:0,mode:'NOTE',redraw:'TRIGGER'},randomPitch:{enabled:0,low:-12,high:12,notes:4095}},
 validOffsets(stats,pitch){
  if(!stats||stats.maxPitch<0||!stats.noteClasses)return [];
  const result=[],tune=Number(stats.tune||0);
  for(let d=Number(pitch.low);d<=Number(pitch.high);d++){
   if(stats.minPitch+tune+d<0||stats.maxPitch+tune+d>127)continue;
   const shift=((tune+d)%12+12)%12,rotated=((stats.noteClasses<<shift)|(stats.noteClasses>>(12-shift)))&4095;
   if((rotated&(4095-Number(pitch.notes)))===0)result.push(d);
  }return result;
 },
 editor({startJitter,randomPitch,prefix='',changed=()=>{},stats=()=>null}){
  const jitter=structuredClone(startJitter||this.defaults.startJitter),pitch=structuredClone(randomPitch||this.defaults.randomPitch);
  const root=node('div',undefined,'phrase-randomization'),fields={};
  const field=(key,title)=>{const f=node('fieldset');f.dataset.randomSection=key;f.append(node('legend',title));root.append(f);fields[key]=f;return f;};
  const labelled=(parent,title,control)=>{const label=node('label',title,'random-control');label.append(control);parent.append(label);return control;};
  const select=(parent,title,label,values,value,update)=>{const input=node('select');input.setAttribute('aria-label',(label+' '+prefix).trim());for(const [v,t] of values){const o=node('option',t);o.value=v;input.append(o);}input.value=value;input.onchange=()=>update(input.value);labelled(parent,title,input);return input;};
  const jf=field('startJitter','START JITTER'),amount=node('input'),amountValue=node('output',jitter.amount+'%');
  amount.type='range';amount.min=0;amount.max=100;amount.step=1;amount.value=jitter.amount;amount.setAttribute('aria-label',('START JITTER '+prefix).trim());
  amount.oninput=()=>{jitter.amount=Number(amount.value);amountValue.value=jitter.amount+'%';};amount.onchange=()=>changed('startJitter',structuredClone(jitter));
  labelled(jf,'ZONE 0–100%',amount).after(amountValue);
  select(jf,'DÉPART','START MODE',[['NOTE','SUR NOTE'],['FREE','LIBRE']],jitter.mode,v=>{jitter.mode=v;changed('startJitter',structuredClone(jitter));});
  select(jf,'TIRAGE','START REDRAW',[['TRIGGER','AU DÉCLENCHEMENT'],['CYCLE','À CHAQUE TOUR DE LOOP']],jitter.redraw,v=>{jitter.redraw=v;changed('startJitter',structuredClone(jitter));});
  jf.append(node('small','0% : départ normal. Sans attaque dans la zone : départ normal. Notes tenues et sustain repris au point choisi.'));
  const pf=field('randomPitch','RANDOM PITCH'),enabled=node('input');enabled.type='checkbox';enabled.checked=!!pitch.enabled;enabled.setAttribute('aria-label',('RANDOM PITCH '+prefix).trim());labelled(pf,'ACTIF',enabled);
  const bounds=node('div',undefined,'random-bounds');pf.append(bounds);
  const warning=node('output');warning.setAttribute('role','status');
  const describe=()=>{const invalid=!Number.isInteger(Number(pitch.low))||!Number.isInteger(Number(pitch.high))||pitch.low<-24||pitch.high>24||pitch.low>pitch.high;
   if(invalid){warning.textContent='BORNES INVALIDES · −24 à +24, LOW ≤ HIGH';warning.dataset.invalid='true';return;}
   if(!pitch.enabled){warning.textContent='OFF · TUNE conservé';warning.dataset.invalid='false';return;}
   const current=stats(),offsets=this.validOffsets(current,pitch);
   warning.textContent=current&&current.maxPitch>=0?(offsets.length?'TRANSPOSITIONS : '+offsets.map(v=>v>0?'+'+v:v).join(' · '):'AUCUNE TRANSPOSITION POSSIBLE · lecture refusée'):'Phrase sans analyse de notes disponible';
   warning.dataset.invalid=String(!!current&&current.maxPitch>=0&&!offsets.length);
  };
  for(const [key,title] of [['low','LOW'],['high','HIGH']]){const input=node('input');input.type='number';input.min=-24;input.max=24;input.step=1;input.value=pitch[key];input.setAttribute('aria-label',('RANDOM PITCH '+title+' '+prefix).trim());input.onchange=()=>{pitch[key]=Number(input.value);describe();changed('randomPitch',structuredClone(pitch));};labelled(bounds,title,input);}
  const palette=node('div',undefined,'random-note-palette');palette.setAttribute('role','group');palette.setAttribute('aria-label',('Notes autorisées '+prefix).trim());pf.append(palette);
  const boxes=[];for(const [i,name] of ['C','C#','D','D#','E','F','F#','G','G#','A','A#','B'].entries()){
   const box=node('input');box.type='checkbox';box.checked=!!(pitch.notes&(1<<i));box.setAttribute('aria-label',(name+' autorisé '+prefix).trim());box.onchange=()=>{pitch.notes=box.checked?pitch.notes|(1<<i):pitch.notes&~(1<<i);describe();changed('randomPitch',structuredClone(pitch));};
   const label=node('label',undefined,'random-note');label.append(box,node('span',name));palette.append(label);boxes.push(box);
  }
  const choose=mask=>{pitch.notes=mask;boxes.forEach((box,i)=>box.checked=!!(mask&(1<<i)));describe();changed('randomPitch',structuredClone(pitch));};
  pf.append(button('TOUTES LES NOTES',()=>choose(4095)),button('AUCUNE NOTE',()=>choose(0)),node('small','Sans répétition immédiate si plusieurs choix · une transposition pour toute la phrase · bornes en demi-tons après TUNE, avant les transformateurs.'),warning);
  enabled.onchange=()=>{pitch.enabled=Number(enabled.checked);describe();changed('randomPitch',structuredClone(pitch));};describe();
  return {root,fields,value:()=>({startJitter:structuredClone(jitter),randomPitch:structuredClone(pitch)}),describe};
 }
};
