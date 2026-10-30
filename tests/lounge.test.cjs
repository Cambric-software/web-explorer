const test=require('node:test');
const assert=require('node:assert/strict');
const {normalize}=require('../docs/lounge.js');
test('theme settings default safely',()=>assert.deepEqual(normalize(null),{theme:'original',chill:false,sound:'rain',volume:25}));
test('each selectable theme is preserved',()=>{for(const theme of ['original','index','terminal'])assert.equal(normalize({theme}).theme,theme)});
test('ambient choices are preserved',()=>{for(const sound of ['rain','drift'])assert.equal(normalize({sound}).sound,sound)});
test('chill mode requires explicit opt-in',()=>{assert.equal(normalize({chill:true}).chill,true);assert.equal(normalize({chill:'true'}).chill,false)});
test('volume is bounded',()=>{assert.equal(normalize({volume:-1}).volume,0);assert.equal(normalize({volume:101}).volume,100);assert.equal(normalize({volume:NaN}).volume,25)});
