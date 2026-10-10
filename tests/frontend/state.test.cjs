const test=require('node:test');
const assert=require('node:assert/strict');
const {createRequestScope,period,periodOrder,filterShots,matchesName,csvValue,videoGamesForSeason}=require('../../src/frontend/js/state.js');

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

test('full-name autocomplete matches a legacy jersey surname without accepting the wrong person',()=>{
  const catalog=['Shane Larkin','Kostas Sloukas'];
  assert.equal(matchesName('Shane Larkin','LARKIN',catalog),true);
  assert.equal(matchesName('Larkin','LARKIN, SHANE',catalog),true);
  assert.equal(matchesName('Shane Larkin','LARKIN, SHANE',catalog),true);
  assert.equal(matchesName('Tom Larkin','LARKIN',catalog),false);
  assert.equal(matchesName('Shane','Shane Larkin',catalog),false);
  assert.equal(matchesName('Mike James','JAMES',['Mike James','LeBron James']),false);
});
test('passing pair answers require both players, in either order',()=>{
  const answer='Kostas Sloukas & Mathias Lessort';
  assert.equal(matchesName('Sloukas',answer),false);
  assert.equal(matchesName('Lessort and Sloukas',answer),true);
  assert.equal(matchesName('Kostas Sloukas & Mathias Lessort',answer),true);
  assert.equal(matchesName('Sloukas & Sloukas',answer),false);
});
test('every game label includes its number and uses stored stage and round when present',()=>{
  const {gameLabel}=require('../../src/frontend/js/state.js');
  assert.equal(gameLabel({gameCode:'333',matchup:'Madrid vs Panathinaikos',stage:'Final',round:'43'}),'Game 333 · Final · Round 43 · Madrid vs Panathinaikos');
  assert.equal(gameLabel({gameCode:'2',matchup:'A vs B'}),'Game 2 · A vs B');
});

test('compound surnames and optional generational suffixes identify the same player',()=>{
  assert.equal(matchesName('De Colo','Nando De Colo'),true);
  assert.equal(matchesName('Wade Baldwin','Wade Baldwin IV'),true);
  assert.equal(matchesName('Baldwin','Wade Baldwin IV'),true);
  assert.equal(matchesName('Tom Baldwin','Wade Baldwin IV'),false);
});

test('Play-by-Play intersects player, period, action type and AI matches; clear all shows none',()=>{
  const {filterActions}=require('../../src/frontend/js/state.js');
  const actions=[
    {uri:'a',playerName:'LESSORT, MATHIAS',quarter:'1st',playTime:'09:00',action_type:'TwoPointShotMade'},
    {uri:'b',playerName:'LESSORT, MATHIAS',quarter:'1st',playTime:'08:00',action_type:'ThreePointShotMissed'},
    {uri:'c',playerName:'TAVARES, WALTER',quarter:'1st',playTime:'07:00',action_type:'TwoPointShotMade'},
    {uri:'d',playerName:'LESSORT, MATHIAS',quarter:'2nd',playTime:'09:00',action_type:'TwoPointShotMade'}
  ];
  const category=action=>action.action_type.startsWith('Two')?'two-pointers':'three-pointers';
  assert.deepEqual(filterActions(actions,{types:new Set()},category),[]);
  assert.deepEqual(filterActions(actions,{player:'LESSORT, MATHIAS',quarter:'1st',types:new Set(['two-pointers']),actionUris:new Set(['a','b','c'])},category).map(a=>a.uri),['a']);
  assert.deepEqual(filterActions(actions,{player:'LESSORT, MATHIAS',types:new Set(['three-pointers'])},category).map(a=>a.uri),['b']);
});

