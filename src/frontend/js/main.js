/* CourtLens navigation, workspace rendering and user interactions. */
(() => {
  'use strict';
  const $ = id => document.getElementById(id);
  const S = window.EuroleagueState;
  const requests = S.createRequestScope();
  const seasons = {E2023:'2023–24',E2024:'2024–25',E2025:'2025–26'};
  const positions = ['Point guard','Shooting guard','Small forward','Power forward','Center'];
  const quizNames = {'who-am-i':'Who am I?','who-is-missing':'Who is missing?','higher-or-lower':'Higher or lower','top-5':'Top 5','fifty-fifty':'50/50'};
  const categories = [
    ['two-pointers','2-point shots',/TwoPointShot/],['three-pointers','3-point shots',/ThreePointShot/],['free-throws','Free throws',/FreeThrow/],['rebounds','Rebounds',/Rebound/],
    ['assists','Assists',/Assist/],['turnovers','Turnovers',/Turnover/],['fouls','Fouls',/Foul/],['steals','Steals',/Steal/],
    ['blocks','Blocks',/Block|ShotRejected/],['substitutions','Substitutions',/Substitution|PlayerIn|PlayerOut/],
    ['timeouts','Timeouts',/Timeout/],['jump-balls','Jump balls',/JumpBall/],['periods','Period events',/BeginPeriod|EndPeriod|PeriodStart|PeriodEnd|GameEnd|EndGame/],['other','Other',/.*/]
  ];
  const state = {exploreMode:'browse',section:'video',videoView:'court',mode:'coach',shots:[],actions:[],roster:[],players:new Map(),games:[],videoCatalog:[],models:[],teams:[],table:[],columns:[],tableLimit:50,pbpLimit:50,aiUris:null,shotUris:null,selectedAction:null,scenario:null,lineup:Array(5).fill(null),slot:0,quiz:null,tableIsShots:false};
  window.App = { get section(){return state.section;}, selectShot:shot=>selectShot(shot), clearShotSelection };
  window.homePlayersSet = new Set();
  const esc = value => String(value ?? '').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
  const show = (id,visible=true) => { $(id).hidden=!visible; };
  const text = (id,value) => { $(id).textContent=value; };
  const cat = action => categories.find(entry=>entry[2].test(action.action_type || ''))[0];
  const periodName = q => ({'1st':'Quarter 1','2nd':'Quarter 2','3rd':'Quarter 3','4th':'Quarter 4','OT':'Overtime'})[S.period(q)] || `Overtime ${parseInt(S.period(q)) || ''}`;
  const actionText = action => ({PlayerIn:'Player enters the court',PlayerOut:'Player leaves the court',TimeoutTV:'Broadcast timeout',PeriodStart:'Start of period',PeriodEnd:'End of period'}[action.action_type] || String(action.action_type || 'Action')).replace(/([a-z])([A-Z])/g,'$1 $2').replace(/Three Point/g,'3-point').replace(/Two Point/g,'2-point').replace(/Free Throw/g,'Free throw');
  const playerName = value => {
    const raw=String(value || 'Unknown player');
    if (raw.includes(',')) {const [last,...first]=raw.split(',');return `${first.join(' ').trim()} ${last.trim()}`.trim();}
    return raw;
  };
  const initials = value => playerName(value).split(/[\s-]+/).slice(0,2).map(word=>word[0] || '').join('').toUpperCase();
  function imageMarkup(player) {
    const src=player?.img;
    return src && /^https?:\/\//.test(src) && src!=='NO_IMG'
      ? `<img class="avatar" src="${esc(src)}" alt="" loading="lazy">`
      : `<span class="avatar" aria-hidden="true">${esc(initials(player?.name || 'Player'))}</span>`;
  }
  function teamMarkup(name,code='') {
    const team=state.teams.find(t=>t.id===code || S.normalizeName(t.name)===S.normalizeName(name));
    const logo=team?.logo;
    return `<span class="team-identity"><span class="team-badge">${logo && /^https?:\/\//.test(logo)?`<img src="${esc(logo)}" alt="" data-team-fallback="${esc(initials(name))}">`:esc(initials(name))}</span><span>${esc(name)}</span></span>`;
  }
  async function loadTeams(signal) {
    if(state.teams.length)return;
    try {const data=await apiRequest('/api/teams',{}, {signal});state.teams=data.teams || [];}
    catch(error){if(error.name==='AbortError')throw error;}
  }
  function personMarkup(player) { return `<span class="table-person">${imageMarkup(player)}<span>${esc(playerName(player?.name || player?.id))}</span></span>`; }
  document.addEventListener('error',event=>{
    if(event.target instanceof HTMLImageElement && event.target.hasAttribute('data-team-fallback')){event.target.parentElement.textContent=event.target.dataset.teamFallback;return;}
    if(event.target instanceof HTMLImageElement){const span=document.createElement('span');span.className='avatar';span.textContent='EL';span.setAttribute('aria-hidden','true');event.target.replaceWith(span);}
  },true);
  function message(id,content,error=false) { const el=$(id); el.textContent=content; el.classList.toggle('error',error); el.hidden=!content; }
  function setBusy(id,busy,label) { const el=$(id);el.disabled=busy;el.textContent=label; }
  function scopeText() {
    const season=$('seasonSelect').value;
    const game=$('gameSelect').selectedOptions[0];
    return `${season==='ALL' ? 'All available seasons (2023–26)' : seasons[season] || 'Choose a season'}${$('gameSelect').value ? ` · ${game.textContent}` : ' · All games'}`;
  }
  function scopeParams() {return {season_code:$('seasonSelect').value,game_code:$('gameSelect').value};}
  function clearAnalysis() {
    document.querySelectorAll('dialog[open]').forEach(dialog=>dialog.close());
    state.shots=[];state.actions=[];state.table=[];state.columns=[];state.aiUris=null;state.shotUris=null;state.selectedAction=null;state.tableIsShots=false;state.roster=[];state.players.clear();
    window.homePlayersSet.clear();
    ['videoCompanion','videoEmptyState','aiPlaySearchResult','evidencePanel','courtPanel','videoPanel','pbpPanel','gameHeading','selectedShot','lineupDetails','mobileViewSwitch'].forEach(id=>show(id,false));
    ['resultTable','pbpList','lineupContent','quarterFilters','rosterFilters','teamShotFilters','pbpActionFilters','playerOptions'].forEach(id=>$(id).replaceChildren());
    $('sparqlQuery').value='';message('queryStatus','');setBusy('runQuery',false,'Run query');$('pbpPlayer').innerHTML='<option value="">All players</option>';$('aiPlaySearchInput').value=''; $('analysisForm').reset();updateTopicFilters();updateAnalysisFilterSummary(); $('followVideo').checked=false;
    $('courtPlayerSearch').value='';show('clearShotSelection',false);text('courtFocusNote','Select a shot to isolate it. Drag to rotate; scroll to zoom.');text('shotFilterCount','');
    $('shotTeam').value='';$('shotTeam').options[1].textContent='Home team';$('shotTeam').options[2].textContent='Away team';$('shotResult').value='';$('pbpQuarter').innerHTML='<option value="">All periods</option>';
    document.querySelectorAll('#analysisSection details').forEach(el=>el.open=false);
    message('workspaceStatus','');text('scopeStatus','');show('retryGamesButton',false);
    setBusy('aiPlaySearchButton',false,'Search');setBusy('runAnalysis',false,'Show results');
    $('aiPlaySearchResult').removeAttribute('aria-busy');
    window.setYouTubeVideo?.(null);window.drawShots?.([]);window.highlightShot?.(null);
    setMobileView('results');
    show('exploreSuggestions',state.section==='explore' && state.exploreMode==='ask');show('videoEmptyState',state.section==='video');
  }
  function resetGames() {
    state.scenario=null;state.lineup=Array(5).fill(null);state.slot=0;state.quiz=null;
    show('coachWorkspace',false);show('simulatorResult',false);show('quizSetup');show('quizGame',false);
    $('quizGame').replaceChildren();$('quizSetupForm').reset();$('coachSeason').value='ALL';
    message('coachStatus','');setBusy('startChallenge',false,'Start challenge');setBusy('runSimulation',true,'Run simulation');
  }
  function navigate(section,mode='coach') {
    // Invalidate pending responses before another workspace can render them.
    requests.reset();state.section=section;state.mode=mode;state.exploreMode='browse';state.videoView='court';
    clearAnalysis();resetGames();
    document.querySelectorAll('[data-section]').forEach(link=>{if(link.dataset.section===section)link.setAttribute('aria-current','page');else link.removeAttribute('aria-current');});
    document.querySelectorAll('[data-mode]').forEach(button=>button.setAttribute('aria-pressed',String(button.dataset.mode===mode)));
    show('analysisSection',section!=='games');show('gamesSection',section==='games');show('coachPanel',mode==='coach');show('quizPanel',mode==='quiz');
    const video=section==='video';
    $(video?'scopeDock':'searchScopeDock').append($('scopeBar'));
    $('workspaceGrid').classList.toggle('video-mode',video);
    show('videoSearch',video);show('queryDetails',video);
    // Move the existing panels so their event listeners and the video player survive view changes.
    if(video){$('videoCompanion').append($('courtPanel'),$('pbpPanel'));$('videoSearchDock').append($('aiSearchPanel'));$('pbpEvidenceDock').append($('evidencePanel'));}
    else {$('workspaceGrid').prepend($('aiSearchPanel'));$('workspaceGrid').append($('courtPanel'),$('pbpPanel'),$('evidencePanel'));$('courtPanel').append($('momentDetails'));}
    setVideoView(state.videoView);
    text('pageEyebrow',video ? 'SYNCHRONIZED GAME FILM':'EUROLEAGUE ANALYSIS');
    text('pageTitle',video ? 'Video Analysis':'Explore');
    text('pageDescription',video ? 'Watch the game alongside its shot chart or Play-by-Play.':'Browse game statistics, shot locations, and player performance across seasons.');
    text('searchLabel',video ? 'AI Search in this game':'AI Search');
    $('aiPlaySearchInput').placeholder=video ? 'Search this game':'Ask about a player, team, or game';
    text('aiSearchNote',video ? 'Try: All shots by Mathias Lessort when Walter Tavares was on the court.':'Search across all available seasons, or narrow your question to a game.');
    document.querySelector('[data-view="results"]').textContent=video ? 'Actions':'Results';
    show('exploreModes',section==='explore');setExploreModeUI();
    $('seasonSelect').innerHTML=video ? '<option value="">Choose a season</option>' : '<option value="ALL">All available seasons</option>'+Object.entries(seasons).map(([key,label])=>`<option value="${key}">${label}</option>`).join('');
    $('gameSelect').innerHTML=`<option value="">${video ? 'Choose a season first':'All games'}</option>`;$('gameSelect').disabled=true;
    $('seasonSelect').disabled=video;
    document.title=`CourtLens · ${section==='video'?'Video Analysis':section==='games'?'Games':'Explore'}`;
    if(video) loadVideoCatalog();
    if(section!=='games') loadModels();
    window.scrollTo({top:0,behavior:'instant'});
  }
  function setVideoView(view) {
    state.videoView=view==='pbp'?'pbp':'court';
    $('workspaceGrid').dataset.videoView=state.videoView;
    document.querySelectorAll('[data-video-view]').forEach(button=>button.setAttribute('aria-pressed',String(button.dataset.videoView===state.videoView)));
    if(state.section!=='video')return;
    const loaded=!$('videoPanel').hidden;show('videoCompanion',loaded);
    show('courtPanel',loaded && state.videoView==='court');show('pbpPanel',loaded && state.videoView==='pbp');show('mobileViewSwitch',false);
    $(state.videoView==='pbp'?'pbpMomentDock':'courtPanel').append($('momentDetails'));
    requestAnimationFrame(()=>window.resizeCourt?.());
  }
  document.querySelectorAll('[data-video-view]').forEach(button=>button.onclick=()=>setVideoView(button.dataset.videoView));
  function setExploreModeUI() {
    const browse=state.section==='explore' && state.exploreMode==='browse';
    show('analysisTools',browse);show('searchForm',!browse);$('aiSearchPanel').setAttribute('aria-label',browse?'Statistics workspace':'AI Search');
    document.querySelectorAll('[data-explore-mode]').forEach(button=>button.setAttribute('aria-pressed',String(button.dataset.exploreMode===state.exploreMode)));
    $(state.section==='video'?'scopeDock':browse?'browseScopeDock':'searchScopeDock').append($('scopeBar'));
  }
  document.querySelectorAll('[data-explore-mode]').forEach(button=>button.onclick=()=>{
    if(state.exploreMode===button.dataset.exploreMode)return;
    requests.reset();state.exploreMode=button.dataset.exploreMode;clearAnalysis();
    $('seasonSelect').value='ALL';$('gameSelect').innerHTML='<option value="">All games</option>';$('gameSelect').disabled=true;
    setExploreModeUI();loadModels();
  });
  function readRoute() { const [section,mode]=location.hash.slice(1).split('/');navigate(['explore','video','games'].includes(section)?section:'video',mode==='quiz'?'quiz':'coach'); }
  window.addEventListener('hashchange',()=>{readRoute();$('mainContent').focus({preventScroll:true});});
  document.querySelector('.skip-link').addEventListener('click',event=>{event.preventDefault();$('mainContent').focus();$('mainContent').scrollIntoView();});
  document.querySelectorAll('[data-mode]').forEach(button=>button.addEventListener('click',()=>{location.hash=button.dataset.mode==='quiz'?'games/quiz':'games';}));
  $('helpButton').addEventListener('click',()=>$('basicsDialog').showModal());
  $('openCourtFilters').onclick=()=>$('courtFilterDialog').showModal();
  $('openAnalysisFilters').onclick=()=>$('advancedFilters').showModal();
  document.querySelectorAll('[data-close-dialog]').forEach(button=>button.onclick=()=>$(button.dataset.closeDialog).close());
  $('courtPlayerSearch').oninput=()=>{
    const term=S.normalizeName($('courtPlayerSearch').value);
    $('rosterFilters').querySelectorAll('[data-shot-player]').forEach(input=>{input.closest('label').hidden=!S.normalizeName(input.dataset.shotPlayer).includes(term);});
  };
  $('resetShotFilters').onclick=()=>{
    $('shotTeam').value='';$('shotResult').value='';$('courtPlayerSearch').value='';
    document.querySelectorAll('[data-shot-quarter],[data-shot-type],[data-shot-player]').forEach(input=>{input.checked=true;input.closest('label').hidden=false;});
    applyShotFilters();
  };
  $('resetAnalysisFilters').onclick=()=>{
    const type=$('analysisType').value;$('analysisForm').reset();$('analysisType').value=type;updateTopicFilters();updateAnalysisFilterSummary();message('analysisFilterError','');
  };
  $('clearSearchButton').addEventListener('click',()=>{const mode=state.exploreMode;navigate(state.section);if(state.section==='explore' && mode==='browse'){state.exploreMode=mode;setExploreModeUI();show('exploreSuggestions',false);}});
  $('seasonSelect').addEventListener('change',()=>{requests.reset();clearAnalysis();loadGames();loadModels();});
  $('gameSelect').addEventListener('change',()=>{requests.reset();clearAnalysis();if($('gameSelect').value)loadGame();loadModels();});
  $('retryGamesButton').addEventListener('click',()=>state.section==='video' && !state.videoCatalog.length ? loadVideoCatalog() : loadGames());
  function setMobileView(view) { $('workspaceGrid').dataset.mobileView=view;document.querySelectorAll('[data-view]').forEach(button=>button.setAttribute('aria-pressed',String(button.dataset.view===view)));requestAnimationFrame(()=>window.resizeCourt?.()); }
  document.querySelectorAll('[data-view]').forEach(button=>button.addEventListener('click',()=>{setMobileView(button.dataset.view);$('mobileViewSwitch').scrollIntoView({block:'start'});}));
  document.querySelectorAll('[data-prompt]').forEach(button=>button.addEventListener('click',()=>{$('aiPlaySearchInput').value=button.dataset.prompt;$('aiPlaySearchInput').focus();$('aiSearchPanel').scrollIntoView({block:'center'});}));

  // Game and provider loading.
  async function loadModels() {
    const ticket=requests.start('models');
    try {
      if(!state.models.length) {const data=await apiRequest('/api/chat/models',{}, {signal:ticket.signal});if(!ticket.current())return;state.models=data.models || [];}
      if(!ticket.current())return;
      $('aiModelSelect').innerHTML=state.models.length ? state.models.map(model=>`<option value="${esc(model.provider)}" ${model.is_default?'selected':''}>${esc(model.label)}</option>`).join('') : '<option value="">No provider available</option>';
      $('aiModelSelect').disabled=!state.models.length;
      text('aiModelStatus',state.models.length ? 'Choose the provider for this search.':'AI Search is currently unavailable. Player profiles and Browse statistics are still available.');
    } catch(error) {if(ticket.current()){text('aiModelStatus',error.message);$('aiModelSelect').disabled=true;}}
  }
  async function loadVideoCatalog() {
    const ticket=requests.start('catalog');state.videoCatalog=[];
    message('workspaceStatus','Loading games with synchronized video…');
    try {
      const data=await fetchAvailableVideoGames(null,ticket.signal);if(!ticket.current())return;
      state.videoCatalog=data.games || [];
      $('seasonSelect').innerHTML='<option value="">Choose a season</option>'+(data.seasons || []).map(code=>`<option value="${esc(code)}">${esc(seasons[code] || code)}</option>`).join('');
      $('seasonSelect').disabled=!state.videoCatalog.length;
      message('workspaceStatus',state.videoCatalog.length ? 'Choose a season and game to open the video workspace.':'No synchronized videos are available yet.');
      text('scopeStatus',`${state.videoCatalog.length} games with video`);
    } catch(error) {if(ticket.current()){message('workspaceStatus',error.message,true);show('retryGamesButton');}}
  }
  async function loadGames() {
    const season=$('seasonSelect').value;const ticket=requests.start('games');
    $('gameSelect').disabled=true;$('gameSelect').innerHTML='<option value="">Loading games…</option>';
    if(!season || season==='ALL'){$('gameSelect').innerHTML='<option value="">All games</option>';return;}
    try {
      const data=await apiRequest('/api/games',{season_code:season},{signal:ticket.signal});if(!ticket.current())return;
      state.games=state.section==='video' ? S.videoGamesForSeason(data.games || [],state.videoCatalog,season) : data.games || [];
      $('gameSelect').innerHTML=`<option value="">${state.section==='video'?'Choose a game':'All games in this season'}</option>`+state.games.map(game=>`<option value="${esc(game.gameCode)}">${esc(S.gameLabel(game))}</option>`).join('');
      $('gameSelect').disabled=!state.games.length;
      message('workspaceStatus',state.games.length ? '' : 'No games are available for this season.');text('scopeStatus',`${state.games.length} games${state.section==='video'?' with video':''}`);
    } catch(error){if(ticket.current()){$('gameSelect').innerHTML='<option value="">Games unavailable</option>';message('workspaceStatus',error.message,true);show('retryGamesButton');}}
  }
  function ingestRoster(data) {
    state.roster=[];state.players.clear();window.homePlayersSet.clear();
    (data.lineups || []).forEach(lineup=>(lineup.players || '').split('@@').filter(Boolean).forEach(info=>{
      const [id,name,img,position]=info.split('|');
      if(state.players.has(id)){const existing=state.players.get(id);existing.position=[...new Set([...(existing.position || '').split(' / '),position].filter(Boolean))].sort().join(' / ');return;}
      const player={id,name:name || id,img,position,side:lineup.teamType};state.players.set(id,player);state.roster.push(player);
      if(player.side==='home')window.homePlayersSet.add(player.name);
    }));
    $('playerOptions').innerHTML=state.roster.map(player=>`<option value="${esc(player.id)}">${esc(playerName(player.name))}</option>`).join('');
  }
  async function loadGame() {
    const ticket=requests.start('game');const params=scopeParams();const video=state.section==='video';
    message('workspaceStatus',video?'Loading video, shots, and Play-by-Play…':'Loading player names for this game…');
    try {
      const [roster,shots,actions,config]=await Promise.all([
        apiRequest('/api/game/lineups',params,{signal:ticket.signal}),
        video ? apiRequest('/api/shots',params,{signal:ticket.signal}):Promise.resolve(null),
        video ? fetchMatchPlayByPlay(params.game_code,params.season_code,ticket.signal):Promise.resolve(null),
        video ? fetchVideoConfig(params.game_code,params.season_code,ticket.signal):Promise.resolve(null),
        loadTeams(ticket.signal)
      ]);
      if(!ticket.current())return;ingestRoster(roster);message('workspaceStatus','');
      const names=(state.games.find(game=>String(game.gameCode)===params.game_code)?.matchup || '').split(/\s+vs\s+/i);
      const home=names[0] || 'Home team',away=names[1] || 'Away team';
      $('shotTeam').options[1].textContent=home;$('shotTeam').options[2].textContent=away;
      show('gameHeading');$('gameHeading').innerHTML=`${teamMarkup(home)}<span class="matchup-separator">vs</span>${teamMarkup(away)}<span class="muted">${esc(seasons[params.season_code])}</span>`;
      if(!video)return;
      if(!config?.available || !config.timeline_available){message('workspaceStatus','This game’s synchronized video is no longer available. Choose another game.',true);return;}
      state.shots=shots.shots || [];state.actions=actions || [];
      show('videoPanel');show('gameHeading');show('videoEmptyState',false);setVideoView(state.videoView);
      $('gameHeading').innerHTML=`${teamMarkup(home)}<span class="game-score">${esc(roster.homeScore ?? '—')} – ${esc(roster.roadScore ?? '—')}<small>Final score</small></span>${teamMarkup(away)}<span class="muted">${esc(seasons[params.season_code])} · Full game</span>`;
      $('shotTeam').options[1].textContent=home;$('shotTeam').options[2].textContent=away;
      window.setYouTubeVideo(config.youtube_id,config.playback_lead_seconds);
      buildShotFilters();buildActionFilters();renderActions();applyShotFilters();$('sparqlQuery').value=defaultVideoQuery();
    } catch(error){if(ticket.current())message('workspaceStatus',error.message,true);}
  }

  // Shot filters and synchronized Play-by-Play.
  function buildShotFilters() {
    const periods=[...new Set(state.shots.map(shot=>S.period(shot.quarter)).filter(Boolean))].sort((a,b)=>S.periodOrder(a)-S.periodOrder(b));
    $('quarterFilters').innerHTML=periods.map(q=>`<label class="filter-chip"><input type="checkbox" aria-label="${esc(periodName(q))}" data-shot-quarter="${esc(q)}" checked><span>${esc(S.periodOrder(q)<=4?'Q'+S.periodOrder(q):q)}</span></label>`).join('');
    const types=[['2pt','2-point shots'],['3pt','3-point shots'],['fastbreak','Fast-break points'],['turnover','Points after turnovers'],['secondchance','Second-chance points']];
    $('teamShotFilters').innerHTML=['home','road'].map((side,index)=>`<fieldset class="team-filter-group"><legend>${esc($('shotTeam').options[index+1].textContent)}</legend><div class="check-group">${types.map(([type,label])=>`<label><input type="checkbox" data-shot-side="${side}" data-shot-type="${type}" checked>${label}</label>`).join('')}</div></fieldset>`).join('');
    const names=[...new Set(state.shots.map(shot=>shot.playerName).filter(Boolean))].sort();
    $('rosterFilters').innerHTML=`<div class="check-group"><button type="button" id="selectAllPlayers" class="text-button">Select all</button><button type="button" id="clearAllPlayers" class="text-button">Clear all</button></div><div class="roster-group">${names.map(name=>{const player=state.roster.find(p=>p.name===name) || {name, img: state.shots.find(s=>s.playerName===name)?.playerImg};return `<label><input type="checkbox" data-shot-player="${esc(name)}" checked>${imageMarkup(player)}${esc(playerName(name))}</label>`;}).join('')}</div>`;
    $('selectAllPlayers').onclick=()=>{document.querySelectorAll('[data-shot-player]').forEach(el=>el.checked=true);applyShotFilters();};
    $('clearAllPlayers').onclick=()=>{document.querySelectorAll('[data-shot-player]').forEach(el=>el.checked=false);applyShotFilters();};
  }
  function visibleShots() {
    const types={home:{},road:{}};document.querySelectorAll('[data-shot-type]').forEach(el=>types[el.dataset.shotSide][el.dataset.shotType]=el.checked);
    return S.filterShots(state.shots,{team:$('shotTeam').value,result:$('shotResult').value,periods:new Set([...document.querySelectorAll('[data-shot-quarter]:checked')].map(el=>el.dataset.shotQuarter)),players:new Set([...document.querySelectorAll('[data-shot-player]:checked')].map(el=>el.dataset.shotPlayer)),types,actionUris:state.shotUris});
  }
  function applyShotFilters() {
    const shots=visibleShots();
    if(state.selectedAction && !shots.some(shot=>shot.action_uri===state.selectedAction))clearShotSelection();
    window.drawShots?.(shots);text('courtCount',`${shots.filter(shot=>Number.isFinite(Number(shot.x)) && Number.isFinite(Number(shot.y)) && !(Number(shot.x)===-1 && Number(shot.y)===-1)).length} mapped shots`);
    const active=Number(Boolean($('shotTeam').value))+Number(Boolean($('shotResult').value))+['[data-shot-quarter]','[data-shot-player]','[data-shot-type]'].filter(selector=>[...document.querySelectorAll(selector)].some(input=>!input.checked)).length;
    text('shotFilterCount',active?` · ${active}`:'');
    if(state.tableIsShots){state.table=shots.map(shot=>({'Player':playerName(shot.playerName),'Shot':/ThreePoint/.test(shot.action_type)?'3-pointer':'2-pointer','Result':shot.isMade?'Made':'Missed','Period':periodName(shot.quarter),'Time left':shot.playTime || '—',_shot:shot,_people:{Player:state.roster.find(player=>player.name===shot.playerName) || {name:shot.playerName, img: shot.playerImg}}}));state.columns=['Player','Shot','Result','Period','Time left'];renderTable();}
    requestAnimationFrame(()=>window.resizeCourt?.());
  }
  $('shotFilters').addEventListener('change',applyShotFilters);
  $('courtFilterDialog').addEventListener('change',applyShotFilters);
  function buildActionFilters() {
    const selectedPlayer=$('pbpPlayer').value;
    const names=[...new Set(state.actions.map(action=>action.playerName).filter(Boolean))].sort((a,b)=>playerName(a).localeCompare(playerName(b)));
    $('pbpPlayer').innerHTML='<option value="">All players</option>'+names.map(name=>`<option value="${esc(name)}">${esc(playerName(name))}</option>`).join('');
    if(names.includes(selectedPlayer))$('pbpPlayer').value=selectedPlayer;
    const active=new Set(state.actions.map(cat));
    $('pbpActionFilters').innerHTML=categories.filter(entry=>active.has(entry[0])).map(([id,label])=>`<label><input data-action-type="${id}" type="checkbox" checked>${label}</label>`).join('');
    const periods=[...new Set(state.actions.map(action=>S.period(action.quarter)))].sort((a,b)=>S.periodOrder(a)-S.periodOrder(b));
    $('pbpQuarter').innerHTML='<option value="">All periods</option>'+periods.map(q=>`<option value="${esc(q)}">${esc(periodName(q))}</option>`).join('');
  }
  function filteredActions() {
    const allowed=new Set([...document.querySelectorAll('[data-action-type]:checked')].map(el=>el.dataset.actionType));
    return S.filterActions(state.actions,{actionUris:state.aiUris,types:allowed,player:$('pbpPlayer').value,quarter:$('pbpQuarter').value},cat);
  }
  function renderActions() {
    const actions=filteredActions();
    if(state.section==='video' && state.videoView==='pbp' && state.selectedAction && !actions.some(action=>action.uri===state.selectedAction)){clearShotSelection();return;}
    const shown=actions.slice(0,state.pbpLimit);let lastPeriod='';
    $('pbpList').innerHTML=shown.map(action=>{
      const divider=S.period(action.quarter)!==lastPeriod?`<li class="period-divider">${esc(periodName(action.quarter))}</li>`:'';lastPeriod=S.period(action.quarter);
      const playable=Number.isFinite(action.videoSeconds) && action.videoSeconds>=0;
      return `${divider}<li class="pbp-event ${state.selectedAction===action.uri?'active':''}" data-action-uri="${esc(action.uri)}"><span class="pbp-clock">${esc(action.playTime || '—')}<small>remaining</small></span><div><strong>${esc(playerName(action.playerName || 'Game event'))}</strong><p>${esc(actionText(action))}</p><p>Score ${esc(action.homeScore ?? '—')}–${esc(action.roadScore ?? '—')}${action.isFastBreak?' · Fast break':''}${action.isSecondChance?' · Second chance':''}${action.isFromTurnover?' · After turnover':''}</p>${state.selectedAction===action.uri && !state.shots.some(shot=>shot.action_uri===action.uri)?'<p>This action has no shot location.</p>':''}</div><button class="text-button" data-watch="${esc(action.uri)}" aria-label="${playable && state.section==='video'?'Watch':'Inspect'} ${esc(actionText(action))} by ${esc(action.playerName || 'game event')} at ${esc(action.playTime)}">${playable && state.section==='video'?'Watch':'Details'}</button></li>`;
    }).join('') || '<li class="empty-message">No actions match these filters. Try another player, period or action type.</li>';
    text('pbpSummary',`${actions.length} ${state.aiUris?'matching ':''}${actions.length===1?'action':'actions'} · Showing ${shown.length}${state.aiUris?' · Search filter applied':''}`);show('clearAiFilter',Boolean(state.aiUris));show('moreActions',actions.length>shown.length);
  }
  $('pbpList').addEventListener('click',event=>{const button=event.target.closest('[data-watch]');if(button)selectAction(state.actions.find(action=>action.uri===button.dataset.watch),true);});
  $('pbpQuarter').addEventListener('change',()=>{state.pbpLimit=50;renderActions();});$('pbpActionFilters').addEventListener('change',()=>{state.pbpLimit=50;renderActions();});
  $('pbpPlayer').addEventListener('change',()=>{state.pbpLimit=50;renderActions();});
  $('clearActionTypes').onclick=()=>{document.querySelectorAll('[data-action-type]').forEach(el=>el.checked=false);state.pbpLimit=50;renderActions();};
  $('allActionTypes').onclick=()=>{document.querySelectorAll('[data-action-type]').forEach(el=>el.checked=true);renderActions();};
  $('moreActions').onclick=()=>{state.pbpLimit+=50;renderActions();};
  $('clearAiFilter').onclick=()=>{state.aiUris=null;state.shotUris=null;state.pbpLimit=50;$('pbpQuarter').value='';$('pbpPlayer').value='';document.querySelectorAll('[data-action-type]').forEach(el=>el.checked=true);renderActions();applyShotFilters();message('aiPlaySearchResult','Search filter cleared. Showing all game actions.');};
  function selectAction(action,watch=false) {
    if(!action)return;state.selectedAction=action.uri;
    const shot=state.shots.find(shot=>shot.action_uri===action.uri);
    if(shot)selectShot(shot,false);else {window.highlightShot?.(null);show('clearShotSelection');text('courtFocusNote','This action has no shot location.');show('lineupDetails',false);show('selectedShot');$('selectedShot').innerHTML=`<strong>${esc(playerName(action.playerName || 'Game event'))}</strong><p>${esc(actionText(action))} · ${esc(periodName(action.quarter))} · ${esc(action.playTime)} remaining</p><p class="muted">${Number.isFinite(action.videoSeconds)?'':'No synchronized video timestamp for this action. '}This action has no shot location.</p>`;loadMomentLineups(action);}
    renderActions();
    if(watch && state.section==='video' && Number.isFinite(action.videoSeconds) && action.videoSeconds>=0)window.playVideoAt?.(action.videoSeconds,action.playbackLeadSeconds);
  }
  async function selectShot(shot,watch=true) {
    show('selectedShot');window.highlightShot?.(shot.action_uri);
    const mapped=Number.isFinite(Number(shot.x)) && Number.isFinite(Number(shot.y)) && !(Number(shot.x)===-1 && Number(shot.y)===-1);
    show('clearShotSelection');text('courtFocusNote',mapped?'Selected shot in focus. Other shots are dimmed.':'This shot has no recorded court location.');
    $('selectedShot').innerHTML=`<strong>${esc(playerName(shot.playerName))}</strong><p>${shot.isMade?'Made':'Missed'} ${/ThreePoint/.test(shot.action_type)?'3-point':'2-point'} shot · ${esc(periodName(shot.quarter))} · ${esc(shot.playTime || '—')} remaining</p><p class="muted">Score at this moment: ${esc(shot.homeScore ?? '—')}–${esc(shot.roadScore ?? '—')}</p>`;
    state.selectedAction=shot.action_uri;updateSelectedResult(); if(state.actions.length)renderActions();
    if(watch && state.section==='video' && Number.isFinite(shot.videoSeconds))window.playVideoAt?.(shot.videoSeconds);
    await loadMomentLineups(shot);
  }
  async function loadMomentLineups(moment) {
    const ticket=requests.start('lineup');
    const lineups=[moment.runningHomeTeamLineup || moment.homeLineup,moment.runningRoadTeamLineup || moment.roadLineup];
    show('lineupDetails');$('lineupDetails').open=true;
    if(!lineups.some(uri=>String(uri || '').includes('Lineup_'))){text('lineupContent','On-court players were not recorded for this action.');return;}
    $('lineupContent').textContent='Loading the players on court…';
    try {
      const groups=await Promise.all(lineups.map(async uri=>{
        const ids=String(uri || '').split('Lineup_')[1]?.split('_').filter(Boolean) || [];
        return Promise.all(ids.map(id=>getPlayer(id,ticket.signal)));
      }));
      if(!ticket.current())return;
      $('lineupContent').innerHTML=groups.map((group,index)=>`<div><strong>${esc($('shotTeam').options[index+1].textContent)}</strong>${group.map(personMarkup).join('') || '<p>Lineup unavailable.</p>'}</div>`).join('');
    }catch(error){if(ticket.current())text('lineupContent',error.message);}
  }
  function clearShotSelection() {
    requests.start('lineup');state.selectedAction=null;window.highlightShot?.(null);
    show('selectedShot',false);show('lineupDetails',false);show('clearShotSelection',false);
    text('courtFocusNote','Select a shot to isolate it. Drag to rotate; scroll to zoom.');
    updateSelectedResult();if(state.actions.length)renderActions();
  }
  $('clearShotSelection').onclick=clearShotSelection;
  async function getPlayer(id,signal) {
    if(state.players.has(id))return state.players.get(id);
    try {const data=await apiRequest('/api/player',{player:id},{signal});return {id,name:data.player?.name || id,img:data.player?.img,position:data.player?.position};}
    catch(error){if(error.name==='AbortError')throw error;return {id,name:id};}
  }
  setInterval(()=>{
    if(state.section!=='video' || !$('followVideo').checked || !window.player || typeof window.player.getCurrentTime!=='function')return;
    const current=window.player.getCurrentTime();
    const action=(state.videoView==='pbp'?filteredActions():state.actions).filter(action=>Number.isFinite(action.videoSeconds) && action.videoSeconds<=current && current-action.videoSeconds<12).sort((a,b)=>b.videoSeconds-a.videoSeconds)[0];
    if(action && action.uri!==state.selectedAction){selectAction(action);const row=[...$('pbpList').querySelectorAll('[data-action-uri]')].find(el=>el.dataset.actionUri===action.uri);if(row && $('pbpList').scrollHeight>$('pbpList').clientHeight)$('pbpList').scrollTop=row.offsetTop-$('pbpList').offsetTop;}
  },700);

  // Result tables and AI answers.
  function valueOf(value) {
    if(value===null || value===undefined)return '—';
    const raw=typeof value==='object' && 'value' in value ? String(value.value):String(value);
    if(/^https?:\/\//.test(raw)){try{return decodeURIComponent(raw.split(/[\/#]/).filter(Boolean).pop()).replace(/[_-]+/g,' ');}catch{return raw;}}
    return raw;
  }
  function columnLabel(key) {
    const labels={player_id:'Player',scorer_id:'Scorer',passer_id:'Passer',total_assists:'Assists',total_points:'Points',total_blocks:'Blocks',total_fouls_drawn:'Fouls drawn',playTime:'Time left',playerName:'Player',teamName:'Team',homeScore:'Home score',roadScore:'Away score'};
    return labels[key] || key.replace(/([a-z])([A-Z])/g,'$1 $2').replace(/[_-]/g,' ').replace(/^./,letter=>letter.toUpperCase());
  }
  function friendlySummary(data,count) {
    if(count!==null)return `${count} matching ${count===1?'play':'plays'} found in this game. Select a play to inspect the moment.`;
    if(typeof data.boolean==='boolean')return data.boolean?'Yes. The selected data includes a matching event.':'No matching event was found in the selected data.';
    const rows=data.results || [];
    if(!rows.length)return count ? `${count} matching plays found. Select a play to inspect the moment.`:'No matching data was found. Try another question or a broader scope.';
    const first=rows[0];
    const find=keys=>{const key=Object.keys(first).find(k=>keys.includes(k.toLowerCase().replace(/[_-]/g,'')));return key===undefined ? null:valueOf(first[key]);};
    const person=find(['playername','player','scorer','passer']);
    const percentage=find(['percentage','shotpercentage','fieldgoalpercentage']);
    if(percentage!==null){const made=find(['made','shotsmade','madeshots']),attempts=find(['attempts','shotattempts','totalattempts']);return `${person?playerName(person):'The selected player'} ${made!==null && attempts!==null?`made ${made} of ${attempts} attempts`:`shot ${percentage.replace('%','')}%`}${made!==null && attempts!==null?` (${percentage.replace('%','')}%)`:''} in the selected data.`;}
    for(const [keys,unit] of [[['totalpoints','points'],'points'],[['totalassists','assists'],'assists'],[['totalblocks','blocks'],'blocks'],[['totalrebounds','rebounds'],'rebounds'],[['totalshots','shots','totalattempts'],'shot attempts'],[['totalfoulsdrawn'],'fouls drawn']]){
      const number=find(keys);if(number!==null)return `${person?playerName(person):'The first result'} recorded ${number} ${unit} in the selected data.${rows.length>1?` Compare all ${rows.length} results below.`:''}`;
    }
    return count!==null ? `${count} matching plays found in this game.`:`${rows.length} ${rows.length===1?'result':'results'} found in the selected data. Explore the details below.`;
  }
  function setAnswer(summary,question='',answer=null) {
    const el=$('aiPlaySearchResult');el.className='answer';el.hidden=false;
    const paragraphs=answer?.paragraphs?.length?answer.paragraphs:[summary];
    const profiles=answer?.profiles || [];
    const sourceLink=url=>{try {const parsed=new URL(url);return parsed.protocol==='https:' && parsed.hostname==='www.euroleaguebasketball.net'?`<a href="${esc(url)}" target="_blank" rel="noopener noreferrer">EuroLeague player profile</a>`:'';}catch{return '';}};
    el.innerHTML=`<div class="answer-heading"><p class="eyebrow">${answer?.kind==='profile'?'PLAYER PROFILE':'ANSWER'}</p>${question?`<p class="answer-question">${esc(question)}</p>`:''}</div>${profiles.length?profiles.map(profile=>`<article class="player-profile"><div class="profile-heading">${imageMarkup({name:profile.name,img:profile.image})}<div><h2>${esc(profile.name)}</h2><p class="muted">${esc([profile.position,profile.country].filter(Boolean).join(' · '))}</p></div></div><div class="answer-prose">${profile.paragraphs.map(p=>`<p>${esc(p)}</p>`).join('')}</div><p class="profile-source">${sourceLink(profile.source_url)}</p></article>`).join(''): `<div class="answer-prose">${paragraphs.map(p=>`<p>${esc(p)}</p>`).join('')}</div>`}<p class="answer-scope">${esc(answer?.note || scopeText())}</p>`;
  }
  function updateSelectedResult() {
    $('resultTable').querySelectorAll('[data-result]').forEach(button=>{const selected=Boolean(state.selectedAction && state.table[Number(button.dataset.result)]?._shot?.action_uri===state.selectedAction);button.setAttribute('aria-pressed',String(selected));button.closest('tr').classList.toggle('selected-result',selected);});
  }
  function renderTable() {
    show('evidencePanel');show('exploreSuggestions',false);
    const rows=state.table.slice(0,state.tableLimit),columns=state.columns;
    const hasAction=rows.some(row=>row._shot || row._lineup);
    $('resultTable').innerHTML=rows.length ? `<table><caption class="sr-only">${esc($('evidenceTitle').textContent)}. ${esc(scopeText())}</caption><thead><tr>${columns.map(key=>`<th scope="col">${esc(columnLabel(key))}</th>`).join('')}${hasAction?'<th scope="col">Details</th>':''}</tr></thead><tbody>${rows.map((row,index)=>`<tr>${columns.map(key=>`<td>${row._people?.[key] ? personMarkup(row._people[key]):esc(valueOf(row[key]))}</td>`).join('')}${hasAction?`<td><button class="text-button" data-result="${index}">${row._lineup?'Show shots':'Inspect shot'}</button></td>`:''}</tr>`).join('')}</tbody></table>` : '<p class="empty-message">No results match the selected filters.</p>';
    text('tableNote',`Showing ${rows.length} of ${state.table.length} results · ${scopeText()}`);show('moreResults',state.table.length>rows.length);updateSelectedResult();
  }
  $('moreResults').onclick=()=>{state.tableLimit+=50;renderTable();};
  $('resultTable').addEventListener('click',event=>{
    const button=event.target.closest('[data-result]');if(!button)return;
    const row=state.table[Number(button.dataset.result)];
    if(row._shot){selectShot(row._shot);setMobileView('court');if(window.matchMedia('(max-width:760px)').matches)$('mobileViewSwitch').scrollIntoView({block:'start'});}
    if(row._lineup){$('analysisType').value='shots';updateTopicFilters();$('lineupFilter').value=row._lineup;updateAnalysisFilterSummary();runAnalysis();}
  });
  $('exportButton').onclick=()=>{
    if(!state.table.length)return;
    const content=[state.columns.map(columnLabel).map(S.csvValue).join(','),...state.table.map(row=>state.columns.map(key=>S.csvValue(valueOf(row[key]))).join(','))].join('\r\n');
    const url=URL.createObjectURL(new Blob(['\uFEFF'+content],{type:'text/csv;charset=utf-8'}));const link=document.createElement('a');link.href=url;link.download='courtlens-results.csv';link.click();setTimeout(()=>URL.revokeObjectURL(url),1000);
  };
  async function runSearch(event) {
    event?.preventDefault();
    const question=$('aiPlaySearchInput').value.trim();if(!question)return;
    const params=scopeParams();
    if(state.section==='video' && (!params.game_code || $('videoPanel').hidden)){message('aiPlaySearchResult','Choose an available video game and wait for it to load first.',true);return;}
    const ticket=requests.start('query');
    if(state.section==='video'){$('sparqlQuery').value='';message('queryStatus','The query will appear when this search completes.');}
    setBusy('runQuery',false,'Run query');setBusy('aiPlaySearchButton',true,'Searching…');setBusy('runAnalysis',false,'Show results');$('aiPlaySearchResult').setAttribute('aria-busy','true');
    show('evidencePanel',false);state.table=[];state.aiUris=null;state.shotUris=null;state.tableIsShots=false;state.tableLimit=50;state.pbpLimit=50;clearShotSelection();
    if(state.section==='explore'){show('courtPanel',false);show('pbpPanel',false);show('mobileViewSwitch',false);window.drawShots?.([]);}
    else {renderActions();applyShotFilters();}
    message('aiPlaySearchResult','Searching the selected basketball data…');show('exploreSuggestions',false);
    try {
      const season=params.season_code==='ALL'?Object.keys(seasons).join(','):params.season_code;
      const data=await fetchAiChat(question,params.game_code,season,$('aiModelSelect').value,ticket.signal,state.section);
      if(!ticket.current())return;
      if(state.section==='video'){$('sparqlQuery').value=data.sparql_query || '';message('queryStatus',data.sparql_query?'Query from the latest search. You can edit and run it.':'This answer has no SPARQL query.');}
      let count=null;
      if(data.playbyplay_filter && params.game_code){
        let actions=state.actions;
        if(!actions.length)actions=await fetchMatchPlayByPlay(params.game_code,params.season_code,ticket.signal);
        if(!ticket.current())return;
        state.actions=actions;state.aiUris=new Set(data.action_uris || []);
        count=actions.filter(action=>state.aiUris.has(action.uri)).length;
        if(state.section==='explore')buildActionFilters();renderActions();show('pbpPanel');
        const shotQuery=/shot/.test(data.playbyplay_action_kind || '') || /shot|three.point|two.point|3pt|2pt/i.test(question);
        if(shotQuery){
          if(state.section==='explore' || !state.shots.length){const loaded=await apiRequest('/api/shots',params,{signal:ticket.signal});if(!ticket.current())return;state.shots=loaded.shots || [];}
          state.shotUris=new Set(data.action_uris || []);state.tableIsShots=state.section==='explore';buildShotFilters();show('courtPanel');show('mobileViewSwitch');applyShotFilters();
        }else if(state.section==='video'){applyShotFilters();}
      }
      if(!ticket.current())return;
      setAnswer(friendlySummary(data,count),question,data.answer);
      if(data.answer?.kind!=='profile' && (!data.playbyplay_filter || !params.game_code)){
        state.table=(data.results || []).map(row=>Object.fromEntries(Object.entries(row).map(([key,value])=>[key,valueOf(value)])));
        state.columns=[...new Set(state.table.flatMap(Object.keys))].filter(key=>!['action','actionuri','play','playuri','event','eventuri','sequence','order'].includes(key.toLowerCase()));
        if(state.columns.length){text('evidenceTitle','Search results');renderTable();}
      }
    } catch(error){if(ticket.current())message('aiPlaySearchResult',error.message,true);}
    finally{if(ticket.current()){if(state.section==='video')setVideoView(state.videoView);setBusy('aiPlaySearchButton',false,'Search');$('aiPlaySearchResult').removeAttribute('aria-busy');}}
  }
  $('searchForm').addEventListener('submit',runSearch);
  function defaultVideoQuery() {
    const scope=scopeParams();
    return `PREFIX bball: <http://www.ics.forth.gr/isl/Basketball#>
SELECT DISTINCT ?action WHERE {
  ?game a bball:Game ; bball:hasCode "${scope.game_code}" ;
        bball:hasSeason ?season ; bball:hasPlayByPlayAction ?action .
  ?season bball:hasCode "${scope.season_code}" .
}
LIMIT 200`;
  }
  $('queryForm').addEventListener('submit',async event=>{
    event.preventDefault();
    if(state.section!=='video' || !$('gameSelect').value || $('videoPanel').hidden)return;
    const ticket=requests.start('query');setBusy('runQuery',true,'Running…');setBusy('aiPlaySearchButton',false,'Search');$('aiPlaySearchResult').removeAttribute('aria-busy');
    message('queryStatus','Running your read-only query…');
    try {
      const data=await apiRequest('/api/query',{}, {method:'POST',signal:ticket.signal,headers:{'Content-Type':'application/json'},body:JSON.stringify({query:$('sparqlQuery').value})});
      if(!ticket.current())return;
      clearShotSelection();state.aiUris=data.playbyplay_filter?new Set(data.action_uris || []):null;state.shotUris=state.aiUris;state.pbpLimit=50;
      state.table=[];state.columns=[];state.tableIsShots=false;show('evidencePanel',false);message('aiPlaySearchResult','');
      renderActions();applyShotFilters();
      if(!data.playbyplay_filter){
        state.table=(data.results || []).map(row=>Object.fromEntries(Object.entries(row).map(([key,value])=>[key,valueOf(value)])));
        state.columns=[...new Set(state.table.flatMap(Object.keys))];state.tableLimit=50;
        if(state.columns.length){text('evidenceTitle','Query results');renderTable();}
      }
      const matches=state.actions.filter(action=>state.aiUris?.has(action.uri)).length;
      message('queryStatus',data.boolean!==undefined && data.boolean!==null ? `Query answer: ${data.boolean?'Yes':'No'}.` : data.playbyplay_filter?`${matches} matching ${matches===1?'action':'actions'} in this game. Player, period and action filters still apply. Up to 200 query rows.`:`${state.table.length} rows returned. Up to 200 query rows.`);
      setVideoView('pbp');
    }catch(error){if(ticket.current())message('queryStatus',error.message,true);}
    finally{if(ticket.current())setBusy('runQuery',false,'Run query');}
  });

  function playerId(input) {const value=$(input).value.trim();return state.roster.find(p=>S.normalizeName(p.name)===S.normalizeName(value) || S.normalizeName(playerName(p.name))===S.normalizeName(value))?.id || value;}
  function updateTopicFilters() {
    const type=$('analysisType').value;
    const relevant={playerFilter:['shots','second-chance','fouls-drawn','defensive-anchors'],assistFilter:['shots'],foulingPlayer:['fouls-drawn'],blockingPlayer:['defensive-anchors'],lineupFilter:[]};
    Object.entries(relevant).forEach(([id,types])=>{const visible=types.includes(type);$(id).closest('label').hidden=!visible;if(!visible && id!=='lineupFilter')$(id).value='';});
    text('analysisDescription',{shots:'Every returned shot, with court locations and a filterable table. Up to 500 shots; choose a game for a complete view.',lineups:'The ten five-player groups with the most points scored together. Scoring totals do not measure defensive performance.','assist-duos':'The ten passer–scorer combinations with the most assisted baskets.','second-chance':'The ten players with the most points after an offensive rebound.','fouls-drawn':'The ten players who drew the most fouls.','defensive-anchors':'The ten players with the most blocked shots.'}[type]);
    $('advancedFilters').querySelectorAll('.filter-section').forEach(section=>section.hidden=![...section.querySelectorAll('label')].some(label=>!label.hidden));
    updateAnalysisFilterSummary();
  }
  function updateAnalysisFilterSummary() {
    const filters=[...$('advancedFilters').querySelectorAll('input,select')].filter(input=>input.value && !input.closest('label').hidden);
    text('analysisFilterCount',filters.length?` · ${filters.length}`:'');
    text('analysisFilterSummary',filters.map(input=>`${input.closest('label').firstChild.textContent.trim()}: ${input.selectedOptions?input.selectedOptions[0].textContent:input.value}`).join(' · '));
    show('analysisFilterSummary',filters.length>0);
  }
  $('advancedFilters').addEventListener('input',updateAnalysisFilterSummary);
  $('analysisForm').addEventListener('invalid',event=>{if(event.target.closest('#advancedFilters'))$('advancedFilters').showModal();},true);
  $('analysisType').addEventListener('change',()=>{$('lineupFilter').value='';updateTopicFilters();});
  async function runAnalysis(event) {
    event?.preventDefault();
    const type=$('analysisType').value;
    const params={...scopeParams(),player:playerId('playerFilter'),assist_by:playerId('assistFilter'),filter_type:$('presenceFilter').value,filter_id:playerId('presencePlayer'),quarter:$('analysisQuarter').value,min_start:$('clockFrom').value,min_end:$('clockTo').value};
    if(params.filter_type && !params.filter_id){message('analysisFilterError','Choose a player or referee for the context filter.',true);$('advancedFilters').showModal();return;}
    if(params.quarter==='OT' && Number(params.min_start)>5){message('analysisFilterError','Overtime periods have five minutes. Choose clock limits from 5 to 0.',true);$('advancedFilters').showModal();return;}
    if((params.min_start==='') !== (params.min_end==='') || (params.min_start!=='' && Number(params.min_start)<Number(params.min_end))){message('analysisFilterError','Enter both times, starting with the larger number of minutes remaining (for example, from 5 to 0).',true);$('advancedFilters').showModal();return;}
    message('analysisFilterError','');$('advancedFilters').close();
    const ticket=requests.start('query');
    setBusy('runAnalysis',true,'Loading…');setBusy('aiPlaySearchButton',false,'Search');$('aiPlaySearchResult').removeAttribute('aria-busy');
    $('aiPlaySearchInput').value='';message('aiPlaySearchResult','Loading the selected report…');show('exploreSuggestions',false);show('evidencePanel',false);show('pbpPanel',false);show('courtPanel',false);show('mobileViewSwitch',false);state.tableLimit=50;state.aiUris=null;state.shotUris=null;state.tableIsShots=type==='shots';clearShotSelection();
    try {
      if(type==='shots'){
        params.lineup_uri=$('lineupFilter').value.trim();const data=await apiRequest('/api/shots',params,{signal:ticket.signal});if(!ticket.current())return;
        state.shots=data.shots || [];buildShotFilters();show('courtPanel');show('mobileViewSwitch');text('evidenceTitle','Shot results');applyShotFilters();
        const made=state.shots.filter(shot=>shot.isMade).length;setAnswer(`${made} of ${state.shots.length} returned shots were made${state.shots.length?` (${(made/state.shots.length*100).toFixed(1)}%)`:''}.${state.shots.length>=500?' The data service returns up to 500 shots. Narrow the season, game, or player to see a more specific set.':''} Missing shot locations remain available in the table.`);
      }else{
        if(type==='second-chance')params.player_id=params.player;
        if(type==='fouls-drawn'){params.fouled_id=params.player;params.fouling_id=playerId('foulingPlayer');}
        if(type==='defensive-anchors'){params.shooter_id=params.player;params.blocker_id=playerId('blockingPlayer');}
        const keys={'lineups':'top_lineups','assist-duos':'assist_duos','second-chance':'second_chance_points','fouls-drawn':'fouls_drawn','defensive-anchors':'defensive_anchors'};
        const data=await apiRequest(`/api/analytics/${type}`,params,{signal:ticket.signal});if(!ticket.current())return;
        const rows=data[keys[type]] || [];
        const ids=[...new Set(rows.flatMap(row=>[row.player_id,row.passer_id,row.scorer_id,...(row.players || [])]).filter(Boolean))];
        const people=new Map(await Promise.all(ids.map(async id=>[id,await getPlayer(id,ticket.signal)])));if(!ticket.current())return;
        state.table=rows.map(row=>{
          if(type==='lineups')return {'Players':(row.players || []).map(id=>playerName(people.get(id)?.name || id)).join(' · '),'Points':row.total_points,_lineup:row.lineup_url};
          if(type==='assist-duos')return {'Passer':playerName(people.get(row.passer_id)?.name),'Scorer':playerName(people.get(row.scorer_id)?.name),'Assists':row.total_assists,_people:{Passer:people.get(row.passer_id),Scorer:people.get(row.scorer_id)}};
          const stat=type==='second-chance'?'Points':type==='fouls-drawn'?'Fouls drawn':'Blocks';
          return {'Player':playerName(people.get(row.player_id)?.name),[stat]:row.total_points ?? row.total_fouls_drawn ?? row.total_blocks,_people:{Player:people.get(row.player_id)}};
        });
        state.columns=Object.keys(state.table[0] || {}).filter(key=>!key.startsWith('_'));text('evidenceTitle',$('analysisType').selectedOptions[0].textContent);renderTable();
        setAnswer(`${rows.length} ${type==='lineups'?'five-player groups':type==='assist-duos'?'passing pairs':'players'} found. ${type==='lineups'?'Points are the team’s scoring while those five players were together.':type==='second-chance'?'Second-chance points follow an offensive rebound.':''}`);
      }
      setMobileView('results');$('aiSearchPanel').scrollIntoView({block:'start'});
    }catch(error){if(ticket.current())message('aiPlaySearchResult',error.message,true);}
    finally{if(ticket.current())setBusy('runAnalysis',false,'Show results');}
  }
  $('analysisForm').addEventListener('submit',runAnalysis);

  // Coach Challenge.
  async function startChallenge() {
    const ticket=requests.start('coach');requests.start('simulation');state.scenario=null;state.lineup=Array(5).fill(null);state.slot=0;
    show('coachWorkspace',false);show('simulatorResult',false);setBusy('startChallenge',true,'Finding a moment…');message('coachStatus','Finding a real fourth-quarter timeout…');
    let season=$('coachSeason').value;if(season==='ALL')season=Object.keys(seasons)[Math.floor(Math.random()*Object.keys(seasons).length)];
    try {
      const scenario=await apiRequest('/api/simulator/scenario',{season_code:season},{signal:ticket.signal});if(!ticket.current())return;
      const roster=await apiRequest('/api/game/lineups',{game_code:scenario.game_code,season_code:season},{signal:ticket.signal});if(!ticket.current())return;ingestRoster(roster);
      await loadTeams(ticket.signal);if(!ticket.current())return;
      const players=await Promise.all((scenario.roster || []).map(p=>getPlayer(p.id,ticket.signal)));if(!ticket.current())return;
      if(players.length<5)throw new Error('This scenario does not have five available players. Try another challenge.');
      state.scenario={...scenario,season,players};show('coachWorkspace');message('coachStatus','');
      const difference=Number(scenario.opp_score)-Number(scenario.user_score);
      $('scenarioHeader').innerHTML=`<p class="eyebrow">${esc(seasons[season])} · GAME ${esc(scenario.game_code)} · FOURTH QUARTER · HISTORICAL SCENARIO</p><h3>You coach ${esc(scenario.user_team_name || scenario.user_team)}.</h3><p>${difference>0?`Your team trails by ${difference}.`:'The scores are level.'} There is <strong>${esc(scenario.clock)}</strong> left.</p><div class="scenario-matchup">${teamMarkup(scenario.user_team_name || scenario.user_team,scenario.user_team)}<strong>${esc(scenario.user_score)} – ${esc(scenario.opp_score)}</strong>${teamMarkup(scenario.opponent_name || scenario.opponent,scenario.opponent)}</div>`;
      renderLineup();$('scenarioHeader').tabIndex=-1;$('scenarioHeader').focus();
    }catch(error){if(ticket.current())message('coachStatus',error.message,true);}
    finally{if(ticket.current())setBusy('startChallenge',false,state.scenario?'New challenge':'Try another challenge');}
  }
  $('startChallenge').onclick=startChallenge;
  $('coachSeason').onchange=()=>{requests.start('coach');requests.start('simulation');state.scenario=null;show('coachWorkspace',false);message('coachStatus','');setBusy('startChallenge',false,'Start challenge');};
  function renderLineup() {
    $('simCourt').innerHTML=positions.map((position,index)=>{
      const person=state.lineup[index];
      return `<div class="position-slot ${state.slot===index?'selected':''}" data-slot="${index}"><button class="text-button slot-label" data-select-slot="${index}" aria-pressed="${state.slot===index}">${position}</button>${person?`${imageMarkup(person)}<strong>${esc(playerName(person.name))}</strong><button class="text-button" data-remove-slot="${index}" aria-label="Remove ${esc(playerName(person.name))}">Remove</button>`:`<button class="text-button" data-select-slot="${index}" aria-label="Choose player for ${position}"><span class="choose-slot">+</span><br>Choose player</button>`}</div>`;
    }).join('');
    $('benchList').innerHTML=(state.scenario?.players || []).map(person=>`<div class="bench-row" draggable="true" data-player-id="${esc(person.id)}">${imageMarkup(person)}<span class="bench-person"><strong>${esc(playerName(person.name))}</strong><small>${esc(person.position || "Position unavailable")}</small></span><button class="secondary-button" data-add-player="${esc(person.id)}" ${state.lineup.some(p=>p?.id===person.id)?'disabled':''}>${state.lineup.some(p=>p?.id===person.id)?'Selected':'Add'}</button></div>`).join('');
    const count=state.lineup.filter(Boolean).length;text('lineupCount',`${count} of 5 selected`);$('runSimulation').disabled=count!==5;
  }
  function invalidateSimulation(){requests.start('simulation');show('simulatorResult',false);text('runSimulation','Run simulation');}
  $('simCourt').addEventListener('click',event=>{
    const choose=event.target.closest('[data-select-slot]'),remove=event.target.closest('[data-remove-slot]');
    if(choose){state.slot=Number(choose.dataset.selectSlot);renderLineup();$('benchList').querySelector('button:not(:disabled)')?.focus();}
    if(remove){invalidateSimulation();state.lineup[Number(remove.dataset.removeSlot)]=null;state.slot=Number(remove.dataset.removeSlot);renderLineup();$('simCourt').querySelector(`[data-select-slot="${state.slot}"]`)?.focus();}
  });
  function addPlayer(id,slot=state.slot){const player=state.scenario?.players.find(p=>p.id===id);if(!player || state.lineup.some(p=>p?.id===id))return;invalidateSimulation();state.lineup[slot]=player;const next=state.lineup.findIndex(p=>!p);state.slot=next<0?slot:next;renderLineup();(next<0?$('runSimulation'):$('benchList').querySelector('button:not(:disabled)'))?.focus({preventScroll:true});}
  $('benchList').addEventListener('click',event=>{const button=event.target.closest('[data-add-player]');if(button)addPlayer(button.dataset.addPlayer);});
  $('benchList').addEventListener('dragstart',event=>{const row=event.target.closest('[data-player-id]');if(row)event.dataTransfer.setData('text/plain',row.dataset.playerId);});
  $('simCourt').addEventListener('dragover',event=>event.preventDefault());
  $('simCourt').addEventListener('drop',event=>{event.preventDefault();const slot=event.target.closest('[data-slot]');if(slot)addPlayer(event.dataTransfer.getData('text/plain'),Number(slot.dataset.slot));});
  $('clearLineup').onclick=()=>{invalidateSimulation();state.lineup=Array(5).fill(null);state.slot=0;renderLineup();};
  $('runSimulation').onclick=async()=>{
    if(!state.scenario || state.lineup.some(p=>!p))return;
    const ticket=requests.start('simulation'),scenario=state.scenario,params={game_code:scenario.game_code,season_code:scenario.season};state.lineup.forEach((p,index)=>params[`p${index+1}`]=p.id);
    setBusy('runSimulation',true,'Simulating…');show('simulatorResult',false);
    try{
      const data=await apiRequest('/api/simulator/crunch-time',params,{signal:ticket.signal,allowError:true});if(!ticket.current())return;
      if(data.error && data.error!=='Lineup never played')throw new Error(data.error);
      const seconds=S.clockSeconds(scenario.clock),possessions=Math.max(1,Math.ceil(seconds/24));
      const chemistry=Number(data.points_for)>0;
      let scored=Math.max(0,Math.round(possessions+Math.floor(Math.random()*7)-3+(chemistry?3:0)));
      const conceded=Math.max(0,Math.round(possessions+Math.floor(Math.random()*5)-2));
      if(seconds<=15 && scored===0)scored=Math.random()>.5?2:0;
      const user=Number(scenario.user_score)+scored,opponent=Number(scenario.opp_score)+conceded;
      $('simulatorResult').innerHTML=`<p class="eyebrow">SIMULATED RESULT</p><h3>${user>opponent?'Your team takes the win.':user<opponent?'A close finish. Try another five.':'All level. This one goes to overtime.'}</h3><p class="score">${user} – ${opponent}</p><p>Your team scored ${scored} and conceded ${conceded} over approximately ${possessions} remaining ${possessions===1?'possession':'possessions'}.</p><p class="muted">${chemistry?'These five players scored together in the historical game, adding a chemistry bonus.':'No scoring history was found for this exact five-player group in this game.'} The simulation includes random variation; it is not a forecast of a real result.</p>`;show('simulatorResult');
    }catch(error){if(ticket.current())message('simulatorResult',error.message,true);}
    finally{if(ticket.current())setBusy('runSimulation',false,'Run again');}
  };

  // Quiz Ball.
  function quizMenu() { requests.start('quiz');state.quiz=null;show('quizSetup');show('quizGame',false);$('quizGame').replaceChildren();$('quizSetup').querySelector('input')?.focus(); }
  $('quizSetupForm').addEventListener('submit',event=>{event.preventDefault();const form=new FormData(event.currentTarget);startQuiz(form.get('category'),form.get('difficulty'));});
  async function startQuiz(category,difficulty,streak=0) {
    const ticket=requests.start('quiz');state.quiz=null;show('quizSetup',false);show('quizGame');
    $('quizGame').innerHTML='<div class="quiz-question"><button class="text-button" data-quiz-menu> Quiz menu</button><p role="status">Preparing your question…</p></div>';
    try {
      const data=await apiRequest(`/api/quiz/${category}`,{difficulty},{signal:ticket.signal});if(!ticket.current())return;
      if(category==='who-am-i' && (!Array.isArray(data.hints) || !data.secret_player_name))throw new Error('This question is incomplete. Please try again.');
      if(category==='who-is-missing' && (!Array.isArray(data.known_players) || !data.secret_player_name))throw new Error('This lineup is incomplete. Please try again.');
      if(category==='higher-or-lower' && (!data.player_a || !data.player_b))throw new Error('The player comparison is unavailable. Please try again.');
      if(category==='top-5' && (!Array.isArray(data.answers) || data.answers.length!==5))throw new Error('Five answers could not be found. Please try again.');
      if(category==='fifty-fifty' && (!Array.isArray(data.options) || data.options.length!==2 || ![0,1].includes(data.correct_index)))throw new Error('The answer choices are unavailable. Please try again.');
      state.quiz={category,difficulty,streak,data,misses:0,hint:0,revealed:new Set(),active:true};renderQuiz();
    }catch(error){if(ticket.current())$('quizGame').innerHTML=`<div class="quiz-question"><button class="text-button" data-quiz-menu> Quiz menu</button><p role="alert">${esc(error.message)}</p><button class="secondary-button" data-retry-category="${esc(category)}" data-retry-difficulty="${esc(difficulty)}">Try again</button></div>`;}
  }
  function renderQuiz() {
    const q=state.quiz;if(!q)return;const data=q.data;
    let content='';
    if(q.category==='who-am-i')content=`<p>Identify the player from the clues. You have ${data.hints.length} attempts.</p><div id="quizHints" class="quiz-hints"><p><strong>Clue 1.</strong> ${esc(data.hints[0])}</p></div>`;
    if(q.category==='who-is-missing')content=`<p>These four players shared the court. Who was the fifth?</p>${missingCourt(data)}<p class="muted">Two attempts. A clue follows your first miss.</p><div id="quizHints" class="quiz-hints"></div>`;
    if(q.category==='higher-or-lower')content=`<p>${esc(data.question_text)}</p><p><strong>${esc(playerName(data.player_a.name))}: ${esc(data.player_a.stat)}</strong> ${esc(data.category_name || '')}</p><p>Did ${esc(playerName(data.player_b.name))} record more or fewer?</p><div class="quiz-options"><button data-choice="higher">Higher</button><button data-choice="lower">Lower</button></div>`;
    if(q.category==='fifty-fifty')content=`<p>${esc(data.question_text)}</p><div class="quiz-options">${data.options.map((value,index)=>`<button data-choice="${index}">${esc(value)}</button>`).join('')}</div>`;
    if(q.category==='top-5')content=`<p>${esc(data.question_text)}</p><p class="muted">Three misses available. Enter a player’s name, or the names in a passing pair.</p><ol id="topFive" class="top-five">${data.answers.map((_,index)=>`<li data-answer-index="${index}">Not found yet</li>`).join('')}</ol>`;
    const typed=['who-am-i','who-is-missing','top-5'].includes(q.category);
    $('quizGame').innerHTML=`<article class="quiz-question"><div class="quiz-meta"><button class="text-button" data-quiz-menu> Quiz menu</button><span>${esc(q.difficulty)} · Streak: ${q.streak}</span></div><h2 tabindex="-1">${quizNames[q.category]}</h2>${content}<p class="muted">${esc([data.game_code && `Game ${data.game_code}`,data.matchup,data.season].filter(Boolean).join(' · '))}</p>${typed?'<form id="quizAnswerForm" class="quiz-answer-form"><label>Your answer<input id="quizAnswerInput" type="text" required minlength="2" maxlength="150" list="quizNameOptions" autocomplete="off" placeholder="Enter a name…"><datalist id="quizNameOptions"></datalist></label><button class="primary-button">Check answer</button></form>':''}<div id="quizFeedback" class="quiz-feedback" role="status" hidden></div></article>`;
    if(typed){
      $('quizAnswerForm').addEventListener('submit',submitQuizGuess);
      $('quizAnswerInput').addEventListener('input',()=>{const raw=$('quizAnswerInput').value;const m=raw.match(/^(.*?\s*(?:&|\band\b|\+)\s*)(.*)$/i);const prefix=m?m[1]:'';const term=S.normalizeName(m?m[2]:raw);$('quizNameOptions').innerHTML=term.length<2?'':(window.QUIZ_PLAYER_NAMES || []).filter(name=>S.normalizeName(name).includes(term)).slice(0,8).map(name=>`<option value="${esc(prefix+name)}"></option>`).join('');});
      $('quizAnswerInput').focus();
    }else $('quizGame').querySelector('h2').focus();
  }
  function missingCourt(data,revealed=false) {
    const lineup=data.lineup || [...data.known_players.map(name=>({player:{name},position:''})),{missing:true,position:''}];
    return `<figure class="missing-lineup"><div class="quiz-court" aria-label="Five-player lineup on an illustrative half court"><svg class="quiz-court-lines" viewBox="0 0 600 440" preserveAspectRatio="none" aria-hidden="true"><path d="M10 10H590V430H10Z M215 10V150H385V10 M215 150A85 85 0 0 0 385 150 M35 10V90C35 445 565 445 565 90V10 M277 27H323"/><circle cx="300" cy="42" r="12"/></svg>${lineup.map(slot=>{
      const person=slot.missing?(revealed?data.secret_player:null):slot.player;
      return `<div class="quiz-court-player${slot.missing?' missing-player':''}"${slot.missing?' id="missingPlayerSlot"':''}>${person?imageMarkup(person):'<span class="avatar missing-avatar" aria-hidden="true">?</span>'}<strong>${esc(person?playerName(person.name):'Who is missing?')}</strong><small>${esc(slot.position || 'Position unavailable')}</small></div>`;
    }).join('')}</div><figcaption>Listed player positions. Court placement is illustrative; these five shared the court in this game.</figcaption></figure>`;
  }
  function revealQuizPlayer() {
    const q=state.quiz,profile=q?.data.secret_player;
    if(!profile)return;
    if(q.category==='who-is-missing') {
      const figure=$('quizGame').querySelector('.missing-lineup');
      if(figure)figure.outerHTML=missingCourt(q.data,true);
    }
    const paragraphs=Array.isArray(profile.paragraphs)?profile.paragraphs:[];
    const source=profile.source_url && /^https:\/\/www\.euroleaguebasketball\.net\//.test(profile.source_url)?profile.source_url:'';
    $('quizFeedback').insertAdjacentHTML('beforeend',`<section class="quiz-player-profile" aria-label="Answer player profile"><div class="quiz-profile-heading">${imageMarkup(profile)}<div><h3>${esc(playerName(profile.name))}</h3><p>${esc([profile.position,profile.country].filter(Boolean).join(' · '))}</p></div></div>${paragraphs.map(paragraph=>`<p>${esc(paragraph)}</p>`).join('')}<p class="profile-source">From stored EuroLeague profiles; career information may have changed.${source?` <a href="${esc(source)}" target="_blank" rel="noopener noreferrer">Player profile</a>`:''}</p></section>`);
  }
  function quizFeedback(content,wrong=false,finished=false) {
    const q=state.quiz;const meta=$('quizGame').querySelector('.quiz-meta>span');if(meta)meta.textContent=`${q.difficulty} · Streak: ${q.streak}`;const feedback=$('quizFeedback');feedback.hidden=false;feedback.className=`quiz-feedback${wrong?' wrong':''}`;feedback.innerHTML=`<p>${esc(content)}</p>`;
    if(finished){q.active=false;revealQuizPlayer();document.querySelectorAll('#quizAnswerForm input,#quizAnswerForm button,.quiz-options button').forEach(el=>el.disabled=true);feedback.insertAdjacentHTML('beforeend',`<button class="primary-button" data-next-quiz data-keep-streak="${wrong?'false':'true'}">${wrong?'Play again':'Next question'}</button>`);}
  }
  function submitQuizGuess(event) {
    event.preventDefault();const q=state.quiz;if(!q?.active)return;const input=$('quizAnswerInput'),guess=input.value.trim();if(!guess)return;
    if(q.category==='top-5'){
      if(!q.partial) q.partial = new Map();
      let newlyRevealed = 0;
      let newlyPartial = 0;
      let alreadyFound = false;

      q.data.answers.forEach((answer, index) => {
        const parts = String(answer.name || '').split(/\s*(?:&|\band\b|\+)\s*/i);
        if (parts.length > 1) {
          if (S.matchesName(guess, answer.name, window.QUIZ_PLAYER_NAMES || [])) {
            if (!q.revealed.has(index)) { q.revealed.add(index); newlyRevealed++; } else { alreadyFound = true; }
          } else {
            const matchedPartIndex = parts.findIndex(p => S.matchesName(guess, p, window.QUIZ_PLAYER_NAMES || []));
            if (matchedPartIndex >= 0 && !q.revealed.has(index)) {
              if (!q.partial.has(index)) q.partial.set(index, new Set());
              const partialSet = q.partial.get(index);
              if (!partialSet.has(matchedPartIndex)) {
                partialSet.add(matchedPartIndex);
                if (partialSet.size === parts.length) { q.revealed.add(index); newlyRevealed++; } else { newlyPartial++; }
              } else { alreadyFound = true; }
            }
          }
        } else {
          if (S.matchesName(guess, answer.name, window.QUIZ_PLAYER_NAMES || [])) {
            if (!q.revealed.has(index)) { q.revealed.add(index); newlyRevealed++; } else { alreadyFound = true; }
          }
        }
      });

      if (newlyRevealed > 0 || newlyPartial > 0) {
        q.data.answers.forEach((answer, index) => {
          const item = $('topFive').querySelector(`[data-answer-index="${index}"]`);
          if (!item) return;
          if (q.revealed.has(index)) {
            item.innerHTML = `<strong>${esc(answer.name)}</strong><small>${esc(answer.stat)}</small>`;
          } else if (q.partial.has(index)) {
            const parts = String(answer.name || '').split(/\s*(?:&|\band\b|\+)\s*/i);
            const pSet = q.partial.get(index);
            item.innerHTML = `<strong>${esc(parts.map((p, i) => pSet.has(i) ? p : '????').join(' & '))}</strong><small>&nbsp;</small>`;
          }
        });
        if (q.revealed.size === 5) { q.streak++; quizFeedback('All five found. Nicely played.', false, true); }
        else { quizFeedback(newlyPartial > 0 ? 'Partial match! Find the other player.' : `Correct. ${q.revealed.size} of 5 found.`); }
      } else if (alreadyFound) {
        quizFeedback('You already found that answer. Try another name.');
      } else {
        q.misses++;
        if (q.misses >= 3) {
          $('topFive').innerHTML = q.data.answers.map(answer => `<li><strong>${esc(answer.name)}</strong><small>${esc(answer.stat)}</small></li>`).join('');
          quizFeedback('Three misses. The answers are revealed above.', true, true);
        } else {
          quizFeedback(`Not on this list. ${3 - q.misses} ${3 - q.misses === 1 ? 'miss' : 'misses'} remaining.`, true);
        }
      }
    }else if(S.matchesName(guess,q.data.secret_player_name,window.QUIZ_PLAYER_NAMES || [])){q.streak++;quizFeedback(`Correct! It was ${playerName(q.data.secret_player_name)}.`,false,true);}
    else {
      q.misses++;const attempts=q.category==='who-am-i'?q.data.hints.length:2;
      if(q.misses>=attempts)quizFeedback(`The player was ${playerName(q.data.secret_player_name)}. Try another question.`,true,true);
      else {const hint=q.category==='who-am-i'?q.data.hints[q.misses]:q.data.hint;$('quizHints').insertAdjacentHTML('beforeend',`<p><strong>${q.category==='who-am-i'?`Clue ${q.misses+1}`:'Hint'}.</strong> ${esc(hint || 'Think about the other players in this lineup.')}</p>`);quizFeedback(`Not quite. ${attempts-q.misses} ${attempts-q.misses===1?'attempt':'attempts'} remaining.`,true);}
    }
    input.value='';if(q.active)input.focus();
  }
  $('quizGame').addEventListener('click',event=>{
    if(event.target.closest('[data-quiz-menu]')){quizMenu();return;}
    const retry=event.target.closest('[data-retry-category]');if(retry){startQuiz(retry.dataset.retryCategory,retry.dataset.retryDifficulty);return;}
    const q=state.quiz;if(!q)return;
    const next=event.target.closest('[data-next-quiz]');if(next){startQuiz(q.category,q.difficulty,next.dataset.keepStreak==='true'?q.streak:0);return;}
    const choice=event.target.closest('[data-choice]');if(!choice || !q.active)return;
    let correct,answer;
    if(q.category==='fifty-fifty'){correct=Number(choice.dataset.choice)===q.data.correct_index;answer=`The answer is ${q.data.options[q.data.correct_index]}.`;}
    else {const higher=Number(q.data.player_b.stat)>Number(q.data.player_a.stat);correct=(choice.dataset.choice==='higher')===higher;answer=`${playerName(q.data.player_b.name)} recorded ${q.data.player_b.stat}; ${playerName(q.data.player_a.name)} recorded ${q.data.player_a.stat}.`;}
    if(correct)q.streak++;quizFeedback(`${correct?'Correct!':'Not this time.'} ${answer} Streak: ${q.streak}.`,!correct,true);
  });
  show('localFileNotice',location.protocol==='file:');
  readRoute();
})();
