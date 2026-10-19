'use strict';
// Production UI handlers, controlled API replies; no simulated MIDI claim.
const assert=require('assert/strict'),fs=require('fs'),vm=require('vm'),path=require('path');
const elements={},listeners={};let interval,requests=[];
function element(id){return elements[id]??=( {value:'',checked:false,textContent:'',disabled:false,options:[],add(o){this.options.push(o);},replaceChildren(...options){this.options=options;},addEventListener(name,fn){this[name]=fn;}});}
element('patch-slot').value='1';
const data={settings:{enabled:false,channel:15,withSnapshot:true,links:{}},snapshots:[{name:'Test snapshot',path:'test.zss'}],phase:'ready',lastError:'',selectedSlot:1};
const panel={set innerHTML(value){for(const match of value.matchAll(/id="([^"]+)"/g))element(match[1]);},querySelectorAll(){return Object.entries(elements).filter(([id])=>id.startsWith('pc-')&&id!=='pc-status').map(([,v])=>v);}};
const context=vm.createContext({document:{hidden:false,createElement:()=>panel,querySelector:()=>({append(){}}),addEventListener:(name,fn)=>listeners[name]=fn},Option:function(text,value){this.text=text;this.value=value;},$:element,pending:false,loadedPatchSlot:1,refreshPatchSlots(){},refreshHostChains(){},refresh(){},confirm:()=>true,setInterval:fn=>interval=fn,request:async(url,body)=>{if(body){requests.push(body);if(body.operation==='configure'){data.settings.enabled=body.enabled;data.settings.channel=body.channel;data.settings.withSnapshot=body.withSnapshot;}if(body.operation==='link')data.settings.links['1']={snapshot:body.snapshot};}return JSON.parse(JSON.stringify(data));}});
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
 console.log('PASS patch recall draft settings, linking, polling, apply and failed apply');
})().catch(error=>{console.error(error);process.exitCode=1;});
