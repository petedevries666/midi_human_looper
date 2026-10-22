'use strict';
// Production UI handlers, controlled API replies; no simulated MIDI claim.
const assert=require('assert/strict'),fs=require('fs'),vm=require('vm'),path=require('path');
const elements={},listeners={};let interval,requests=[];
function element(id){return elements[id]??=( {value:'',checked:false,textContent:'',disabled:false,options:[],add(o){this.options.push(o);},replaceChildren(...options){this.options=options;},addEventListener(name,fn){this[name]=fn;}});}
element('patch-slot').value='1';
const data={settings:{enabled:false,channel:15,withSnapshot:true,links:{}},snapshots:[{name:'Test snapshot',path:'test.zss'}],phase:'ready',lastError:'',selectedSlot:1};
const panel={set innerHTML(value){for(const match of value.matchAll(/id="([^"]+)"/g))element(match[1]);},querySelectorAll(){return Object.entries(elements).filter(([id])=>id.startsWith('pc-')&&id!=='pc-status').map(([,v])=>v);}};
const nodes=[];
function fakeNode(tag,text){const n={tag,textContent:text,children:[],dataset:{},attributes:{},append(...values){this.children.push(...values);},replaceChildren(...values){this.children=values;},querySelectorAll(){return this.children.flatMap(c=>typeof c==='object'?[...(c.tag==='button'?[c]:[]),...c.querySelectorAll()]:[]);},setAttribute(k,v){this.attributes[k]=v;}};nodes.push(n);return n;}
function fakeButton(text,action){const n=fakeNode('button',text);n.onclick=action;return n;}
const context=vm.createContext({node:fakeNode,button:fakeButton,document:{hidden:false,createElement:()=>panel,querySelector:()=>({append(){}}),addEventListener:(name,fn)=>listeners[name]=fn},Option:function(text,value){this.text=text;this.value=value;},$:element,pending:false,loadedPatchSlot:1,refreshPatchSlots(){},refreshHostChains(){},refresh(){},confirm:()=>true,setInterval:fn=>interval=fn,request:async(url,body)=>{if(body){requests.push(body);if(body.operation==='configure'){data.settings.enabled=body.enabled;data.settings.channel=body.channel;data.settings.withSnapshot=body.withSnapshot;}if(body.operation==='link')data.settings.links['1']={snapshot:body.snapshot};}return JSON.parse(JSON.stringify(data));}});
vm.runInContext(fs.readFileSync(path.join(__dirname,'../headless/web/patch-recall.js'),'utf8'),context);
const settle=()=>new Promise(resolve=>setImmediate(resolve));
(async()=>{
 listeners.DOMContentLoaded();await settle();assert.equal(element('pc-enabled').checked,false);
 element('pc-enabled').checked=true;element('pc-enabled').onchange();
 element('pc-link').value='test.zss';element('pc-link').onchange();
 await interval();assert.equal(element('pc-link').value,'test.zss','poll preserves a draft snapshot selection');
 element('pc-associate').onclick();await settle();
 assert.equal(requests.at(-1).operation,'link');assert.equal(data.settings.enabled,false,'link must not silently enable MIDI recall');
 assert.equal(element('pc-enabled').checked,true,'link response preserves the unapplied checkbox');assert.match(element('pc-status').textContent,/APPLIQUER/);
 element('pc-apply').onclick();await settle();assert.equal(data.settings.enabled,true);assert.equal(element('pc-enabled').checked,true);assert.doesNotMatch(element('pc-status').textContent,/ATTENTE/);
 element('pc-enabled').checked=false;element('pc-enabled').onchange();context.request=async()=>{throw new Error('Unavailable');};
 element('pc-apply').onclick();await settle();assert.equal(element('pc-enabled').checked,false,'failed apply preserves the draft');assert.equal(element('pc-enabled').disabled,false);
 data.chainRecalls=[{chainId:1,identity:'chain-one',channel:1,current:[{instrument:'Surge XT',preset:'Bass',role:'INSTRUMENT'},{instrument:'Delay',preset:'Echo',role:'FX'}],reference:{processors:[{instrument:'Surge XT',preset:'Previous'}]},fingerprint:'a'.repeat(64),state:'modified',canSave:true,engineSessionId:5},{chainId:2,current:[],state:'unlinked',canSave:false}];
 context.request=async(url,body)=>{if(body)requests.push(body);return JSON.parse(JSON.stringify(data));};
 await interval();
 assert(nodes.some(n=>n.textContent?.includes('FX · Delay → Echo')),'show the current effect and preset');
 const save=nodes.findLast(n=>n.attributes['aria-label']==='SAVE chaîne 1');assert.equal(save.disabled,false);
 save.onclick();await settle();
 assert.equal(requests.at(-1).operation,'save_chain');assert.equal(requests.at(-1).chainId,1);assert.equal(requests.at(-1).slot,1);assert.equal(requests.at(-1).fingerprint,'a'.repeat(64));assert.equal(requests.at(-1).expectedEngineSessionId,5);
 assert.equal(element('pc-enabled').checked,false,'chain save must preserve unapplied recall settings');
 await interval();assert.equal(nodes.findLast(n=>n.attributes['aria-label']==='SAVE chaîne 2').disabled,true,'an unlinked chain stays disabled after another action');
 data.phase='snapshot';await interval();data.phase='ready';await interval();assert.equal(element('patch-status').textContent,'PATCH RAPPELÉ');
 data.phase='restore';await interval();data.phase='failed';data.lastError='Previous patch restored';await interval();assert.equal(element('patch-status').textContent,'Previous patch restored');
 console.log('PASS patch recall drafts, link/apply and scoped chain SAVE UI');
})().catch(error=>{console.error(error);process.exitCode=1;});
