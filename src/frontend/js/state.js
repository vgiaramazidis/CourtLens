/* Request ownership, result filtering and player-name matching. */
(function(root) {
  function createRequestScope() {
    let generation = 0;
    const requests = new Map();
    return {
      reset() { generation++; requests.forEach(controller => controller.abort()); requests.clear(); },
      start(key) {
        requests.get(key)?.abort();
        const controller = new AbortController();
        const version = generation;
        requests.set(key, controller);
        return { signal:controller.signal, current:() => version === generation && requests.get(key) === controller && !controller.signal.aborted };
      }
    };
  }
  function period(value) {
    const q = String(value || '').trim().toUpperCase();
    if (['OT','1OT','OT1'].includes(q)) return 'OT';
    const match = q.match(/^(?:OT(\d+)|(\d+)OT)$/);
    return match ? `${Number(match[1] || match[2])}OT` : q.toLowerCase();
  }
  function periodOrder(value) { const q=period(value); return ({'1st':1,'2nd':2,'3rd':3,'4th':4,'OT':5})[q] || (q.endsWith('OT') ? 4+parseInt(q) : 99); }
  function clockSeconds(value) { const parts=String(value || '').split(':').map(Number); return parts.length === 2 && parts.every(Number.isFinite) ? parts[0]*60+parts[1] : -1; }
  function normalizeName(value) { return String(value || '').normalize('NFD').replace(/[\u0300-\u036f]/g,'').toLowerCase().replace(/[^a-z0-9]+/g,' ').trim(); }
  function matchesName(guess, answer, catalog=[]) {
    const splitPair=value=>String(value || '').split(/\s*(?:&|\band\b|\+)\s*/i);
    const answers=splitPair(answer), guesses=splitPair(guess);
    if(answers.length>1 || guesses.length>1) {
      if(answers.length!==guesses.length)return false;
      const remaining=[...answers];
      return guesses.every(name=>{const index=remaining.findIndex(candidate=>matchesName(name,candidate,catalog));if(index<0)return false;remaining.splice(index,1);return true;});
    }
    const identity=value=>normalizeName(value).replace(/\s+(?:jr|sr|ii|iii|iv)$/,'');
    const g=identity(guess), a=identity(answer);
    if(!g || g.length<2 || !a)return false;
    if(a===g)return true;
    const words=a.split(' '), guessed=g.split(' ');
    if(words.length===guessed.length && [...words].sort().join(' ')===[...guessed].sort().join(' '))return true;
    const surname=String(answer).includes(',') ? normalizeName(String(answer).split(',')[0]) : words.at(-1);
    if((g===surname || (words.length>2 && g===words.slice(1).join(' '))) && g.length>=3)return true;
    // Legacy jersey-only answers can expand only to a unique known full name.
    if(words.length===1 && guessed.length>1) {
      const candidates=catalog.filter(name=>{
        const normalized=normalizeName(name);
        return (String(name).includes(',') ? normalizeName(name.split(',')[0]) : normalized.split(' ').at(-1))===a;
      });
      return candidates.length===1 && matchesName(guess,candidates[0]);
    }
    return false;
  }
  function gameLabel(game) {
    return [`Game ${game.gameCode}`,game.stage,game.round && `Round ${game.round}`,game.matchup].filter(Boolean).join(' · ');
  }
  function filterShots(shots, filters) {
    return shots.filter(shot => {
      const side=shot.teamType==='home' ? 'home' : 'road';
      const rules=filters.types?.[side] || {};
      
      const is3pt = /ThreePoint/.test(shot.action_type || '') || shot.is3P;
      const basePass = rules[is3pt ? '3pt' : '2pt'] !== false;
      const specialFails = 
        (shot.isFastBreak && rules.fastbreak === false) ||
        (shot.isFromTurnover && rules.turnover === false) ||
        (shot.isSecondChance && rules.secondchance === false);
      const typePass = basePass && !specialFails;

      return (!filters.team || filters.team===side)
        && (!filters.result || (filters.result==='made')===Boolean(shot.isMade))
        && (!filters.periods || filters.periods.has(period(shot.quarter)))
        && (!filters.players || filters.players.has(shot.playerName))
        && (!filters.actionUris || filters.actionUris.has(shot.action_uri))
        && typePass;
    });
  }
  function filterActions(actions, filters, category) {
    return actions.filter(action=>(!filters.actionUris || filters.actionUris.has(action.uri))
      && (!filters.types || filters.types.has(category(action)))
      && (!filters.player || action.playerName===filters.player)
      && (!filters.quarter || period(action.quarter)===period(filters.quarter)))
      .sort((a,b)=>periodOrder(a.quarter)-periodOrder(b.quarter) || (Number(a.sequence)>0 && Number(b.sequence)>0 ? Number(a.sequence)-Number(b.sequence) : 0) || clockSeconds(b.playTime)-clockSeconds(a.playTime) || String(a.uri || '').localeCompare(String(b.uri || '')));
  }
  function availablePeriods(shots, actions=[]) {
    return [...new Set([...shots,...actions].map(item=>period(item.quarter)).filter(Boolean))].sort((a,b)=>periodOrder(a)-periodOrder(b));
  }
  function hasShotLocation(shot) {
    return shot.x!==null && shot.y!==null && shot.x!=='' && shot.y!=='' && Number.isFinite(Number(shot.x)) && Number.isFinite(Number(shot.y)) && !(Number(shot.x)===-1 && Number(shot.y)===-1);
  }
  function csvValue(value) { let text=String(value ?? ''); if (/^[=+@\-\t\r]/.test(text)) text="'"+text; return '"'+text.replace(/"/g,'""')+'"'; }
  function quizRules(difficulty) {
    return difficulty==='easy' ? {clues:3,choices:3,bank:8,misses:5} : difficulty==='medium' ? {clues:2,choices:4,bank:10,misses:4} : {clues:1,choices:0,bank:0,misses:3};
  }
  function quizChoices(answers, pool, count, excluded=[], random=Math.random) {
    const choices=[...answers];
    const candidates=[...new Set(pool)].filter(name=>![...answers,...excluded].some(other=>matchesName(name,other,pool)));
    function shuffle(items) { for(let i=items.length-1;i>0;i--){const j=Math.floor(random()*(i+1));[items[i],items[j]]=[items[j],items[i]];}return items; }
    choices.push(...shuffle(candidates).slice(0,Math.max(0,count-choices.length)));
    return shuffle(choices);
  }
  function simulateFinish(scenario, lineup, history, random=Math.random) {
    // A transparent game mechanic, not an estimate of a real team's win probability.
    const seconds=Math.max(0,clockSeconds(scenario.clock));
    const possessions=seconds>0?Math.max(1,Math.ceil(seconds/36)):0;
    const known=lineup.filter(player=>/guard|forward|center/i.test(player.position || ''));
    const missingRoles=known.length===5?['guard','forward','center'].filter(role=>!known.some(player=>player.position.toLowerCase().includes(role))):[];
    const pointsFor=Math.max(0,Number(history.points_for)||0),pointsAgainst=Math.max(0,Number(history.points_against)||0);
    // Shrink small samples toward neutral and cap their influence on each possession.
    const historyEdge=Math.max(-.10,Math.min(.10,(pointsFor-pointsAgainst)/(pointsFor+pointsAgainst+20)*.20));
    const scoringChance=.53+historyEdge-missingRoles.length*.04;
    const possessionPoints=chance=>random()>=chance?0:random()<.12?1:random()<.30?3:2;
    let scored=0,conceded=0;
    for(let i=0;i<possessions;i++){scored+=possessionPoints(scoringChance);conceded+=possessionPoints(.53-historyEdge);}
    return {scored,conceded,possessions,historyEdge,missingRoles,positionsKnown:known.length===5,user:Number(scenario.user_score)+scored,opponent:Number(scenario.opp_score)+conceded};
  }
  function videoGamesForSeason(games,catalog,season) { const allowed=new Set(catalog.filter(game=>game.season_code===season).map(game=>String(game.game_code)));return games.filter(game=>allowed.has(String(game.gameCode))); }
  const api={createRequestScope,availablePeriods,hasShotLocation,period,periodOrder,clockSeconds,normalizeName,matchesName,gameLabel,filterShots,filterActions,csvValue,videoGamesForSeason,quizRules,quizChoices,simulateFinish};
  if (typeof module!=='undefined' && module.exports) module.exports=api;
  else root.EuroleagueState=api;
})(typeof window!=='undefined' ? window : globalThis);
