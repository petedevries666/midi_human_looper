const assert=require('node:assert/strict');
const fs=require('node:fs'),vm=require('node:vm'),path=require('node:path');
const context={window:{},structuredClone};vm.createContext(context);
vm.runInContext(fs.readFileSync(path.join(__dirname,'../headless/web/phrase-randomization.js'),'utf8'),context);
const api=context.window.MBMF_RANDOM;
const chord={noteClasses:145,minPitch:60,maxPitch:67,tune:0};
const offsets=(p,c)=>Array.from(api.validOffsets(p,c));
assert.deepEqual(offsets(chord,{low:-12,high:12,notes:145}),Array.from({length:25},(_,i)=>i-12));
assert.deepEqual(offsets(chord,{low:-2,high:2,notes:4095}),[-2,-1,0,1,2]);
assert.deepEqual(offsets(chord,{low:-24,high:24,notes:0}),[]);
assert.deepEqual(offsets({...chord,tune:5},{low:0,high:0,notes:545}),[0]);
assert.deepEqual(offsets({...chord,minPitch:120,maxPitch:127},{low:1,high:12,notes:4095}),Array.from({length:12},(_,i)=>i+1));
assert.deepEqual(offsets({...chord,minPitch:0,maxPitch:7,tune:-1},{low:0,high:0,notes:4095}),[0]);
assert.deepEqual(offsets(null,{low:0,high:0,notes:4095}),[]);
assert.equal(api.quantize(61,5,1),62);
assert.equal(api.quantize(61,5,-1),60);
assert.equal(api.quantize(61,5,0),60);
assert.equal(api.quantize(59,5,-1),60);
assert.equal(api.quantize(151,5,24),122);
assert.equal(api.quantize(-24,5,-24),0);
for(let mask=1;mask<4096;mask+=31)for(let note=-24;note<=151;note++)for(const direction of [-1,0,1]){
 const result=api.quantize(note,mask,direction),bounded=Math.max(0,Math.min(127,note));
 const allowed=Array.from({length:128},(_,i)=>i).filter(n=>mask&(1<<(n%12)));
 const distance=Math.min(...allowed.map(n=>Math.abs(n-bounded)));
 const closest=allowed.filter(n=>Math.abs(n-bounded)===distance);
 assert.equal(result,direction>0?closest.at(-1):closest[0]);
}
console.log('PASS RANDOM PITCH: full offset range, nearest checked notes, directional ties, unchanged notes and MIDI bounds');
