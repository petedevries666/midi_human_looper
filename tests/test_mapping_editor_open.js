'use strict';
// Exercise production selection/editor code. No MIDI or browser-layout claim.
const fs=require('fs'),path=require('path'),vm=require('vm'),assert=require('assert/strict');
const source=fs.readFileSync(path.join(__dirname,'../headless/web/app.js'),'utf8');
class Element{
 constructor(tag='div',text=''){this.tag=tag;this.textContent=text;this.children=[];this.dataset={};this.open=false;this.value='';}
 append(...children){this.children.push(...children);}
 replaceChildren(...children){this.children=children;}
 setAttribute(name,value){this[name]=value;}
 addEventListener(name,listener){this.listeners??={};(this.listeners[name]??=[]).push(listener);}
 matches(selector){return selector==='input[type=range]';}
 show(){this.open=true;this.shows=(this.shows||0)+1;}
 close(){this.open=false;}
 scrollIntoView(){this.scrolled=true;}
}
const elements=Object.fromEntries(['editor','editor-content','mapping-editor','mapping-editor-content','mapping-editor-section','error'].map(id=>[id,new Element()]));
elements.editor.open=true;elements['editor-content'].textContent='Transformer draft';
const original={id:7,targetId:1,sourceId:3,instrumentId:4,moduleId:18,kind:2,enabled:1,points:[[0,0,0],[1,1,0]]};
let mappings=[original],writes=[],accept=false;
const context=vm.createContext({structuredClone,confirm:()=>accept,$:id=>elements[id],catalog:{},latest:{phrases:[],instruments:[{id:4,transformers:[{id:18,parameters:[{kind:2}]}]}]},revision:1,engineSession:9,hostChains:null,
 controllerConfiguration:()=>({sources:[{id:3,name:'PEDAL'}],mappings}),parameter:kind=>({label:'PARAM '+kind,assignmentEligible:true}),descriptorForMapping:()=>({parameters:[]}),freshId:()=>99,node:(tag,text)=>new Element(tag,text),button:(text,onclick)=>Object.assign(new Element('button',text),{onclick}),curveEditor:points=>Object.assign(new Element('svg'),{points}),render:()=>{},request:async(url,body)=>{writes.push(body);return{};}});
const selectStart=source.indexOf('function openAssignedCurve('),selectEnd=source.indexOf('\nfunction curveY',selectStart);
const editStart=source.indexOf('function editMapping('),editEnd=source.indexOf('\nfunction descriptorForMapping',editStart);
vm.runInContext(source.slice(selectStart,selectEnd)+'\n'+source.slice(editStart,editEnd),context);
const bindStart=source.indexOf('function bindModulation('),bindEnd=source.indexOf('\nasync function assignmentMenu',bindStart);
vm.runInContext(source.slice(bindStart,bindEnd),context);context.mappingFor=()=>null;
(async()=>{
 context.binding={instrumentId:4,moduleId:18,kind:2};vm.runInContext('openAssignedCurve(binding)',context);
 assert(elements['mapping-editor'].open);assert(elements['mapping-editor-section'].open);assert(elements['mapping-editor'].scrolled);
 assert(elements.editor.open,'opening curve must retain transformer editor');assert.equal(elements['editor-content'].textContent,'Transformer draft');assert.equal(writes.length,0,'selection must not reassign or send MIDI');
 const curve=elements['mapping-editor-content'].children.find(n=>n.tag==='svg');curve.points[0][1]=.25;
 context.control=new Element('input');context.control.parentElement=new Element();vm.runInContext('bindModulation(control,binding)',context);
 let prevented=false,stopped=false;for(const listener of context.control.listeners.keydown)listener({key:'Enter',preventDefault:()=>prevented=true,stopPropagation:()=>stopped=true});assert(prevented&&stopped,'Enter must not activate the newly focused close button');
 vm.runInContext('openAssignedCurve(binding)',context);assert.equal(elements['mapping-editor'].shows,1,'same selection retains unsaved curve');
 assert.equal(original.points[0][1],0,'editing is a draft');
 mappings.push({...original,id:8,moduleId:19});context.other={instrumentId:4,moduleId:19,kind:2};
 vm.runInContext('openAssignedCurve(other)',context);assert.equal(elements['mapping-editor'].dataset.mappingId,7,'declined switch preserves draft');
 accept=true;vm.runInContext('openAssignedCurve(other)',context);assert.equal(elements['mapping-editor'].dataset.mappingId,8);
 elements['mapping-editor'].close();mappings=[{...original,enabled:0}];vm.runInContext('openAssignedCurve(binding)',context);assert(elements['mapping-editor'].open,'bypassed mapping remains editable');
 const done=elements['mapping-editor-content'].children.find(n=>n.textContent==='DONE');await done.onclick();assert.equal(writes.length,1);assert.equal(writes[0].action,'mapping_commit');assert.equal(writes[0].mapping.enabled,0);assert.equal(writes[0].mapping.id,7);
 const html=fs.readFileSync(path.join(__dirname,'../headless/web/index.html'),'utf8');assert(html.indexOf('id="mapping-editor-section"')>html.indexOf('id="module-editor-section"'));
 console.log('PASS assigned-slider curve opening, independent dock, draft retention and scoped commit');
})().catch(e=>{console.error(e);process.exitCode=1;});
