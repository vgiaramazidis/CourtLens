// main.js
window.quizState = {
    isActive: false,
    hints: [],
    currentHintIndex: 0,
    secretName: "",
    category: "",
    difficulty: "medium",
    streak: 0,
    playerBStat: 0
};
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
const videoStatusMessage = document.getElementById("videoStatusMessage");

window.homePlayersSet = new Set();
window.roadPlayersSet = new Set();
window.currentShotsData = [];
let queryGeneration = 0;
let activeShotRequestController = null;

function showVideoStatus(message = "", type = "") {
    if (!videoStatusMessage) return;
    videoStatusMessage.textContent = message;
    videoStatusMessage.className = `video-status-message video-shots-only${message ? " visible" : ""}${type ? ` ${type}` : ""}`;
}

function resetGameSelection() {
    globalSeasonSelect.value = "";
    globalGameSelect.innerHTML = "<option value=''>-- Επίλεξε πρώτα Season --</option>";
    globalGameSelect.disabled = true;
}

function resetShotQueryState() {
    if (activeShotRequestController) {
        activeShotRequestController.abort();
        activeShotRequestController = null;
    }
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
    window.lastAiPbpMatches = [];
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
    if (mainActionBtn) mainActionBtn.disabled = false;

    if (typeof window.setYouTubeVideo === "function") window.setYouTubeVideo(null);
    showVideoStatus();
    const courtContainer = document.getElementById("courtContainer");
    const legendContainer = document.getElementById("legendContainer");
    const mode = document.getElementById("mainModeSelect")?.value;
    
    // Αν είμαστε στο γενικό mode, κρύψε το παρκέ μέχρι να γίνει αναζήτηση
    if (mode === "euro-chart") {
        if (courtContainer) courtContainer.style.display = "none";
        if (legendContainer) legendContainer.style.display = "none";
        

    } else if (mode === "video-shots") {
        // Στο video mode, δείχνε το πάντα
        if (courtContainer) courtContainer.style.display = "block";
        if (legendContainer) legendContainer.style.display = "block";
        
    }
}

function showAiSearchMessage(message, type = "") {
    if (!aiPlaySearchResult) return;
    aiPlaySearchResult.className = `ai-search-result visible${type ? ` ${type}` : ""}`;
    aiPlaySearchResult.textContent = message;
}

