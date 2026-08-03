// main.js

// --- DOM ELEMENTS ---
const mainModeSelect = document.getElementById("mainModeSelect");
const globalSeasonSelect = document.getElementById("globalSeasonSelect");
const globalGameSelect = document.getElementById("globalGameSelect");
const optAllSeasons = document.getElementById("optAllSeasons");
const playerSelectInput = document.getElementById("playerSelect");

const shotFiltersForm = document.getElementById("shotFiltersForm");
const mainActionBtn = document.getElementById("mainActionBtn");

// UI Sections
const euroChartWrapper = document.getElementById("euroChartWrapper");
const videoSearchWrapper = document.getElementById("videoSearchWrapper");
const analyticsWrapper = document.getElementById("analyticsWrapper");

const courtContainer = document.getElementById("courtContainer");
const mediaContainer = document.getElementById("videoContainer").parentNode; 

// Euroleague Mode Containers
const euroCenterArea = document.querySelector("#euroChartWrapper .euro-center-area");
const homePlayersContainer = document.getElementById("homePlayersContainer");
const roadPlayersContainer = document.getElementById("roadPlayersContainer");

// Video Mode Containers
const videoCenterArea = document.querySelector("#videoSearchWrapper .euro-center-area");
const videoHomeLineup = document.getElementById("videoHomeLineup");
const videoRoadLineup = document.getElementById("videoRoadLineup");

// Analytics Containers
const analyticsContent = document.getElementById("analyticsContent");
const analyticsTitle = document.getElementById("analyticsTitle");

window.homePlayersSet = new Set();
window.roadPlayersSet = new Set();
window.currentShotsData = []; 

// --- 1. ΕΝΑΛΛΑΓΗ ΛΕΙΤΟΥΡΓΙΑΣ (MENU) ---
mainModeSelect.addEventListener("change", (e) => {
    const mode = e.target.value;

    euroChartWrapper.style.display = "none";
    videoSearchWrapper.style.display = "none";
    analyticsWrapper.style.display = "none";
    
    analyticsContent.innerHTML = "<div style='grid-column: 1 / -1; text-align: center; color: #777; font-style: italic; font-size: 1.1rem;'>Πάτα 'ΕΚΤΕΛΕΣΗ ΑΝΑΛΥΣΗΣ' για να δεις τα δεδομένα...</div>";
    
    if (mode === "top-lineups") analyticsTitle.innerText = "Top Lineups";
    else if (mode === "second-chance") analyticsTitle.innerText = "Second Chance Points";
    else if (mode === "assist-duos") analyticsTitle.innerText = "Top Assist Duos";
    else if (mode === "fouls-drawn") analyticsTitle.innerText = "Fouls Drawn Gravity";
    else if (mode === "defensive-anchors") analyticsTitle.innerText = "Defensive Anchors";
    else analyticsTitle.innerText = "Αποτελέσματα Ανάλυσης";
    
    const shooterFilter = document.getElementById("defensiveFiltersContainer");
    if (shooterFilter) shooterFilter.style.display = (mode === "defensive-anchors") ? "block" : "none";

    const foulsFilter = document.getElementById("foulsFiltersContainer");
    if (foulsFilter) foulsFilter.style.display = (mode === "fouls-drawn") ? "block" : "none";
    
    if (mode === "euro-chart") {
        optAllSeasons.style.display = "none"; 
        if(globalSeasonSelect.value === "ALL") {
            globalSeasonSelect.value = "E2023";  
            loadGamesForSeason("E2023");
        }
        euroChartWrapper.style.display = "flex";
        shotFiltersForm.style.display = "block";
        euroCenterArea.insertBefore(courtContainer, euroCenterArea.querySelector('.legend'));
        mainActionBtn.innerText = "ΑΝΑΖΗΤΗΣΗ ΣΟΥΤ (GAME)";
    } 
    else if (mode === "video-shots") {
        optAllSeasons.style.display = "block"; 
        videoSearchWrapper.style.display = "flex";
        shotFiltersForm.style.display = "block";
        videoCenterArea.insertBefore(courtContainer, videoCenterArea.firstChild);
        videoCenterArea.appendChild(mediaContainer);
        mainActionBtn.innerText = "ΑΝΑΖΗΤΗΣΗ ΣΟΥΤ (VIDEO)";
    } 
    else {
        optAllSeasons.style.display = "block"; 
        analyticsWrapper.style.display = "block";
        shotFiltersForm.style.display = "none";
        mainActionBtn.innerText = "ΕΚΤΕΛΕΣΗ ΑΝΑΛΥΣΗΣ";
    }

    if(typeof window.resizeCourt === "function") window.resizeCourt();
});

