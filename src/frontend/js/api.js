// api.js

const API_BASE_URL = "http://localhost:8000"; // Η διεύθυνση του Python server σου (π.χ. FastAPI)

/**
 * Ζητάει τα σουτ από το backend βάσει φίλτρων.
 */
async function fetchFilteredShots(playerId = null, assistPlayerId = null, gameCode = null, seasonCode = "E2023", filterType = null, filterId = null) {
    try {
        const params = new URLSearchParams();
        if (playerId) params.append("player", playerId);
        if (assistPlayerId) params.append("assist_by", assistPlayerId);
        if (gameCode) params.append("game_code", gameCode);
        if (seasonCode) params.append("season_code", seasonCode);
        
        if (filterType && filterId) {
            params.append("filter_type", filterType);
            params.append("filter_id", filterId);
        }

        const url = `${API_BASE_URL}/api/shots?${params.toString()}`;
        console.log("Fetching from:", url);
        const response = await fetch(url);
        
        if (!response.ok) {
            throw new Error(`HTTP error! status: ${response.status}`);
        }

        const data = await response.json();
        return data.shots; // Επιστρέφει έναν πίνακα με τα αποτελέσματα του SPARQL query

    } catch (error) {
        console.error("Σφάλμα κατά την ανάκτηση των δεδομένων:", error);
        return [];
    }
}

/**
 * Ζητάει τα κορυφαία δίδυμα (Assist Duos) από το backend, με προαιρετικά φίλτρα!
 */
async function fetchTopAssistDuos(filterType = null, filterId = null) {
    try {
        const params = new URLSearchParams();
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
 * Ζητάει τις Καλύτερες Πεντάδες (Top Lineups) με τα προαιρετικά φίλτρα.
 */
async function fetchTopLineups(filterType = null, filterId = null) {
    try {
        const params = new URLSearchParams();
        if (filterType && filterId) {
            params.append("filter_type", filterType);
            params.append("filter_id", filterId);
        }

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
 * Ζητάει τους Second Chance Points με προαιρετικά φίλτρα.
 */
async function fetchSecondChancePoints(filterType = null, filterId = null) {
    try {
        const params = new URLSearchParams();
        if (filterType && filterId) {
            params.append("filter_type", filterType);
            params.append("filter_id", filterId);
        }

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