function getAiResultValue(value) {
    if (value === null || value === undefined) return "—";
    const rawValue = typeof value === "object" && "value" in value ? String(value.value) : String(value);
    if (/^https?:\/\//i.test(rawValue)) {
        const compactValue = rawValue.split(/[\/#]/).filter(Boolean).pop() || rawValue;
        try {
            return decodeURIComponent(compactValue).replace(/[_-]+/g, " ");
        } catch (_error) {
            return compactValue.replace(/[_-]+/g, " ");
        }
    }
    return rawValue;
}

function getAiResultLabel(column) {
    const normalized = String(column).toLowerCase().replace(/[^a-z0-9]/g, "");
    const labels = {
        player: "Player", playername: "Player", assistingplayer: "Assisting player",
        assistingplayername: "Assisting player", receiver: "Receiver", receivername: "Receiver",
        team: "Team", teamname: "Team", points: "Points", totalpoints: "Total points",
        assists: "Assists", totalassists: "Total assists", count: "Total", quarter: "Quarter",
        clock: "Game clock", playtime: "Game clock", actiontype: "Action", order: "Sequence",
        sequence: "Sequence", score: "Score", homescore: "Home score", roadscore: "Road score"
    };
    if (labels[normalized]) return labels[normalized];
    return String(column)
        .replace(/([a-z])([A-Z])/g, "$1 $2")
        .replace(/[_-]+/g, " ")
        .replace(/^./, character => character.toUpperCase());
}

function getBindingValue(result, candidateKeys) {
    const normalizedCandidates = new Set(candidateKeys.map(key => key.toLowerCase().replace(/[^a-z0-9]/g, "")));
    const matchingKey = Object.keys(result || {}).find(key => normalizedCandidates.has(key.toLowerCase().replace(/[^a-z0-9]/g, "")));
    return matchingKey ? getAiResultValue(result[matchingKey]) : "";
}

function getFriendlyActionExplanation(action) {
    const actionType = String(action.action_type || "Action");
    const player = action.playerName || "A player";
    const relatedMadeShot = (window.currentPlayByPlayData || [])
        .filter(candidate => /PointShotMade/.test(candidate.action_type || "")
            && candidate.quarter === action.quarter
            && (candidate.playTime === action.playTime
                || Math.abs(Number(candidate.sequence || 0) - Number(action.sequence || 0)) <= 3))
        .sort((a, b) => {
            const sameClockA = a.playTime === action.playTime ? 0 : 1;
            const sameClockB = b.playTime === action.playTime ? 0 : 1;
            return sameClockA - sameClockB
                || Math.abs(Number(a.sequence || 0) - Number(action.sequence || 0))
                - Math.abs(Number(b.sequence || 0) - Number(action.sequence || 0));
        })[0];

    if (/Assist/.test(actionType)) {
        const receiver = relatedMadeShot?.playerName;
        const shotValue = relatedMadeShot?.action_type?.includes("ThreePoint") ? "three-point basket" : "basket";
        return receiver
            ? `${player} created the ${shotValue} scored by ${receiver}.`
            : `${player} created a scoring chance that a teammate finished.`;
    }
    if (/ThreePointShotMade/.test(actionType)) return `${player} made a three-point shot and added 3 points.`;
    if (/TwoPointShotMade/.test(actionType)) return `${player} made a two-point shot and added 2 points.`;
    if (/FreeThrowMade/.test(actionType)) return `${player} made a free throw and added 1 point.`;
    if (/ThreePointShotMissed/.test(actionType)) return `${player} attempted a three-point shot but missed.`;
    if (/TwoPointShotMissed/.test(actionType)) return `${player} attempted a two-point shot but missed.`;
    if (/FreeThrowMissed/.test(actionType)) return `${player} attempted a free throw but missed.`;
    if (/OffensiveRebound/.test(actionType)) return `${player} collected the offensive rebound and kept the attack alive.`;
    if (/DefensiveRebound/.test(actionType)) return `${player} collected the defensive rebound and ended the opponent's attack.`;
    if (/Turnover/.test(actionType)) return `${player} lost possession of the ball.`;
    if (/FoulDrawn/.test(actionType)) return `${player} forced an opponent to commit a foul.`;
    if (/Foul/.test(actionType)) return `${player} committed a foul.`;
    if (/Steal/.test(actionType)) return `${player} won possession with a steal.`;
    if (/Block|ShotRejected/.test(actionType)) return `${player} stopped an opponent's shot with a block.`;
    return `${player} was involved in this play.`;
}

function renderFriendlyPlayByPlayResults(actions) {
    const section = document.createElement("section");
    section.className = "ai-friendly-actions";
    const heading = document.createElement("strong");
    heading.className = "ai-friendly-heading";
    heading.textContent = "What happened in the game";
    const explanation = document.createElement("p");
    explanation.textContent = "Each card below is linked to the matching moment in the Play-by-Play.";
    section.append(heading, explanation);

    const grid = document.createElement("div");
    grid.className = "ai-friendly-action-grid";
    actions.forEach(action => {
        const card = document.createElement("article");
        card.className = "ai-friendly-action-card";
        const description = document.createElement("strong");
        description.textContent = getFriendlyActionExplanation(action);
        const details = document.createElement("div");
        details.className = "ai-friendly-action-meta";
        const quarter = String(action.quarter || "period").toUpperCase();
        const clock = action.playTime || "--:--";
        details.textContent = `${quarter} quarter · ${clock} remaining · Score ${action.homeScore ?? 0}–${action.roadScore ?? 0}`;
        const badge = document.createElement("span");
        badge.className = "ai-friendly-action-badge";
        badge.textContent = getAiResultLabel(String(action.action_type || "Action").replace(/Made|Missed/g, ""));
        card.append(description, details, badge);
        grid.appendChild(card);
    });
    section.appendChild(grid);
    return section;
}

function buildFriendlyDataSummary(results, booleanAnswer) {
    if (typeof booleanAnswer === "boolean") {
        return booleanAnswer
            ? "Yes — the game data confirms that this happened."
            : "No — the game data does not contain a matching event.";
    }
    if (results.length === 0) return "";

    const result = results[0];
    const player = getBindingValue(result, ["playerName", "player", "scorer", "passer", "assistingPlayerName"]);
    const percentage = getBindingValue(result, ["percentage", "shotPercentage", "fieldGoalPercentage"]);
    if (percentage) {
        const made = getBindingValue(result, ["made", "shotsMade", "madeShots"]);
        const attempts = getBindingValue(result, ["attempts", "shotAttempts", "totalAttempts"]);
        const numericPercentage = Number(String(percentage).replace("%", ""));
        const displayPercentage = Number.isFinite(numericPercentage)
            ? (Number.isInteger(numericPercentage) ? String(numericPercentage) : numericPercentage.toFixed(1))
            : String(percentage).replace("%", "");
        if (made && attempts) {
            return `${player || "The selected player"} made ${made} of ${attempts} attempts — ${displayPercentage}% shooting.`;
        }
        return `${player || "The selected player"} shot ${displayPercentage}% for the requested shot type.`;
    }
    const metrics = [
        { keys: ["totalPoints", "points"], unit: "points", verb: "scored" },
        { keys: ["totalMissedFreeThrows"], unit: "free throws", verb: "missed" },
        { keys: ["totalMissedThreePointShots"], unit: "three-point shots", verb: "missed" },
        { keys: ["totalMissedTwoPointShots"], unit: "two-point shots", verb: "missed" },
        { keys: ["totalMissedShots"], unit: "shot attempts", verb: "missed" },
        { keys: ["totalMadeFreeThrows"], unit: "free throws", verb: "made" },
        { keys: ["totalMadeThreePointShots"], unit: "three-point shots", verb: "made" },
        { keys: ["totalMadeTwoPointShots"], unit: "two-point shots", verb: "made" },
        { keys: ["totalMadeShots"], unit: "shots", verb: "made" },
        { keys: ["totalFreeThrows"], unit: "free-throw attempts", verb: "took" },
        { keys: ["totalThreePointShots"], unit: "three-point attempts", verb: "took" },
        { keys: ["totalTwoPointShots"], unit: "two-point attempts", verb: "took" },
        { keys: ["totalShots"], unit: "shot attempts", verb: "took" },
        { keys: ["totalAssists", "assists"], unit: "assists", verb: "recorded" },
        { keys: ["totalRebounds", "rebounds"], unit: "rebounds", verb: "collected" },
        { keys: ["totalTurnovers", "turnovers"], unit: "turnovers", verb: "recorded" },
        { keys: ["totalFouls", "fouls"], unit: "fouls", verb: "recorded" },
        { keys: ["count", "total", "actionCount"], unit: "matching actions", verb: "recorded" }
    ];
    for (const metric of metrics) {
        const value = getBindingValue(result, metric.keys);
        if (value) {
            const singularUnits = {
                "points": "point", "free throws": "free throw", "three-point shots": "three-point shot",
                "two-point shots": "two-point shot", "shot attempts": "shot attempt", "shots": "shot",
                "free-throw attempts": "free-throw attempt", "three-point attempts": "three-point attempt",
                "two-point attempts": "two-point attempt", "assists": "assist", "rebounds": "rebound",
                "turnovers": "turnover", "fouls": "foul", "matching actions": "matching action"
            };
            const displayUnit = Number(value) === 1 ? (singularUnits[metric.unit] || metric.unit) : metric.unit;
            return player
                ? `${player} ${metric.verb} ${value} ${displayUnit} in the selected game.`
                : `The answer is ${value} ${displayUnit} in the selected game.`;
        }
    }
    return "";
}

function renderAiSearchResponse(data, playByPlayMatchCount = null, question = "") {
    if (!aiPlaySearchResult) return;
    aiPlaySearchResult.className = "ai-search-result visible";
    aiPlaySearchResult.replaceChildren();

    const results = Array.isArray(data.results) ? data.results : [];
    const matchedPlayByPlayActions = Array.isArray(window.lastAiPbpMatches) ? window.lastAiPbpMatches : [];
    const header = document.createElement("div");
    header.className = "ai-answer-header";
    const headingText = document.createElement("div");
    const title = document.createElement("strong");
    title.textContent = "AI game answer";
    headingText.appendChild(title);
    if (question) {
        const questionText = document.createElement("span");
        questionText.className = "ai-answer-question";
        questionText.textContent = question;
        headingText.appendChild(questionText);
    }
    const countBadge = document.createElement("span");
    countBadge.className = "ai-answer-count";
    if (typeof data.boolean === "boolean") {
        countBadge.textContent = data.boolean ? "YES" : "NO";
    } else if (playByPlayMatchCount !== null) {
        countBadge.textContent = playByPlayMatchCount === 1 ? "1 PLAY" : `${playByPlayMatchCount} PLAYS`;
    } else {
        countBadge.textContent = results.length === 1 ? "1 RESULT" : `${results.length} RESULTS`;
    }
    header.append(headingText, countBadge);
    aiPlaySearchResult.appendChild(header);

    const selectedGameLabel = globalGameSelect.options[globalGameSelect.selectedIndex]?.textContent?.replace(/^\[[^\]]+\]\s*/, "") || "Selected game";
    const context = document.createElement("div");
    context.className = "ai-answer-context";
    context.textContent = `${selectedGameLabel} · ${globalSeasonSelect.options[globalSeasonSelect.selectedIndex]?.textContent || globalSeasonSelect.value}`;
    aiPlaySearchResult.appendChild(context);

    if (playByPlayMatchCount !== null) {
        const playByPlayNotice = document.createElement("div");
        playByPlayNotice.className = playByPlayMatchCount > 0 ? "ai-filter-success" : "ai-filter-empty";
        playByPlayNotice.textContent = playByPlayMatchCount === 0
            ? "No matching Play-by-Play actions were found."
            : (playByPlayMatchCount === 1
                ? "✓ The Play-by-Play now shows the matching action."
                : `✓ The Play-by-Play now shows ${playByPlayMatchCount} matching actions.`);
        aiPlaySearchResult.appendChild(playByPlayNotice);
    }

    const friendlySummary = buildFriendlyDataSummary(results, data.boolean);
    if (friendlySummary) {
        const summary = document.createElement("div");
        summary.className = "ai-friendly-summary";
        summary.textContent = friendlySummary;
        aiPlaySearchResult.appendChild(summary);
    }

    if (matchedPlayByPlayActions.length > 0) {
        aiPlaySearchResult.appendChild(renderFriendlyPlayByPlayResults(matchedPlayByPlayActions));
        return;
    }

    if (results.length > 0) {
        const columns = [...new Set(results.flatMap(result => Object.keys(result)))].filter(column => {
            const normalized = column.toLowerCase().replace(/[^a-z0-9]/g, "");
            return !["action", "actionuri", "play", "playuri", "event", "eventuri", "order", "sequence"].includes(normalized);
        });
        if (columns.length === 0) {
            if (typeof data.boolean !== "boolean" && playByPlayMatchCount === null) {
                const emptyMessage = document.createElement("div");
                emptyMessage.className = "ai-answer-empty";
                emptyMessage.textContent = "The matching actions are available in the Play-by-Play panel.";
                aiPlaySearchResult.appendChild(emptyMessage);
            }
        } else {
            const cards = document.createElement("div");
            cards.className = "ai-answer-grid";
            results.forEach((result, index) => {
                const card = document.createElement("article");
                card.className = "ai-answer-item";
                card.setAttribute("aria-label", `Result ${index + 1}`);
                columns.forEach(column => {
                    if (!(column in result)) return;
                    const field = document.createElement("div");
                    field.className = "ai-answer-field";
                    const label = document.createElement("span");
                    label.className = "ai-answer-label";
                    label.textContent = getAiResultLabel(column);
                    const value = document.createElement("strong");
                    value.className = "ai-answer-value";
                    value.textContent = getAiResultValue(result[column]);
                    field.append(label, value);
                    card.appendChild(field);
                });
                cards.appendChild(card);
            });
            aiPlaySearchResult.appendChild(cards);
        }
    } else if (typeof data.boolean !== "boolean" && playByPlayMatchCount !== 0) {
        const emptyMessage = document.createElement("div");
        emptyMessage.className = "ai-answer-empty";
        emptyMessage.textContent = "No matching game data was found for this question.";
        aiPlaySearchResult.appendChild(emptyMessage);
    }
}

async function runAiPlaySearch() {
    if (!aiPlaySearchInput || !aiPlaySearchButton) return;

    const message = aiPlaySearchInput.value.trim();
    let seasonCode = globalSeasonSelect.value;
    let gameCode = globalGameSelect.value.trim();

    // 1. Μεταφράζουμε το "ALL" στις συγκεκριμένες σεζόν που θέλεις
    if (seasonCode === "ALL") {
        seasonCode = "E2023,E2024,E2025"; 
    }

    // 2. Αν δεν έχει επιλεγεί αγώνας, το στέλνουμε ως null για να το δεχτεί το backend χωρίς error
    if (gameCode === "") {
        gameCode = null;
    }

    if (!message) {
        showAiSearchMessage("Γράψε πρώτα μια ερώτηση.", "error");
        aiPlaySearchInput.focus();
        return;
    }
    if (!seasonCode || (!gameCode && mainModeSelect.value === "video-shots")) {
        showAiSearchMessage("Επίλεξε Season και Game πριν από το AI Search.", "error");
        return;
    }

    const activeQueryGeneration = queryGeneration;
    const playByPlayGameKey = `${seasonCode}:${gameCode}`;
    const shouldLoadPlayByPlay = gameCode && (window.currentPlayByPlayGameKey !== playByPlayGameKey || window.currentPlayByPlayData.length === 0);
    aiPlaySearchButton.disabled = true;
    aiPlaySearchButton.textContent = "SEARCHING...";
    aiPlaySearchResult?.setAttribute("aria-busy", "true");
    showAiSearchMessage("The AI is searching this game's data...", "loading");
    if (window.aiPbpActionUris instanceof Set && typeof window.clearAiPlayByPlayFilter === "function") {
        window.clearAiPlayByPlayFilter();
    }
    const pbpList = document.getElementById("pbpList");
    if (pbpList) {
        pbpList.innerHTML = "<li class='pbp-filter-empty' style='color: #6c63ff; font-weight: bold;'>Αναζήτηση στο Play-by-Play... ⏱️</li>";
    }
    try {
        const [data, loadedPlayByPlay] = await Promise.all([
            fetchAiChat(message, gameCode, seasonCode),
            shouldLoadPlayByPlay ? fetchMatchPlayByPlay(gameCode, seasonCode) : Promise.resolve(null)
        ]);
        const courtContainer = document.getElementById("courtContainer");
        const legendContainer = document.getElementById("legendContainer");

        if (mainModeSelect.value === "euro-chart" && window.currentShotsData.length === 0 && gameCode) {
            try {
                window.currentShotsData = await fetchFilteredShots(null, null, gameCode, seasonCode);
            } catch (e) {
                console.error("Δεν μπόρεσαν να φορτωθούν τα σουτ:", e);
            }
        }

        // 2. Πιο "έξυπνος" έλεγχος για την εμφάνιση του παρκέ
        if (mainModeSelect.value === "euro-chart") {
            const kind = data ? String(data.playbyplay_action_kind || "").toLowerCase() : "";
            const userMsg = message.toLowerCase();
            
            // Ψάχνουμε αν το AI μας είπε "shot" Ή αν ο χρήστης έγραψε λέξεις σχετικές με σουτ στην ερώτησή του!
            const isShotQuery = kind.includes("shot") || 
                                userMsg.includes("shot") || 
                                userMsg.includes("σουτ") || 
                                userMsg.includes("σούτ") ||
                                userMsg.includes("τρίποντ") ||
                                userMsg.includes("3pt") ||
                                userMsg.includes("2pt");

            if (isShotQuery) {
                courtContainer.style.display = "block";
                if (legendContainer) legendContainer.style.display = "block";

                // Φιλτράρουμε και ζωγραφίζουμε τα σουτ που βρήκε το AI
                if (data.action_uris && window.currentShotsData) {
                    const aiUris = new Set(data.action_uris);
                    const aiShots = window.currentShotsData.filter(shot => aiUris.has(shot.action_uri));
                    if (typeof window.drawShots === "function") {
                        window.drawShots(aiShots);
                    }
                }
            } else {
                // Αν ρωτάμε για assists, turnovers κλπ, κρύβουμε το παρκέ
                courtContainer.style.display = "none";
                if (legendContainer) legendContainer.style.display = "none";
            }
        } else {
            // Στο video mode, δείχνουμε πάντα το παρκέ
            courtContainer.style.display = "block";
            if (legendContainer) legendContainer.style.display = "block";
        }
        const currentPlayByPlayGameKey = `${globalSeasonSelect.value}:${globalGameSelect.value.trim()}`;
        if (activeQueryGeneration !== queryGeneration || (mainModeSelect.value !== "video-shots" && mainModeSelect.value !== "euro-chart") || currentPlayByPlayGameKey !== playByPlayGameKey) return;
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
                message.length > 60 ? `${message.slice(0, 57)}...` : message,
                data.playbyplay_action_kind || ""
            );
        } else if (window.aiPbpActionUris instanceof Set && typeof window.clearAiPlayByPlayFilter === "function") {
            window.clearAiPlayByPlayFilter();
        }
        renderAiSearchResponse(data, playByPlayMatchCount, message);
    } catch (error) {
        if (activeQueryGeneration === queryGeneration && error.name !== "AbortError") {
            showAiSearchMessage("Το AI Search ή το Play-by-Play δεν απάντησε. Δοκίμασε ξανά.", "error");
        }
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
    const courtContainer = document.getElementById("courtContainer");
    const legendContainer = document.getElementById("legendContainer");
    
    if (mode === "euro-chart") {
        if (courtContainer) courtContainer.style.display = "none";
        if (legendContainer) legendContainer.style.display = "none";
    } else if (mode === "video-shots") {
        if (courtContainer) courtContainer.style.display = "block";
        if (legendContainer) legendContainer.style.display = "block";
    }
}

