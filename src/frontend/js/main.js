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
    const shooterFilter = document.getElementById("defensiveFiltersContainer");
    if (shooterFilter) {
        shooterFilter.style.display = (mode === "defensive-anchors") ? "block" : "none";
    }

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
    const foulsFilter = document.getElementById("foulsFiltersContainer");
    if (foulsFilter) {
        foulsFilter.style.display = (mode === "fouls-drawn") ? "block" : "none";
    }
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
        // Μετάβαση σε Analytics (Εξαφανίζουμε γήπεδο και πεντάδες για να έχουμε όλη την οθόνη!)
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
    const filterType = document.getElementById("extraFilterType") ? document.getElementById("extraFilterType").value : null;
    const filterId = document.getElementById("extraFilterId") ? document.getElementById("extraFilterId").value : null;
    const quarter = document.getElementById("quarterSelectAnalytics") ? document.getElementById("quarterSelectAnalytics").value : null;
    const minStart = document.getElementById("minStart") ? document.getElementById("minStart").value : null;
    const shooterId = document.getElementById("shooterIdInput") ? document.getElementById("shooterIdInput").value : null;
    const blockerId = document.getElementById("blockerIdInput") ? document.getElementById("blockerIdInput").value : null;
    const fouledId = document.getElementById("fouledIdInput") ? document.getElementById("fouledIdInput").value : null;
    const foulingId = document.getElementById("foulingIdInput") ? document.getElementById("foulingIdInput").value : null;
    const gameCode = document.getElementById("analyticsGameCodeInput") ? document.getElementById("analyticsGameCodeInput").value.trim() : null;


    if (mode === "shots") {
        // ==== ΕΚΤΕΛΕΣΗ ΓΙΑ ΤΟ 3D COURT ====
        const selectedPlayer = document.getElementById("playerSelect").value;
        const selectedAssistant = document.getElementById("assistSelect").value;
        const selectedGame = document.getElementById("gameSelect").value;
        const selectedSeason = document.getElementById("seasonSelect").value;
        
        const shotsData = await fetchFilteredShots(selectedPlayer, selectedAssistant, selectedGame, selectedSeason, filterType, filterId, quarter, minStart, minEnd);
        drawShots(shotsData); 
    }else if (mode === "top-lineups") {
        // ==== ΕΚΤΕΛΕΣΗ ΓΙΑ ΤΑ TOP LINEUPS ====
        analyticsTitle.innerText = "Top Lineups ";
        analyticsContent.innerHTML = "<div style='grid-column: 1 / -1; text-align: center; color: #ea5314; font-weight: bold; font-size: 1.2rem; padding: 40px;'>Φόρτωση δεδομένων...</div>";
        
        // Διαβάζουμε τα Extra Filters (αν υπάρχουν)
        const filterType = document.getElementById("extraFilterType") ? document.getElementById("extraFilterType").value : "";
        const filterId = document.getElementById("extraFilterId") ? document.getElementById("extraFilterId").value : "";
        
        const lineups = await fetchTopLineups(filterType, filterId, quarter, minStart, minEnd, gameCode);
        if (!lineups || lineups.length === 0) {
            analyticsContent.innerHTML = "<div style='grid-column: 1 / -1;'>Δεν βρέθηκαν δεδομένα.</div>";
            return;
        }

        analyticsContent.innerHTML = ""; 

        // Για κάθε πεντάδα φτιάχνουμε μία κάρτα
        lineups.forEach((lineup, index) => {
            const card = document.createElement("div");
            card.style.background = "#fff";
            card.style.padding = "20px";
            card.style.borderRadius = "12px";
            card.style.boxShadow = "0 4px 15px rgba(0,0,0,0.05)";
            card.style.borderTop = "5px solid #ea5314"; // Πορτοκαλί περίγραμμα πάνω
            
            // Το μοναδικό ID για να βάλουμε τους 5 παίκτες
            const containerId = `lineup_container_${index}`;
            
            card.innerHTML = `
                <div style="display: flex; justify-content: space-between; align-items: center; border-bottom: 1px solid #eee; padding-bottom: 10px; margin-bottom: 15px;">
                    <span style="font-weight: 900; font-size: 1.2rem; color: #ccc;">#${index + 1}</span>
                    <span style="font-weight: bold; font-size: 1.1rem; color: #2b528a;">
                        Σύνολο: <span style="color: #ea5314; font-size: 1.3rem;">${lineup.total_points}</span> πόντοι
                    </span>
                </div>
                <!-- Το container που θα μπουν οι φωτογραφίες των παικτών οριζόντια -->
                <div id="${containerId}" style="display: flex; justify-content: space-around; flex-wrap: wrap; gap: 8px;">
                </div>
            `;
            
            analyticsContent.appendChild(card);

            // Γεμίζουμε δυναμικά τις 5 φωτογραφίες
            const playersContainer = document.getElementById(containerId);
            lineup.players.forEach((playerId) => {
                if (!playerId) return;
                
                const playerDiv = document.createElement("div");
                playerDiv.style.display = "flex";
                playerDiv.style.flexDirection = "column";
                playerDiv.style.alignItems = "center";
                playerDiv.style.width = "18%"; // Για να χωράνε ακριβώς 5 παίκτες δίπλα-δίπλα
                
                playerDiv.innerHTML = `
                    <img src="https://media-api-front.euroleague.net/images/players/p${playerId}.png" 
                         onerror="this.src='https://upload.wikimedia.org/wikipedia/commons/8/89/Portrait_Placeholder.png'"
                         style="width: 50px; height: 50px; border-radius: 50%; object-fit: cover; border: 2px solid #ccc; background-color: #fff;">
                    <span style="font-size: 0.7rem; margin-top: 5px; font-weight: 700; color: #333; text-align: center; word-break: break-word;" id="name_${playerId}_${index}">...</span>
                `;
                playersContainer.appendChild(playerDiv);
                
                // Φέρνουμε το όνομα του κάθε παίκτη
                fetchPlayerNameForCard(playerId, `name_${playerId}_${index}`);
            });
        });
    } else if (mode === "fouls-drawn") {
        analyticsTitle.innerText = "Fouls Drawn Gravity";
        analyticsContent.innerHTML = "<div style='grid-column: 1 / -1; text-align: center; color: #e74c3c; font-weight: bold; font-size: 1.2rem; padding: 40px;'>Φόρτωση δεδομένων...</div>";
        
        // Κλήση με τα variables που έχουν ήδη διαβαστεί στο event listener!
        const players = await fetchFoulsDrawn(filterType, filterId, quarter, minStart, minEnd, fouledId, foulingId, gameCode);
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
                    <img src="https://media-api-front.euroleague.net/images/players/p${player.player_id}.png" 
                         onerror="this.src='https://upload.wikimedia.org/wikipedia/commons/8/89/Portrait_Placeholder.png'"
                         style="width: 70px; height: 70px; border-radius: 50%; object-fit: cover; border: 3px solid #e74c3c; background-color: #fff;">
                    <span style="font-size: 0.9rem; margin-top: 8px; font-weight: 700; color: #333;" id="name_fd_${player.player_id}_${index}">...</span>
                </div>
                <div style="display: flex; flex-direction: column; align-items: center; justify-content: center; padding: 0 15px;">
                    <span style="font-size: 2.2rem; color: #e74c3c; font-weight: 900;">${player.total_fouls_drawn}</span>
                    <span style="font-size: 0.75rem; font-weight: bold; color: #555;">ΚΕΡΔΙΣΜΕΝΑ ΦΑΟΥΛ</span>
                </div>
            `;
            analyticsContent.appendChild(card);
            fetchPlayerNameForCard(player.player_id, `name_fd_${player.player_id}_${index}`);
        });

    } else if (mode === "defensive-anchors") {
        analyticsTitle.innerText = "Defensive Anchors ";
        analyticsContent.innerHTML = "<div style='grid-column: 1 / -1; text-align: center; color: #34495e; font-weight: bold; font-size: 1.2rem; padding: 40px;'>Φόρτωση δεδομένων...</div>";
        
        // Κλήση με τα variables
        const players = await fetchDefensiveAnchors(filterType, filterId, quarter, minStart, minEnd, shooterId, blockerId, gameCode);        
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
                    <img src="https://media-api-front.euroleague.net/images/players/p${player.player_id}.png" 
                         onerror="this.src='https://upload.wikimedia.org/wikipedia/commons/8/89/Portrait_Placeholder.png'"
                         style="width: 70px; height: 70px; border-radius: 50%; object-fit: cover; border: 3px solid #34495e; background-color: #fff;">
                    <span style="font-size: 0.9rem; margin-top: 8px; font-weight: 700; color: #333;" id="name_da_${player.player_id}_${index}">...</span>
                </div>
                <div style="display: flex; flex-direction: column; align-items: center; justify-content: center; padding: 0 15px;">
                    <span style="font-size: 2.2rem; color: #34495e; font-weight: 900;">${player.total_blocks}</span>
                    <span style="font-size: 0.75rem; font-weight: bold; color: #555;">ΜΠΛΟΚ (ΤΑΠΕΣ)</span>
                </div>
            `;
            analyticsContent.appendChild(card);
            fetchPlayerNameForCard(player.player_id, `name_da_${player.player_id}_${index}`);
        });
    }else if (mode === "second-chance") {
        // ==== ΕΚΤΕΛΕΣΗ ΓΙΑ ΤΑ SECOND CHANCE POINTS ====
        analyticsTitle.innerText = "Second Chance Points 🏀";
        analyticsContent.innerHTML = "<div style='grid-column: 1 / -1; text-align: center; color: #27ae60; font-weight: bold; font-size: 1.2rem; padding: 40px;'>Φόρτωση δεδομένων...</div>";
        
        // Κάνουμε fetch περνώντας τις μεταβλητές (filterType, quarter, κτλ) που ήδη έχουμε διαβάσει στην αρχή του click event!
        const players = await fetchSecondChancePoints(filterType, filterId, quarter, minStart, minEnd, gameCode);        
        if (!players || players.length === 0) {
            analyticsContent.innerHTML = "<div style='grid-column: 1 / -1;'>Δεν βρέθηκαν δεδομένα για αυτά τα φίλτρα.</div>";
            return;
        }

        analyticsContent.innerHTML = ""; 

        // Δημιουργία των πράσινων καρτών
        players.forEach((player, index) => {
            const card = document.createElement("div");
            card.style.background = "#fff";
            card.style.padding = "20px";
            card.style.borderRadius = "12px";
            card.style.boxShadow = "0 4px 15px rgba(0,0,0,0.05)";
            card.style.borderTop = "5px solid #27ae60"; // Πράσινο χρώμα για τα Second Chance
            card.style.display = "flex";
            card.style.alignItems = "center";
            card.style.justifyContent = "space-between";

            card.innerHTML = `
                <div style="font-weight: 900; font-size: 1.5rem; color: #ccc; width: 40px;">#${index + 1}</div>
                
                <div style="display: flex; flex-direction: column; align-items: center; flex: 1; text-align: center;">
                    <img src="https://media-api-front.euroleague.net/images/players/p${player.player_id}.png" 
                         onerror="this.src='https://upload.wikimedia.org/wikipedia/commons/8/89/Portrait_Placeholder.png'"
                         style="width: 70px; height: 70px; border-radius: 50%; object-fit: cover; border: 3px solid #27ae60; background-color: #fff;">
                    <span style="font-size: 0.9rem; margin-top: 8px; font-weight: 700; color: #333;" id="name_${player.player_id}_${index}">...</span>
                </div>
                
                <div style="display: flex; flex-direction: column; align-items: center; justify-content: center; padding: 0 15px;">
                    <span style="font-size: 2.2rem; color: #27ae60; font-weight: 900;">${player.total_points}</span>
                    <span style="font-size: 0.75rem; font-weight: bold; color: #555; letter-spacing: 1px;">ΠΟΝΤΟΙ</span>
                </div>
            `;
            
            analyticsContent.appendChild(card);
            
            // Φέρνουμε το όνομα του παίκτη
            fetchPlayerNameForCard(player.player_id, `name_${player.player_id}_${index}`);
        });
    }else if (mode === "assist-duos") {
        // ==== ΕΚΤΕΛΕΣΗ ΓΙΑ ΤΑ TOP ASSIST DUOS ====
        analyticsTitle.innerText = "Top Assist Duos ";
        analyticsContent.innerHTML = "<div style='grid-column: 1 / -1; text-align: center; color: #ea5314; font-weight: bold; font-size: 1.2rem; padding: 40px;'>Φόρτωση δεδομένων...</div>";
        
        // Διαβάζουμε τα φίλτρα (αν ο χρήστης έγραψε κάτι)
        const filterType = document.getElementById("extraFilterType") ? document.getElementById("extraFilterType").value : "";
        const filterId = document.getElementById("extraFilterId") ? document.getElementById("extraFilterId").value : "";
        
        const quarter = document.getElementById("quarterSelectAnalytics").value;
        const minStart = document.getElementById("minStart").value;
        const minEnd = document.getElementById("minEnd").value;
        
        // Στέλνουμε και τα 5 φίλτρα!
        const duos = await fetchTopAssistDuos(filterType, filterId, quarter, minStart, minEnd, gameCode);        
        if (!duos || duos.length === 0) {
            analyticsContent.innerHTML = "<div style='grid-column: 1 / -1;'>Δεν βρέθηκαν δεδομένα.</div>";
            return;
        }

        analyticsContent.innerHTML = ""; // Καθαρίζουμε το loading

        duos.forEach((duo, index) => {
            const card = document.createElement("div");
            // Στυλ για τις νέες, μεγάλες κάρτες (αφού έχουμε χώρο!)
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
                
                <div style="display: flex; flex-direction: column; align-items: center; flex: 1; text-align: center;">
                    <img src="https://media-api-front.euroleague.net/images/players/p${duo.passer_id}.png" 
                        onerror="this.src='https://upload.wikimedia.org/wikipedia/commons/8/89/Portrait_Placeholder.png'"
                        style="width: 60px; height: 60px; border-radius: 50%; object-fit: cover; border: 3px solid #e0e0e0; background-color: #fff;">
                    <span style="font-size: 0.85rem; margin-top: 8px; font-weight: 700; color: #333;" id="name_${duo.passer_id}_${index}">...</span>
                    <span style="font-size: 0.7rem; color: #888;">PASSER</span>
                </div>
                
                <div style="display: flex; flex-direction: column; align-items: center; justify-content: center; padding: 0 15px;">
                    <span style="font-size: 1.8rem; color: #ea5314; font-weight: 900;">${duo.total_assists}</span>
                    <span style="font-size: 0.75rem; font-weight: bold; color: #555; letter-spacing: 1px;">ΑΣΙΣΤ</span>
                    <span style="color: #2b528a; font-size: 1.5rem; margin-top: -5px;">➔</span>
                </div>
                
                <div style="display: flex; flex-direction: column; align-items: center; flex: 1; text-align: center;">
                    <img src="https://media-api-front.euroleague.net/images/players/p${duo.scorer_id}.png" 
                        onerror="this.src='https://upload.wikimedia.org/wikipedia/commons/8/89/Portrait_Placeholder.png'"
                        style="width: 60px; height: 60px; border-radius: 50%; object-fit: cover; border: 3px solid #ea5314; background-color: #fff;">
                    <span style="font-size: 0.85rem; margin-top: 8px; font-weight: 700; color: #333;" id="name_${duo.scorer_id}_${index}">...</span>
                    <span style="font-size: 0.7rem; color: #888;">SCORER</span>
                </div>
            `;
            analyticsContent.appendChild(card);

            fetchPlayerNameForCard(duo.passer_id, `name_${duo.passer_id}_${index}`);
            fetchPlayerNameForCard(duo.scorer_id, `name_${duo.scorer_id}_${index}`);
        });
    } 
    else {
        analyticsTitle.innerText = "Σε εξέλιξη...";
        analyticsContent.innerHTML = "<div style='grid-column: 1 / -1; color: #555;'>Αυτή η λειτουργία θα προστεθεί στο επόμενο βήμα!</div>";
    }
});

// --- Βοηθητική συνάρτηση για τα ονόματα των παικτών ---
async function fetchPlayerNameForCard(playerId, htmlElementId) {
    try {
        const response = await fetch(`http://localhost:8000/api/player/${playerId}`);
        const data = await response.json();
        let displayName = data.name;
        if (displayName.includes(",")) {
            displayName = displayName.split(",")[0]; 
        }
        document.getElementById(htmlElementId).innerText = displayName;
    } catch (err) {
        document.getElementById(htmlElementId).innerText = `ID: ${playerId}`;
    }
}