// --- 2. ΦΟΡΤΩΣΗ ΑΓΩΝΩΝ ---
async function loadGamesForSeason(seasonCode) {
    if (!globalGameSelect) return;
    
    if (seasonCode === "ALL") {
        globalGameSelect.innerHTML = "<option value=''>-- Όλα τα Παιχνίδια --</option>";
        globalGameSelect.disabled = true;
        return;
    }

    globalGameSelect.innerHTML = "<option value=''>Φόρτωση αγώνων...</option>";
    globalGameSelect.disabled = true;

    try {
        const response = await fetch(`${API_BASE_URL}/api/games?season_code=${seasonCode}`);
        const data = await response.json();
        
        globalGameSelect.innerHTML = "<option value=''>-- Επίλεξε Αγώνα --</option>";
        if (data.games && data.games.length > 0) {
            data.games.forEach(game => {
                const option = document.createElement("option");
                option.value = game.gameCode;
                option.textContent = `[${game.gameCode}] ${game.matchup}`;
                globalGameSelect.appendChild(option);
            });
            globalGameSelect.disabled = false;
        }
    } catch (error) {
        globalGameSelect.innerHTML = "<option value=''>Σφάλμα φόρτωσης</option>";
    }
}

globalSeasonSelect.addEventListener("change", (e) => loadGamesForSeason(e.target.value));


// === ΚΕΝΤΡΙΚΟΣ "ΑΤΡΩΤΟΣ" ΕΛΕΓΧΟΣ ΚΛΙΚ ΓΙΑ ΟΛΑ ΤΑ CHECKBOXES (EVENT DELEGATION) ===
document.addEventListener("change", (e) => {
    // Αν το κλικ έγινε πάνω σε ΟΠΟΙΟΔΗΠΟΤΕ φίλτρο (Quarters, Παίκτες, Τύποι Σουτ)
    if (e.target.classList.contains('quarter-cb') || 
        e.target.classList.contains('player-cb') || 
        e.target.classList.contains('shot-filter-cb') || 
        e.target.closest('.roster-sub')) {
        
        // Ειδική λογική για τα "Select All"
        if (e.target.closest('.roster-sub')) {
            const rosterContainer = e.target.closest('.euro-roster').querySelector('.players-list');
            if (rosterContainer) {
                rosterContainer.querySelectorAll('.player-cb').forEach(cb => cb.checked = e.target.checked);
            }
        }
        
        // Τρέξε αμέσως τη Μηχανή Φιλτραρίσματος
        if (typeof window.applyChartFilters === "function") {
            window.applyChartFilters();
        }
    }
});


