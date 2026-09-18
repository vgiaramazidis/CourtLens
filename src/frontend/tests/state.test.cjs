const test=require('node:test');
const assert=require('node:assert/strict');
const {createRequestScope,period,periodOrder,filterShots,matchesName,csvValue,videoGamesForSeason}=require('../js/state.js');

test('leaving a workspace cancels all operations and rejects late completions',async()=>{
  const scope=createRequestScope();const search=scope.start('query'),games=scope.start('games'),quiz=scope.start('quiz');
  let resolve;const delayed=new Promise(done=>{resolve=done;});let result='new workspace';
  const pending=delayed.then(value=>{if(search.current())result=value;});
  scope.reset();const next=scope.start('query');resolve('stale response');await pending;
  assert.equal(result,'new workspace');assert.equal(search.signal.aborted,true);assert.equal(games.current(),false);assert.equal(quiz.current(),false);assert.equal(next.current(),true);
});
test('a replacement search cancels its predecessor without cancelling independent data',()=>{
  const scope=createRequestScope(),game=scope.start('game'),old=scope.start('query'),next=scope.start('query');
  assert.equal(old.current(),false);assert.equal(next.current(),true);assert.equal(game.current(),true);
});
test('video choices are scoped by both season and game ID',()=>{
  const games=[{gameCode:7},{gameCode:8},{gameCode:9}];
  const catalog=[{season_code:'E2023',game_code:'7'},{season_code:'E2024',game_code:'8'}];
  assert.deepEqual(videoGamesForSeason(games,catalog,'E2023'),[{gameCode:7}]);
  assert.deepEqual(videoGamesForSeason(games,[],'E2023'),[]);
});
test('clearing players or periods means no shots, not all shots',()=>{
  const shots=[{playerName:'A',quarter:'OT',teamType:'home',isMade:true,action_uri:'one'}];
  assert.deepEqual(filterShots(shots,{players:new Set()}),[]);
  assert.deepEqual(filterShots(shots,{periods:new Set()}),[]);
  assert.equal(filterShots(shots,{players:new Set(['A']),periods:new Set(['OT'])}).length,1);
});
test('shot filters intersect AI matches, team, result, type and scoring context',()=>{
  const shots=[{playerName:'A',quarter:'1OT',teamType:'home',isMade:true,action_type:'ThreePointShotMade',action_uri:'one',isFastBreak:true},{playerName:'B',quarter:'2OT',teamType:'road',isMade:false,action_type:'TwoPointShotMissed',action_uri:'two'}];
  assert.equal(filterShots(shots,{actionUris:new Set(['one']),periods:new Set(['OT']),result:'made'}).length,1);
  assert.deepEqual(filterShots(shots,{actionUris:new Set(['one']),types:{home:{fastbreak:false}}}),[]);
  assert.deepEqual(filterShots(shots,{team:'home',result:'missed'}),[]);
});
test('overtime aliases sort after regulation and before later overtime',()=>{
  assert.equal(period('OT1'),'OT');assert.equal(period('1OT'),'OT');assert.equal(period('OT2'),'2OT');
  assert.ok(periodOrder('4th')<periodOrder('OT'));assert.ok(periodOrder('OT')<periodOrder('2OT'));
});
test('quiz accepts names without accents and surname order, but not arbitrary substrings',()=>{
  assert.equal(matchesName('sloukas','SLOUKAS, KOSTAS'),true);
  assert.equal(matchesName('Kostas Sloukas','SLOUKAS, KOSTAS'),true);
  assert.equal(matchesName('micic','Vasilije Micić'),true);
  assert.equal(matchesName('s','Kostas Sloukas'),false);assert.equal(matchesName('lou','Kostas Sloukas'),false);
});
test('CSV export escapes quotes and neutralizes spreadsheet formulas',()=>{
  assert.equal(csvValue('=1+1'),'"\'=1+1"');assert.equal(csvValue('A "quoted" name'),'"A ""quoted"" name"');
});
