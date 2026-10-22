// Unit test of async UI bookkeeping; not a fabricated browser/API qualification.
const fs=require('fs'),vm=require('vm'),assert=require('assert');
const source=fs.readFileSync(require('path').join(__dirname,'../headless/web/app.js'),'utf8');
const between=(a,b)=>source.slice(source.indexOf(a),source.indexOf(b,source.indexOf(a)));
const instrument={id:5,transformers:[{id:19,type:5},{id:20,type:4}]};
let release,calls=0;
const ui={open:false},context=vm.createContext({Map,Set,latest:{instruments:[instrument]},descriptor:()=>({label:'VELOCITY'}),$:()=>ui,render:()=>{},renderedModel:'',command:async()=>{calls++;return await new Promise(r=>release=r);}});
vm.runInContext('const transformerAdds=new Map();'+between('function settleTransformerAdds(s){','let hostChains=')+between('function transformerAddProblem(i,type){','function addEmptyTransformer(i){'),context);
(async()=>{
 const first=vm.runInContext('addTransformerAndEdit(latest.instruments[0],4)',context);
 assert.strictEqual(await vm.runInContext('addTransformerAndEdit(latest.instruments[0],4)',context),false);
 assert.strictEqual(calls,1,'A second click must not enqueue another add');release(true);assert.strictEqual(await first,true);
 assert.strictEqual(vm.runInContext('settleTransformerAdds(latest).length',context),0,'Existing same-type block is not the new block');
 instrument.transformers.push({id:21,type:2});assert.strictEqual(vm.runInContext('settleTransformerAdds(latest).length',context),0,'An unrelated new block cannot settle this add');
 instrument.transformers.push({id:22,type:4});assert.strictEqual(vm.runInContext('settleTransformerAdds(latest)[0][1].id',context),22);
 assert.strictEqual(vm.runInContext('transformerAdds.size',context),0);
 context.command=async()=>false;assert.strictEqual(await vm.runInContext('addTransformerAndEdit(latest.instruments[0],4)',context),false);
 assert.strictEqual(vm.runInContext('transformerAdds.size',context),0,'Refusal must unlock the next attempt');
 console.log('PASS deferred add: one request, wait for actual new identity, ignore unrelated blocks, unlock refusal');
})().catch(e=>{console.error(e);process.exitCode=1;});
