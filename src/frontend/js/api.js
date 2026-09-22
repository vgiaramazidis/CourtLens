/* HTTP requests and user-facing errors for the CourtLens API. */
const API_BASE_URL = window.EUROLEAGUE_API_BASE_URL
  || `${window.location.protocol==='https:'?'https:':'http:'}//${window.location.hostname || 'localhost'}:8000`;

async function apiRequest(path, params = {}, options = {}) {
  if(window.location.protocol==='file:' && !window.EUROLEAGUE_API_BASE_URL)throw new Error('Open the app through its web server at http://localhost:3000 to load basketball data.');
  const query = new URLSearchParams();
  Object.entries(params).forEach(([key,value]) => {
    if (value !== undefined && value !== null && value !== '' && value !== 'ALL') query.set(key,String(value));
  });
  const { allowError = false, ...fetchOptions } = options;
  let response;
  try { response = await fetch(`${API_BASE_URL}${path}${query.size ? `?${query}` : ''}`, fetchOptions); }
  catch (error) {
    if (error.name === 'AbortError') throw error;
    throw new Error('We could not reach the basketball data service. Please try again.');
  }
  const data = await response.json().catch(() => ({}));
  if (!response.ok || (data.error && !allowError)) {
    const detail = typeof data.detail === 'string' ? data.detail : data.detail?.message;
    const message = detail || data.error || `The request could not be completed (${response.status}).`;
    if(/configure|not configured|AI generation is currently unavailable/i.test(message))throw new Error('AI generation is unavailable on this server. Please choose another activity.');
    if(response.status===429 || /429|RESOURCE_EXHAUSTED|rate.limit/i.test(message))throw new Error('The service has reached its request limit. Please try again later.');
    if(response.status===503 || /503|high demand|temporarily unavailable/i.test(message))throw new Error(/AI provider|quiz provider/.test(message)?message:'The service is temporarily busy. Please try again in a moment.');
    throw new Error(/[\u0370-\u03ff\u1f00-\u1fff]/.test(message) ? 'The data service could not complete this request. Please try again.' : message);
  }
  return data;
}

function fetchAiChat(message, game_code, season_code, provider, signal, workspace = 'explore') {
  return apiRequest('/api/chat', {}, {method:'POST',signal,headers:{'Content-Type':'application/json'},body:JSON.stringify({message,game_code:game_code || null,season_code,provider:provider || null,include_answer:true,show_query:workspace==='video',workspace})});
}
function fetchAvailableVideoGames(season_code, signal) { return apiRequest('/api/video/games',{season_code},{signal}); }
function fetchMatchPlayByPlay(game_code, season_code, signal) { return apiRequest('/api/match/playbyplay',{game_code,season_code},{signal}).then(data=>data.actions || []); }
function fetchVideoConfig(game_code, season_code, signal) { return apiRequest('/api/video/config',{game_code,season_code},{signal}); }