test('official action order wins over corrected or rounded game clocks',()=>{
  const {filterActions}=require('../../src/frontend/js/state.js');
  const actions=[
    {uri:'later',quarter:'4OT',sequence:733,playTime:'00:01'},
    {uri:'first',quarter:'1st',sequence:1,playTime:'09:58'},
    {uri:'second',quarter:'1st',sequence:2,playTime:'10:00'},
    {uri:'third',quarter:'2nd',sequence:3,playTime:'10:00'}
  ];
  assert.deepEqual(filterActions(actions,{},()=> 'other').map(a=>a.uri),['first','second','third','later']);
});
test('court periods include all recorded overtimes and periods without a mapped shot',()=>{
  const {availablePeriods,hasShotLocation}=require('../../src/frontend/js/state.js');
  assert.deepEqual(availablePeriods([{quarter:'1st'}],['4OT','2OT','1OT','3OT','4th','3rd','2nd'].map(quarter=>({quarter}))),['1st','2nd','3rd','4th','OT','2OT','3OT','4OT']);
  assert.equal(hasShotLocation({x:-100,y:250}),true);
  assert.equal(hasShotLocation({x:null,y:null}),false);
  assert.equal(hasShotLocation({x:-1,y:-1}),false);
});
test('special scoring flags cannot re-enable an excluded shot type',()=>{
  const shot={action_type:'TwoPointShotMade',teamType:'home',isFastBreak:true};
  assert.deepEqual(filterShots([shot],{types:{home:{'2pt':false,'3pt':true,fastbreak:true}}}),[]);
});

test('quiz levels progressively reduce clues and choices',()=>{
  const {quizRules,quizChoices}=require('../../src/frontend/js/state.js');
  const easy=quizRules('easy'),medium=quizRules('medium'),hard=quizRules('hard');
  assert.ok(easy.clues>medium.clues && medium.clues>hard.clues);
  assert.equal(easy.choices,3);assert.equal(medium.choices,4);assert.equal(hard.choices,0);
  assert.ok(easy.misses>medium.misses && medium.misses>hard.misses);
  const choices=quizChoices(['Shane Larkin'],['Shane Larkin','LARKIN, SHANE','Mike James','Kendrick Nunn','Perry Dozier Jr'],3,['Mike James'],()=>.5);
  assert.equal(choices.length,3);assert.equal(choices.filter(name=>matchesName(name,'Shane Larkin')).length,1);
  assert.ok(!choices.includes('Mike James'));
});

test('coach outcomes allow wins and losses and reward history and role coverage statistically',()=>{
  const {simulateFinish}=require('../../src/frontend/js/state.js');
  const balanced=['Guard','Guard','Forward','Forward','Center'].map(position=>({position}));
  const unbalanced=balanced.map(()=>({position:'Guard'}));
  const scenario={clock:'03:00',user_score:70,opp_score:73};
  function run(lineup,history){
    let seed=123456,wins=0,losses=0,margin=0;
    const rng=()=>((seed=(1664525*seed+1013904223)>>>0)/4294967296);
    for(let i=0;i<10000;i++){
      const result=simulateFinish(scenario,lineup,history,rng);
      wins+=result.user>result.opponent;losses+=result.user<result.opponent;margin+=result.user-result.opponent;
      assert.ok(result.scored>=0 && result.scored<=result.possessions*3);
      assert.ok(result.conceded>=0 && result.conceded<=result.possessions*3);
    }
    return {wins,losses,margin};
  }
  const strong=run(balanced,{points_for:30,points_against:10});
  const neutral=run(balanced,{}),weak=run(balanced,{points_for:10,points_against:30});
  const poorRoles=run(unbalanced,{});
  assert.ok(strong.wins>neutral.wins && neutral.wins>weak.wins);
  assert.ok(neutral.wins>poorRoles.wins);
  for(const stats of [strong,neutral,weak,poorRoles])assert.ok(stats.wins>0 && stats.losses>0);
  const unknown=simulateFinish(scenario,Array(5).fill({position:''}),{});
  assert.equal(unknown.missingRoles.length,0);
  assert.equal(unknown.historyEdge,0);
  const ended=simulateFinish({...scenario,clock:'00:00'},balanced,{});
  assert.equal(ended.scored,0);assert.equal(ended.conceded,0);
});
