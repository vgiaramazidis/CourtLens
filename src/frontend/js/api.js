// api.js

const API_BASE_URL = "http://localhost:8000"; 

function appendCommonParams(params, seasonCode, gameCode, quarter, minStart, minEnd, filterType, filterId) {
    if (seasonCode && seasonCode !== "ALL") params.append("season_code", seasonCode);
    if (gameCode) params.append("game_code", gameCode);
    if (quarter) params.append("quarter", quarter);
    if (minStart) params.append("min_start", minStart);
    if (minEnd) params.append("min_end", minEnd);
    if (filterType && filterId) {
        params.append("filter_type", filterType);
        params.append("filter_id", filterId);
    }
}

async function fetchFilteredShots(playerId = null, assistPlayerId = null, gameCode = null, seasonCode = null, filterType = null, filterId = null, quarter = null, minStart = null, minEnd = null, lineupUri = null) {
    try {
        const params = new URLSearchParams();
        appendCommonParams(params, seasonCode, gameCode, quarter, minStart, minEnd, filterType, filterId);
        
        if (playerId) params.append("player", playerId);
        if (assistPlayerId) params.append("assist_by", assistPlayerId);
        if (lineupUri) params.append("lineup_uri", lineupUri); 
        
        const url = `${API_BASE_URL}/api/shots?${params.toString()}`;
        console.log("Fetching shots from:", url);
        const response = await fetch(url);
        if (!response.ok) throw new Error(`HTTP error! status: ${response.status}`);
        
        const data = await response.json();
        return data.shots; 
    } catch (error) { console.error("Σφάλμα στα σουτ:", error); return []; }
}

async function fetchFilteredPlayer(playerId){
    try {
        const url = `${API_BASE_URL}/api/player?player=${playerId}`;
        const response = await fetch(url);
        if (!response.ok) throw new Error(`HTTP error! status: ${response.status}`);
        const data = await response.json();
        return data.player; 
    } catch (error) { return null; }
}

async function fetchTopAssistDuos(filterType = null, filterId = null, quarter = null, minStart = null, minEnd = null, gameCode = null, seasonCode = null) {    
    try {
        const params = new URLSearchParams();
        appendCommonParams(params, seasonCode, gameCode, quarter, minStart, minEnd, filterType, filterId);
        
        const url = `${API_BASE_URL}/api/analytics/assist-duos?${params.toString()}`;
        const response = await fetch(url);
        if (!response.ok) throw new Error(`HTTP error! status: ${response.status}`);
        const data = await response.json();
        return data.assist_duos;
    } catch (error) { return []; }
}

async function fetchTopLineups(filterType = null, filterId = null, quarter = null, minStart = null, minEnd = null, gameCode = null, seasonCode = null) {
    try {
        const params = new URLSearchParams();
        appendCommonParams(params, seasonCode, gameCode, quarter, minStart, minEnd, filterType, filterId);
        
        const url = `${API_BASE_URL}/api/analytics/lineups?${params.toString()}`;
        const response = await fetch(url);
        if (!response.ok) throw new Error(`HTTP error! status: ${response.status}`);
        const data = await response.json();
        return data.top_lineups;
    } catch (error) { return []; }
}

async function fetchSecondChancePoints(filterType = null, filterId = null, quarter = null, minStart = null, minEnd = null, gameCode = null, seasonCode = null, playerId = null) {
    try {
        const params = new URLSearchParams();
        appendCommonParams(params, seasonCode, gameCode, quarter, minStart, minEnd, filterType, filterId);
        
        // Προσθήκη του παίκτη (αν υπάρχει)
        if (playerId) params.append("player_id", playerId);
        
        const url = `${API_BASE_URL}/api/analytics/second-chance?${params.toString()}`;
        const response = await fetch(url);
        if (!response.ok) throw new Error(`HTTP error! status: ${response.status}`);
        const data = await response.json();
        return data.second_chance_points;
    } catch (error) { return []; }
}

async function fetchFoulsDrawn(filterType = null, filterId = null, quarter = null, minStart = null, minEnd = null, fouledId = null, foulingId = null, gameCode = null, seasonCode = null) {
    try {
        const params = new URLSearchParams();
        appendCommonParams(params, seasonCode, gameCode, quarter, minStart, minEnd, filterType, filterId);
        
        if (fouledId) params.append("fouled_id", fouledId);
        if (foulingId) params.append("fouling_id", foulingId);
        
        const url = `${API_BASE_URL}/api/analytics/fouls-drawn?${params.toString()}`;
        const response = await fetch(url);
        if (!response.ok) throw new Error(`HTTP error! status: ${response.status}`);
        const data = await response.json();
        return data.fouls_drawn;
    } catch (error) { return []; }
}

async function fetchDefensiveAnchors(filterType = null, filterId = null, quarter = null, minStart = null, minEnd = null, shooterId = null, blockerId = null, gameCode = null, seasonCode = null) {
    try {
        const params = new URLSearchParams();
        appendCommonParams(params, seasonCode, gameCode, quarter, minStart, minEnd, filterType, filterId);
        
        if (shooterId) params.append("shooter_id", shooterId);
        if (blockerId) params.append("blocker_id", blockerId); 
        
        const url = `${API_BASE_URL}/api/analytics/defensive-anchors?${params.toString()}`;
        const response = await fetch(url);
        if (!response.ok) throw new Error(`HTTP error! status: ${response.status}`);
        const data = await response.json();
        return data.defensive_anchors;
    } catch (error) { return []; }
}