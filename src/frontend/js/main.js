// main.js

// Παίρνουμε τα στοιχεία από το HTML
const mainModeSelect = document.getElementById("mainModeSelect");
const shotFiltersForm = document.getElementById("shotFiltersForm");
const mainActionBtn = document.getElementById("mainActionBtn");

const courtWrapper = document.getElementById("courtWrapper");
const analyticsWrapper = document.getElementById("analyticsWrapper");
const analyticsContent = document.getElementById("analyticsContent");
const analyticsTitle = document.getElementById("analyticsTitle");
const rightPanel = document.getElementById("rightPanel");

// --- 1. ΛΟΓΙΚΗ ΓΙΑ ΤΗΝ ΑΛΛΑΓΗ ΤΟΥ DROPDOWN ---
mainModeSelect.addEventListener("change", (e) => {
    const mode = e.target.value;
    
    // Εμφάνιση/Απόκρυψη ειδικών φίλτρων
    const shooterFilter = document.getElementById("defensiveFiltersContainer");
    if (shooterFilter) shooterFilter.style.display = (mode === "defensive-anchors") ? "block" : "none";

    const foulsFilter = document.getElementById("foulsFiltersContainer");
    if (foulsFilter) foulsFilter.style.display = (mode === "fouls-drawn") ? "block" : "none";
    
    const analyticsGameFilter = document.getElementById("analyticsGameFilterContainer");

    if (mode === "shots") {
        // Επιστροφή στο Γήπεδο
        shotFiltersForm.style.display = "block";
        courtWrapper.style.display = "flex";
        analyticsWrapper.style.display = "none";
        rightPanel.style.display = "flex"; // Επαναφέρουμε τις πεντάδες
        if (analyticsGameFilter) analyticsGameFilter.style.display = "none";
        mainActionBtn.innerText = "ΑΝΑΖΗΤΗΣΗ ΣΟΥΤ";
        mainActionBtn.style.backgroundColor = "#ea5314"; 
    } else {
        // Μετάβαση σε Analytics (Εξαφανίζουμε γήπεδο και πεντάδες)
        shotFiltersForm.style.display = "none";
        courtWrapper.style.display = "none";
        analyticsWrapper.style.display = "block";
        rightPanel.style.display = "none"; 
        if (analyticsGameFilter) analyticsGameFilter.style.display = "block";
        analyticsContent.innerHTML = "<div style='grid-column: 1 / -1; text-align: center; color: #777; font-style: italic; font-size: 1.1rem;'>Πάτα 'ΕΚΤΕΛΕΣΗ ΑΝΑΛΥΣΗΣ' για να δεις τα δεδομένα...</div>";
        analyticsTitle.innerText = "Αποτελέσματα Ανάλυσης";
        mainActionBtn.innerText = "ΕΚΤΕΛΕΣΗ ΑΝΑΛΥΣΗΣ";
        mainActionBtn.style.backgroundColor = "#2b528a";
    }
});

