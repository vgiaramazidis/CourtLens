// api.js

const API_BASE_URL = "http://localhost:8000"; // Η διεύθυνση του Python server σου

/**
 * Ζητάει τα σουτ από το backend βάσει φίλτρων.
 */
async function fetchFilteredShots(playerId = null, assistPlayerId = null, gameCode = null, seasonCode = "E2023", filterType = null, filterId = null, quarter = null, minStart = null, minEnd = null, lineupUri = null) {
    try {
        const params = new URLSearchParams();
        if (playerId) params.append("player", playerId);
        if (assistPlayerId) params.append("assist_by", assistPlayerId);
        if (gameCode) params.append("game_code", gameCode);
        if (seasonCode) params.append("season_code", seasonCode);
        if (quarter) params.append("quarter", quarter);
        if (minStart) params.append("min_start", minStart);
        if (minEnd) params.append("min_end", minEnd);
        if (lineupUri) params.append("lineup_uri", lineupUri); // <-- ΠΡΟΣΘΗΚΗ!
        
        if (filterType && filterId) {
            params.append("filter_type", filterType);
            params.append("filter_id", filterId);
        }

        const url = `${API_BASE_URL}/api/shots?${params.toString()}`;
        console.log("Fetching from:", url);
        const response = await fetch(url);
        
        if (!response.ok) throw new Error(`HTTP error! status: ${response.status}`);

        const data = await response.json();
        return data.shots; 

    } catch (error) {
        console.error("Σφάλμα κατά την ανάκτηση των δεδομένων:", error);
        return [];
    }
}

/**
 * Ζητάει τα στοιχεία ενός παίκτη (Κάρτα Παίκτη).
 */
async function fetchFilteredPlayer(playerId){
    try {
        const params = new URLSearchParams();
        if (playerId) params.append("player", playerId);
        
        const url = `${API_BASE_URL}/api/player?${params.toString()}`;
        const response = await fetch(url);
        
        if (!response.ok) throw new Error(`HTTP error! status: ${response.status}`);

        const data = await response.json();
        return data.player; // Διορθώθηκε από data.shots σε data.player

    } catch (error) {
        console.error("Σφάλμα κατά την ανάκτηση δεδομένων παίκτη:", error);
        return null;
    }
}

/**
 * Ζητάει τα κορυφαία δίδυμα (Assist Duos).
 */
async function fetchTopAssistDuos(filterType = null, filterId = null, quarter = null, minStart = null, minEnd = null, gameCode = null, seasonCode = null) {    
    try {
        const params = new URLSearchParams();
        if (quarter) params.append("quarter", quarter);
        if (minStart) params.append("min_start", minStart);
        if (minEnd) params.append("min_end", minEnd);
        if (gameCode) params.append("game_code", gameCode);
        if (seasonCode) params.append("season_code", seasonCode);
        if (filterType && filterId) {
            params.append("filter_type", filterType);
            params.append("filter_id", filterId);
        }

        const url = `${API_BASE_URL}/api/analytics/assist-duos?${params.toString()}`;
        const response = await fetch(url);
        
        if (!response.ok) throw new Error(`HTTP error! status: ${response.status}`);
        
        const data = await response.json();
        return data.assist_duos;
    } catch (error) {
        console.error("Σφάλμα κατά την ανάκτηση των Top Assist Duos:", error);
        return [];
    }
}

/**
 * Ζητάει τις Καλύτερες Πεντάδες (Top Lineups).
 */
async function fetchTopLineups(filterType = null, filterId = null, quarter = null, minStart = null, minEnd = null, gameCode = null, seasonCode = null) {
    try {
        const params = new URLSearchParams();
        if (filterType && filterId) {
            params.append("filter_type", filterType);
            params.append("filter_id", filterId);
        }
        if (quarter) params.append("quarter", quarter);
        if (minStart) params.append("min_start", minStart);
        if (minEnd) params.append("min_end", minEnd);
        if (gameCode) params.append("game_code", gameCode);
        if (seasonCode) params.append("season_code", seasonCode); // ΠΡΟΣΘΗΚΗ
        
        const url = `${API_BASE_URL}/api/analytics/lineups?${params.toString()}`;
        const response = await fetch(url);
        
        if (!response.ok) throw new Error(`HTTP error! status: ${response.status}`);
        
        const data = await response.json();
        return data.top_lineups;
    } catch (error) {
        console.error("Σφάλμα κατά την ανάκτηση των Top Lineups:", error);
        return [];
    }
}