// === ΔΥΝΑΜΙΚΗ ΔΗΜΙΟΥΡΓΙΑ QUARTERS ΜΕ ΤΟ ΣΚΟΡ ΤΟΥΣ ===
function buildDynamicQuarters(shotsData) {
    const quartersBars = document.querySelectorAll('.quarters-bar');
    if (quartersBars.length === 0) return;

    const quartersMap = new Map();
    // Προκατασκευάζουμε πάντα τα 4 βασικά δεκάλεπτα
    ["1st", "2nd", "3rd", "4th"].forEach(q => quartersMap.set(q, { maxHome: 0, maxRoad: 0 }));

    shotsData.forEach(shot => {
        console.log("Processing shot:", shot);
        if (shot.quarter) {
            if (!quartersMap.has(shot.quarter)) {
                quartersMap.set(shot.quarter, { maxHome: 0, maxRoad: 0 });
            }
            const qData = quartersMap.get(shot.quarter);
            if (shot.homeScore !== undefined && shot.homeScore > 0) qData.maxHome = Math.max(qData.maxHome, shot.homeScore);
            if (shot.roadScore !== undefined && shot.roadScore > 0) qData.maxRoad = Math.max(qData.maxRoad, shot.roadScore);
        }
    });

    const order = ["1st", "2nd", "3rd", "4th", "OT", "2OT", "3OT", "4OT", "5OT"];
    console.log("Quarters Map:", quartersMap);
    const uniqueQuarters = Array.from(quartersMap.keys()).sort((a, b) => order.indexOf(a) - order.indexOf(b));

    quartersBars.forEach(bar => {
        // Διατηρούμε την κατάσταση αν ήταν ήδη τσεκαρισμένα
        const previouslyChecked = new Set();
        bar.querySelectorAll('.quarter-cb:checked').forEach(cb => previouslyChecked.add(cb.value));
        const hasPrevious = previouslyChecked.size > 0;

        bar.innerHTML = "";
        uniqueQuarters.forEach(q => {
            const qData = quartersMap.get(q);
            
            // Το σκορ θα δείχνει "-" μέχρι να κάνεις import τα νέα δεδομένα από το parser.py!
            let scoreLabel = `<span style="font-size: 0.65rem; color: #777; margin-top:2px;">-</span>`;
            if (qData && (qData.maxHome > 0 || qData.maxRoad > 0)) {
                scoreLabel = `<span style="font-size: 0.65rem; color: #777; margin-top:2px; font-weight:bold;">${qData.maxHome} - ${qData.maxRoad}</span>`;
            }

            const isChecked = hasPrevious ? previouslyChecked.has(q) : true;

            const qBox = document.createElement("div");
            qBox.className = "quarter-box";
            qBox.style.cssText = "display:flex; flex-direction:column; align-items:center; justify-content:center; padding:4px 10px;";
            
            qBox.innerHTML = `
                <div style="display:flex; align-items:center; gap:5px;">
                    <span>${q.toUpperCase()}</span> 
                    <input type="checkbox" class="euro-checkbox quarter-cb" value="${q}" ${isChecked ? 'checked' : ''}>
                </div>
                ${scoreLabel}
            `;
            bar.appendChild(qBox);
        });
    });
}