// --- 2. ΛΟΓΙΚΗ ΟΤΑΝ ΠΑΤΑΕΙ ΤΟ ΚΟΥΜΠΙ ---
mainActionBtn.addEventListener("click", async () => {
    const mode = mainModeSelect.value;
    // Πιάνουμε τη Season από παντού!
    const selectedSeason = document.getElementById("seasonSelect") ? document.getElementById("seasonSelect").value : "";
    
    const filterType = document.getElementById("extraFilterType") ? document.getElementById("extraFilterType").value : null;
    const filterId = document.getElementById("extraFilterId") ? document.getElementById("extraFilterId").value : null;
    const quarter = document.getElementById("quarterSelectAnalytics") ? document.getElementById("quarterSelectAnalytics").value : null;
    const minStart = document.getElementById("minStart") ? document.getElementById("minStart").value : null;
    const minEnd = document.getElementById("minEnd") ? document.getElementById("minEnd").value : null;
    const shooterId = document.getElementById("shooterIdInput") ? document.getElementById("shooterIdInput").value : null;
    const blockerId = document.getElementById("blockerIdInput") ? document.getElementById("blockerIdInput").value : null;
    const fouledId = document.getElementById("fouledIdInput") ? document.getElementById("fouledIdInput").value : null;
    const foulingId = document.getElementById("foulingIdInput") ? document.getElementById("foulingIdInput").value : null;
    const gameCode = document.getElementById("analyticsGameCodeInput") ? document.getElementById("analyticsGameCodeInput").value.trim() : null;

    if (mode === "shots") {
        const selectedPlayer = document.getElementById("playerSelect") ? document.getElementById("playerSelect").value : null;
        const selectedAssistant = document.getElementById("assistSelect") ? document.getElementById("assistSelect").value : null;
        const selectedGame = document.getElementById("gameSelect") ? document.getElementById("gameSelect").value : null;
        
        // Στέλνουμε το selectedSeason
        const shotsData = await fetchFilteredShots(selectedPlayer, selectedAssistant, selectedGame, selectedSeason, filterType, filterId, quarter, minStart, minEnd);
        drawShots(shotsData); 
    } 
    else if (mode === "top-lineups") {
        analyticsTitle.innerText = "Top Lineups";
        analyticsContent.innerHTML = "<div style='grid-column: 1 / -1; text-align: center; color: #ea5314; font-weight: bold; font-size: 1.2rem; padding: 40px;'>Φόρτωση δεδομένων...</div>";
        
        // Στέλνουμε το selectedSeason
        const lineups = await fetchTopLineups(filterType, filterId, quarter, minStart, minEnd, gameCode, selectedSeason);
        if (!lineups || lineups.length === 0) {
            analyticsContent.innerHTML = "<div style='grid-column: 1 / -1;'>Δεν βρέθηκαν δεδομένα.</div>";
            return;
        }

        analyticsContent.innerHTML = ""; 
        lineups.forEach((lineup, index) => {
            const card = document.createElement("div");
            card.style.background = "#fff";
            card.style.padding = "20px";
            card.style.borderRadius = "12px";
            card.style.boxShadow = "0 4px 15px rgba(0,0,0,0.05)";
            card.style.borderTop = "5px solid #ea5314"; 
            
            const containerId = `lineup_container_${index}`;
            card.innerHTML = `
                <div style="display: flex; justify-content: space-between; align-items: center; border-bottom: 1px solid #eee; padding-bottom: 10px; margin-bottom: 15px;">
                    <span style="font-weight: 900; font-size: 1.2rem; color: #ccc;">#${index + 1}</span>
                    <span style="font-weight: bold; font-size: 1.1rem; color: #2b528a;">
                        Σύνολο: <span style="color: #ea5314; font-size: 1.3rem;">${lineup.total_points}</span> πόντοι
                    </span>
                </div>
                <div id="${containerId}" style="display: flex; justify-content: space-around; flex-wrap: wrap; gap: 8px;"></div>
            `;
            analyticsContent.appendChild(card);

            const playersContainer = document.getElementById(containerId);
            lineup.players.forEach((playerId) => {
                if (!playerId) return;
                const playerDiv = document.createElement("div");
                playerDiv.style.display = "flex";
                playerDiv.style.flexDirection = "column";
                playerDiv.style.alignItems = "center";
                playerDiv.style.width = "18%"; 
                
                playerDiv.innerHTML = `
                    <!-- Προστέθηκε ID στην εικόνα και default avatar -->
                    <img id="img_lineup_${playerId}_${index}" src="https://www.euroleaguebasketball.net/media/com_easysocial/avatars/users/default_avatar.png" 
                         style="width: 50px; height: 50px; border-radius: 50%; object-fit: cover; border: 2px solid #ccc; background-color: #fff;">
                    <span style="font-size: 0.7rem; margin-top: 5px; font-weight: 700; color: #333; text-align: center; word-break: break-word;" id="name_lineup_${playerId}_${index}">...</span>
                `;
                playersContainer.appendChild(playerDiv);
                
                // Καλούμε τη ΝΕΑ συνάρτηση για κάθε παίκτη της πεντάδας!
                fetchPlayerDetailsForCard(playerId, `name_lineup_${playerId}_${index}`, `img_lineup_${playerId}_${index}`);
            });
        });
    } 
    else if (mode === "fouls-drawn") {
        analyticsTitle.innerText = "Fouls Drawn Gravity";
        analyticsContent.innerHTML = "<div style='grid-column: 1 / -1; text-align: center; color: #e74c3c; font-weight: bold; font-size: 1.2rem; padding: 40px;'>Φόρτωση δεδομένων...</div>";
        
        const players = await fetchFoulsDrawn(filterType, filterId, quarter, minStart, minEnd, fouledId, foulingId, gameCode, selectedSeason);
        if (!players || players.length === 0) {
            analyticsContent.innerHTML = "<div style='grid-column: 1 / -1;'>Δεν βρέθηκαν δεδομένα.</div>";
            return;
        }

        analyticsContent.innerHTML = "";
        players.forEach((player, index) => {
            const card = document.createElement("div");
            card.style.background = "#fff";
            card.style.padding = "20px";
            card.style.borderRadius = "12px";
            card.style.boxShadow = "0 4px 15px rgba(0,0,0,0.05)";
            card.style.borderTop = "5px solid #e74c3c";
            card.style.display = "flex";
            card.style.alignItems = "center";
            card.style.justifyContent = "space-between";

            card.innerHTML = `
                <div style="font-weight: 900; font-size: 1.5rem; color: #ccc; width: 40px;">#${index + 1}</div>
                <div style="display: flex; flex-direction: column; align-items: center; flex: 1; text-align: center;">
                    <!-- Προστέθηκε ID στην εικόνα και default avatar -->
                    <img id="img_fd_${player.player_id}_${index}" src="https://www.euroleaguebasketball.net/media/com_easysocial/avatars/users/default_avatar.png" 
                         style="width: 70px; height: 70px; border-radius: 50%; object-fit: cover; border: 3px solid #e74c3c; background-color: #fff;">
                    
                    <span style="font-size: 0.9rem; margin-top: 8px; font-weight: 700; color: #333;" id="name_fd_${player.player_id}_${index}">...</span>
                </div>
                <div style="display: flex; flex-direction: column; align-items: center; justify-content: center; padding: 0 15px;">
                    <span style="font-size: 2.2rem; color: #e74c3c; font-weight: 900;">${player.total_fouls_drawn}</span>
                    <span style="font-size: 0.75rem; font-weight: bold; color: #555;">ΚΕΡΔΙΣΜΕΝΑ ΦΑΟΥΛ</span>
                </div>
            `;
            analyticsContent.appendChild(card);
            
            // Καλούμε τη ΝΕΑ συνάρτηση!
            fetchPlayerDetailsForCard(player.player_id, `name_fd_${player.player_id}_${index}`, `img_fd_${player.player_id}_${index}`);
        });
    } 
    else if (mode === "defensive-anchors") {
        analyticsTitle.innerText = "Defensive Anchors";
        analyticsContent.innerHTML = "<div style='grid-column: 1 / -1; text-align: center; color: #34495e; font-weight: bold; font-size: 1.2rem; padding: 40px;'>Φόρτωση δεδομένων...</div>";
        
        const players = await fetchDefensiveAnchors(filterType, filterId, quarter, minStart, minEnd, shooterId, blockerId, gameCode, selectedSeason);        
        if (!players || players.length === 0) {
            analyticsContent.innerHTML = "<div style='grid-column: 1 / -1;'>Δεν βρέθηκαν δεδομένα.</div>";
            return;
        }

        analyticsContent.innerHTML = "";
        players.forEach((player, index) => {
            const card = document.createElement("div");
            card.style.background = "#fff";
            card.style.padding = "20px";
            card.style.borderRadius = "12px";
            card.style.boxShadow = "0 4px 15px rgba(0,0,0,0.05)";
            card.style.borderTop = "5px solid #34495e";
            card.style.display = "flex";
            card.style.alignItems = "center";
            card.style.justifyContent = "space-between";

            card.innerHTML = `
                <div style="font-weight: 900; font-size: 1.5rem; color: #ccc; width: 40px;">#${index + 1}</div>
                <div style="display: flex; flex-direction: column; align-items: center; flex: 1; text-align: center;">
                    <!-- Προστέθηκε ID στην εικόνα και default avatar -->
                    <img id="img_da_${player.player_id}_${index}" src="https://www.euroleaguebasketball.net/media/com_easysocial/avatars/users/default_avatar.png" 
                         style="width: 70px; height: 70px; border-radius: 50%; object-fit: cover; border: 3px solid #34495e; background-color: #fff;">
                    
                    <span style="font-size: 0.9rem; margin-top: 8px; font-weight: 700; color: #333;" id="name_da_${player.player_id}_${index}">...</span>
                </div>
                <div style="display: flex; flex-direction: column; align-items: center; justify-content: center; padding: 0 15px;">
                    <span style="font-size: 2.2rem; color: #34495e; font-weight: 900;">${player.total_blocks}</span>
                    <span style="font-size: 0.75rem; font-weight: bold; color: #555;">ΜΠΛΟΚ (ΤΑΠΕΣ)</span>
                </div>
            `;
            analyticsContent.appendChild(card);
            
            // Καλούμε τη ΝΕΑ συνάρτηση!
            fetchPlayerDetailsForCard(player.player_id, `name_da_${player.player_id}_${index}`, `img_da_${player.player_id}_${index}`);
        });
    }
    else if (mode === "second-chance") {
        analyticsTitle.innerText = "Second Chance Points 🏀";
        analyticsContent.innerHTML = "<div style='grid-column: 1 / -1; text-align: center; color: #27ae60; font-weight: bold; font-size: 1.2rem; padding: 40px;'>Φόρτωση δεδομένων...</div>";
        
        const players = await fetchSecondChancePoints(filterType, filterId, quarter, minStart, minEnd, gameCode, selectedSeason);        
        if (!players || players.length === 0) {
            analyticsContent.innerHTML = "<div style='grid-column: 1 / -1;'>Δεν βρέθηκαν δεδομένα για αυτά τα φίλτρα.</div>";
            return;
        }

        analyticsContent.innerHTML = ""; 
        players.forEach((player, index) => {
            const card = document.createElement("div");
            card.style.background = "#fff";
            card.style.padding = "20px";
            card.style.borderRadius = "12px";
            card.style.boxShadow = "0 4px 15px rgba(0,0,0,0.05)";
            card.style.borderTop = "5px solid #27ae60"; 
            card.style.display = "flex";
            card.style.alignItems = "center";
            card.style.justifyContent = "space-between";

            card.innerHTML = `
                <div style="font-weight: 900; font-size: 1.5rem; color: #ccc; width: 40px;">#${index + 1}</div>
                <div style="display: flex; flex-direction: column; align-items: center; flex: 1; text-align: center;">
                    <!-- Προστέθηκε ID στην εικόνα και μπήκε το default avatar -->
                    <img id="img_sc_${player.player_id}_${index}" src="https://www.euroleaguebasketball.net/media/com_easysocial/avatars/users/default_avatar.png" 
                         style="width: 70px; height: 70px; border-radius: 50%; object-fit: cover; border: 3px solid #27ae60; background-color: #fff;">
                    
                    <!-- Ανανεώθηκε το ID στο span του ονόματος -->
                    <span style="font-size: 0.9rem; margin-top: 8px; font-weight: 700; color: #333;" id="name_sc_${player.player_id}_${index}">...</span>
                </div>
                <div style="display: flex; flex-direction: column; align-items: center; justify-content: center; padding: 0 15px;">
                    <span style="font-size: 2.2rem; color: #27ae60; font-weight: 900;">${player.total_points}</span>
                    <span style="font-size: 0.75rem; font-weight: bold; color: #555; letter-spacing: 1px;">ΠΟΝΤΟΙ</span>
                </div>
            `;
            analyticsContent.appendChild(card);
            
            // Καλούμε τη ΝΕΑ συνάρτηση περνώντας και το id της εικόνας
            fetchPlayerDetailsForCard(player.player_id, `name_sc_${player.player_id}_${index}`, `img_sc_${player.player_id}_${index}`);
        });
    }
    else if (mode === "assist-duos") {
        analyticsTitle.innerText = "Top Assist Duos";
        analyticsContent.innerHTML = "<div style='grid-column: 1 / -1; text-align: center; color: #ea5314; font-weight: bold; font-size: 1.2rem; padding: 40px;'>Φόρτωση δεδομένων...</div>";
        
        const duos = await fetchTopAssistDuos(filterType, filterId, quarter, minStart, minEnd, gameCode, selectedSeason);        
        if (!duos || duos.length === 0) {
            analyticsContent.innerHTML = "<div style='grid-column: 1 / -1;'>Δεν βρέθηκαν δεδομένα.</div>";
            return;
        }

        analyticsContent.innerHTML = ""; 
        duos.forEach((duo, index) => {
            const card = document.createElement("div");
            card.style.background = "#fff";
            card.style.padding = "20px";
            card.style.borderRadius = "12px";
            card.style.boxShadow = "0 4px 15px rgba(0,0,0,0.05)";
            card.style.borderTop = "5px solid #2b528a";
            card.style.display = "flex";
            card.style.alignItems = "center";
            card.style.justifyContent = "space-between";

            card.innerHTML = `
                <div style="font-weight: 900; font-size: 1.5rem; color: #ccc; width: 40px;">#${index + 1}</div>
                
                <!-- PASSER -->
                <div style="display: flex; flex-direction: column; align-items: center; flex: 1; text-align: center;">
                    <img id="img_passer_${duo.passer_id}_${index}" src="https://www.euroleaguebasketball.net/media/com_easysocial/avatars/users/default_avatar.png" 
                        style="width: 60px; height: 60px; border-radius: 50%; object-fit: cover; border: 3px solid #e0e0e0; background-color: #fff;">
                    <span style="font-size: 0.85rem; margin-top: 8px; font-weight: 700; color: #333;" id="name_passer_${duo.passer_id}_${index}">...</span>
                    <span style="font-size: 0.7rem; color: #888;">PASSER</span>
                </div>
                
                <!-- STATS -->
                <div style="display: flex; flex-direction: column; align-items: center; justify-content: center; padding: 0 15px;">
                    <span style="font-size: 1.8rem; color: #ea5314; font-weight: 900;">${duo.total_assists}</span>
                    <span style="font-size: 0.75rem; font-weight: bold; color: #555; letter-spacing: 1px;">ΑΣΙΣΤ</span>
                    <span style="color: #2b528a; font-size: 1.5rem; margin-top: -5px;">➔</span>
                </div>
                
                <!-- SCORER -->
                <div style="display: flex; flex-direction: column; align-items: center; flex: 1; text-align: center;">
                    <img id="img_scorer_${duo.scorer_id}_${index}" src="https://www.euroleaguebasketball.net/media/com_easysocial/avatars/users/default_avatar.png" 
                        style="width: 60px; height: 60px; border-radius: 50%; object-fit: cover; border: 3px solid #ea5314; background-color: #fff;">
                    <span style="font-size: 0.85rem; margin-top: 8px; font-weight: 700; color: #333;" id="name_scorer_${duo.scorer_id}_${index}">...</span>
                    <span style="font-size: 0.7rem; color: #888;">SCORER</span>
                </div>
            `;
            analyticsContent.appendChild(card);
            
            // Κλήση της νέας συνάρτησης!
            fetchPlayerDetailsForCard(duo.passer_id, `name_passer_${duo.passer_id}_${index}`, `img_passer_${duo.passer_id}_${index}`);
            fetchPlayerDetailsForCard(duo.scorer_id, `name_scorer_${duo.scorer_id}_${index}`, `img_scorer_${duo.scorer_id}_${index}`);
        });
    } 
    else {
        analyticsTitle.innerText = "Σε εξέλιξη...";
        analyticsContent.innerHTML = "<div style='grid-column: 1 / -1; color: #555;'>Αυτή η λειτουργία θα προστεθεί στο επόμενο βήμα!</div>";
    }
});

