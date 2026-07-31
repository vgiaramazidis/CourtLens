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
mainModeSelect.addEventListener("change",async (e) => {
    if (mainActionBtn.innerText === "ΕΞΟΔΟΣ ΑΠΟ GAME") {
        const integratedSimulator = document.getElementById("integratedSimulator");
        const actualSimulatorUI = document.getElementById("actualSimulatorUI");
        const extraFilters = document.getElementById("extraFiltersContainer");
        const timeFilters = document.getElementById("timeFiltersContainer");
        const tryGameBtn = document.getElementById("tryGameBtn");

        // 1. Κρύβουμε όλο το Simulator block
        if (integratedSimulator) integratedSimulator.style.display = "none";
        if (actualSimulatorUI) actualSimulatorUI.style.display = "none"; 

        // 2. Επαναφέρουμε τα φίλτρα
        if (extraFilters) extraFilters.style.display = "block";
        if (timeFilters) timeFilters.style.display = "block";
        if (analyticsContent) analyticsContent.style.display = "block";
        if (analyticsTitle) analyticsTitle.style.display = "block";
        
        // 3. Επαναφέρουμε τα κουμπιά
        mainActionBtn.innerText = "ΑΝΑΖΗΤΗΣΗ";
        mainActionBtn.style.backgroundColor = "#ea5314";
        
        if (tryGameBtn) {
            tryGameBtn.innerText = "TRY GAME";
            tryGameBtn.style.display = "block"; // Το εμφανίζουμε ξανά γιατί μπορεί να είχε κρυφτεί πατώντας GAME
        }

        // 4. Scroll πίσω στην κορυφή (στα Top Lineups)
        window.scrollTo({ top: 0, behavior: 'smooth' });
        
        return; // Σταματάμε εδώ την εκτέλεση! Δεν θέλουμε να κάνει νέα αναζήτηση.
    }
    
    const mode = e.target.value;
    if (analyticsContent) analyticsContent.innerHTML = "";
    if (analyticsTitle) analyticsTitle.innerText = "Αποτελέσματα";
    // Εμφάνιση/Απόκρυψη ειδικών φίλτρων
    const shooterFilter = document.getElementById("defensiveFiltersContainer");
    if (shooterFilter) shooterFilter.style.display = (mode === "defensive-anchors") ? "block" : "none";

    const foulsFilter = document.getElementById("foulsFiltersContainer");
    if (foulsFilter) foulsFilter.style.display = (mode === "fouls-drawn") ? "block" : "none";
    
    const analyticsGameFilter = document.getElementById("analyticsGameFilterContainer");

    const extraFilters = document.getElementById("extraFiltersContainer");
    const timeFilters = document.getElementById("timeFiltersContainer");
    const seasonSelectParent = document.getElementById("seasonSelect") ? document.getElementById("seasonSelect").parentElement : null;

    if (mode === "shots") {
        shotFiltersForm.style.display = "block";
        courtWrapper.style.display = "flex";
        analyticsWrapper.style.display = "none";
        
        rightPanel.style.display = "flex";
        mainActionBtn.style.display = "block";
        
        if (extraFilters) extraFilters.style.display = "block";
        if (timeFilters) timeFilters.style.display = "block";
        if (seasonSelectParent) seasonSelectParent.style.display = "block";
        if (tryGameBtn) tryGameBtn.style.display = "none";
        if (integratedSimulator) integratedSimulator.style.display = "none";
    } 
    else {
        shotFiltersForm.style.display = "none";
        courtWrapper.style.display = "none";
        analyticsWrapper.style.display = "block";
        rightPanel.style.display = "none"; 
        mainActionBtn.style.display = "block";
        
        if (extraFilters) extraFilters.style.display = "block";
        if (timeFilters) timeFilters.style.display = "block";
        if (seasonSelectParent) seasonSelectParent.style.display = "block";

        // ΝΕΟ: Έλεγχος εμφάνισης του κουμπιού Try Game και απόκρυψη του Simulator
        const tryGameBtn = document.getElementById("tryGameBtn");
        const integratedSimulator = document.getElementById("integratedSimulator");
        
        if (mode === "top-lineups") {
            if (tryGameBtn) tryGameBtn.style.display = "block"; // Εμφανίζουμε το Try Game
            if (integratedSimulator) integratedSimulator.style.display = "none"; // Κρύβουμε το Simulator αρχικά
        } else {
            if (tryGameBtn) tryGameBtn.style.display = "none";
            if (integratedSimulator) integratedSimulator.style.display = "none";
        }
    }
});