function setSidebarFiltersForMode(mode) {
    const isVideoMode = mode === "video-shots";
    const isEuroChartMode = mode === "euro-chart";
    const isQuizMode = mode === "quiz-ball";
    const isCoachSimulator = mode === "coach-simulator";

    // 1. Εμφάνιση / Απόκρυψη Season Select (Το κρύβουμε ΜΟΝΟ στο Quiz)
    if (globalSeasonSelect && globalSeasonSelect.parentElement) {
        globalSeasonSelect.parentElement.style.display = isQuizMode ? "none" : "block";
    }

    // 2. Εμφάνιση / Απόκρυψη Game Select (Το κρύβουμε στο Quiz ΚΑΙ στο Coach Simulator)
    if (globalGameSelect && globalGameSelect.parentElement) {
        globalGameSelect.parentElement.style.display = (isQuizMode || isCoachSimulator) ? "none" : "block";
    }

    // 3. Εμφάνιση / Απόκρυψη των υπολοίπων (Extra) Φίλτρων
    // Τα κρύβουμε όλα στο Video Mode, στο Quiz και στο Coach Simulator
    const hideExtraFilters = isVideoMode || isQuizMode || isCoachSimulator;
    
    if (playerFilterGroup) playerFilterGroup.style.display = hideExtraFilters ? "none" : "block";
    if (shotFiltersDivider) shotFiltersDivider.style.display = hideExtraFilters ? "none" : "block";
    if (extraFiltersContainer) extraFiltersContainer.style.display = hideExtraFilters ? "none" : "block";
    if (timeFiltersContainer) timeFiltersContainer.style.display = hideExtraFilters ? "none" : "block";

    // 4. Ειδικά για τα Shot Filters (εμφανίζονται ΜΟΝΟ στο Game Shot Search / euro-chart)
    if (shotFiltersForm) shotFiltersForm.style.display = isEuroChartMode ? "block" : "none";

    // 5. Διαχείριση Κουμπιών Αναζήτησης / Παιχνιδιού
    if (mainActionBtn) {
        mainActionBtn.style.display = (isQuizMode || isCoachSimulator || isEuroChartMode) ? "none" : "block";
    }
    
    const tryGameBtn = document.getElementById("tryGameBtn");
    if (tryGameBtn) {
        tryGameBtn.style.display = isCoachSimulator ? "block" : "none";
    }

    // 6. Λογική για το "All Seasons" option
    if (optAllSeasons) {
        optAllSeasons.hidden = isVideoMode;
        optAllSeasons.disabled = isVideoMode;
    }
    if (optSelectSeason) optSelectSeason.hidden = false;
}
async function setSeasonOptionsForMode(mode) {
    if (!globalSeasonSelect) return;
    const seasonOptions = Array.from(globalSeasonSelect.options)
        .filter(option => /^E\d{4}$/.test(option.value));

    if (mode !== "video-shots") {
        seasonOptions.forEach(option => {
            option.hidden = false;
            option.disabled = false;
        });
        globalSeasonSelect.disabled = false;
        return;
    }

    globalSeasonSelect.disabled = true;
    const videoCatalog = await fetchAvailableVideoGames();
    if (mainModeSelect.value !== "video-shots") return;
    const availableSeasons = new Set(videoCatalog.seasons || []);
    seasonOptions.forEach(option => {
        const available = availableSeasons.has(option.value);
        option.hidden = !available;
        option.disabled = !available;
    });
    globalSeasonSelect.disabled = availableSeasons.size === 0;
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
        if (playerFilterGroup) playerFilterGroup.style.display = "block";
        
        // 3. Επαναφέρουμε τα κουμπιά
        mainActionBtn.innerText = "ΑΝΑΖΗΤΗΣΗ";
        mainActionBtn.style.backgroundColor = "#ea5314";
        
        if (tryGameBtn) {
            tryGameBtn.innerText = "TRY GAME";
            tryGameBtn.style.display = e.target.value === "top-lineups" ? "block" : "none";
        }

        // 4. Scroll πίσω στην κορυφή (στα Top Lineups)
        window.scrollTo({ top: 0, behavior: 'smooth' });
        
        // Continue with the selected section so changing mode also exits the simulator cleanly.
    }
    const mode = e.target.value;
    const tryGameBtn = document.getElementById("tryGameBtn");
    const integratedSimulator = document.getElementById("integratedSimulator");
    if (analyticsContent) analyticsContent.innerHTML = "";
    if (analyticsTitle) analyticsTitle.innerText = "Αποτελέσματα";
    resetShotQueryState();
    resetGameSelection();
    setSidebarFiltersForMode(mode);
    setSeasonOptionsForMode(mode);

    analyticsWrapper.style.display = "none";
    
    analyticsContent.innerHTML = "<div style='grid-column: 1 / -1; text-align: center; color: #777; font-style: italic; font-size: 1.1rem;'>Πάτα 'ΕΚΤΕΛΕΣΗ ΑΝΑΛΥΣΗΣ' για να δεις τα δεδομένα...</div>";
    
    if (mode === "top-lineups") analyticsTitle.innerText = "Top Lineups";
    else if (mode === "second-chance") analyticsTitle.innerText = "Second Chance Points";
    else if (mode === "assist-duos") analyticsTitle.innerText = "Top Assist Duos";
    else if (mode === "fouls-drawn") analyticsTitle.innerText = "Fouls Drawn Gravity";
    else if (mode === "defensive-anchors") analyticsTitle.innerText = "Defensive Anchors";
    else if (mode === "quiz-ball") analyticsTitle.innerText = "Quiz Ball";
    else analyticsTitle.innerText = "Αποτελέσματα Ανάλυσης";
    
    const shooterFilter = document.getElementById("defensiveFiltersContainer");
    if (shooterFilter) shooterFilter.style.display = (mode === "defensive-anchors") ? "block" : "none";

    const foulsFilter = document.getElementById("foulsFiltersContainer");
    if (foulsFilter) foulsFilter.style.display = (mode === "fouls-drawn") ? "block" : "none";
    if (tryGameBtn) tryGameBtn.style.display = "none";
    if (integratedSimulator) integratedSimulator.style.display = "none";
    if (mode === "euro-chart" || mode === "video-shots") {
        const isGameMode = mode === "euro-chart";

        // Video mode uses the responsive CSS grid; Euro Chart keeps the side-by-side flex layout.
        shotSearchWrapper.style.display = isGameMode ? "flex" : "";
        setShotViewMode(mode);
        mainActionBtn.innerText = isGameMode ? "ΑΝΑΖΗΤΗΣΗ ΣΟΥΤ (GAME)" : "ΑΝΑΖΗΤΗΣΗ ΣΟΥΤ (VIDEO)";
    } 
    else {
        shotSearchWrapper.style.display = "none";
        analyticsWrapper.style.display = "block";
        
        mainActionBtn.innerText = "ΕΚΤΕΛΕΣΗ ΑΝΑΛΥΣΗΣ";
        
        // ΝΕΟ: Έλεγχος εμφάνισης του κουμπιού Try Game και απόκρυψη του Simulator
        if (mode === "coach-simulator") {
            const integratedSimulator = document.getElementById("integratedSimulator");
            const gameInstructions = document.getElementById("gameInstructions");
            const actualSimulatorUI = document.getElementById("actualSimulatorUI");

            // Εμφανίζουμε κατευθείαν το γενικό container του Simulator
            if (integratedSimulator) integratedSimulator.style.display = "block";
            if (gameInstructions) gameInstructions.style.display = "block"; 
            if (actualSimulatorUI) actualSimulatorUI.style.display = "none";

            // Κρύβουμε τα analytics
            if (analyticsContent) analyticsContent.style.display = "none";

            // Εμφανίζουμε το κουμπί έναρξης / νέου σεναρίου
            if (tryGameBtn) {
                tryGameBtn.style.display = "block";
                tryGameBtn.innerText = "ΠΑΙΞΕ / ΝΕΟ ΣΕΝΑΡΙΟ"; 
            }
            if (mainActionBtn) mainActionBtn.style.display = "none";
        } else {
            // --- ΠΡΟΣΘΗΚΗ: Επαναφορά του πλαισίου για το Quiz Ball και τα υπόλοιπα ---
            if (analyticsContent) analyticsContent.style.display = "grid"; 
            const integratedSimulator = document.getElementById("integratedSimulator");
            if (integratedSimulator) integratedSimulator.style.display = "none";
        }
        if (mode === "quiz-ball") {
            analyticsContent.innerHTML = `
                <div class="quiz-menu-container">
                    <h2 style="color:#2b528a; text-align:center; margin-bottom:20px; font-size:2rem; font-weight:900; text-transform:uppercase;">ΕΠΙΛΟΓΗ ΚΑΤΗΓΟΡΙΑΣ</h2>

                    <!-- 1. ΠΟΙΟΣ ΕΙΜΑΙ; -->
                    <div class="quiz-category-row" style="background: linear-gradient(90deg, #9706d5 0%, #9b59b6 100%); margin-bottom: 15px;">
                        <div class="quiz-category-left">
                            <div class="quiz-icon">👤</div>
                            <span>ΠΟΙΟΣ ΕΙΜΑΙ;</span>
                        </div>
                        <div class="quiz-difficulties">
                            <button class="quiz-diff-btn" onclick="startQuizCategory('who-am-i', 'easy')">ΕΥΚ</button>
                            <button class="quiz-diff-btn" onclick="startQuizCategory('who-am-i', 'medium')">ΜΕΤ</button>
                            <button class="quiz-diff-btn" onclick="startQuizCategory('who-am-i', 'hard')">ΔΥΣ</button>
                        </div>
                    </div>

                    <!-- 2. ΠΟΙΟΣ ΛΕΙΠΕΙ; -->
                    <div class="quiz-category-row" style="background: linear-gradient(90deg, #057935 0%, #05e964 100%);">
                        <div class="quiz-category-left">
                            <div class="quiz-icon">❓</div>
                            <span>ΠΟΙΟΣ ΛΕΙΠΕΙ;</span>
                        </div>
                        <div class="quiz-difficulties">
                            <button class="quiz-diff-btn" onclick="startQuizCategory('who-is-missing', 'easy')">ΕΥΚ</button>
                            <button class="quiz-diff-btn" onclick="startQuizCategory('who-is-missing', 'medium')">ΜΕΤ</button>
                            <button class="quiz-diff-btn" onclick="startQuizCategory('who-is-missing', 'hard')">ΔΥΣ</button>
                        </div>
                    </div>
                    <!-- 2. HIGHER / LOWER -->
                    <div class="quiz-category-row" style="background: linear-gradient(90deg, #600404fe 0%, #f10303 100%);">
                        <div class="quiz-category-left">
                            <div class="quiz-icon">📈</div>
                            <span>HIGHER / LOWER</span>
                        </div>
                        <div class="quiz-difficulties">
                            <button class="quiz-diff-btn" onclick="startQuizCategory('higher-or-lower', 'easy')">ΕΥΚ</button>
                            <button class="quiz-diff-btn" onclick="startQuizCategory('higher-or-lower', 'medium')">ΜΕΤ</button>
                            <button class="quiz-diff-btn" onclick="startQuizCategory('higher-or-lower', 'hard')">ΔΥΣ</button>
                        </div>
                    </div>
                    <!-- 3. TOP 5 -->
                    <div class="quiz-category-row" style="background: linear-gradient(90deg, #1e8449 0%, #2ecc71 100%); margin-bottom: 15px;">
                        <div class="quiz-category-left">
                            <div class="quiz-icon">🔝</div>
                            <span>ΤΟΠ 5</span>
                        </div>
                        <div class="quiz-difficulties">
                            <button class="quiz-diff-btn" onclick="startQuizCategory('top-5', 'easy')">ΕΥΚ</button>
                            <button class="quiz-diff-btn" onclick="startQuizCategory('top-5', 'medium')">ΜΕΤ</button>
                            <button class="quiz-diff-btn" onclick="startQuizCategory('top-5', 'hard')">ΔΥΣ</button>
                        </div>
                    </div>
                    <!-- 5. 50/50 -->
                    <div class="quiz-category-row" style="background: linear-gradient(90deg, #0b18a7 0%, #0f9bce 100%);">
                        <div class="quiz-category-left">
                            <div class="quiz-icon">⚖️</div>
                            <span>50 / 50</span>
                        </div>
                        <div class="quiz-difficulties">
                            <button class="quiz-diff-btn" onclick="startQuizCategory('fifty-fifty', 'easy')">ΕΥΚ</button>
                            <button class="quiz-diff-btn" onclick="startQuizCategory('fifty-fifty', 'medium')">ΜΕΤ</button>
                            <button class="quiz-diff-btn" onclick="startQuizCategory('fifty-fifty', 'hard')">ΔΥΣ</button>
                        </div>
                    </div>
                </div>
            `;
            return;
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
        const isVideoMode = mainModeSelect.value === "video-shots";
        const [response, videoCatalog] = await Promise.all([
            fetch(`${API_BASE_URL}/api/games?season_code=${seasonCode}`),
            isVideoMode ? fetchAvailableVideoGames(seasonCode) : Promise.resolve(null)
        ]);
        const data = await response.json();
        const availableGameCodes = isVideoMode
            ? new Set((videoCatalog?.games || []).map(game => String(game.game_code)))
            : null;
        const games = (data.games || []).filter(game =>
            !availableGameCodes || availableGameCodes.has(String(game.gameCode))
        );
        
        globalGameSelect.innerHTML = "<option value=''>-- Επίλεξε Αγώνα --</option>";
        if (games.length > 0) {
            games.forEach(game => {
                const option = document.createElement("option");
                option.value = game.gameCode;
                option.textContent = `[${game.gameCode}] ${game.matchup}`;
                globalGameSelect.appendChild(option);
            });
            globalGameSelect.disabled = false;
        } else if (isVideoMode) {
            globalGameSelect.innerHTML = "<option value=''>Δεν υπάρχουν έτοιμα video games</option>";
        }
    } catch (error) {
        globalGameSelect.innerHTML = "<option value=''>Σφάλμα φόρτωσης</option>";
    }
}