// --- Βοηθητικές Συναρτήσεις ---
async function fetchPlayerDetailsForCard(playerId, nameElementId, imgElementId) {
    try {
        // 1. Fetch από το backend (όπως ακριβώς στο court.js)
        const response = await fetch(`http://localhost:8000/api/player?player=${playerId}`);
        const data = await response.json();
        const playerData = data.player;

        const nameEl = document.getElementById(nameElementId);
        const imgEl = document.getElementById(imgElementId);

        if (playerData) {
            // Όνομα
            let playerName = playerData.name || `ID: ${playerId}`;
            if (playerName.includes(",")) {
                playerName = playerName.split(",")[0]; 
            }
            if (nameEl) nameEl.innerText = playerName;

            // Εικόνα: Παίρνει αυτή της βάσης, αλλιώς βάζει το default (όπως στο court.js)
            const playerImg = playerData.img || "https://www.euroleaguebasketball.net/media/com_easysocial/avatars/users/default_avatar.png";
            if (imgEl) imgEl.src = playerImg;
        } else {
            if (nameEl) nameEl.innerText = `ID: ${playerId}`;
            if (imgEl) imgEl.src = "https://www.euroleaguebasketball.net/media/com_easysocial/avatars/users/default_avatar.png";
        }
    } catch (err) {
        console.error(`Σφάλμα για τον παίκτη ${playerId}:`, err);
        const nameEl = document.getElementById(nameElementId);
        const imgEl = document.getElementById(imgElementId);
        if (nameEl) nameEl.innerText = `ID: ${playerId}`;
        if (imgEl) imgEl.src = "https://www.euroleaguebasketball.net/media/com_easysocial/avatars/users/default_avatar.png";
    }
}