// Η Μηχανή Φιλτραρίσματος
window.applyChartFilters = function() {
    if (!window.currentShotsData || window.currentShotsData.length === 0) return;
    const mode = mainModeSelect.value;
    
    if (mode !== "euro-chart" && mode !== "video-shots") {
        if (typeof window.drawShots === "function") window.drawShots(window.currentShotsData);
        return;
    }

    // ΠΟΛΥ ΣΗΜΑΝΤΙΚΟ: Βρίσκουμε την οθόνη που είναι ΑΝΟΙΧΤΗ αυτή τη στιγμή!
    const activeWrapper = mode === "euro-chart" ? document.getElementById("euroChartWrapper") : document.getElementById("videoSearchWrapper");
    if (!activeWrapper) return;

    // 1. Quarters Filter (Μόνο από την ανοιχτή οθόνη)
    const activeQuarters = new Set();
    activeWrapper.querySelectorAll('.quarter-cb:checked').forEach(cb => activeQuarters.add(cb.value));

    // 2. Players Filter (Μόνο από την ανοιχτή οθόνη)
    const activePlayers = new Set();
    activeWrapper.querySelectorAll('.player-cb:checked').forEach(cb => activePlayers.add(cb.value));

    // 3. ΔΙΑΒΑΣΜΑ ΤΩΝ ΔΙΑΚΟΠΤΩΝ (Μόνο από την ανοιχτή οθόνη)
    const homeFilters = {
        fastbreak: activeWrapper.querySelector('.home-filter[data-type="fastbreak"]')?.checked ?? true,
        turnover: activeWrapper.querySelector('.home-filter[data-type="turnover"]')?.checked ?? true,
        secondchance: activeWrapper.querySelector('.home-filter[data-type="secondchance"]')?.checked ?? true,
        pt2: activeWrapper.querySelector('.home-filter[data-type="2pt"]')?.checked ?? true,
        pt3: activeWrapper.querySelector('.home-filter[data-type="3pt"]')?.checked ?? true,
    };

    const roadFilters = {
        fastbreak: activeWrapper.querySelector('.road-filter[data-type="fastbreak"]')?.checked ?? true,
        turnover: activeWrapper.querySelector('.road-filter[data-type="turnover"]')?.checked ?? true,
        secondchance: activeWrapper.querySelector('.road-filter[data-type="secondchance"]')?.checked ?? true,
        pt2: activeWrapper.querySelector('.road-filter[data-type="2pt"]')?.checked ?? true,
        pt3: activeWrapper.querySelector('.road-filter[data-type="3pt"]')?.checked ?? true,
    };

    // 4. ΚΕΝΤΡΙΚΟ ΦΙΛΤΡΑΡΙΣΜΑ
    const filteredShots = window.currentShotsData.filter(shot => {
        const playerMatch = activePlayers.has(shot.playerName);
        const quarterMatch = !shot.quarter || activeQuarters.has(shot.quarter);
        
        if (!playerMatch || !quarterMatch) return false;

        let isHome = window.homePlayersSet && window.homePlayersSet.has(shot.playerName);
        const filters = isHome ? homeFilters : roadFilters;

        const is3P = shot.action_type?.includes("ThreePoint") || shot.is3P === true; 
        const is2P = !is3P;

        let passesTypeFilter = true;
        if (is3P && !filters.pt3) passesTypeFilter = false;
        if (is2P && !filters.pt2) passesTypeFilter = false;
        if (shot.isFastBreak && !filters.fastbreak) passesTypeFilter = false;
        if (shot.isFromTurnover && !filters.turnover) passesTypeFilter = false;
        if (shot.isSecondChance && !filters.secondchance) passesTypeFilter = false;

        return passesTypeFilter;
    });

    if (typeof window.drawShots === "function") window.drawShots(filteredShots);
};

// --- 3. ΚΟΥΜΠΙ: ΑΝΑΖΗΤΗΣΗ ΣΟΥΤ Ή ΑΝΑΛΥΣΗ ---
document.addEventListener("DOMContentLoaded", () => {
    loadGamesForSeason(globalSeasonSelect.value);
});