// --- 2. ΛΟΓΙΚΗ ΟΤΑΝ ΠΑΤΑΕΙ ΤΟ ΚΟΥΜΠΙ ---
mainActionBtn.addEventListener("click", async () => {
    const tryGameBtn = document.getElementById("tryGameBtn");

    // ΝΕΟ ΠΙΟ ΑΣΦΑΛΕΣ: Έλεγχος αν είμαστε σε Game Mode (Έξοδος)
    if (mainActionBtn.innerText.includes("ΕΞΟΔΟΣ")) {
        const integratedSimulator = document.getElementById("integratedSimulator");
        const actualSimulatorUI = document.getElementById("actualSimulatorUI");
        const extraFilters = document.getElementById("extraFiltersContainer");
        const timeFilters = document.getElementById("timeFiltersContainer");
        const analyticsContent = document.getElementById("analyticsContent");
        const analyticsTitle = document.getElementById("analyticsTitle");
        const gameInput = document.getElementById("analyticsGameCodeInput");
        // 1. Κρύβουμε όλο το Simulator block
        if (integratedSimulator) integratedSimulator.style.display = "none";
        if (actualSimulatorUI) actualSimulatorUI.style.display = "none"; 

        // 2. Επαναφέρουμε τα φίλτρα
        if (extraFilters) extraFilters.style.display = "block";
        if (timeFilters) timeFilters.style.display = "block";
        if (analyticsTitle) analyticsTitle.style.display = "block";
        if (analyticsContent) analyticsContent.style.display = "grid";
        // 3. Επαναφέρουμε το μεγάλο κουμπί
        if (gameInput) gameInput.value = "";
        mainActionBtn.innerText = "ΑΝΑΖΗΤΗΣΗ";
        mainActionBtn.style.backgroundColor = "#ea5314";
        
        // 4. ΣΙΓΟΥΡΗ ΕΠΑΝΑΦΟΡΑ ΤΟΥ TRY GAME
        if (tryGameBtn) {
            tryGameBtn.style.display = "block"; // Το εμφανίζουμε ΞΑΝΑ
            tryGameBtn.innerText = " TRY GAME"; // Του δίνουμε το αρχικό κείμενο
        }

        // 5. Scroll πίσω στην κορυφή
        window.scrollTo({ top: 0, behavior: 'smooth' });
        
        return; // Σταματάμε εδώ!
    }
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
        const integratedSimulator = document.getElementById("integratedSimulator");
        if (integratedSimulator) integratedSimulator.style.display = "none";
        
        if (tryGameBtn) {
            tryGameBtn.style.display = "block";
            tryGameBtn.innerText = " TRY GAME";
        }

        analyticsTitle.innerText = "Top Lineups";
        analyticsContent.innerHTML = "<div style='grid-column: 1 / -1; text-align: center; color: #ea5314; font-weight: bold; font-size: 1.2rem; padding: 40px;'>Φόρτωση δεδομένων...</div>";
        
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
                
                // ΝΕΟ: Φτιάχνουμε την κάρτα με drag & drop δυνατότητες
                const playerDiv = document.createElement("div");
                playerDiv.className = "player-card"; // Το class του simulator!
                playerDiv.draggable = true; 
                playerDiv.setAttribute("data-id", playerId);
                playerDiv.style.width = "55px"; 
                playerDiv.style.height = "75px";
                
                playerDiv.innerHTML = `
                    <img id="img_lineup_${playerId}_${index}" src="https://www.euroleaguebasketball.net/media/com_easysocial/avatars/users/default_avatar.png" 
                         style="width: 45px; height: 45px; border-radius: 50%; object-fit: cover; border: 2px solid #ccc; background-color: #fff; pointer-events: none;">
                    <span style="font-size: 0.65rem; margin-top: 5px; font-weight: 700; color: #333; text-align: center; word-break: break-word; pointer-events: none;" id="name_lineup_${playerId}_${index}">...</span>
                `;
                playersContainer.appendChild(playerDiv);
                
                fetchPlayerDetailsForCard(playerId, `name_lineup_${playerId}_${index}`, `img_lineup_${playerId}_${index}`);

                // Events για Drag & Drop (κάνει clone τον παίκτη αντί να τον κλέψει από τη λίστα)
                playerDiv.addEventListener('dragstart', function() {
                    window.draggedCard = this.cloneNode(true);
                    
                    // Κάνουμε και τον κλώνο draggable αν τον πιάσουμε από το παρκέ μετά
                    window.draggedCard.addEventListener('dragstart', function() {
                        window.draggedCard = this;
                        setTimeout(() => this.style.opacity = '0.5', 0);
                    });
                    window.draggedCard.addEventListener('dragend', function() {
                        setTimeout(() => { this.style.opacity = '1'; window.draggedCard = null; }, 0);
                    });

                    setTimeout(() => this.style.opacity = '0.5', 0);
                });

                playerDiv.addEventListener('dragend', function() {
                    setTimeout(() => { this.style.opacity = '1'; }, 0);
                });
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

// ==========================================
// DRAG & DROP ΛΟΓΙΚΗ ΓΙΑ ΤΟ SIMULATOR
// ==========================================
document.addEventListener("DOMContentLoaded", () => {
    const slots = document.querySelectorAll('.slot');
    const rosterPool = document.getElementById('rosterPool');

    slots.forEach(slot => {
        slot.addEventListener('dragover', function(e) {
            e.preventDefault(); 
            this.classList.add('drag-over');
        });

        slot.addEventListener('dragleave', function() {
            this.classList.remove('drag-over');
        });

        slot.addEventListener('drop', function(e) {
            e.preventDefault();
            this.classList.remove('drag-over');
            
            if (window.draggedCard) {
                // Εάν υπάρχει ήδη παίκτης, τον πετάμε πίσω στον πάγκο
                const existingCard = this.querySelector('.player-card');
                if (existingCard) {
                    rosterPool.appendChild(existingCard);
                }
                
                // Τοποθετούμε το νέο παίκτη
                this.appendChild(window.draggedCard);
                
                // Κρύβουμε το placeholder κείμενο (PG, SG κλπ)
                const textNode = Array.from(this.childNodes).find(node => node.nodeType === Node.TEXT_NODE);
                if (textNode) textNode.remove();
            }
        });
    });

    if (rosterPool) {
        rosterPool.addEventListener('dragover', function(e) {
            e.preventDefault();
        });

        rosterPool.addEventListener('drop', function(e) {
            e.preventDefault();
            if (window.draggedCard) {
                this.appendChild(window.draggedCard);
            }
        });
    }
});

const simBtn = document.getElementById("runSimulatorBtn");

if (simBtn) {
    simBtn.addEventListener("click", async () => {
        const resultDiv = document.getElementById("simulatorResult");
        
        // Διαβάζουμε τους παίκτες που υπάρχουν μέσα στα slots του γηπέδου
        const slotPG = document.querySelector("#slot-pg .player-card");
        const slotSG = document.querySelector("#slot-sg .player-card");
        const slotSF = document.querySelector("#slot-sf .player-card");
        const slotPF = document.querySelector("#slot-pf .player-card");
        const slotC  = document.querySelector("#slot-c .player-card");

        if (!slotPG || !slotSG || !slotSF || !slotPF || !slotC) {
            resultDiv.innerHTML = `<span style="color: #e74c3c; font-size: 1.2rem; font-weight: bold;">ΛΕΙΠΟΥΝ ΠΑΙΚΤΕΣ! Πρέπει να τοποθετήσεις 5 παίκτες στο παρκέ.</span>`;
            return;
        }

        const p1 = slotPG.getAttribute("data-id");
        const p2 = slotSG.getAttribute("data-id");
        const p3 = slotSF.getAttribute("data-id");
        const p4 = slotPF.getAttribute("data-id");
        const p5 = slotC.getAttribute("data-id");
        
        const gameCode = document.getElementById("analyticsGameCodeInput") ? document.getElementById("analyticsGameCodeInput").value.trim() : "333";
        
        resultDiv.innerHTML = `<span style="color: #f39c12; font-size: 1.2rem; font-weight: bold;">Προσομοίωση αγώνα σε εξέλιξη... 🎲</span>`;

        try {
            // Ζητάμε τα δεδομένα από το API (για να δούμε αν υπάρχει χημεία)
            const data = await fetchSimulatorResult(p1, p2, p3, p4, p5, gameCode);
            const scenario = window.currentScenario;
            
            // 1. Υπολογισμός χρόνου και κατοχών
            const clockParts = scenario.clock.split(":");
            const remainingSeconds = parseInt(clockParts[0]) * 60 + parseInt(clockParts[1]);
            const numPossessions = Math.max(1, Math.ceil(remainingSeconds / 24)); // Μία κατοχή ανά ~24 δευτερόλεπτα

            let projectedPointsFor = 0;
            let projectedPointsAgainst = 0;
            let chemistryBonusMsg = "";

            // 2. Έλεγχος Χημείας: Έπαιξαν όντως μαζί στο ματς;
            let hasChemistry = false;
            if (data && !data.error && data.points_for !== undefined && data.points_for > 0) {
                hasChemistry = true;
                chemistryBonusMsg = `<br><span style="color: #2ecc71; font-size: 0.9rem;">✨ <strong>Chemistry Bonus:</strong> Αυτή η πεντάδα είχε παίξει μαζί στο πραγματικό ματς!</span>`;
            }

            // 3. Η Μεγάλη Αλλαγή: Υπολογισμός με Power Rating & Παράγοντα Τύχης (RNG)
            let expectedPoints = numPossessions * 1.1; // Βασική παραγωγή της ομάδας σου
            let oppExpectedPoints = numPossessions * 1.0; // Βασική παραγωγή του αντιπάλου

            // Ρίχνουμε "ζάρια" (Τύχη από -3 έως +3 πόντους)
            const luckDice = Math.floor(Math.random() * 7) - 3; 
            const oppLuckDice = Math.floor(Math.random() * 5) - 2; 

            // Προσθέτουμε τη Χημεία αν ισχύει
            const chemistryBonus = hasChemistry ? 3 : 0;

            projectedPointsFor = Math.max(0, Math.round(expectedPoints + luckDice + chemistryBonus));
            projectedPointsAgainst = Math.max(0, Math.round(oppExpectedPoints + oppLuckDice));

            // Boost αν το ματς τελειώνει στα επόμενα δευτερόλεπτα (Buzzer Beater)
            if (remainingSeconds <= 15 && projectedPointsFor === 0) {
                projectedPointsFor = (Math.random() > 0.5) ? 2 : 0; // 50% πιθανότητα για καλάθι
            }

            // 4. Υπολογισμός Τελικού Σκορ
            const finalUserScore = parseInt(scenario.user_score) + projectedPointsFor;
            const finalOppScore = parseInt(scenario.opp_score) + projectedPointsAgainst;

            // 5. Η Ετυμηγορία
            let resultMessage = "";
            let color = "";
            if (finalUserScore > finalOppScore) {
                resultMessage = " ΝΙΚΗ! Η πεντάδα έκανε το θαύμα της!";
                color = "#27ae60";
            } else if (finalUserScore < finalOppScore) {
                resultMessage = " ΗΤΤΑ... Ο ρυθμός της ομάδας δεν έφτανε.";
                color = "#e74c3c";
            } else {
                resultMessage = " ΠΑΡΑΤΑΣΗ! Το ματς έληξε ισόπαλο.";
                color = "#f39c12";
            }

            // 6. Εμφάνιση στον Χρήστη
            resultDiv.innerHTML = `
                <div style="background-color: #1a1a24; padding: 20px; border-radius: 10px; border: 2px solid ${color}; box-shadow: 0 4px 15px rgba(0,0,0,0.3);">
                    <div style="color: ${color}; font-size: 1.5rem; font-weight: bold; margin-bottom: 15px; text-transform: uppercase;">${resultMessage}</div>
                    <div style="font-size: 1.5rem; color: white;">
                        Τελικό Σκορ: <strong style="font-size: 2.5rem; color: ${color};">${finalUserScore} - ${finalOppScore}</strong>
                    </div>
                    <div style="color: #bdc3c7; font-size: 1rem; margin-top: 15px; background: #2c3e50; padding: 10px; border-radius: 6px;">
                        <strong>Ανάλυση Πρόβλεψης:</strong><br>
                        Στα <strong>${remainingSeconds} δευτερόλεπτα</strong> (${numPossessions} κατοχές), η ομάδα σου σκόραρε <strong>${projectedPointsFor}</strong> πόντους και δέχτηκε <strong>${projectedPointsAgainst}</strong>.
                        ${chemistryBonusMsg}
                    </div>
                </div>
            `;
        } catch (error) {
            console.error("Σφάλμα:", error);
            resultDiv.innerHTML = `<span style="color: #e74c3c; font-size: 1.2rem; font-weight: bold;">Προέκυψε σφάλμα στην προσομοίωση.</span>`;
        }
    });
}

// ==========================================
// ΛΟΓΙΚΗ ΓΙΑ ΤΟ "TRY GAME" ΚΑΙ "GAME" BUTTON
// ==========================================
const tryGameBtn = document.getElementById("tryGameBtn");
if (tryGameBtn) {
    tryGameBtn.addEventListener("click", async () => {
        const integratedSimulator = document.getElementById("integratedSimulator");
        const gameInstructions = document.getElementById("gameInstructions");
        const actualSimulatorUI = document.getElementById("actualSimulatorUI");
        const extraFilters = document.getElementById("extraFiltersContainer");
        const timeFilters = document.getElementById("timeFiltersContainer");
        const mainActionBtn = document.getElementById("mainActionBtn");
        
        // ----------------------------------------------------
        // ΦΑΣΗ 1: Μπαίνει στο Mode Οδηγιών (Πατώντας TRY GAME)
        // ----------------------------------------------------
        if (tryGameBtn.innerText.includes("TRY GAME")) {
            // 1. Κρύβουμε τα φίλτρα
            if (extraFilters) extraFilters.style.display = "none";
            if (timeFilters) timeFilters.style.display = "none";
            if (analyticsContent) analyticsContent.style.display = "none";
            if (analyticsTitle) analyticsTitle.style.display = "none";
            // 2. Αλλάζουμε το κουμπί της Αναζήτησης σε Έξοδο
            if (mainActionBtn) {
                mainActionBtn.innerText = "ΕΞΟΔΟΣ ΑΠΟ GAME";
                mainActionBtn.style.backgroundColor = "#c0392b"; 
            }

            // 3. Εμφανίζουμε ΜΟΝΟ τις οδηγίες
            if (integratedSimulator) {
                integratedSimulator.style.display = "block";
                if (gameInstructions) gameInstructions.style.display = "block";
                if (actualSimulatorUI) actualSimulatorUI.style.display = "none";
                integratedSimulator.scrollIntoView({ behavior: 'smooth', block: 'start' });
            }

            // 4. Αλλάζουμε το κείμενο σε σκέτο GAME για το επόμενο κλικ
            tryGameBtn.innerText = " GAME";
            return; // Σταματάμε εδώ την εκτέλεση!
        }

        // ----------------------------------------------------
        // ΦΑΣΗ 2: Ξεκινάει η Προσομοίωση (Πατώντας GAME)
        // ----------------------------------------------------
        if (tryGameBtn.innerText.includes("GAME")) {
            // 1. Κρύβουμε τις οδηγίες και το ίδιο το κουμπί
            if (gameInstructions) gameInstructions.style.display = "none";
            tryGameBtn.style.display = "none"; 
            
            // 2. Εμφανίζουμε το παρκέ (UI)
            if (actualSimulatorUI) actualSimulatorUI.style.display = "block";

            // 3. Ξεκινάμε το Fetching του παιχνιδιού
            const selectedSeason = document.getElementById("seasonSelect") ? document.getElementById("seasonSelect").value : "";
            const simMatchupTitle = document.getElementById("simMatchupTitle");
            const simScenarioText = document.getElementById("simScenarioText");
            const rosterPool = document.getElementById("rosterPool");

            if (simMatchupTitle) simMatchupTitle.innerText = "Φόρτωση κρίσιμου σημείου...";
            if (simScenarioText) simScenarioText.innerText = "Ο διαιτητής σφυρίζει Timeout...";

            document.querySelectorAll('.slot').forEach(slot => {
                const existingCard = slot.querySelector('.player-card');
                if (existingCard) existingCard.remove();
                if (!slot.textContent.trim()) slot.textContent = slot.getAttribute("data-position");
            });
            document.getElementById("simulatorResult").innerHTML = "";

            const scenario = await fetchSimulatorScenario(selectedSeason?.trim()? selectedSeason: ["E2023", "E2024", "E2025"][Math.floor(Math.random() * 3)]);

            if (scenario && !scenario.error) {
                window.currentScenario = scenario;
                const gameInput = document.getElementById("analyticsGameCodeInput");
                if (gameInput) gameInput.value = scenario.game_code;
                const seasonSelect = document.getElementById("seasonSelect");
                const userSelectedText = seasonSelect && seasonSelect.selectedIndex >= 0 
                                         ? seasonSelect.options[seasonSelect.selectedIndex].text 
                                         : "Άγνωστη Επιλογή";
                if (simMatchupTitle) simMatchupTitle.innerText = `CRUNCH TIME: Είσαι ο Προπονητής της ${scenario.user_team}!`;
                if (simScenarioText) {
                    simScenarioText.innerHTML = `
                        !-- ΝΕΟ: Εμφάνιση των λεπτομερειών της σεζόν -->
                        <div style="color: #f39c12; font-size: 0.9rem; margin-bottom: 10px;">
                            <em>Φίλτρο Αναζήτησης: <strong>${userSelectedText}</strong> | Σεζόν Αγώνα: <strong>${scenario.game_season_name}</strong></em>
                        </div>
                        <strong>Αντίπαλος:</strong> ${scenario.opponent} | <strong>4th Quarter</strong> | <strong>Χρόνος:</strong> ${scenario.clock}<br>
                        <strong>Σκορ:</strong> ${scenario.user_score} - ${scenario.opp_score} (Υπέρ - Κατά)<br><br>
                        Έχεις Timeout! Τοποθέτησε 5 παίκτες από τον πάγκο (ή από τις Top Lineups) στο παρκέ!
                    `;
                }

                if (rosterPool) {
                    rosterPool.innerHTML = ""; 
                    scenario.roster.forEach(player => {
                        const card = document.createElement("div");
                        card.className = "player-card";
                        card.draggable = true;
                        card.setAttribute("data-id", player.id);

                        card.innerHTML = `
                            <img id="sim_img_${player.id}" src="https://www.euroleaguebasketball.net/media/com_easysocial/avatars/users/default_avatar.png" style="pointer-events: none;">
                            <span id="sim_name_${player.id}" style="pointer-events: none;">Φόρτωση...</span>
                        `;
                        rosterPool.appendChild(card);
                        fetchPlayerDetailsForCard(player.id, `sim_name_${player.id}`, `sim_img_${player.id}`);

                        card.addEventListener('dragstart', function() {
                            window.draggedCard = this;
                            setTimeout(() => this.style.opacity = '0.5', 0);
                        });
                        card.addEventListener('dragend', function() {
                            setTimeout(() => { this.style.opacity = '1'; window.draggedCard = null; }, 0);
                        });
                    });
                }
            } else {
                if (simMatchupTitle) simMatchupTitle.innerText = "Σφάλμα Σεναρίου";
                if (simScenarioText) simScenarioText.innerText = "Δεν βρέθηκαν κατάλληλα Timeouts στη βάση για αυτή τη σεζόν.";
            }
        }
    });
}