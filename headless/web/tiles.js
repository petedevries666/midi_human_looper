/* Presentation only: immutable entity identity chooses original user artwork. */
(function(root){
'use strict';
const pools={
 SMART_SWITCH:['punk-electricity','punk-megaphone','spiral-glasses','animal-trio','dog-target','punk-turntable','sloth-disco','punk-coffee'],
 PHRASE:['cassette','raccoon-microphone','dog-drums','punk-flute','dog-vocals','dog-tape','punk-television','sloth-no-tempo'],
 INSTRUMENT:['paw-keyboard','punk-guitar','dog-keyboard','punk-bass','dog-drums','dog-picks'],
 TRANSFORMER:['paw-modular','dog-cables','punk-patchbay','punk-skull','dog-mixer','punk-television'],
 CONTROLLER:['sloth-knobs','paw-modular','punk-patchbay','dog-mixer','dog-target','paw-keyboard'],
 MOVEMENT:['punk-electricity','punk-megaphone','raccoon-disco','spiral-glasses','punk-turntable','sloth-disco'],
 SNAPSHOT:['cassette','sloth-headphones','sloth-listening','dog-tape','dog-pizza','sloth-whiskey','punk-coffee']
};
function hash(text){let n=2166136261;for(const c of String(text)){n^=c.charCodeAt(0);n=Math.imul(n,16777619);}return n>>>0;}
function choose(kind,id){const pool=pools[kind]||pools.TRANSFORMER;const numeric=Number(id);const seed=Number.isSafeInteger(numeric)&&numeric>=0?numeric+hash(kind):hash(kind+':'+id);return pool[seed%pool.length];}
function decorate(element,kind,id,add=false){const tile=choose(kind,id);element.classList.add('illustrated-tile');element.dataset.tileKind=kind;element.dataset.tileId=tile;element.style.setProperty('--tile-image',`url("/assets/tiles/${tile}.webp")`);if(add)element.classList.add('add-tile');return element;}
root.MBMF_TILES={choose,decorate,pools};
if(typeof module!=='undefined')module.exports={choose,pools};
})(typeof window==='undefined'?{}:window);