mainActionBtn.addEventListener("click", async () => {
    const mode = mainModeSelect.value;
    const selectedSeason = globalSeasonSelect.value;
    const selectedGame = globalGameSelect.value.trim() || null;
    const selectedPlayer = playerSelectInput ? playerSelectInput.value.trim() : null;
    const selectedAssistant = document.getElementById("assistSelect") ? document.getElementById("assistSelect").value : null;
    
    let filterType = document.getElementById("extraFilterType") ? document.getElementById("extraFilterType").value : null;
    let filterId = document.getElementById("extraFilterId") ? document.getElementById("extraFilterId").value : null;
    const quarter = document.getElementById("quarterSelectAnalytics") ? document.getElementById("quarterSelectAnalytics").value : null;
    const minStart = document.getElementById("minStart") ? document.getElementById("minStart").value : null;
    const minEnd = document.getElementById("minEnd") ? document.getElementById("minEnd").value : null;
    
    let fouledId = document.getElementById("fouledIdInput") ? document.getElementById("fouledIdInput").value.trim() : null;
    let foulingId = document.getElementById("foulingIdInput") ? document.getElementById("foulingIdInput").value.trim() : null;
    let shooterId = document.getElementById("shooterIdInput") ? document.getElementById("shooterIdInput").value.trim() : null;
    let blockerId = document.getElementById("blockerIdInput") ? document.getElementById("blockerIdInput").value.trim() : null;

    let secondChancePlayer = null; 
    
    if (selectedPlayer && mode !== "euro-chart" && mode !== "video-shots") {
        if (mode === "top-lineups") { if (!filterId) { filterId = selectedPlayer; filterType = "on_court"; } } 
        else if (mode === "fouls-drawn") { if (!fouledId) fouledId = selectedPlayer; } 
        else if (mode === "defensive-anchors") { if (!blockerId) blockerId = selectedPlayer; }
        else if (mode === "second-chance") { secondChancePlayer = selectedPlayer; }
    }

    if (mode === "euro-chart" || mode === "video-shots") {
        const shots = await fetchFilteredShots(selectedPlayer, selectedAssistant, selectedGame, selectedSeason, filterType, filterId, quarter, minStart, minEnd);
        window.currentShotsData = shots;

        // Δημιουργία δυναμικών Quarters με βάση τα δεδομένα του αγώνα
        buildDynamicQuarters(shots);

        if (selectedGame && selectedSeason !== "ALL") {
            try {
                const opt = globalGameSelect.options[globalGameSelect.selectedIndex];
                if (opt && opt.text.includes("vs")) {
                    const matchText = opt.text.includes("] ") ? opt.text.split("] ")[1] : opt.text;
                    const teams = matchText.split(/vs/i);
                    
                    const homeTeamName = (teams[0] || "HOME").trim() || "HOME";
                    const roadTeamName = (teams[1] || "ROAD").trim() || "ROAD";
                    
                    document.querySelectorAll('#txtHomeTeamName, #txtHomeTeamName2, #txtHomeTeamName3, #txtHomeTeamName4, #txtHomeTeamName5').forEach(el => el.innerText = homeTeamName.toUpperCase());
                    document.querySelectorAll('#txtRoadTeamName, #txtRoadTeamName2, #txtRoadTeamName3, #txtRoadTeamName4, #txtRoadTeamName5').forEach(el => el.innerText = roadTeamName.toUpperCase());
                    document.getElementById("uiHomeTeam").innerText = homeTeamName.substring(0,3).toUpperCase();
                    document.getElementById("uiRoadTeam").innerText = roadTeamName.substring(0,3).toUpperCase();
                    
                    // Αλλαγή των Titles αν υπάρχουν (homeTeamTitle)
                    const homeTitleEl = document.getElementById("homeTeamTitle");
                    if (homeTitleEl) homeTitleEl.innerText = homeTeamName.toUpperCase();
                    const roadTitleEl = document.getElementById("roadTeamTitle");
                    if (roadTitleEl) roadTitleEl.innerText = roadTeamName.toUpperCase();
                }

                const response = await fetch(`${API_BASE_URL}/api/game/lineups?game_code=${selectedGame}&season_code=${selectedSeason}`);
                const data = await response.json();

                window.homePlayersSet.clear();
                window.roadPlayersSet.clear();
                window.homeRosterDetails = [];
                window.roadRosterDetails = [];

                data.lineups.forEach(lineup => {
                    if (!lineup.players) return;
                    lineup.players.split("@@").forEach(pInfo => {
                        const parts = pInfo.split("|");
                        const pId = parts[0];
                        const pName = parts[1] || parts[0];
                        // Διαβάζουμε την εικόνα κατευθείαν από το ίδιο πακέτο!
                        const pImg = (parts[2] && parts[2] !== "NO_IMG") ? parts[2] : null;
                        
                        if (lineup.teamType === "home") {
                            window.homePlayersSet.add(pName); 
                            if (!window.homeRosterDetails.some(x => x.id === pId)) {
                                window.homeRosterDetails.push({id: pId, name: pName, img: pImg});
                            }
                        } else if (lineup.teamType === "road") {
                            window.roadPlayersSet.add(pName);
                            if (!window.roadRosterDetails.some(x => x.id === pId)) {
                                window.roadRosterDetails.push({id: pId, name: pName, img: pImg});
                            }
                        }
                    });
                });

                const homeScoreEl = document.getElementById("uiScoreHome");
                if (homeScoreEl) homeScoreEl.innerText = data.homeScore || 0;
                
                const roadScoreEl = document.getElementById("uiScoreRoad");
                if (roadScoreEl) roadScoreEl.innerText = data.roadScore || 0;
                
                buildRoster(window.homeRosterDetails, homePlayersContainer, "home");
                buildRoster(window.roadRosterDetails, roadPlayersContainer, "road");
                
                const hsa = document.querySelector('.euro-roster.home .roster-sub input');
                if (hsa) hsa.checked = true;
                const rsa = document.querySelector('.euro-roster.road .roster-sub input');
                if (rsa) rsa.checked = true;

            } catch (error) { console.error("Σφάλμα στα lineups:", error); }
        }

        applyChartFilters();
    } 
    else {
        analyticsContent.innerHTML = "<div style='grid-column: 1 / -1; text-align: center; color: #ea5314; font-weight: bold;'>Φόρτωση δεδομένων...</div>";
        
        try {
            if (mode === "top-lineups") {
                const lineups = await fetchTopLineups(filterType, filterId, quarter, minStart, minEnd, selectedGame, selectedSeason);
                renderTopLineups(lineups);
            } 
            else if (mode === "second-chance") {
                const players = await fetchSecondChancePoints(filterType, filterId, quarter, minStart, minEnd, selectedGame, selectedSeason, secondChancePlayer);        
                renderPlayerCards(players, "total_points", "ΠΟΝΤΟΙ", "#27ae60");
            } 
            else if (mode === "assist-duos") {
                const duos = await fetchTopAssistDuos(filterType, filterId, quarter, minStart, minEnd, selectedGame, selectedSeason);        
                renderAssistDuos(duos);
            }
            else if (mode === "fouls-drawn") {
                const players = await fetchFoulsDrawn(filterType, filterId, quarter, minStart, minEnd, fouledId, foulingId, selectedGame, selectedSeason);
                renderPlayerCards(players, "total_fouls_drawn", "ΚΕΡΔΙΣΜΕΝΑ ΦΑΟΥΛ", "#e74c3c");
            } 
            else if (mode === "defensive-anchors") {
                const players = await fetchDefensiveAnchors(filterType, filterId, quarter, minStart, minEnd, shooterId, blockerId, selectedGame, selectedSeason);        
                renderPlayerCards(players, "total_blocks", "ΜΠΛΟΚ", "#34495e");
            }
        } catch (error) {
            analyticsContent.innerHTML = "<div style='grid-column: 1 / -1; color: red;'>Σφάλμα φόρτωσης.</div>";
        }
    }
});