globalSeasonSelect.addEventListener("change", (e) => {
    resetShotQueryState();
    loadGamesForSeason(e.target.value);
});
globalGameSelect.addEventListener("change", () => resetShotQueryState());


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


function normalizeQuarterLabel(quarter) {
    const value = String(quarter || "").trim().toUpperCase();
    const regulation = { "1": "1st", "Q1": "1st", "1ST": "1st", "2": "2nd", "Q2": "2nd", "2ND": "2nd", "3": "3rd", "Q3": "3rd", "3RD": "3rd", "4": "4th", "Q4": "4th", "4TH": "4th" };
    if (regulation[value]) return regulation[value];
    if (["OT", "1OT", "OT1"].includes(value)) return "OT";
    const overtimeMatch = value.match(/^(?:OT(\d+)|(\d+)OT)$/);
    if (overtimeMatch) {
        const overtimeNumber = Number(overtimeMatch[1] || overtimeMatch[2]);
        return overtimeNumber <= 1 ? "OT" : `${overtimeNumber}OT`;
    }
    return String(quarter || "").trim();
}

function quarterSortValue(quarter) {
    const normalized = normalizeQuarterLabel(quarter);
    const regulationOrder = { "1st": 0, "2nd": 1, "3rd": 2, "4th": 3, "OT": 4 };
    if (normalized in regulationOrder) return regulationOrder[normalized];
    const overtimeMatch = normalized.match(/^(\d+)OT$/);
    return overtimeMatch ? 3 + Number(overtimeMatch[1]) : 99;
}

