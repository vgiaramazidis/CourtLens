// main.js

// --- DOM ELEMENTS ---
const mainModeSelect = document.getElementById("mainModeSelect");
const globalSeasonSelect = document.getElementById("globalSeasonSelect");
const globalGameSelect = document.getElementById("globalGameSelect");
const optSelectSeason = document.getElementById("optSelectSeason");
const optAllSeasons = document.getElementById("optAllSeasons");
const playerSelectInput = document.getElementById("playerSelect");

const shotFiltersForm = document.getElementById("shotFiltersForm");
const mainActionBtn = document.getElementById("mainActionBtn");
const playerFilterGroup = document.getElementById("playerFilterGroup");
const shotFiltersDivider = document.getElementById("shotFiltersDivider");
const extraFiltersContainer = document.getElementById("extraFiltersContainer");
const timeFiltersContainer = document.getElementById("timeFiltersContainer");

// UI Sections
const shotSearchWrapper = document.getElementById("shotSearchWrapper");
const analyticsWrapper = document.getElementById("analyticsWrapper");

// Shared shot mode containers
const shotCenterArea = document.getElementById("shotCenterArea");
const homePlayersContainer = document.getElementById("homePlayersContainer");
const roadPlayersContainer = document.getElementById("roadPlayersContainer");

// Current lineups shown in Euro Chart mode
const currentHomeLineup = document.getElementById("currentHomeLineup");
const currentRoadLineup = document.getElementById("currentRoadLineup");

// Analytics Containers
const analyticsContent = document.getElementById("analyticsContent");
const analyticsTitle = document.getElementById("analyticsTitle");
const aiPlaySearchInput = document.getElementById("aiPlaySearchInput");
const aiPlaySearchButton = document.getElementById("aiPlaySearchButton");
const aiPlaySearchResult = document.getElementById("aiPlaySearchResult");

window.homePlayersSet = new Set();
window.roadPlayersSet = new Set();
window.currentShotsData = [];
let queryGeneration = 0;

function resetGameSelection() {
    globalSeasonSelect.value = "";
    globalGameSelect.innerHTML = "<option value=''>-- Επίλεξε πρώτα Season --</option>";
    globalGameSelect.disabled = true;
}