// --- CURRENT LINEUPS ΓΙΑ ΤΟ VIDEO MODE ---
window.updateVideoLineups = async function(homeUrl, roadUrl) {
    await buildCurrentLineup(homeUrl, videoHomeLineup);
    await buildCurrentLineup(roadUrl, videoRoadLineup);
};

async function buildCurrentLineup(url, container) {
    if (!url || !url.includes("Lineup_")) {
        container.innerHTML = "<div style='color:#999;text-align:center;'>Μη διαθέσιμη πεντάδα</div>";
        return;
    }
    container.innerHTML = "<div style='text-align:center;'>Φόρτωση...</div>";
    const parts = url.split("Lineup_")[1].split("_");
    container.innerHTML = "";
    
    parts.forEach(playerId => {
        if(!playerId) return;
        const row = document.createElement("div");
        row.className = "player-row";
        const tempNameId = `vid_name_${playerId}_${Math.floor(Math.random()*1000)}`;
        const tempImgId = `vid_img_${playerId}_${Math.floor(Math.random()*1000)}`;
        row.innerHTML = `
            <img src="https://upload.wikimedia.org/wikipedia/commons/8/89/Portrait_Placeholder.png" class="player-photo" id="${tempImgId}">
            <div class="player-info">
                <span class="player-name" id="${tempNameId}">...</span>
            </div>
        `;
        container.appendChild(row);
        fetchPlayerDetails(playerId, tempNameId, tempImgId);
    });
}