// === ΔΥΝΑΜΙΚΗ ΔΗΜΙΟΥΡΓΙΑ QUARTERS ΜΕ ΤΟ ΣΚΟΡ ΤΟΥΣ ===
function buildDynamicQuarters(shotsData, preserveSelection = false) {
    const quartersBars = document.querySelectorAll('.quarters-bar');
    if (quartersBars.length === 0) return;

    const quartersMap = new Map();
    // Προκατασκευάζουμε πάντα τα 4 βασικά δεκάλεπτα
    ["1st", "2nd", "3rd", "4th"].forEach(q => quartersMap.set(q, { maxHome: 0, maxRoad: 0 }));

    shotsData.forEach(shot => {
        if (shot.quarter) {
            const quarter = normalizeQuarterLabel(shot.quarter);
            if (!quartersMap.has(quarter)) {
                quartersMap.set(quarter, { maxHome: 0, maxRoad: 0 });
            }
            const qData = quartersMap.get(quarter);
            if (shot.homeScore !== undefined && shot.homeScore > 0) qData.maxHome = Math.max(qData.maxHome, shot.homeScore);
            if (shot.roadScore !== undefined && shot.roadScore > 0) qData.maxRoad = Math.max(qData.maxRoad, shot.roadScore);
        }
    });

    const uniqueQuarters = Array.from(quartersMap.keys()).sort((a, b) => quarterSortValue(a) - quarterSortValue(b));

    quartersBars.forEach(bar => {
        // Preserve explicit choices, while newly discovered overtime periods default to checked.
        const previousStates = new Map();
        if (preserveSelection) {
            bar.querySelectorAll('.quarter-cb').forEach(cb => previousStates.set(normalizeQuarterLabel(cb.value), cb.checked));
        }

        bar.innerHTML = "";
        uniqueQuarters.forEach(q => {
            const qData = quartersMap.get(q);
            
            // Το σκορ θα δείχνει "-" μέχρι να κάνεις import τα νέα δεδομένα από το parser.py!
            let scoreLabel = `<span style="font-size: 0.65rem; color: #777; margin-top:2px;">-</span>`;
            if (qData && (qData.maxHome > 0 || qData.maxRoad > 0)) {
                scoreLabel = `<span style="font-size: 0.65rem; color: #777; margin-top:2px; font-weight:bold;">${qData.maxHome} - ${qData.maxRoad}</span>`;
            }

            const isChecked = previousStates.has(q) ? previousStates.get(q) : true;

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
        const quarterMatch = !shot.quarter || activeQuarters.has(normalizeQuarterLabel(shot.quarter));
        
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
    setSeasonOptionsForMode(mainModeSelect.value);
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
        if (playerFilterGroup) playerFilterGroup.style.display = "block";
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
    if (mode === "quiz-ball") {
        if (!selectedGame || !selectedSeason) {
            window.alert("Επίλεξε Season και Game για να παίξεις Quiz Ball.");
            return;
        }

        analyticsContent.innerHTML = "<div style='grid-column: 1 / -1; text-align: center; color: #6c63ff; font-weight: bold; font-size: 1.5rem; padding: 40px;'>Ο Αιμίλιος διαβάζει τα στατιστικά... ⏱️</div>";

        try {
            const response = await fetch(`${API_BASE_URL}/api/quiz/who-am-i?game_code=${selectedGame}&season_code=${selectedSeason}`);
            const data = await response.json();

            if (data.error || !data.hints) throw new Error(data.error || "Αποτυχία φόρτωσης quiz.");

            window.quizState.isActive = true;
            window.quizState.hints = data.hints;
            window.quizState.secretName = data.secret_player_name;
            window.quizState.currentHintIndex = 0;

            // Χτίζουμε ένα καθαρό αυτόνομο UI ερωταπαντήσεων μέσα στο analyticsContent
            analyticsContent.innerHTML = `
                <div style="grid-column: 1 / -1; background:#fff; padding:30px; border-radius:12px; border-left:8px solid #6c63ff; box-shadow:0 10px 25px rgba(0,0,0,0.1);">
                    <h2 style="color:#2b528a; margin-bottom: 20px;">🤔 Quiz Ball: Ποιος Είμαι;</h2>
                    <div id="quizChatBox" style="min-height: 150px; background: #f4f6f8; padding: 20px; border-radius: 8px; font-size: 1.1rem; line-height: 1.6; margin-bottom: 20px;">
                        <p style="color: #e74c3c; font-weight: bold;">Στοιχείο 1:</p>
                        <p>${window.quizState.hints[0]}</p>
                    </div>
                    <div style="display: flex; gap: 10px;">
                        <input type="text" id="quizAnswerInput" placeholder="Μάντεψε το όνομα του παίκτη..." autocomplete="off" style="flex: 1; padding: 12px; border: 2px solid #cdd4e2; border-radius: 8px; font-size: 1rem;">
                        <button id="quizAnswerBtn" style="padding: 12px 25px; background: #6c63ff; color: #fff; border: none; border-radius: 8px; font-weight: bold; cursor: pointer; transition: background 0.2s;">ΑΠΑΝΤΗΣΗ</button>
                    </div>
                </div>
            `;

            const quizInput = document.getElementById("quizAnswerInput");
            const quizBtn = document.getElementById("quizAnswerBtn");
            const chatBox = document.getElementById("quizChatBox");

            // Τοπική συνάρτηση για την υποβολή της απάντησης
            const submitAnswer = () => {
                if (!window.quizState.isActive || !quizInput.value.trim()) return;

                const userGuess = quizInput.value.trim().toLowerCase();
                const secret = window.quizState.secretName.toLowerCase();

                // Δέχεται τη σωστή απάντηση ακόμα και αν ο χρήστης γράψει μόνο το επίθετο
                if (secret.includes(userGuess)) {
                    chatBox.innerHTML += `
                        <div style="margin-top: 20px; padding: 15px; background: #d5f5e3; border-radius: 8px; border-left: 5px solid #27ae60;">
                            <strong style="color: #27ae60;">🎉 ΣΩΣΤΟ!</strong> Ήταν ο <b>${window.quizState.secretName}</b>!
                        </div>`;
                    window.quizState.isActive = false;
                    quizBtn.disabled = true;
                    quizInput.disabled = true;
                } else {
                    window.quizState.currentHintIndex++;
                    if (window.quizState.currentHintIndex < 3) {
                        chatBox.innerHTML += `
                            <div style="margin-top: 15px; padding-top: 15px; border-top: 2px dashed #ccc;">
                                <p style="color: #e74c3c; font-weight: bold;">❌ Λάθος! Στοιχείο ${window.quizState.currentHintIndex + 1}:</p>
                                <p>${window.quizState.hints[window.quizState.currentHintIndex]}</p>
                            </div>`;
                    } else {
                        chatBox.innerHTML += `
                            <div style="margin-top: 20px; padding: 15px; background: #fadbd8; border-radius: 8px; border-left: 5px solid #c0392b;">
                                <strong style="color: #c0392b;">ΧΑΣΑΤΕ! 😢</strong> Ο παίκτης ήταν ο <b>${window.quizState.secretName}</b>.
                            </div>`;
                        window.quizState.isActive = false;
                        quizBtn.disabled = true;
                        quizInput.disabled = true;
                        quizBtn.style.display= "none";
                        quizInput.style.display= "none";  
                    }
                }
                quizInput.value = "";
                quizInput.focus();
            };

            // Event Listeners για το κουμπί "Απάντηση" και το πλήκτρο "Enter"
            quizBtn.addEventListener("click", submitAnswer);
            quizInput.addEventListener("keydown", (e) => { if (e.key === "Enter") submitAnswer(); });
            quizInput.focus();

        } catch (error) {
            analyticsContent.innerHTML = `<div style='grid-column: 1 / -1; color: red; text-align:center;'>Σφάλμα: ${error.message}</div>`;
        }
        return; // Τερματίζουμε την εκτέλεση εδώ, αποφεύγοντας την κλήση των άλλων analytics queries
    }
    if (selectedPlayer && mode !== "euro-chart" && mode !== "video-shots") {
        if (mode === "top-lineups") { if (!filterId) { filterId = selectedPlayer; filterType = "on_court"; } } 
        else if (mode === "fouls-drawn") { if (!fouledId) fouledId = selectedPlayer; } 
        else if (mode === "defensive-anchors") { if (!blockerId) blockerId = selectedPlayer; }
        else if (mode === "second-chance") { secondChancePlayer = selectedPlayer; }
    }

    if (mode === "euro-chart" || mode === "video-shots") {
        if (activeShotRequestController) activeShotRequestController.abort();
        const requestController = new AbortController();
        activeShotRequestController = requestController;
        queryGeneration += 1;
        const activeQueryGeneration = queryGeneration;
        mainActionBtn.disabled = true;
        mainActionBtn.innerText = "ΦΟΡΤΩΣΗ...";
        if (isVideoShotMode) {
            showVideoStatus("Φόρτωση video, σουτ και Play-by-Play...");
            const pbpList = document.getElementById("pbpList");
            if (pbpList) pbpList.innerHTML = "<li class='pbp-filter-empty'>Φόρτωση Play-by-Play...</li>";
        }

        try {
            const [shots, playByPlayActions, videoConfig] = await Promise.all([
                fetchFilteredShots(selectedPlayer, selectedAssistant, selectedGame, selectedSeason, filterType, filterId, quarter, minStart, minEnd, null, requestController.signal),
                isVideoShotMode ? fetchMatchPlayByPlay(selectedGame, selectedSeason, requestController.signal) : Promise.resolve([]),
                isVideoShotMode ? fetchVideoConfig(selectedGame, selectedSeason, requestController.signal) : Promise.resolve(null)
            ]);
            if (activeQueryGeneration !== queryGeneration || mainModeSelect.value !== mode) return;
            showVideoStatus();

            if (isVideoShotMode && typeof window.setYouTubeVideo === "function") {
                window.setYouTubeVideo(
                    videoConfig?.available ? videoConfig.youtube_id : null,
                    videoConfig?.playback_lead_seconds ?? 5
                );
                if (!videoConfig?.available || !videoConfig?.timeline_available) {
                    showVideoStatus("Δεν υπάρχει διαθέσιμο ή συγχρονισμένο video για αυτό το παιχνίδι.", "error");
                }
            }
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

                const response = await fetch(`${API_BASE_URL}/api/game/lineups?game_code=${selectedGame}&season_code=${selectedSeason}`, { signal: requestController.signal });
                if (!response.ok) throw new Error(`HTTP error! status: ${response.status}`);
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

                } catch (error) {
                    if (error.name === "AbortError") throw error;
                    console.error("Σφάλμα στα lineups:", error);
                    showVideoStatus("Τα σουτ φορτώθηκαν, αλλά το roster δεν ήταν διαθέσιμο.", "error");
                }
            }

            if (isVideoShotMode && typeof window.setPlayByPlayActions === "function") {
                window.setPlayByPlayActions(playByPlayActions);
                window.currentPlayByPlayGameKey = `${selectedSeason}:${selectedGame}`;
            }
            applyChartFilters();
        } catch (error) {
            if (error.name !== "AbortError" && activeQueryGeneration === queryGeneration) {
                console.error("Σφάλμα στη φόρτωση του shot view:", error);
                if (isVideoShotMode) {
                    showVideoStatus("Αποτυχία φόρτωσης του video game. Έλεγξε ότι το backend τρέχει και δοκίμασε ξανά.", "error");
                    if (typeof window.setPlayByPlayActions === "function") window.setPlayByPlayActions([]);
                } else {
                    window.alert("Αποτυχία φόρτωσης των σουτ. Δοκίμασε ξανά.");
                }
            }
        } finally {
            if (activeShotRequestController === requestController) activeShotRequestController = null;
            if (activeQueryGeneration === queryGeneration) {
                mainActionBtn.disabled = false;
                mainActionBtn.innerText = isVideoShotMode ? "ΑΝΑΖΗΤΗΣΗ ΣΟΥΤ (VIDEO)" : "ΑΝΑΖΗΤΗΣΗ ΣΟΥΤ (GAME)";
            }
        }
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
        
        const gameCodeInput = document.getElementById("analyticsGameCodeInput");
        const gameCode = gameCodeInput?.value.trim() || window.currentScenario?.game_code || "";
        
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
            let expectedPoints = numPossessions * 1.0; // Βασική παραγωγή της ομάδας σου
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
        // 1. ΕΛΕΓΧΟΣ: Έχει επιλέξει Season ο χρήστης;
        let selectedSeason = globalSeasonSelect.value.trim();
        
        if (!selectedSeason) {
            window.alert("Παρακαλώ επέλεξε πρώτα Season (π.χ. 2023-24) ή 'ALL SEASONS' για να παίξεις!");
            return;
        }

        // Αν επέλεξε ALL SEASONS, διαλέγουμε τυχαία μία σεζόν
        if (selectedSeason === "ALL") {
            const availableSeasons = ["E2023", "E2024", "E2025"];
            selectedSeason = availableSeasons[Math.floor(Math.random() * availableSeasons.length)];
        }

        const gameInstructions = document.getElementById("gameInstructions");
        const actualSimulatorUI = document.getElementById("actualSimulatorUI");
        const simMatchupTitle = document.getElementById("simMatchupTitle");
        const simScenarioText = document.getElementById("simScenarioText");
        const rosterPool = document.getElementById("rosterPool");

        // 2. Κρύβουμε τις οδηγίες και εμφανίζουμε αμέσως το Παρκέ
        if (gameInstructions) gameInstructions.style.display = "none";
        if (actualSimulatorUI) actualSimulatorUI.style.display = "block";

        if (simMatchupTitle) simMatchupTitle.innerText = "Φόρτωση κρίσιμου σημείου...";
        if (simScenarioText) simScenarioText.innerText = "Ο διαιτητής σφυρίζει Timeout...";

        // Καθαρισμός προηγούμενου παιχνιδιού
        document.querySelectorAll('.slot').forEach(slot => {
            const existingCard = slot.querySelector('.player-card');
            if (existingCard) existingCard.remove();
            if (!slot.textContent.trim()) slot.textContent = slot.getAttribute("data-position");
        });
        document.getElementById("simulatorResult").innerHTML = "";

        // 3. Φέρνουμε το Σενάριο
        const scenario = await fetchSimulatorScenario(selectedSeason);

        if (scenario && !scenario.error) {
            window.currentScenario = scenario;
            
            const seasonNames = {
                "E2023": "2023-24 Season",
                "E2024": "2024-25 Season",
                "E2025": "2025-26 Season"
            };

            const userSelectedText = globalSeasonSelect.value === "ALL" 
                ? `ALL SEASONS (Έτυχε: ${seasonNames[selectedSeason] || selectedSeason})` 
                : globalSeasonSelect.options[globalSeasonSelect.selectedIndex].text;

            if (simMatchupTitle) simMatchupTitle.innerText = `CRUNCH TIME: Είσαι ο Προπονητής της ${scenario.user_team}!`;
            if (simScenarioText) {
                simScenarioText.innerHTML = `
                    <div style="color: #f39c12; font-size: 0.9rem; margin-bottom: 10px;">
                        <em>Επιλεγμένη Σεζόν: <strong>${userSelectedText}</strong></em>
                    </div>
                    <strong>Αντίπαλος:</strong> ${scenario.opponent} | <strong>4th Quarter</strong> | <strong>Χρόνος:</strong> ${scenario.clock}<br>
                    <strong>Σκορ:</strong> ${scenario.user_score} - ${scenario.opp_score} (Υπέρ - Κατά)<br><br>
                    Έχεις Timeout! Τοποθέτησε 5 παίκτες από τον πάγκο στο παρκέ!
                `;
            }

            // Φόρτωση Ρόστερ
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
    });
}

window.startQuizCategory = async function(category, difficulty,keepStreak = false) {
    if (!keepStreak) window.quizState.streak = 0;
    window.quizState.difficulty = difficulty;
    const analyticsContent = document.getElementById("analyticsContent");

    analyticsContent.innerHTML = "<div style='grid-column: 1 / -1; text-align: center; color: #6c63ff; font-weight: bold; font-size: 1.5rem; padding: 40px;'>Ετοιμάζεται η ερώτηση... ⏱️</div>";

    try {
        const response = await fetch(`${API_BASE_URL}/api/quiz/${category}?difficulty=${difficulty}`);
        const data = await response.json();

        if (data.error) throw new Error(data.error);

        window.quizState.isActive = true;
        window.quizState.secretName = data.secret_player_name;
        window.quizState.category = category; // Κρατάμε το είδος του quiz
        window.quizState.currentHintIndex = 0; // Χρησιμοποιείται ως μετρητής λαθών/hints

        let initialMessage = "";
        const quizPresentation = {
            'who-am-i': { color: '#6c63ff', title: '🤔 Ποιος Είμαι;' },
            'who-is-missing': { color: '#27ae60', title: '❓ Ποιος Λείπει;' },
            'higher-or-lower': { color: '#c0392b', title: '📈 Higher / Lower' },
            'top-5': { color: '#117A65', title: '🔝 Top 5' },
            'fifty-fifty': { color: '#0f9bce', title: '⚖️ 50 / 50' }
        };
        const presentation = quizPresentation[category] || quizPresentation['who-am-i'];
        const themeColor = presentation.color;
        const quizTitle = presentation.title;

        // Διαμόρφωση UI ανάλογα με το παιχνίδι
        if (category === "who-am-i") {
            window.quizState.hints = data.hints;
            initialMessage = `<p style="color: #e74c3c; font-weight: bold;">Στοιχείο 1:</p><p>${window.quizState.hints[0]}</p>`;
        } else if (category === "fifty-fifty") {
            initialMessage = `
                <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 20px;">
                    <span style="background: #e67e22; color: white; padding: 5px 15px; border-radius: 20px; font-weight: 900; font-size: 0.85rem; letter-spacing: 1px;">⚖️ 50 / 50</span>
                    <span style="background: #e74c3c; color: white; padding: 5px 15px; border-radius: 20px; font-weight: 900; font-size: 0.85rem; box-shadow: 0 2px 4px rgba(0,0,0,0.2);">🔥 STREAK: ${window.quizState.streak}</span>
                </div>
                <p style="color: #333; font-weight: 600; text-align: center; font-size: 1.15rem; margin-bottom: 25px;"><i>"${data.question_text}"</i></p>

                <div id="fiftyFiftyButtons" style="display: flex; gap: 20px; justify-content: center;">
                    <button onclick="handleFiftyFifty(0, ${data.correct_index})" style="flex: 1; padding: 25px; background: #34495e; color: white; border: none; border-radius: 12px; font-weight: 900; font-size: 2.5rem; cursor: pointer; transition: transform 0.2s; box-shadow: 0 5px 15px rgba(0,0,0,0.2);">${data.options[0]}</button>
                    <button onclick="handleFiftyFifty(1, ${data.correct_index})" style="flex: 1; padding: 25px; background: #34495e; color: white; border: none; border-radius: 12px; font-weight: 900; font-size: 2.5rem; cursor: pointer; transition: transform 0.2s; box-shadow: 0 5px 15px rgba(0,0,0,0.2);">${data.options[1]}</button>
                </div>

                <div style="text-align: center; margin-top: 20px; font-size: 0.85rem; color: #777; font-weight: bold;">
                    ${data.matchup} | ${data.season}
                </div>
            `;

            window.handleFiftyFifty = function(selectedIndex, correctIndex) {
                const buttonsDiv = document.getElementById("fiftyFiftyButtons");
                if (!buttonsDiv) return;
                const buttons = buttonsDiv.querySelectorAll("button");
                const chatBox = document.getElementById("quizChatBox");

                buttons.forEach(button => { button.disabled = true; });
                buttons[correctIndex].style.background = "#2ecc71";
                const wrongIndex = correctIndex === 0 ? 1 : 0;
                buttons[wrongIndex].style.background = "#e74c3c";

                if (selectedIndex === correctIndex) {
                    window.quizState.streak++;
                    chatBox.innerHTML += `
                        <div style="margin-top: 20px; padding: 15px; background: #d5f5e3; border-radius: 8px; border-left: 5px solid #27ae60; text-align: center;">
                            <strong style="color: #27ae60; font-size: 1.2rem;">🎉 ΣΩΣΤΟ!</strong><br>
                            Φόρτωση επόμενου γύρου... ⏳
                        </div>`;
                    setTimeout(() => {
                        window.startQuizCategory('fifty-fifty', window.quizState.difficulty, true);
                    }, 2000);
                } else {
                    chatBox.innerHTML += `
                        <div style="margin-top: 20px; padding: 15px; background: #fadbd8; border-radius: 8px; border-left: 5px solid #c0392b; text-align: center;">
                            <strong style="color: #c0392b; font-size: 1.2rem;">❌ ΛΑΘΟΣ!</strong><br>
                            Το σερί σου σταμάτησε στο <b>${window.quizState.streak}</b> 🔥!<br><br>
                            <button onclick="window.startQuizCategory('fifty-fifty', window.quizState.difficulty, false)" style="padding: 10px 20px; background: #c0392b; color: white; border: none; border-radius: 8px; font-weight: bold; cursor: pointer; box-shadow: 0 4px 6px rgba(0,0,0,0.2);">🔄 ΠΑΙΞΕ ΞΑΝΑ</button>
                        </div>`;
                }
            };
        } else if (category === "who-is-missing") {
            // 1. Προετοιμασία των παικτών για το γήπεδο
            let allPlayers = [...data.known_players];
            // Επιλέγουμε μια τυχαία θέση (0 έως 4) για τον μυστικό παίκτη
            const secretIndex = Math.floor(Math.random() * 5);
            allPlayers.splice(secretIndex, 0, { isSecret: true });

            // 2. Συντεταγμένες για 5 θέσεις σε μισό γήπεδο (Top-down view)
            const positions = [
                { top: '15px', left: '50%', transform: 'translateX(-50%)' }, // Playmaker (Κορυφή)
                { top: '110px', left: '12%' },                               // Φτερό Αριστερά
                { top: '110px', right: '12%' },                              // Φτερό Δεξιά
                { bottom: '90px', left: '28%' },                             // Post Αριστερά
                { bottom: '90px', right: '28%' }                             // Post Δεξιά
            ];

            // 3. Δημιουργία των εικονιδίων των παικτών
            let playersHTML = '';
            allPlayers.forEach((player, i) => {
                const pos = positions[i];
                const posStyle = `position:absolute; top:${pos.top || 'auto'}; bottom:${pos.bottom || 'auto'}; left:${pos.left || 'auto'}; right:${pos.right || 'auto'}; ${pos.transform ? 'transform:'+pos.transform+';' : ''} display:flex; flex-direction:column; align-items:center; width:80px; z-index: 2;`;

                if (player.isSecret) {
                    playersHTML += `
                        <div style="${posStyle}">
                            <div style="width:50px; height:50px; background: radial-gradient(circle, #e74c3c, #c0392b); border: 2px solid #fff; border-radius: 50%; display:flex; justify-content:center; align-items:center; color:white; font-size:2rem; font-weight:900; box-shadow: 0 4px 10px rgba(0,0,0,0.4); text-shadow: 1px 1px 2px rgba(0,0,0,0.5);">?</div>
                        </div>
                    `;
                } else {
                    // Παίρνουμε το επίθετο για να χωράει κάτω από το εικονίδιο
                    let shortName = player.split(' ').pop();
                    playersHTML += `
                        <div style="${posStyle}">
                            <div style="width:45px; height:45px; background: radial-gradient(circle, #e67e22, #d35400); border: 2px solid #fff; border-radius: 50%; display:flex; justify-content:center; align-items:center; color:white; font-size:1.3rem; box-shadow: 0 4px 8px rgba(0,0,0,0.3);">🏀</div>
                            <span style="color:white; font-weight:800; font-size:0.75rem; text-shadow: 1px 1px 2px #000; text-align:center; margin-top:5px; background: rgba(0,0,0,0.5); padding: 2px 8px; border-radius: 4px; letter-spacing: 0.5px;">${shortName}</span>
                        </div>
                    `;
                }
            });

            // 4. Κατασκευή του Γηπέδου και του Banner (εμπνευσμένο από την εικόνα)
            initialMessage = `
                <div style="position: relative; width: 100%; max-width: 500px; height: 320px; background-color: #d4a373; border: 4px solid #fff; border-radius: 12px; margin: 0 auto 20px; overflow: hidden; box-shadow: 0 10px 20px rgba(0,0,0,0.2);">

                    <!-- Γραμμές Γηπέδου -->
                    <div style="position: absolute; bottom: 0; left: 50%; transform: translateX(-50%); width: 140px; height: 160px; border: 3px solid rgba(255,255,255,0.7); border-bottom: none; background: rgba(255,255,255,0.1);"></div>
                    <div style="position: absolute; bottom: 0; left: 50%; transform: translateX(-50%); width: 400px; height: 300px; border: 3px solid rgba(255,255,255,0.7); border-radius: 50% 50% 0 0 / 100% 100% 0 0; border-bottom: none;"></div>

                    <!-- Παίκτες -->
                    ${playersHTML}

                    <!-- Πράσινο Banner Στατιστικών (Στο κάτω μέρος) -->
                    <div style="position: absolute; bottom: 0; left: 0; width: 100%; background: linear-gradient(to right, #2ecc71, #27ae60); padding: 8px 15px; color: white; display: flex; align-items: center; justify-content: space-between; border-top: 2px solid rgba(255,255,255,0.4); z-index: 3;">
                        <div style="display:flex; align-items:center; gap: 10px;">
                            <div style="background: rgba(255,255,255,0.3); border-radius:50%; width: 35px; height: 35px; display:flex; align-items:center; justify-content:center; font-size:1.2rem;">❓</div>
                            <div style="display: flex; flex-direction: column;">
                                <span style="font-size: 1.05rem; font-weight: 900; text-shadow: 1px 1px 2px rgba(0,0,0,0.3); line-height: 1.1; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; max-width: 250px;">${data.matchup}</span>
                                <span style="font-size: 0.75rem; font-weight: 600; opacity: 0.9;">${data.season}</span>
                            </div>
                        </div>
                        <div style="background: rgba(255,255,255,0.2); padding: 5px 10px; border-radius: 20px; font-weight: 900; font-size: 0.8rem; border: 1px solid rgba(255,255,255,0.5);">
                            ${difficulty.toUpperCase()}
                        </div>
                    </div>
                </div>

                <div style="background: #fdf2e9; padding: 15px; border-radius: 8px; border-left: 5px solid #e67e22;">
                    <p style="color: #d35400; font-weight: 900; margin-bottom: 5px; font-size: 0.9rem; text-transform: uppercase;">Βοηθεια Αιμιλιου:</p>
                    <p style="color: #333; font-weight: 600;">${data.hint}</p>
                </div>
            `;
        } else if (category === "higher-or-lower") {
            window.quizState.playerBStat = data.player_b.stat;

            initialMessage = `
                <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 20px;">
                    <span style="background: #2b528a; color: white; padding: 5px 15px; border-radius: 20px; font-weight: 900; font-size: 0.85rem; letter-spacing: 1px;">📊 ${data.category_name}</span>
                    <span style="background: #e74c3c; color: white; padding: 5px 15px; border-radius: 20px; font-weight: 900; font-size: 0.85rem; box-shadow: 0 2px 4px rgba(0,0,0,0.2);">🔥 STREAK: ${window.quizState.streak}</span>
                </div>
                <p style="color: #333; font-weight: 600; text-align: center; font-size: 1.15rem; margin-bottom: 25px;"><i>"${data.question_text}"</i></p>

                <div style="display: flex; gap: 20px; justify-content: center; align-items: stretch;">
                    <!-- Player A (Φανερό Στατιστικό) -->
                    <div style="flex: 1; background: white; border: 3px solid #3498db; border-radius: 12px; padding: 20px; text-align: center; box-shadow: 0 5px 15px rgba(0,0,0,0.1);">
                        <div style="font-size: 2.5rem; margin-bottom: 10px;">🏀</div>
                        <h3 style="color: #2b528a; margin-bottom: 10px; font-size: 1.1rem;">${data.player_a.name}</h3>
                        <div style="font-size: 3rem; font-weight: 900; color: #3498db;">${data.player_a.stat}</div>
                        <div style="font-size: 0.8rem; color: #777; font-weight: bold; text-transform: uppercase;">${data.category_name}</div>
                    </div>

                    <div style="display: flex; align-items: center; justify-content: center; font-size: 2rem; font-weight: 900; color: #bdc3c7;">VS</div>

                    <!-- Player B (Επιλογή) -->
                    <div style="flex: 1; background: #2b528a; border: 3px solid #2b528a; border-radius: 12px; padding: 20px; text-align: center; box-shadow: 0 5px 15px rgba(0,0,0,0.2); display: flex; flex-direction: column; justify-content: space-between;">
                        <div>
                            <div style="font-size: 2.5rem; margin-bottom: 10px;">❓</div>
                            <h3 style="color: white; margin-bottom: 15px; font-size: 1.1rem;">${data.player_b.name}</h3>
                        </div>
                        <div id="holButtons" style="display: flex; flex-direction: column; gap: 10px;">
                            <button onclick="handleHigherLower('higher', ${data.player_a.stat})" style="padding: 15px; background: #2ecc71; color: white; border: none; border-radius: 8px; font-weight: 900; font-size: 1.2rem; cursor: pointer; transition: transform 0.1s;">⬆️ HIGHER</button>
                            <button onclick="handleHigherLower('lower', ${data.player_a.stat})" style="padding: 15px; background: #e74c3c; color: white; border: none; border-radius: 8px; font-weight: 900; font-size: 1.2rem; cursor: pointer; transition: transform 0.1s;">⬇️ LOWER</button>
                        </div>
                        <div id="holResultDisplay" style="display: none; font-size: 3rem; font-weight: 900; color: white;"></div>
                    </div>
                </div>

                <div style="text-align: center; margin-top: 20px; font-size: 0.85rem; color: #777; font-weight: bold;">
                    ${data.matchup} | ${data.season}
                </div>
            `;

            window.handleHigherLower = function(guess, statA) {
                const statB = window.quizState.playerBStat;
                const buttonsDiv = document.getElementById("holButtons");
                const resultDiv = document.getElementById("holResultDisplay");
                const chatBox = document.getElementById("quizChatBox");

                buttonsDiv.style.display = "none";
                resultDiv.style.display = "block";
                resultDiv.innerText = statB;

                const isHigher = statB > statA;
                const isCorrect = (guess === "higher" && isHigher) || (guess === "lower" && !isHigher);

                if (isCorrect) {
                    window.quizState.streak++;
                    resultDiv.style.color = "#2ecc71";
                    chatBox.innerHTML += `
                        <div style="margin-top: 20px; padding: 15px; background: #d5f5e3; border-radius: 8px; border-left: 5px solid #27ae60; text-align: center;">
                            <strong style="color: #27ae60; font-size: 1.2rem;">🎉 ΣΩΣΤΟ!</strong><br>
                            Ο ${data.player_b.name} είχε ${statB}. Φόρτωση επόμενου γύρου... ⏳
                        </div>`;

                    // Κρύβουμε το input box του chat αφού δεν χρειάζεται
                    document.getElementById("quizAnswerInput").parentElement.style.display = "none";

                    // Αυτόματη φόρτωση επόμενου γύρου μετά από 2 δευτερόλεπτα
                    setTimeout(() => {
                        window.startQuizCategory('higher-or-lower', window.quizState.difficulty, true);
                    }, 2000);

                } else {
                    resultDiv.style.color = "#e74c3c";
                    chatBox.innerHTML += `
                        <div style="margin-top: 20px; padding: 15px; background: #fadbd8; border-radius: 8px; border-left: 5px solid #c0392b; text-align: center;">
                            <strong style="color: #c0392b; font-size: 1.2rem;">❌ ΛΑΘΟΣ!</strong><br>
                            Ο ${data.player_b.name} είχε ${statB}. Το σερί σου σταμάτησε στο <b>${window.quizState.streak}</b> 🔥!<br><br>
                            <button onclick="window.startQuizCategory('higher-or-lower', window.quizState.difficulty, false)" style="padding: 10px 20px; background: #c0392b; color: white; border: none; border-radius: 8px; font-weight: bold; cursor: pointer; box-shadow: 0 4px 6px rgba(0,0,0,0.2);">🔄 ΠΑΙΞΕ ΞΑΝΑ</button>
                        </div>`;

                    // Κρύβουμε το input box του chat
                    document.getElementById("quizAnswerInput").parentElement.style.display = "none";
                }
            };
        } else if (category === "top-5") {
            window.quizState.top5Answers = data.answers;
            window.quizState.top5Revealed = [false, false, false, false, false];
            window.quizState.strikes = 0;

            // Το UI της πράσινης κάρτας
            initialMessage = `
                <div style="background: linear-gradient(135deg, #117A65 0%, #2ecc71 100%); padding: 25px; border-radius: 16px; color: white; box-shadow: 0 10px 25px rgba(0,0,0,0.2); max-width: 600px; margin: 0 auto;">
                    <div style="display: flex; align-items: center; gap: 15px; margin-bottom: 20px;">
                        <div style="background: white; color: #27ae60; font-weight: 900; font-size: 1.5rem; width: 50px; height: 50px; border-radius: 50%; display: flex; align-items: center; justify-content: center; box-shadow: 0 4px 8px rgba(0,0,0,0.2);">🔝5</div>
                        <h3 style="font-size: 1.8rem; font-weight: 900; margin: 0; text-shadow: 1px 1px 2px rgba(0,0,0,0.3);">TOP 5</h3>
                    </div>

                    <div id="top5Board" style="display: flex; flex-direction: column; gap: 12px; margin-bottom: 25px;">
                        ${data.answers.map((ans, i) => `
                            <div id="top5-slot-${i}" style="background: rgba(255,255,255,0.2); border-radius: 12px; padding: 12px 20px; font-size: 1.3rem; font-weight: 800; display: flex; align-items: center; box-shadow: inset 0 2px 5px rgba(0,0,0,0.1); border: 2px solid rgba(255,255,255,0.1);">
                                <span style="background: white; color: #27ae60; border-radius: 50%; width: 28px; height: 28px; display: flex; align-items: center; justify-content: center; font-size: 1rem; margin-right: 15px;">${i + 1}</span>
                                <span id="top5-text-${i}" style="opacity: 0;">??????????</span>
                                <span id="top5-stat-${i}" style="margin-left: auto; font-size: 1rem; opacity: 0; background: rgba(0,0,0,0.2); padding: 4px 10px; border-radius: 8px;">${ans.stat}</span>
                            </div>
                        `).join('')}
                    </div>

                    <div id="strikesContainer" style="display: flex; gap: 10px; background: rgba(0,0,0,0.2); padding: 10px; border-radius: 999px; width: fit-content;">
                        <div class="strike-box" style="width: 25px; height: 25px; border-radius: 50%; background: rgba(255,255,255,0.3); display: flex; align-items: center; justify-content: center; font-weight: bold; color: transparent;">X</div>
                        <div class="strike-box" style="width: 25px; height: 25px; border-radius: 50%; background: rgba(255,255,255,0.3); display: flex; align-items: center; justify-content: center; font-weight: bold; color: transparent;">X</div>
                        <div class="strike-box" style="width: 25px; height: 25px; border-radius: 50%; background: rgba(255,255,255,0.3); display: flex; align-items: center; justify-content: center; font-weight: bold; color: transparent;">X</div>
                    </div>

                    <div style="background: white; color: #1e8449; padding: 15px; border-radius: 12px; margin-top: 20px; text-align: center; font-weight: 900; font-size: 1.1rem; box-shadow: 0 4px 10px rgba(0,0,0,0.1);">
                        ${data.question_text}
                    </div>
                </div>
            `;
        }

        analyticsContent.innerHTML = `
            <div style="grid-column: 1 / -1; background:#fff; padding:30px; border-radius:12px; border-left:8px solid ${themeColor}; box-shadow:0 10px 25px rgba(0,0,0,0.1); position: relative;">
                <button onclick="document.getElementById('mainModeSelect').dispatchEvent(new Event('change'))" style="position:absolute; top:20px; right:20px; background:none; border:none; color:#777; cursor:pointer; font-weight:bold; font-size:1rem;">🔙 Πίσω στο Μενού</button>
                <h2 style="color:#2b528a; margin-bottom: 20px; text-transform: uppercase;">${quizTitle} (${difficulty.toUpperCase()})</h2>

                <div id="quizChatBox" style="min-height: 150px; background: #f4f6f8; padding: 20px; border-radius: 8px; font-size: 1.1rem; line-height: 1.6; margin-bottom: 20px;">
                    ${initialMessage}
                </div>

                <!-- ΑΛΛΑΓΗ ΓΙΑ ΤΟ AUTOCOMPLETE -->
                <div style="display: flex; gap: 10px; align-items: flex-start;">
                    <div style="flex: 1; position: relative;">
                        <input type="text" id="quizAnswerInput" placeholder="Μάντεψε τον παίκτη..." autocomplete="off" style="width: 100%; padding: 12px; border: 2px solid #cdd4e2; border-radius: 8px; font-size: 1rem; box-sizing: border-box;">
                        
                        <!-- Η κρυφή λίστα που θα εμφανίζεται σαν το Google Search -->
                        <div id="autocompleteList" style="position: absolute; top: 100%; left: 0; right: 0; background: #fff; border: 1px solid #cdd4e2; border-top: none; border-radius: 0 0 8px 8px; z-index: 1000; max-height: 200px; overflow-y: auto; display: none; box-shadow: 0 4px 6px rgba(0,0,0,0.1);"></div>
                    </div>
                    <button id="quizAnswerBtn" style="padding: 12px 25px; background: ${themeColor}; color: #fff; border: none; border-radius: 8px; font-weight: bold; cursor: pointer; height: 46px;">ΑΠΑΝΤΗΣΗ</button>
                </div>
            </div>
        `;

        const quizInput = document.getElementById("quizAnswerInput");
        const quizBtn = document.getElementById("quizAnswerBtn");
        const chatBox = document.getElementById("quizChatBox");
        if (category === "fifty-fifty" || category === "higher-or-lower") {
            quizInput.parentElement.style.display = "none";
        }
        
        const autocompleteList = document.getElementById("autocompleteList");

        if (category === "fifty-fifty" || category === "higher-or-lower") {
            quizInput.parentElement.parentElement.style.display = "none";
        }

        // Λίστα με ονόματα παικτών (Εδώ μπορείς να προσθέσεις όσους θες!)
       const euroleaguePlayers = [
            // 1. Panathinaikos AKTOR
            "Kendrick Nunn", "Kostas Sloukas", "Mathias Lessort", "Lorenzo Brown", 
            "Jerian Grant", "Dinos Mitoglou", "Marius Grigonis", "Juancho Hernangomez", 
            "Omer Yurtseven", "Cedi Osman", "Ioannis Papapetrou", "Panagiotis Kalaitzakis", 
            "Dimitris Moraitis", "Alexandros Samodurov", "Kostas Antetokounmpo",

            // 2. Olympiacos Piraeus
            "Sasha Vezenkov", "Evan Fournier", "Kostas Papanikolaou", "Thomas Walkup", 
            "Nikola Milutinov", "Alec Peters", "Moustapha Fall", "Shaquielle McKissic", 
            "Nigel Williams-Goss", "Luca Vildoza", "Tyler Dorsey", "Giannoulis Larentzakis", 
            "Naz Mitrou-Long", "Moses Wright", "Antonis Karagiannidis",

            // 3. Real Madrid
            "Facundo Campazzo", "Mario Hezonja", "Edy Tavares", "Dzanan Musa", 
            "Gabriel Deck", "Sergio Llull", "Serge Ibaka", "Xavier Rathan-Mayes", 
            "Usman Garuba", "Andres Feliz", "Eli Ndiaye", "Alberto Abalde", "Hugo Gonzalez",

            // 4. FC Barcelona
            "Kevin Punter", "Tomas Satoransky", "Nicolas Laprovittola", "Jan Vesely", 
            "Willy Hernangomez", "Jabari Parker", "Chimezie Metu", "Dario Brizuela", 
            "Joel Parra", "Alex Abrines", "Justin Anderson", "Dame Sarr", "Youssoupha Fall",

            // 5. Fenerbahce Beko
            "Nigel Hayes-Davis", "Wade Baldwin", "Bonzie Colson", "Nicolo Melli", 
            "Marko Guduric", "Boban Marjanovic", "Tarik Biberovic", "Sertac Sanli", 
            "Devon Hall", "Erten Gazi", "Melih Mahmutoglu", "Dyshawn Pierre", 
            "Khem Birch", "Scottie Wilbekin", "Metecan Birsen",

            // 6. AS Monaco
            "Mike James", "Elie Okobo", "Alpha Diallo", "Donatas Motiejunas", 
            "Georgios Papagiannis", "Nick Calathes", "Furkan Korkmaz", "Jaron Blossomgame", 
            "Matthew Strazel", "Terry Tarpey", "Mam Jaiteh", "Vitto Brown", "Jordan Loyd",

            // 7. Anadolu Efes
            "Shane Larkin", "Darius Thompson", "Rodrigue Beaubois", "Vincent Poirier", 
            "Rolands Smits", "PJ Dozier", "Stanley Johnson", "Derek Willis", 
            "Dogus Ozdemiroglu", "Ercan Osmani", "Erkan Yilmaz", "Justus Hollatz", 
            "Daniel Oturu", "Burak Can Yildizli",

            // 8. Baskonia Vitoria-Gasteiz
            "Markus Howard", "Chima Moneke", "Tadas Sedekerskis", "Timothe Luwawu-Cabarrot", 
            "Kamar Baldwin", "Trent Forrest", "Donta Hall", "Ognjen Jaramaz", 
            "Nikos Rogkavopoulos", "Sander Raieste", "Khalifa Diop", "Pavel Savkov",

            // 9. Partizan Mozzart Bet Belgrade
            "Carlik Jones", "Frank Ntilikina", "Iffe Lundberg", "Vanja Marinkovic", 
            "Brandon Davies", "Sterling Brown", "Isaac Bonga", "Tyrique Jones", 
            "Aleksej Pokusevski", "Mario Nakic", "Balsa Koprivica", "Arijan Lakic", 
            "Duane Washington Jr.", "Isiaha Mike",

            // 10. Crvena Zvezda Meridianbet Belgrade
            "Milos Teodosic", "Nemanja Nedovic", "Isaiah Canaan", "Joel Bolomboy", 
            "Codi Miller-McIntyre", "Nikola Kalinic", "Luka Mitrovic", "Rokas Giedraitis", 
            "Yago dos Santos", "Mike Daum", "Dejan Davidovac", "Branko Lazic", 
            "Uros Plavsic", "Ognjen Dobric",

            // 11. EA7 Emporio Armani Milan
            "Nikola Mirotic", "Shavon Shields", "Josh Nebo", "Nenad Dimitrijevic", 
            "Zach LeDay", "Fabien Causeur", "Armoni Brooks", "Leandro Bolmaro", 
            "Stefano Tonut", "Giampaolo Ricci", "Guglielmo Caruso", "Diego Flaccadori", 
            "Ousmane Diop",

            // 12. Virtus Segafredo Bologna
            "Toko Shengelia", "Daniel Hackett", "Marco Belinelli", "Isaia Cordinier", 
            "Will Clyburn", "Ante Zizic", "Matt Morgan", "Alessandro Pajola", 
            "Achille Polonara", "Devontae Cacok", "Rayjon Tucker", "Mouhamet Diouf", 
            "Andrejs Grazulis",

            // 13. Paris Basketball
            "T.J. Shorts", "Nadir Hifi", "Collin Malcolm", "Tyson Ward", 
            "Kevarrius Hayes", "Maodo Lo", "Mikael Jantunen", "Bandja Sy", 
            "Sebastjan Janc", "Yakuba Ouattara", "Leopold Cavaliere", "Enzo Shahrvin",

            // 14. Maccabi Playtika Tel Aviv
            "Tamir Blatt", "Jasiel Rivero", "Levi Randolph", "Rokas Jokubaitis", 
            "Jaylen Hoard", "Wenyen Gabriel", "Roman Sorkin", "John DiBartolomeo", 
            "Jake Cohen", "Will Rayman", "Alpha Kaba", "David DeJulius",

            // 15. Zalgiris Kaunas
            "Sylvain Francisco", "Ignas Brazdeikis", "Edgaras Ulanovas", "Alen Smailagic", 
            "Deividas Sirvydis", "Laurynas Birutis", "Lukas Lekavicius", "Brady Manek", 
            "Arnas Butkevicius", "Bryant Dunston", "Matt Mitchell", "Dovydas Giedraitis",

            // 16. FC Bayern Munich
            "Devin Booker", "Vladimir Lucic", "Shabazz Napier", "Johannes Voigtmann", 
            "Carsen Edwards", "Andreas Obst", "Nick Weiler-Babb", "Elias Harris", 
            "Niels Giffey", "Yam Madar", "Danko Brankovic", "Oscar da Silva", 
            "Ivan Kharchenkov",

            // 17. ALBA Berlin
            "Martin Hermannsson", "Louis Olinde", "Gabriele Procida", "Matteo Spagnolo", 
            "Malte Delow", "Matt Thomas", "Justin Bean", "Yanni Wetzell", 
            "Trevion Williams", "Jonas Mattisseck", "Ziga Samar", "Tim Schneider", 
            "Khalifa Koumadje",

            // 18. LDLC ASVEL Villeurbanne
            "Paris Lee", "Theo Maledon", "Joffrey Lauvergne", "Nando De Colo", 
            "Tarik Black", "Shaquille Harrison", "Mbaye Ndiaye", "Neal Sako", 
            "Edwin Jackson", "Charles Kahudi", "Melvin Ajinca", "David Lighty",

            // --- EXTRA TEAMS GIA NA VGOUN 20 ---

            // 19. Valencia Basket 
            "Chris Jones", "Semi Ojeleye", "Jean Montero", "Nate Sestina", 
            "Ethan Happ", "Matt Costello", "Xabi Lopez-Arostegui", "Stefan Jovic", 
            "Jaime Pradilla", "Brancou Badio", "Josep Puerto",

            // 20. CSKA Moscow
            "Melo Trimble", "Aleksa Avramovic", "Casper Ware", "Amath M'Baye", 
            "Tonye Jekiri", "Livio Jean-Charles", "Semen Antonov", "Anton Astapkovich", 
            "Ivan Ukhov", "Vladimir Karpenko"
        ];

        // Event Listener όταν ο χρήστης πληκτρολογεί
        quizInput.addEventListener("input", function() {
            const val = this.value.trim();
            autocompleteList.innerHTML = ""; // Καθαρίζουμε την προηγούμενη λίστα
            
            if (!val) {
                autocompleteList.style.display = "none";
                return;
            }

            // Φιλτράρουμε τους παίκτες που περιέχουν τα γράμματα που πληκτρολόγησε ο χρήστης
            const matches = euroleaguePlayers.filter(player => 
                player.toLowerCase().includes(val.toLowerCase())
            );
            
            if (matches.length > 0) {
                autocompleteList.style.display = "block";
                matches.forEach(match => {
                    const item = document.createElement("div");
                    item.style.cssText = "padding: 10px; cursor: pointer; border-bottom: 1px solid #eee; transition: background 0.2s;";
                    
                    // Κάνουμε Highlight (χρωματίζουμε) τα γράμματα που έγραψε ο χρήστης
                    const regex = new RegExp(`(${val})`, "gi");
                    item.innerHTML = match.replace(regex, `<strong style="color: ${themeColor};">$1</strong>`);

                    // Όταν κάνει κλικ σε μια επιλογή
                    item.addEventListener("click", function() {
                        quizInput.value = match; // Βάζουμε το όνομα στο input
                        autocompleteList.innerHTML = ""; // Καθαρίζουμε τη λίστα
                        autocompleteList.style.display = "none"; // Κρύβουμε το dropdown
                        quizInput.focus(); // Επαναφέρουμε τον κέρσορα στο πεδίο
                    });
                    
                    // Εφέ Hover
                    item.addEventListener("mouseover", () => item.style.backgroundColor = "#f4f6f8");
                    item.addEventListener("mouseout", () => item.style.backgroundColor = "#fff");

                    autocompleteList.appendChild(item);
                });
            } else {
                autocompleteList.style.display = "none";
            }
        });

        // Αν κάνει κλικ οπουδήποτε αλλού στη σελίδα, η λίστα κλείνει
        document.addEventListener("click", function(e) {
            if (e.target !== quizInput) {
                autocompleteList.style.display = "none";
            }
        });
        const submitAnswer = () => {
            if (!window.quizState.isActive || !quizInput.value.trim()) return;

            const userGuess = quizInput.value.trim().toLowerCase();

            if (window.quizState.category === "top-5") {
                let foundMatch = false;

                // Ελέγχουμε όλες τις απαντήσεις του Top 5
                window.quizState.top5Answers.forEach((ans, index) => {
                    if (!window.quizState.top5Revealed[index] && ans.name.toLowerCase().includes(userGuess)) {
                        window.quizState.top5Revealed[index] = true;
                        foundMatch = true;

                        // Αποκάλυψη στο UI
                        const textEl = document.getElementById(`top5-text-${index}`);
                        const statEl = document.getElementById(`top5-stat-${index}`);
                        textEl.innerText = ans.name;
                        textEl.style.opacity = "1";
                        statEl.style.opacity = "1";
                        document.getElementById(`top5-slot-${index}`).style.background = "rgba(255,255,255,0.9)";
                        document.getElementById(`top5-slot-${index}`).style.color = "#27ae60";
                    }
                });

                if (foundMatch) {
                    // Έλεγχος αν τα βρήκε όλα
                    if (window.quizState.top5Revealed.every(v => v === true)) {
                        chatBox.innerHTML += `<div style="margin-top: 15px; padding: 15px; background: #d5f5e3; border-radius: 8px; border-left: 5px solid #27ae60; text-align: center;"><strong style="color: #27ae60;">🎉 ΤΑ ΒΡΗΚΕΣ ΟΛΑ! ΕΙΣΑΙ ΘΡΥΛΟΣ!</strong></div>`;
                        window.quizState.isActive = false;
                        quizBtn.disabled = true;
                        quizInput.disabled = true;
                        quizBtn.style.display="none";
                        quizInput.style.display="none";
                    }
                } else {
                    // Λάθος μαντεψιά -> Χάνεις ζωή
                    window.quizState.strikes++;
                    const strikes = document.querySelectorAll(".strike-box");
                    if (window.quizState.strikes <= 3) {
                        strikes[window.quizState.strikes - 1].style.background = "#e74c3c";
                        strikes[window.quizState.strikes - 1].style.color = "white";
                    }

                    if (window.quizState.strikes >= 3) {
                        // Game Over -> Αποκαλύπτουμε τις υπόλοιπες απαντήσεις
                        window.quizState.top5Answers.forEach((ans, index) => {
                            if (!window.quizState.top5Revealed[index]) {
                                const textEl = document.getElementById(`top5-text-${index}`);
                                const statEl = document.getElementById(`top5-stat-${index}`);
                                textEl.innerText = ans.name;
                                textEl.style.opacity = "1";
                                textEl.style.color = "#e74c3c"; // Κόκκινο για αυτά που δεν βρήκε
                                statEl.style.opacity = "1";
                            }
                        });
                        chatBox.innerHTML += `<div style="margin-top: 15px; padding: 15px; background: #fadbd8; border-radius: 8px; border-left: 5px solid #c0392b; text-align: center;"><strong style="color: #c0392b;">GAME OVER! ❌</strong> Οι απαντήσεις αποκαλύφθηκαν.</div>`;
                        window.quizState.isActive = false;
                        quizBtn.disabled = true;
                        quizInput.disabled = true;
                        quizBtn.style.display="none";
                        quizInput.style.display="none";
                    }
                }
                quizInput.value = "";
                quizInput.focus();
                return; // Τερματίζουμε την εκτέλεση εδώ για το Top 5
            }
            const secret = window.quizState.secretName.toLowerCase();

            if (secret.includes(userGuess)) {
                chatBox.innerHTML += `
                    <div style="margin-top: 20px; padding: 15px; background: #d5f5e3; border-radius: 8px; border-left: 5px solid #27ae60;">
                        <strong style="color: #27ae60;">🎉 ΣΩΣΤΟ!</strong> Ήταν ο <b>${window.quizState.secretName}</b>!
                    </div>`;
                window.quizState.isActive = false;
                quizBtn.disabled = true;
                quizInput.disabled = true;
                quizBtn.style.display= "none";
                quizInput.style.display= "none";
            } else {
                window.quizState.currentHintIndex++;

                if (window.quizState.category === "who-am-i") {
                    if (window.quizState.currentHintIndex < 3) {
                        chatBox.innerHTML += `
                            <div style="margin-top: 15px; padding-top: 15px; border-top: 2px dashed #ccc;">
                                <p style="color: #e74c3c; font-weight: bold;">❌ Λάθος! Στοιχείο ${window.quizState.currentHintIndex + 1}:</p>
                                <p>${window.quizState.hints[window.quizState.currentHintIndex]}</p>
                            </div>`;
                    } else {
                        chatBox.innerHTML += `
                            <div style="margin-top: 20px; padding: 15px; background: #fadbd8; border-radius: 8px; border-left: 5px solid #c0392b;">
                                <strong style="color: #c0392b;">ΧΑΣΑΤΕ! 😢</strong> Ο παίκτης ήταν ο <b>${window.quizState.secretName}</b>.
                            </div>`;
                        window.quizState.isActive = false;
                        quizBtn.disabled = true;
                        quizInput.disabled = true;
                        quizBtn.style.display= "none";
                        quizInput.style.display= "none";
                    }
                } else if (window.quizState.category === "who-is-missing") {
                    // Στο "Ποιος Λείπει;" δίνουμε 2 ευκαιρίες συνολικά
                    if (window.quizState.currentHintIndex < 2) {
                        chatBox.innerHTML += `
                            <div style="margin-top: 15px; padding-top: 15px; border-top: 2px dashed #ccc;">
                                <p style="color: #e74c3c; font-weight: bold;">❌ Λάθος! Έχεις άλλη 1 ευκαιρία. Ξαναπροσπάθησε!</p>
                            </div>`;
                    } else {
                        chatBox.innerHTML += `
                            <div style="margin-top: 20px; padding: 15px; background: #fadbd8; border-radius: 8px; border-left: 5px solid #c0392b;">
                                <strong style="color: #c0392b;">ΧΑΣΑΤΕ! 😢</strong> Ο παίκτης που έλειπε ήταν ο <b>${window.quizState.secretName}</b>.
                            </div>`;
                        window.quizState.isActive = false;
                        quizBtn.disabled = true;
                        quizInput.disabled = true;
                        quizBtn.style.display= "none";
                        quizInput.style.display= "none";
                    }
                }
            }
            quizInput.value = "";
            quizInput.focus();
        };

        quizBtn.addEventListener("click", submitAnswer);
        quizInput.addEventListener("keydown", (e) => { if (e.key === "Enter") submitAnswer(); });
        quizInput.focus();

    } catch (error) {
        analyticsContent.innerHTML = `<div style='grid-column: 1 / -1; color: red; text-align:center;'>Σφάλμα: ${error.message}</div>`;
    }
};