/**
 * Ζητάει τους Second Chance Points.
 */
async function fetchSecondChancePoints(filterType = null, filterId = null, quarter = null, minStart = null, minEnd = null, gameCode = null,seasonCode=null) {
    try {
        const params = new URLSearchParams();
        if (filterType && filterId) {
            params.append("filter_type", filterType);
            params.append("filter_id", filterId);
        }
        if (quarter) params.append("quarter", quarter);
        if (minStart) params.append("min_start", minStart);
        if (minEnd) params.append("min_end", minEnd);
        if (gameCode) params.append("game_code", gameCode);
        if (seasonCode) params.append("season_code", seasonCode);
        const url = `${API_BASE_URL}/api/analytics/second-chance?${params.toString()}`;
        const response = await fetch(url);
        
        if (!response.ok) throw new Error(`HTTP error! status: ${response.status}`);
        
        const data = await response.json();
        return data.second_chance_points;
    } catch (error) {
        console.error("Σφάλμα κατά την ανάκτηση των Second Chance Points:", error);
        return [];
    }
}

/**
 * Ζητάει τα Κερδισμένα Φάουλ (Fouls Drawn).
 */
async function fetchFoulsDrawn(filterType = null, filterId = null, quarter = null, minStart = null, minEnd = null, fouledId = null, foulingId = null, gameCode = null,seasonCode=null) {
    try {
        const params = new URLSearchParams();
        if (filterType && filterId) {
            params.append("filter_type", filterType);
            params.append("filter_id", filterId);
        }
        if (quarter) params.append("quarter", quarter);
        if (minStart) params.append("min_start", minStart);
        if (minEnd) params.append("min_end", minEnd);
        if (fouledId) params.append("fouled_id", fouledId);
        if (foulingId) params.append("fouling_id", foulingId);
        if (gameCode) params.append("game_code", gameCode);
        if (seasonCode) params.append("season_code", seasonCode);
        const url = `${API_BASE_URL}/api/analytics/fouls-drawn?${params.toString()}`;
        const response = await fetch(url);
        
        if (!response.ok) throw new Error(`HTTP error! status: ${response.status}`);
        const data = await response.json();
        return data.fouls_drawn;
    } catch (error) {
        console.error("Σφάλμα Fouls Drawn:", error);
        return [];
    }
}

/**
 * Ζητάει τους Αμυντικούς Ογκόλιθους (Defensive Anchors - Blocks).
 */
async function fetchDefensiveAnchors(filterType = null, filterId = null, quarter = null, minStart = null, minEnd = null, shooterId = null, blockerId = null, gameCode = null,seasonCode=null) {
    try {
        const params = new URLSearchParams();
        if (filterType && filterId) {
            params.append("filter_type", filterType);
            params.append("filter_id", filterId);
        }
        if (quarter) params.append("quarter", quarter);
        if (minStart) params.append("min_start", minStart);
        if (minEnd) params.append("min_end", minEnd);
        if (shooterId) params.append("shooter_id", shooterId);
        if (blockerId) params.append("blocker_id", blockerId); 
        if (gameCode) params.append("game_code", gameCode);
        if (seasonCode) params.append("season_code", seasonCode);
        const url = `${API_BASE_URL}/api/analytics/defensive-anchors?${params.toString()}`;
        const response = await fetch(url);
        
        if (!response.ok) throw new Error(`HTTP error! status: ${response.status}`);
        const data = await response.json();
        return data.defensive_anchors;
    } catch (error) {
        console.error("Σφάλμα Defensive Anchors:", error);
        return [];
    }
}