function buildRoster(playersArray, container, side) {
    container.innerHTML = "";
    
    playersArray.sort((a, b) => a.name.localeCompare(b.name)).forEach((player, index) => {
        const row = document.createElement("div");
        row.className = "player-row";
        
        // Χρησιμοποιούμε την εικόνα που ήρθε από το πρώτο request!
        const imgUrl = player.img || "https://upload.wikimedia.org/wikipedia/commons/8/89/Portrait_Placeholder.png";
        
        const cbHtml = `<input type="checkbox" class="euro-checkbox player-cb" value="${player.name}" checked>`;

        if (side === "home") {
            row.innerHTML = `<img src="${imgUrl}" class="player-photo"><div class="player-info"><span class="player-name">${player.name}</span></div>${cbHtml}`;
        } else {
            row.innerHTML = `${cbHtml}<img src="${imgUrl}" class="player-photo"><div class="player-info" style="align-items: flex-end; text-align: right;"><span class="player-name">${player.name}</span></div>`;
        }
        container.appendChild(row);
        
        // ΔΙΑΓΡΑΦΗΚΕ το fetchPlayerDetails από εδώ. Το load πλέον είναι στιγμιαίο!
    });
}

async function fetchPlayerDetails(playerId, htmlElementId, imgElementId) {
    try {
        if (playerId.includes(" ") || playerId.includes(",")) {
            let displayName = playerId;
            if (displayName.includes(",")) displayName = displayName.split(",")[0]; 
            const el = document.getElementById(htmlElementId);
            if(el) el.innerText = displayName;
            return;
        }

        const response = await fetch(`${API_BASE_URL}/api/player?player=${playerId}`);
        const data = await response.json();
        
        if (data && data.player) {
            if (data.player.name) {
                let displayName = data.player.name;
                if (displayName.includes(",")) displayName = displayName.split(",")[0]; 
                const el = document.getElementById(htmlElementId);
                if (el) el.innerText = displayName;
            }
            if (data.player.img && imgElementId) {
                const imgEl = document.getElementById(imgElementId);
                if (imgEl) imgEl.src = data.player.img;
            }
        } else {
            const el = document.getElementById(htmlElementId);
            if (el) el.innerText = playerId;
        }
    } catch (err) {
        const el = document.getElementById(htmlElementId);
        if (el) el.innerText = playerId;
    }
}

// --- Συναρτήσεις Render Analytics ---
function renderPlayerCards(data, statKey, statLabel, color) {
    if (!data || data.length === 0) { analyticsContent.innerHTML = "<div>Δεν βρέθηκαν δεδομένα.</div>"; return; }
    analyticsContent.innerHTML = ""; 
    data.forEach((item, index) => {
        const card = document.createElement("div");
        card.style.cssText = `background:#fff; padding:20px; border-radius:12px; border-top:5px solid ${color}; display:flex; align-items:center; justify-content:space-between; box-shadow:0 4px 15px rgba(0,0,0,0.05);`;
        card.innerHTML = `
            <div style="font-weight:900; font-size:1.5rem; color:#ccc; width:40px;">#${index + 1}</div>
            <div style="display:flex; flex-direction:column; align-items:center; flex:1;">
                <img src="https://upload.wikimedia.org/wikipedia/commons/8/89/Portrait_Placeholder.png" style="width:70px; height:70px; object-fit:cover; border-radius:50%; border:3px solid ${color};" id="img_${item.player_id}_${index}">
                <span style="font-size:0.9rem; margin-top:8px; font-weight:700;" id="name_${item.player_id}_${index}">...</span>
            </div>
            <div style="display:flex; flex-direction:column; align-items:center;">
                <span style="font-size:2.2rem; color:${color}; font-weight:900;">${item[statKey]}</span>
                <span style="font-size:0.75rem; font-weight:bold; color:#555;">${statLabel}</span>
            </div>
        `;
        analyticsContent.appendChild(card);
        fetchPlayerDetails(item.player_id, `name_${item.player_id}_${index}`, `img_${item.player_id}_${index}`);
    });
}

