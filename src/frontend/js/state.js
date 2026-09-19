/* Shared, independently testable rules for request ownership and result filtering. */
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
      return (!filters.team || filters.team===side)
        && (!filters.result || (filters.result==='made')===Boolean(shot.isMade))
        && (!filters.periods || filters.periods.has(period(shot.quarter)))
        && (!filters.players || filters.players.has(shot.playerName))
        && (!filters.actionUris || filters.actionUris.has(shot.action_uri))
        && rules[/ThreePoint/.test(shot.action_type || '') || shot.is3P ? '3pt':'2pt']!==false
        && !(shot.isFastBreak && rules.fastbreak===false)
        && !(shot.isFromTurnover && rules.turnover===false)
        && !(shot.isSecondChance && rules.secondchance===false);
    });
  }
  function csvValue(value) { let text=String(value ?? ''); if (/^[=+@\-\t\r]/.test(text)) text="'"+text; return '"'+text.replace(/"/g,'""')+'"'; }
  function videoGamesForSeason(games,catalog,season) { const allowed=new Set(catalog.filter(game=>game.season_code===season).map(game=>String(game.game_code)));return games.filter(game=>allowed.has(String(game.gameCode))); }
  const api={createRequestScope,period,periodOrder,clockSeconds,normalizeName,matchesName,gameLabel,filterShots,csvValue,videoGamesForSeason};
  if (typeof module!=='undefined' && module.exports) module.exports=api;
  else root.EuroleagueState=api;
})(typeof window!=='undefined' ? window : globalThis);