function resetShotQueryState() {
    queryGeneration += 1;
    window.currentShotsData = [];
    window.homePlayersSet.clear();
    window.roadPlayersSet.clear();
    window.homeRosterDetails = [];
    window.roadRosterDetails = [];
    window.currentPlayByPlayData = [];
    window.activePbpCategories = new Set();
    window.aiPbpActionUris = null;
    window.aiPbpFilterLabel = "";
    window.currentPlayByPlayGameKey = "";

    if (typeof window.drawShots === "function") window.drawShots([]);

    if (playerSelectInput) playerSelectInput.value = "";
    ["assistSelect", "extraFilterType", "extraFilterId", "quarterSelectAnalytics", "minStart", "minEnd", "aiPlaySearchInput",
        "fouledIdInput", "foulingIdInput", "shooterIdInput", "blockerIdInput"].forEach(id => {
        const element = document.getElementById(id);
        if (element) element.value = "";
    });

    document.querySelectorAll(".shot-filter-cb, .quarter-cb, .player-cb, .roster-sub input[type='checkbox']")
        .forEach(checkbox => { checkbox.checked = true; });

    if (homePlayersContainer) homePlayersContainer.innerHTML = "<div style='padding:20px;text-align:center;color:#999;'>Επίλεξε Season και Game...</div>";
    if (roadPlayersContainer) roadPlayersContainer.innerHTML = "<div style='padding:20px;text-align:center;color:#999;'>Επίλεξε Season και Game...</div>";
    if (currentHomeLineup) currentHomeLineup.innerHTML = "<div style='text-align:center;color:#999;font-size:0.8rem;'>Κάνε νέα αναζήτηση...</div>";
    if (currentRoadLineup) currentRoadLineup.innerHTML = "<div style='text-align:center;color:#999;font-size:0.8rem;'>Κάνε νέα αναζήτηση...</div>";

    const textDefaults = {
        uiHomeTeam: "HOME",
        uiRoadTeam: "ROAD",
        uiScoreHome: "0",
        uiScoreRoad: "0",
        homeTeamTitle: "HOME TEAM",
        roadTeamTitle: "ROAD TEAM"
    };
    Object.entries(textDefaults).forEach(([id, value]) => {
        const element = document.getElementById(id);
        if (element) element.innerText = value;
    });

    document.querySelectorAll("[id^='txtHomeTeamName']").forEach(el => { el.innerText = "HOME TEAM"; });
    document.querySelectorAll("[id^='txtRoadTeamName']").forEach(el => { el.innerText = "ROAD TEAM"; });
    buildDynamicQuarters([]);

    const pbpList = document.getElementById("pbpList");
    if (pbpList) pbpList.innerHTML = "<li style='color:#777;text-align:center;'>Επίλεξε Season και Game και κάνε αναζήτηση.</li>";
    const pbpActionFilters = document.getElementById("pbpActionFilters");
    if (pbpActionFilters) pbpActionFilters.innerHTML = "";
    if (aiPlaySearchResult) {
        aiPlaySearchResult.className = "ai-search-result";
        aiPlaySearchResult.replaceChildren();
    }
    if (aiPlaySearchButton) {
        aiPlaySearchButton.disabled = false;
        aiPlaySearchButton.textContent = "AI SEARCH";
    }

    if (typeof player !== "undefined" && player && typeof player.stopVideo === "function") {
        player.stopVideo();
    }
}

function showAiSearchMessage(message, type = "") {
    if (!aiPlaySearchResult) return;
    aiPlaySearchResult.className = `ai-search-result visible${type ? ` ${type}` : ""}`;
    aiPlaySearchResult.textContent = message;
}

function getAiResultValue(value) {
    if (value === null || value === undefined) return "—";
    if (typeof value === "object" && "value" in value) return String(value.value);
    return String(value);
}