async function loadLineups() {
    const response = await fetch(`${API_BASE_URL}/api/game/lineups?game_code=333&season_code=E2023`);
    const data = await response.json();
    
    const homeSelect = document.getElementById("homeLineupSelect");
    const roadSelect = document.getElementById("roadLineupSelect");
    
    if (homeSelect && roadSelect && data.lineups) {
        data.lineups.forEach(lineup => {
            const option = document.createElement("option");
            option.value = lineup.uri;
            option.textContent = lineup.players; 
            
            if (lineup.teamType === "home") {
                homeSelect.appendChild(option);
            } else if (lineup.teamType === "road") {
                roadSelect.appendChild(option);
            }
        });
    }
}

function handleLineupSelection(event) {
    const selectedLineupUri = event.target.value;
    const playerNames = event.target.options[event.target.selectedIndex].text.split(", ");
    
    const playersDiv = document.getElementById("lineupPlayersDiv");
    if (!playersDiv) return;
    
    playersDiv.innerHTML = ""; 
    
    if (!selectedLineupUri) return;

    playerNames.forEach(name => {
        const btn = document.createElement("button");
        btn.textContent = name;
        btn.style.padding = "5px 10px";
        btn.style.cursor = "pointer";
        
        btn.onclick = async () => {
            // Η σωστή σειρά παραμέτρων: playerId, assistId, gameCode, seasonCode, filterType, filterId, quarter, minStart, minEnd, lineupUri
            const shots = await fetchFilteredShots(name, null, null, "E2023", null, null, null, null, null, selectedLineupUri); 
            drawShots(shots);
        };
        playersDiv.appendChild(btn);
    });
}

// Αρχικοποίηση
document.addEventListener("DOMContentLoaded", () => {
    loadLineups();
    
    const homeSelect = document.getElementById("homeLineupSelect");
    const roadSelect = document.getElementById("roadLineupSelect");
    
    if (homeSelect) homeSelect.addEventListener("change", handleLineupSelection);
    if (roadSelect) roadSelect.addEventListener("change", handleLineupSelection);
});
