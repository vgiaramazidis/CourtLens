// api.js teo

const API_BASE_URL = window.EUROLEAGUE_API_BASE_URL
    || `${window.location.protocol}//${window.location.hostname || "localhost"}:8000`;

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

async function fetchFilteredShots(playerId = null, assistPlayerId = null, gameCode = null, seasonCode = null, filterType = null, filterId = null, quarter = null, minStart = null, minEnd = null, lineupUri = null, signal = null) {
    try {
        const params = new URLSearchParams();
        appendCommonParams(params, seasonCode, gameCode, quarter, minStart, minEnd, filterType, filterId);
        
        if (playerId) params.append("player", playerId);
        if (assistPlayerId) params.append("assist_by", assistPlayerId);
        if (lineupUri) params.append("lineup_uri", lineupUri); 
        
        const url = `${API_BASE_URL}/api/shots?${params.toString()}`;
        console.log("Fetching shots from:", url);
        const response = await fetch(url, { signal });
        if (!response.ok) throw new Error(`HTTP error! status: ${response.status}`);
        
        const data = await response.json();
        return data.shots; 
    } catch (error) {
        if (error.name !== "AbortError") console.error("Σφάλμα στα σουτ:", error);
        throw error;
    }
}

async function fetchMatchPlayByPlay(gameCode, seasonCode, signal = null) {
    try {
        const params = new URLSearchParams({
            game_code: gameCode,
            season_code: seasonCode
        });
        const response = await fetch(`${API_BASE_URL}/api/match/playbyplay?${params.toString()}`, { signal });
        if (!response.ok) throw new Error(`HTTP error! status: ${response.status}`);
        const data = await response.json();
        return data.actions || [];
    } catch (error) {
        if (error.name !== "AbortError") console.error("Σφάλμα στο play-by-play:", error);
        throw error;
    }
}

async function fetchVideoConfig(gameCode, seasonCode, signal = null) {
    try {
        const params = new URLSearchParams({
            game_code: gameCode,
            season_code: seasonCode
        });
        const response = await fetch(`${API_BASE_URL}/api/video/config?${params.toString()}`, { signal });
        if (!response.ok) throw new Error(`HTTP error! status: ${response.status}`);
        return await response.json();
    } catch (error) {
        if (error.name !== "AbortError") console.error("Σφάλμα στη ρύθμιση του βίντεο:", error);
        throw error;
    }
}

async function fetchAvailableVideoGames(seasonCode = null) {
    try {
        const params = new URLSearchParams();
        if (seasonCode) params.set("season_code", seasonCode);
        const suffix = params.toString() ? `?${params.toString()}` : "";
        const response = await fetch(`${API_BASE_URL}/api/video/games${suffix}`);
        if (!response.ok) throw new Error(`HTTP error! status: ${response.status}`);
        return await response.json();
    } catch (error) {
        console.error("Σφάλμα στη λίστα video games:", error);
        return { seasons: [], games: [] };
    }
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

/**
 * SIMULATOR: Υπολογίζει το +/- μιας 5άδας (σε ολόκληρο τον αγώνα)
 */
async function fetchSimulatorResult(p1, p2, p3, p4, p5, gameCode) {
    try {
        const params = new URLSearchParams();
        params.append("p1", p1);
        params.append("p2", p2);
        params.append("p3", p3);
        params.append("p4", p4);
        params.append("p5", p5);
        if (gameCode) params.append("game_code", gameCode);
        
        // Αφαιρέσαμε το quarter για να ελέγχει όλο το ματς!

        const url = `${API_BASE_URL}/api/simulator/crunch-time?${params.toString()}`;
        const response = await fetch(url);
        
        if (!response.ok) throw new Error(`HTTP error! status: ${response.status}`);
        return await response.json();
    } catch (error) {
        console.error("Σφάλμα στο Simulator:", error);
        return null;
    }
}
/**
 * SIMULATOR: Ζητάει όλους τους αγώνες μιας σεζόν για να διαλέξουμε έναν τυχαία.
 */
/**
 * SIMULATOR: Ζητάει ένα πλήρες τυχαίο σενάριο 4ου δεκαλέπτου
 */
async function fetchSimulatorScenario(seasonCode) {
    try {
        const url = `${API_BASE_URL}/api/simulator/scenario?season_code=${seasonCode}`;
        const response = await fetch(url);
        if (!response.ok) throw new Error(`HTTP error! status: ${response.status}`);
        return await response.json();
    } catch (error) {
        console.error("Σφάλμα κατά τη δημιουργία σεναρίου:", error);
        return null;
    }
}
/**
 * SIMULATOR: Φέρνει το πραγματικό ρόστερ (τους παίκτες που έπαιξαν) του αγώνα
 */
async function fetchGameRoster(gameCode) {
    try {
        const url = `${API_BASE_URL}/api/game/roster?game_code=${gameCode}`;
        const response = await fetch(url);
        if (!response.ok) throw new Error(`HTTP error! status: ${response.status}`);
        const data = await response.json();
        return data.roster || [];
    } catch (error) {
        console.error("Σφάλμα κατά την ανάκτηση του ρόστερ:", error);
        return [];
    }
}

async function fetchAiChat(userMessage, gameCode, seasonCode) {
    try {
        const response = await fetch(`${API_BASE_URL}/api/chat`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                message: userMessage,
                game_code: gameCode,
                season_code: seasonCode
            })
        });

        if (!response.ok) {
            const errorPayload = await response.json().catch(() => ({}));
            throw new Error(errorPayload.detail || `HTTP error! status: ${response.status}`);
        }
        return await response.json();
    } catch (error) {
        console.error("Error with AI Chat:", error);
        return { error: error.message || "AI Search request failed." };
    }
}