function renderAiSearchResponse(data, playByPlayMatchCount = null) {
    if (!aiPlaySearchResult) return;
    aiPlaySearchResult.className = "ai-search-result visible";
    aiPlaySearchResult.replaceChildren();

    const results = Array.isArray(data.results) ? data.results : [];
    const summary = document.createElement("strong");
    if (typeof data.boolean === "boolean") {
        summary.textContent = `Απάντηση: ${data.boolean ? "Ναι" : "Όχι"}`;
    } else {
        summary.textContent = results.length === 1 ? "Βρέθηκε 1 αποτέλεσμα" : `Βρέθηκαν ${results.length} αποτελέσματα`;
    }
    aiPlaySearchResult.appendChild(summary);

    if (playByPlayMatchCount !== null) {
        const playByPlayNotice = document.createElement("div");
        playByPlayNotice.style.marginTop = "6px";
        playByPlayNotice.style.color = "#5148c8";
        playByPlayNotice.style.fontWeight = "800";
        playByPlayNotice.textContent = playByPlayMatchCount === 1
            ? "Το Play-by-Play φιλτραρίστηκε σε 1 ενέργεια."
            : `Το Play-by-Play φιλτραρίστηκε σε ${playByPlayMatchCount} ενέργειες.`;
        aiPlaySearchResult.appendChild(playByPlayNotice);
    }

    if (results.length > 0) {
        const columns = [...new Set(results.flatMap(result => Object.keys(result)))].filter(column => {
            const normalized = column.toLowerCase().replace(/[^a-z0-9]/g, "");
            return !["action", "actionuri", "play", "playuri", "event", "eventuri"].includes(normalized);
        });
        if (columns.length === 0) {
            if (typeof data.boolean !== "boolean" && playByPlayMatchCount === null) {
                const emptyMessage = document.createElement("div");
                emptyMessage.textContent = "Τα αποτελέσματα αντιστοιχούν σε Play-by-Play ενέργειες.";
                emptyMessage.style.marginTop = "6px";
                aiPlaySearchResult.appendChild(emptyMessage);
            }
        } else {
            const table = document.createElement("table");
            table.className = "ai-result-table";

            const headerRow = document.createElement("tr");
            columns.forEach(column => {
                const th = document.createElement("th");
                th.textContent = column;
                headerRow.appendChild(th);
            });
            const thead = document.createElement("thead");
            thead.appendChild(headerRow);
            table.appendChild(thead);

            const tbody = document.createElement("tbody");
            results.forEach(result => {
                const row = document.createElement("tr");
                columns.forEach(column => {
                    const td = document.createElement("td");
                    td.textContent = getAiResultValue(result[column]);
                    row.appendChild(td);
                });
                tbody.appendChild(row);
            });
            table.appendChild(tbody);
            aiPlaySearchResult.appendChild(table);
        }
    } else if (typeof data.boolean !== "boolean") {
        const emptyMessage = document.createElement("div");
        emptyMessage.textContent = "Δεν βρέθηκαν εγγραφές για αυτή την ερώτηση.";
        emptyMessage.style.marginTop = "6px";
        aiPlaySearchResult.appendChild(emptyMessage);
    }

    if (data.generated_query) {
        const details = document.createElement("details");
        details.className = "ai-query-details";
        const detailsSummary = document.createElement("summary");
        detailsSummary.textContent = "Generated SPARQL";
        const query = document.createElement("pre");
        query.textContent = data.generated_query;
        details.append(detailsSummary, query);
        aiPlaySearchResult.appendChild(details);
    }
}

async function runAiPlaySearch() {
    if (!aiPlaySearchInput || !aiPlaySearchButton) return;

    const message = aiPlaySearchInput.value.trim();
    const seasonCode = globalSeasonSelect.value;
    const gameCode = globalGameSelect.value.trim();

    if (!message) {
        showAiSearchMessage("Γράψε πρώτα μια ερώτηση.", "error");
        aiPlaySearchInput.focus();
        return;
    }
    if (!seasonCode || !gameCode) {
        showAiSearchMessage("Επίλεξε Season και Game πριν από το AI Search.", "error");
        return;
    }

    const activeQueryGeneration = queryGeneration;
    const playByPlayGameKey = `${seasonCode}:${gameCode}`;
    const shouldLoadPlayByPlay = window.currentPlayByPlayGameKey !== playByPlayGameKey || window.currentPlayByPlayData.length === 0;
    aiPlaySearchButton.disabled = true;
    aiPlaySearchButton.textContent = "SEARCHING...";
    aiPlaySearchResult?.setAttribute("aria-busy", "true");
    showAiSearchMessage("Το AI δημιουργεί και εκτελεί το SPARQL query...", "loading");

    try {
        const [data, loadedPlayByPlay] = await Promise.all([
            fetchAiChat(message, gameCode, seasonCode),
            shouldLoadPlayByPlay ? fetchMatchPlayByPlay(gameCode, seasonCode) : Promise.resolve(null)
        ]);
        const currentPlayByPlayGameKey = `${globalSeasonSelect.value}:${globalGameSelect.value.trim()}`;
        if (activeQueryGeneration !== queryGeneration || mainModeSelect.value !== "video-shots" || currentPlayByPlayGameKey !== playByPlayGameKey) return;
        if (loadedPlayByPlay !== null && typeof window.setPlayByPlayActions === "function") {
            window.setPlayByPlayActions(loadedPlayByPlay);
            window.currentPlayByPlayGameKey = playByPlayGameKey;
        }
        if (!data || data.error) {
            showAiSearchMessage(data?.error || "Το AI Search δεν απάντησε.", "error");
            return;
        }

        let playByPlayMatchCount = null;
        if (data.playbyplay_filter && typeof window.applyAiPlayByPlayFilter === "function") {
            playByPlayMatchCount = window.applyAiPlayByPlayFilter(
                data.action_uris || [],
                message.length > 60 ? `${message.slice(0, 57)}...` : message
            );
        } else if (window.aiPbpActionUris instanceof Set && typeof window.clearAiPlayByPlayFilter === "function") {
            window.clearAiPlayByPlayFilter();
        }
        renderAiSearchResponse(data, playByPlayMatchCount);
    } finally {
        if (activeQueryGeneration === queryGeneration) {
            aiPlaySearchButton.disabled = false;
            aiPlaySearchButton.textContent = "AI SEARCH";
            aiPlaySearchResult?.removeAttribute("aria-busy");
        }
    }
}

