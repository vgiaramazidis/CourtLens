// main.js

document.getElementById("searchBtn").addEventListener("click", async () => {
    // 1. Παίρνουμε τις τιμές από τα φίλτρα του HTML
    const selectedPlayer = document.getElementById("playerSelect").value;
    const selectedAssistant = document.getElementById("assistSelect").value;

    // 2. Τραβάμε τα δεδομένα
    const shotsData = await fetchFilteredShots(selectedPlayer, selectedAssistant);

    // 3. Ζωγραφίζουμε το γήπεδο
    drawShots(shotsData);
});

// Κάλεσέ τη μόλις φορτώσει το DOM
document.addEventListener("DOMContentLoaded", () => {
    loadGameLineups();
});

async function loadLineups() {
    // Φέρε τα δεδομένα (μπορείς να τα κάνεις δυναμικά αν έχεις dropdown για τα games)
    const response = await fetch(`${API_BASE_URL}/api/game/lineups?game_code=333&season_code=E2023`);
    const data = await response.json();
    
    const homeSelect = document.getElementById("homeLineupSelect");
    const roadSelect = document.getElementById("roadLineupSelect");
    
    data.lineups.forEach(lineup => {
        const option = document.createElement("option");
        option.value = lineup.uri;
        option.textContent = lineup.players; 
        
        // Απόλυτα δυναμικός διαχωρισμός, ανεξαρτήτως ομάδας!
        if (lineup.teamType === "home") {
            homeSelect.appendChild(option);
        } else if (lineup.teamType === "road") {
            roadSelect.appendChild(option);
        }
    });
}

// Όταν επιλέγεις πεντάδα, βγάζει τα κουμπάκια!
function handleLineupSelection(event) {
    const selectedLineupUri = event.target.value;
    const playerNames = event.target.options[event.target.selectedIndex].text.split(", ");
    
    const playersDiv = document.getElementById("lineupPlayersDiv");
    playersDiv.innerHTML = ""; // Καθάρισμα
    
    if (!selectedLineupUri) return;

    playerNames.forEach(name => {
        const btn = document.createElement("button");
        btn.textContent = name;
        btn.style.padding = "5px 10px";
        btn.style.cursor = "pointer";
        
        btn.onclick = async () => {
            // Όταν πατάς τον παίκτη της πεντάδας, ψάχνει τα σουτ ΤΟΥ, για ΟΣΟ ήταν αυτή η πεντάδα μέσα!
            const shots = await fetchFilteredShots(name, null, selectedLineupUri); 
            drawShots(shots);
        };
        playersDiv.appendChild(btn);
    });
}

document.getElementById("homeLineupSelect").addEventListener("change", handleLineupSelection);
document.getElementById("roadLineupSelect").addEventListener("change", handleLineupSelection);

document.addEventListener("DOMContentLoaded", loadLineups);