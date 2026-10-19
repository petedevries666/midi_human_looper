'use strict';
// Exercise the production loader with controlled HTTP outcomes and a fake clock.
// No musical state, browser rendering or device compatibility is claimed here.
const fs=require('fs'),vm=require('vm'),assert=require('assert/strict');
const source=fs.readFileSync(require('path').join(__dirname,'../headless/web/app.js'),'utf8');
const begin=source.indexOf('let descriptorRequest='),end=source.indexOf('\nfunction mappingFor',begin);
assert(begin>=0&&end>begin);
const elements={'error':{textContent:''},'token':{value:'test-only'},'app-version':{textContent:''}};
let calls=0,release,timers=[],rendered=0;
const context=vm.createContext({document:{hidden:false},$:id=>elements[id],catalog:null,latest:{revision:1},renderedModel:'old',render:()=>rendered++,request:()=>{calls++;return new Promise(resolve=>release=resolve);},setTimeout:(callback,delay)=>{const timer={callback,delay};timers.push(timer);return timer;},clearTimeout:timer=>{if(timer)timers=timers.filter(t=>t!==timer);}});
vm.runInContext(source.slice(begin,end),context);
(async()=>{
 const first=vm.runInContext('loadDescriptors()',context),second=vm.runInContext('loadDescriptors()',context);
 assert.equal(calls,1,'concurrent state/CONNECT must share one HTTP request');
 release({modules:[],parameters:[],displayVersion:'V.2 DICKINSON'});
 assert.equal(await first,true);assert.equal(await second,true);assert.equal(rendered,1);
 assert.equal(elements['app-version'].textContent,'V.2 DICKINSON');
 context.catalog=null;context.request=async()=>{calls++;throw new Error('Temporary failure');};
 assert.equal(await vm.runInContext('loadDescriptors()',context),false);
 assert.equal(timers.length,1);assert.equal(timers[0].delay,2000);assert.match(elements.error.textContent,/Temporary failure/);
 context.request=async()=>({modules:[{engineType:5,label:'ARPEGGIATOR'}],parameters:[],displayVersion:'V.2 DICKINSON'});
 timers.shift().callback();await new Promise(resolve=>setImmediate(resolve));
 assert.equal(context.catalog.modules[0].label,'ARPEGGIATOR');assert.equal(elements.error.textContent,'');assert.equal(timers.length,0);
 context.request=async()=>({modules:null,parameters:[]});
 assert.equal(await vm.runInContext('loadDescriptors()',context),false);assert.equal(context.catalog.modules[0].label,'ARPEGGIATOR','invalid reply must preserve the last valid catalog');
 assert.match(elements.error.textContent,/Invalid module definitions/);
 console.log('PASS descriptor coalescing, recovery, validation and native version');
})().catch(error=>{console.error(error);process.exitCode=1;});