if (aiPlaySearchButton) aiPlaySearchButton.addEventListener("click", runAiPlaySearch);
if (aiPlaySearchInput) {
    aiPlaySearchInput.addEventListener("keydown", event => {
        if (event.key === "Enter") {
            event.preventDefault();
            runAiPlaySearch();
        }
    });
}

function setShotViewMode(mode) {
    const isVideoMode = mode === "video-shots";
    shotSearchWrapper.classList.toggle("video-mode", isVideoMode);
    mainActionBtn.innerText = isVideoMode ? "ΑΝΑΖΗΤΗΣΗ ΣΟΥΤ (VIDEO)" : "ΑΝΑΖΗΤΗΣΗ ΣΟΥΤ (GAME)";

    const missMarker = document.getElementById("missLegendMarker");
    const madeMarker = document.getElementById("madeLegendMarker");
    if (missMarker) missMarker.style.borderColor = isVideoMode ? "#c0392b" : "#ea5314";
    if (madeMarker) madeMarker.style.backgroundColor = isVideoMode ? "#27ae60" : "#ea5314";

    // Both modes share one canvas; reset only the scroll position, never move the canvas node.
    if (shotCenterArea) shotCenterArea.scrollTop = 0;
}

function setSidebarFiltersForMode(mode) {
    const isVideoMode = mode === "video-shots";
    const isEuroChartMode = mode === "euro-chart";

    if (playerFilterGroup) playerFilterGroup.style.display = isVideoMode ? "none" : "block";
    if (shotFiltersDivider) shotFiltersDivider.style.display = isVideoMode ? "none" : "block";
    if (shotFiltersForm) shotFiltersForm.style.display = isEuroChartMode ? "block" : "none";
    if (extraFiltersContainer) extraFiltersContainer.style.display = isVideoMode ? "none" : "block";
    if (timeFiltersContainer) timeFiltersContainer.style.display = isVideoMode ? "none" : "block";

    // Video searches must always target one concrete season and game.
    if (optAllSeasons) {
        optAllSeasons.hidden = isVideoMode;
        optAllSeasons.disabled = isVideoMode;
    }
    if (optSelectSeason) optSelectSeason.hidden = false;
}

