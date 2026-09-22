const test=require('node:test');
const assert=require('node:assert/strict');
const vm=require('node:vm');
const fs=require('node:fs');
function api(fetch){
  const context=vm.createContext({window:{location:{protocol:'http:',hostname:'localhost'}},fetch,URLSearchParams});
  vm.runInContext(fs.readFileSync(require.resolve('../../src/frontend/js/api.js'),'utf8'),context);
  return context;
}
test('AI requests ask for readable answers and preserve the video workspace',async()=>{
  let payload;
  const context=api(async(url,options)=>{payload=JSON.parse(options.body);return {ok:true,json:async()=>({answer:{kind:'actions'}})};});
  await context.fetchAiChat('Show made threes','333','E2023','openai',undefined,'video');
  assert.equal(payload.workspace,'video');assert.equal(payload.include_answer,true);assert.equal(payload.show_query,true);
  assert.equal(payload.include_query,undefined);
  assert.equal(payload.game_code,'333');assert.equal(payload.provider,'openai');
});
test('manual requests omit all-season sentinels but retain a zero-minute clock limit',async()=>{
  let url;
  const context=api(async(value)=>{url=value;return {ok:true,json:async()=>({shots:[]})};});
  await context.apiRequest('/api/shots',{season_code:'ALL',min_end:0,player:"O'Bryant"});
  const params=new URL(url).searchParams;
  assert.equal(params.has('season_code'),false);assert.equal(params.get('min_end'),'0');assert.equal(params.get('player'),"O'Bryant");
});
test('AI outage preserves the actionable provider-switch message',async()=>{
  const message='The selected AI provider is temporarily unavailable. Choose another provider in Search options or try again later.';
  const context=api(async()=>({ok:false,status:503,json:async()=>({detail:message})}));
  await assert.rejects(()=>context.apiRequest('/api/chat'),{message});
});
test('a canceled search remains an abort rather than a visible network error',async()=>{
  const error=Object.assign(new Error('Canceled'),{name:'AbortError'});
  const context=api(async()=>{throw error;});
  await assert.rejects(()=>context.apiRequest('/api/chat'),{name:'AbortError'});
});