function renderAssistDuos(duos) {
    if (!duos || duos.length === 0) { analyticsContent.innerHTML = "<div>Δεν βρέθηκαν δεδομένα.</div>"; return; }
    analyticsContent.innerHTML = ""; 
    duos.forEach((duo, index) => {
        const card = document.createElement("div");
        card.style.cssText = "background:#fff; padding:20px; border-radius:12px; border-top:5px solid #2b528a; display:flex; align-items:center; justify-content:space-between;";
        card.innerHTML = `
            <div style="font-weight:900; font-size:1.5rem; color:#ccc; width:40px;">#${index + 1}</div>
            <div style="display:flex; flex-direction:column; align-items:center; flex:1;">
                <img src="https://upload.wikimedia.org/wikipedia/commons/8/89/Portrait_Placeholder.png" style="width:60px; height:60px; object-fit:cover; border-radius:50%;" id="img_passer_${duo.passer_id}_${index}">
                <span style="font-size:0.85rem; font-weight:700;" id="name_passer_${duo.passer_id}_${index}">...</span>
            </div>
            <div style="display:flex; flex-direction:column; align-items:center; padding:0 15px;">
                <span style="font-size:1.8rem; color:#ea5314; font-weight:900;">${duo.total_assists}</span><span>➔</span>
            </div>
            <div style="display:flex; flex-direction:column; align-items:center; flex:1;">
                <img src="https://upload.wikimedia.org/wikipedia/commons/8/89/Portrait_Placeholder.png" style="width:60px; height:60px; object-fit:cover; border-radius:50%;" id="img_scorer_${duo.scorer_id}_${index}">
                <span style="font-size:0.85rem; font-weight:700;" id="name_scorer_${duo.scorer_id}_${index}">...</span>
            </div>
        `;
        analyticsContent.appendChild(card);
        fetchPlayerDetails(duo.passer_id, `name_passer_${duo.passer_id}_${index}`, `img_passer_${duo.passer_id}_${index}`);
        fetchPlayerDetails(duo.scorer_id, `name_scorer_${duo.scorer_id}_${index}`, `img_scorer_${duo.scorer_id}_${index}`);
    });
}

function renderTopLineups(lineups) {
    if (!lineups || lineups.length === 0) { analyticsContent.innerHTML = "<div>Δεν βρέθηκαν δεδομένα.</div>"; return; }
    analyticsContent.innerHTML = ""; 
    lineups.forEach((lineup, index) => {
        const card = document.createElement("div");
        card.style.cssText = "background:#fff; padding:20px; border-radius:12px; border-top:5px solid #ea5314;";
        const containerId = `lineup_container_${index}`;
        card.innerHTML = `
            <div style="display:flex; justify-content:space-between; border-bottom:1px solid #eee; padding-bottom:10px; margin-bottom:15px;">
                <span style="font-weight:900; font-size:1.2rem; color:#ccc;">#${index + 1}</span>
                <span style="font-weight:bold; color:#2b528a;">Σύνολο: <span style="color:#ea5314; font-size:1.3rem;">${lineup.total_points}</span> πόντοι</span>
            </div>
            <div id="${containerId}" style="display:flex; justify-content:space-around; flex-wrap:wrap;"></div>
        `;
        analyticsContent.appendChild(card);
        const playersContainer = document.getElementById(containerId);
        lineup.players.forEach((playerId) => {
            if (!playerId) return;
            const playerDiv = document.createElement("div");
            playerDiv.style.cssText = "display:flex; flex-direction:column; align-items:center; width:18%;";
            playerDiv.innerHTML = `<img src="https://upload.wikimedia.org/wikipedia/commons/8/89/Portrait_Placeholder.png" style="width:50px; height:50px; object-fit:cover; border-radius:50%;" id="img_${playerId}_${index}"><span style="font-size:0.7rem; font-weight:700; text-align:center; word-wrap:break-word;" id="name_${playerId}_${index}">...</span>`;
            playersContainer.appendChild(playerDiv);
            fetchPlayerDetails(playerId, `name_${playerId}_${index}`, `img_${playerId}_${index}`);
        });
    });
}