// --- 1. ΕΝΑΛΛΑΓΗ ΛΕΙΤΟΥΡΓΙΑΣ (MENU) ---
mainModeSelect.addEventListener("change", (e) => {
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
    const tryGameBtn = document.getElementById("tryGameBtn");
    const integratedSimulator = document.getElementById("integratedSimulator");
    if (analyticsContent) analyticsContent.innerHTML = "";
    if (analyticsTitle) analyticsTitle.innerText = "Αποτελέσματα";
    resetShotQueryState();
    resetGameSelection();
    setSidebarFiltersForMode(mode);

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
    if (tryGameBtn) tryGameBtn.style.display = "none";
    if (integratedSimulator) integratedSimulator.style.display = "none";
    if (mode === "euro-chart" || mode === "video-shots") {
        const isGameMode = mode === "euro-chart";

        shotSearchWrapper.style.display = "flex";
        setShotViewMode(mode);
        mainActionBtn.innerText = isGameMode ? "ΑΝΑΖΗΤΗΣΗ ΣΟΥΤ (GAME)" : "ΑΝΑΖΗΤΗΣΗ ΣΟΥΤ (VIDEO)";
    } 
    else {
        shotSearchWrapper.style.display = "none";
        analyticsWrapper.style.display = "block";
        shotFiltersForm.style.display = "none";
        mainActionBtn.innerText = "ΕΚΤΕΛΕΣΗ ΑΝΑΛΥΣΗΣ";
        
        // ΝΕΟ: Έλεγχος εμφάνισης του κουμπιού Try Game και απόκρυψη του Simulator
        if (mode === "top-lineups") {
            if (tryGameBtn) tryGameBtn.style.display = "block"; // Εμφανίζουμε το Try Game
            if (integratedSimulator) integratedSimulator.style.display = "none"; // Κρύβουμε το Simulator αρχικά
        }
    }

    if (typeof window.resizeCourt === "function") window.resizeCourt();
});

