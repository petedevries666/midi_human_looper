'use strict';
const assert=require('node:assert/strict'),fs=require('node:fs'),path=require('node:path');
const {choose,pools}=require('../headless/web/tiles.js');
const manifest=JSON.parse(fs.readFileSync(path.join(__dirname,'../headless/web/assets/tiles/manifest.json'),'utf8'));
const ids=new Set(manifest.tiles.map(t=>t.id));
for(const [kind,pool] of Object.entries(pools)){
 for(const id of pool)assert(ids.has(id),`Missing ${kind} artwork: ${id}`);
 const before=Array.from({length:64},(_,i)=>[i+1,choose(kind,i+1)]);
 for(const [id,image] of before){assert.equal(choose(kind,id),image);assert.equal(choose(kind,id),choose(kind,id));}
 for(let i=1;i<64;i++)assert.notEqual(choose(kind,i),choose(kind,i+1));
 assert.equal(choose(kind,'persistent-uuid'),choose(kind,'persistent-uuid'));
}
console.log('PASS: artwork identity, pool coverage, and adjacent numeric identities');
