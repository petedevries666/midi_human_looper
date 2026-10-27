const assert=require('node:assert/strict');
const fs=require('node:fs');
const vm=require('node:vm');
const context={structuredClone};
vm.createContext(context);
vm.runInContext(fs.readFileSync(require('node:path').join(__dirname,'../headless/web/conductor.js'),'utf8'),context);
let serial=0;const uuid=()=>`new-${++serial}`;
const original={id:'step',transition:'END_OF_PHRASE',layers:[
 {id:'layer1',block:{id:'block1',type:'PHRASE',sourceId:'phrase-source',overrides:{phrase_base_velocity:{mode:'OVERRIDE',value:.5}}}},
 {id:'layer2',block:{id:'block2',type:'MOVEMENT',sourceId:'movement-source',overrides:{movementDuration:{mode:'OVERRIDE',value:.6}}}},
 {id:'layer3',block:null}],supercharge:{thresholdMs:700,bindings:[{blockId:'block2',key:'movementDuration',factor:2},{target:{instrumentId:1,kind:4},factor:.5}]}};
const before=structuredClone(original),copy=context.duplicateConductorStep(original,uuid);
assert.deepEqual(original,before);
assert.equal(new Set([copy.id,...copy.layers.flatMap(l=>[l.id,...(l.block?[l.block.id]:[])])]).size,6);
assert.equal(copy.layers[0].block.sourceId,'phrase-source');
assert.equal(copy.layers[1].block.sourceId,'movement-source');
assert.equal(copy.supercharge.bindings[0].blockId,copy.layers[1].block.id);
assert.deepEqual(copy.supercharge.bindings[1].target,original.supercharge.bindings[1].target);
assert.equal(copy.transition,'END_OF_PHRASE');
copy.layers[0].block.overrides.phrase_base_velocity.value=.9;
assert.equal(original.layers[0].block.overrides.phrase_base_velocity.value,.5);
assert.equal(copy.layers[2].block,null);
console.log('PASS complete STEP duplication: unique identities, shared sources, independent overrides and local supercharge targets');