// --- 2. ΦΟΡΤΩΣΗ ΑΓΩΝΩΝ ---
async function loadGamesForSeason(seasonCode) {
    if (!globalGameSelect) return;

    if (!seasonCode) {
        globalGameSelect.innerHTML = "<option value=''>-- Επίλεξε πρώτα Season --</option>";
        globalGameSelect.disabled = true;
        return;
    }
    
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
    const activeWrapper = shotSearchWrapper;
    if (!activeWrapper) return;

    // 1. Quarters Filter (Μόνο από την ανοιχτή οθόνη)
    const activeQuarters = new Set();
    activeWrapper.querySelectorAll('.quarter-cb:checked').forEach(cb => activeQuarters.add(cb.value));

    // 2. Players Filter (Μόνο από την ανοιχτή οθόνη)
    const activePlayers = new Set();
    if (mode === "video-shots") {
        activeWrapper.querySelectorAll('.player-cb:checked').forEach(cb => activePlayers.add(cb.value));
    }

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
        // The selectable roster belongs to Video mode; Euro Chart uses clicked-shot lineups.
        const playerMatch = activePlayers.size === 0 || activePlayers.has(shot.playerName);
        const quarterMatch = !shot.quarter || activeQuarters.has(shot.quarter);
        
        if (!playerMatch || !quarterMatch) return false;

        let isHome = shot.teamType === "home" || (
            !shot.teamType && window.homePlayersSet && window.homePlayersSet.has(shot.playerName)
        );
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
    setShotViewMode(mainModeSelect.value);
    setSidebarFiltersForMode(mainModeSelect.value);
    resetGameSelection();
});

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
    const isVideoShotMode = mode === "video-shots";
    const selectedSeason = globalSeasonSelect.value;
    const selectedGame = globalGameSelect.value.trim() || null;

    if (!selectedSeason) {
        window.alert("Επίλεξε Season πριν από την αναζήτηση.");
        return;
    }
    if (isVideoShotMode && !selectedGame) {
        window.alert("Στο Video Shot Search πρέπει να επιλέξεις συγκεκριμένο Game.");
        return;
    }
    const selectedPlayer = !isVideoShotMode && playerSelectInput ? playerSelectInput.value.trim() : null;
    const selectedAssistant = !isVideoShotMode && document.getElementById("assistSelect") ? document.getElementById("assistSelect").value : null;
    
    let filterType = !isVideoShotMode && document.getElementById("extraFilterType") ? document.getElementById("extraFilterType").value : null;
    let filterId = !isVideoShotMode && document.getElementById("extraFilterId") ? document.getElementById("extraFilterId").value : null;
    const quarter = !isVideoShotMode && document.getElementById("quarterSelectAnalytics") ? document.getElementById("quarterSelectAnalytics").value : null;
    const minStart = !isVideoShotMode && document.getElementById("minStart") ? document.getElementById("minStart").value : null;
    const minEnd = !isVideoShotMode && document.getElementById("minEnd") ? document.getElementById("minEnd").value : null;
    
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
        const activeQueryGeneration = queryGeneration;
        const [shots, playByPlayActions] = await Promise.all([
            fetchFilteredShots(selectedPlayer, selectedAssistant, selectedGame, selectedSeason, filterType, filterId, quarter, minStart, minEnd),
            isVideoShotMode ? fetchMatchPlayByPlay(selectedGame, selectedSeason) : Promise.resolve([])
        ]);
        if (activeQueryGeneration !== queryGeneration || mainModeSelect.value !== mode) return;
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
                if (activeQueryGeneration !== queryGeneration || mainModeSelect.value !== mode) return;

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

        if (isVideoShotMode && typeof window.setPlayByPlayActions === "function") {
            window.setPlayByPlayActions(playByPlayActions);
            window.currentPlayByPlayGameKey = `${selectedSeason}:${selectedGame}`;
        }
        applyChartFilters();
    } 
    else {
        analyticsContent.innerHTML = "<div style='grid-column: 1 / -1; text-align: center; color: #ea5314; font-weight: bold;'>Φόρτωση δεδομένων...</div>";
        
        try {
            if (mode === "top-lineups") {
                const integratedSimulator = document.getElementById("integratedSimulator");
                if (integratedSimulator) integratedSimulator.style.display = "none";
                
                if (tryGameBtn) {
                    tryGameBtn.style.display = "block";
                    tryGameBtn.innerText = " TRY GAME";
                }

                analyticsTitle.innerText = "Top Lineups";
                analyticsContent.innerHTML = "<div style='grid-column: 1 / -1; text-align: center; color: #ea5314; font-weight: bold; font-size: 1.2rem; padding: 40px;'>Φόρτωση δεδομένων...</div>";
                
                const lineups = await fetchTopLineups(filterType, filterId, quarter, minStart, minEnd, selectedGame, selectedSeason);
                if (!lineups || lineups.length === 0) {
                    analyticsContent.innerHTML = "<div style='grid-column: 1 / -1;'>Δεν βρέθηκαν δεδομένα.</div>";
                    return;
                }
                await renderTopLineups(lineups, selectedGame, selectedSeason);
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

// --- CURRENT LINEUPS ΓΙΑ ΤΟ EURO CHART MODE ---
window.updateCurrentLineups = async function(homeUrl, roadUrl) {
    await buildCurrentLineup(homeUrl, currentHomeLineup);
    await buildCurrentLineup(roadUrl, currentRoadLineup);
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

const PLAYER_PLACEHOLDER_IMAGE = "https://upload.wikimedia.org/wikipedia/commons/8/89/Portrait_Placeholder.png";

async function loadRosterPlayerDetails(playerIds, gameCode = null, seasonCode = null) {
    const uniquePlayerIds = [...new Set(playerIds.filter(Boolean))];
    const detailsById = new Map();

    // Use the same batched player name/image payload as the team roster whenever a game is selected.
    if (gameCode && seasonCode && seasonCode !== "ALL") {
        try {
            const response = await fetch(`${API_BASE_URL}/api/game/lineups?game_code=${encodeURIComponent(gameCode)}&season_code=${encodeURIComponent(seasonCode)}`);
            if (response.ok) {
                const data = await response.json();
                (data.lineups || []).forEach(lineup => {
                    if (!lineup.players) return;
                    lineup.players.split("@@").forEach(playerInfo => {
                        const [id, name, image] = playerInfo.split("|");
                        if (!id || detailsById.has(id)) return;
                        detailsById.set(id, {
                            id,
                            name: name || id,
                            img: image && image !== "NO_IMG" ? image : PLAYER_PLACEHOLDER_IMAGE
                        });
                    });
                });
            }
        } catch (error) {
            console.error("Σφάλμα φόρτωσης στοιχείων ρόστερ:", error);
        }
    }

    const missingPlayerIds = uniquePlayerIds.filter(playerId => !detailsById.has(playerId));
    const fallbackDetails = await Promise.all(missingPlayerIds.map(async playerId => {
        const player = await fetchFilteredPlayer(playerId);
        return {
            id: playerId,
            name: player?.name || playerId,
            img: player?.img || PLAYER_PLACEHOLDER_IMAGE
        };
    }));
    fallbackDetails.forEach(player => detailsById.set(player.id, player));

    return detailsById;
}

function makeLineupPlayerDraggable(playerDiv) {
    playerDiv.addEventListener("dragstart", function() {
        window.draggedCard = this.cloneNode(true);
        window.draggedCard.addEventListener("dragstart", function() {
            window.draggedCard = this;
            setTimeout(() => this.style.opacity = "0.5", 0);
        });
        window.draggedCard.addEventListener("dragend", function() {
            setTimeout(() => {
                this.style.opacity = "1";
                window.draggedCard = null;
            }, 0);
        });
        setTimeout(() => this.style.opacity = "0.5", 0);
    });

    playerDiv.addEventListener("dragend", function() {
        setTimeout(() => this.style.opacity = "1", 0);
    });
}

async function renderTopLineups(lineups, gameCode = null, seasonCode = null) {
    if (!lineups || lineups.length === 0) { analyticsContent.innerHTML = "<div>Δεν βρέθηκαν δεδομένα.</div>"; return; }
    const playerDetails = await loadRosterPlayerDetails(
        lineups.flatMap(lineup => lineup.players || []),
        gameCode,
        seasonCode
    );
    analyticsContent.innerHTML = ""; 
    lineups.forEach((lineup, index) => {
        const card = document.createElement("div");
        card.style.cssText = "background:#fff; padding:20px; border-radius:12px; border-top:5px solid #ea5314; box-shadow:0 4px 15px rgba(0,0,0,0.05);";
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
            const player = playerDetails.get(playerId) || {
                id: playerId,
                name: playerId,
                img: PLAYER_PLACEHOLDER_IMAGE
            };
            const playerDiv = document.createElement("div");
            playerDiv.className = "player-card";
            playerDiv.draggable = true;
            playerDiv.dataset.id = player.id;
            playerDiv.style.cssText = "display:flex; flex-direction:column; align-items:center; width:55px; min-height:75px;";
            playerDiv.innerHTML = `
                <img src="${player.img}" alt="${player.name}" style="width:45px; height:45px; object-fit:cover; border-radius:50%; border:2px solid #ccc; background:#fff; pointer-events:none;">
                <span style="font-size:0.65rem; margin-top:5px; font-weight:700; color:#333; text-align:center; word-break:break-word; pointer-events:none;">${player.name}</span>
            `;
            playersContainer.appendChild(playerDiv);
            makeLineupPlayerDraggable(playerDiv);
        });
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
                    const rosterDetails = await loadRosterPlayerDetails(
                        scenario.roster.map(player => player.id),
                        scenario.game_code,
                        selectedSeason
                    );
                    rosterPool.innerHTML = "";
                    scenario.roster.forEach(rosterPlayer => {
                        const player = rosterDetails.get(rosterPlayer.id) || {
                            id: rosterPlayer.id,
                            name: rosterPlayer.id,
                            img: PLAYER_PLACEHOLDER_IMAGE
                        };
                        const card = document.createElement("div");
                        card.className = "player-card";
                        card.draggable = true;
                        card.setAttribute("data-id", player.id);

                        card.innerHTML = `
                            <img src="${player.img}" alt="${player.name}" style="pointer-events: none;">
                            <span style="pointer-events: none;">${player.name}</span>
                        `;
                        rosterPool.appendChild(card);

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
