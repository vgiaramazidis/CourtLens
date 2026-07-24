// api.js

const API_BASE_URL = "http://localhost:8000"; // Η διεύθυνση του Python server σου (π.χ. FastAPI)

/**
 * Ζητάει τα σουτ από το backend βάσει φίλτρων.
 */
async function fetchFilteredShots(playerId = null, assistPlayerId = null) {
    try {
        // Χτίζουμε δυναμικά τα query parameters
        const params = new URLSearchParams();
        if (playerId) params.append("player", playerId);
        if (assistPlayerId) params.append("assist_by", assistPlayerId);

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