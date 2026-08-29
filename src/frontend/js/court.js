// court.js

const container = document.getElementById("courtContainer");

// --- 1. ΒΑΣΙΚΗ ΣΚΗΝΗ & ΚΑΜΕΡΑ ---
const scene = new THREE.Scene();
scene.background = new THREE.Color(0x1a1a24); 

const camera = new THREE.PerspectiveCamera(45, container.clientWidth / container.clientHeight, 0.1, 1000);
camera.position.set(0, 160, 120); 

const renderer = new THREE.WebGLRenderer({ antialias: true });
renderer.setSize(container.clientWidth, container.clientHeight);
container.appendChild(renderer.domElement);

const controls = new THREE.OrbitControls(camera, renderer.domElement);
controls.target.set(0, 0, 0); 
controls.update();

const ambientLight = new THREE.AmbientLight(0xffffff, 0.8);
scene.add(ambientLight);

window.resizeCourt = function() {
    if (!container.clientWidth) return;
    renderer.setSize(container.clientWidth, container.clientHeight);
    camera.aspect = container.clientWidth / container.clientHeight;
    camera.updateProjectionMatrix();
};
window.addEventListener('resize', window.resizeCourt);

// --- 2. ΠΑΡΚΕ ---
// EuroLeague coordinates are centimetres with the centre of the rim at (0, 0).
// The Three.js scene uses decimetres, then applies one uniform display scale.
const SHOT_COORDS_PER_SCENE_UNIT = 10;
const S = 0.92;
const FIBA_COURT = Object.freeze({
    halfLength: 140,
    halfWidth: 75,
    basketFromBaseline: 15.75
});
const courtLength = FIBA_COURT.halfLength * 2 * S;
const courtWidth = FIBA_COURT.halfWidth * 2 * S;

const courtGeometry = new THREE.PlaneGeometry(courtLength, courtWidth);
const courtMaterial = new THREE.MeshStandardMaterial({ color: 0xcba073, side: THREE.DoubleSide, roughness: 0.8 });
const court = new THREE.Mesh(courtGeometry, courtMaterial);
court.rotation.x = -Math.PI / 2; 
scene.add(court);

// --- 3. ΖΩΓΡΑΦΙΖΟΝΤΑΣ ΤΟ FULL COURT ---
function drawCourtLines() {
    const lineMaterial = new THREE.LineBasicMaterial({ color: 0xffffff, linewidth: 2 });
    const linesGroup = new THREE.Group();
    linesGroup.position.y = 0.2; 

    function createLine(points) {
        const geometry = new THREE.BufferGeometry().setFromPoints(points);
        return new THREE.Line(geometry, lineMaterial);
    }

    const L = FIBA_COURT.halfLength * S;
    const W = FIBA_COURT.halfWidth * S;

    linesGroup.add(createLine([
        new THREE.Vector3(-L, 0, -W), new THREE.Vector3(L, 0, -W),
        new THREE.Vector3(L, 0, W), new THREE.Vector3(-L, 0, W), new THREE.Vector3(-L, 0, -W)
    ]));
    linesGroup.add(createLine([new THREE.Vector3(0, 0, -W), new THREE.Vector3(0, 0, W)])); 
    
    const centerCurve = new THREE.EllipseCurve(0, 0, 18 * S, 18 * S, 0, Math.PI * 2, false, 0);
    linesGroup.add(createLine(centerCurve.getPoints(50).map(p => new THREE.Vector3(p.x, 0, p.y))));

    [-1, 1].forEach(sign => {
        const baselineX = L * sign;
        const hoopX = (L - FIBA_COURT.basketFromBaseline * S) * sign;
        const paintEndX = (L - 58 * S) * sign;

        linesGroup.add(createLine([
            new THREE.Vector3(baselineX, 0, -24.5 * S), new THREE.Vector3(paintEndX, 0, -24.5 * S),
            new THREE.Vector3(paintEndX, 0, 24.5 * S), new THREE.Vector3(baselineX, 0, 24.5 * S)
        ]));

        const ftCurve = new THREE.EllipseCurve(paintEndX, 0, 18 * S, 18 * S, -Math.PI/2, Math.PI/2, sign === 1, 0);
        linesGroup.add(createLine(ftCurve.getPoints(50).map(p => new THREE.Vector3(p.x, 0, p.y))));

        const cornerDepthX = (L - 29.9 * S) * sign;
        const cornerW = 66 * S;
        linesGroup.add(createLine([new THREE.Vector3(baselineX, 0, -cornerW), new THREE.Vector3(cornerDepthX, 0, -cornerW)]));
        linesGroup.add(createLine([new THREE.Vector3(baselineX, 0, cornerW), new THREE.Vector3(cornerDepthX, 0, cornerW)]));

        const pts = [];
        for (let i = 0; i <= 50; i++) {
            const theta = (sign === -1 ? -Math.PI/2 : Math.PI/2) + (i/50) * Math.PI;
            const x = hoopX + 67.5 * S * Math.cos(theta);
            const z = 67.5 * S * Math.sin(theta);
            if (Math.abs(z) <= cornerW + 0.1) pts.push(new THREE.Vector3(x, 0, z));
        }
        linesGroup.add(createLine(pts));

        const boardMat = new THREE.MeshStandardMaterial({ color: 0xe6f2ff, transparent: true, opacity: 0.35 });
        const backboard = new THREE.Mesh(new THREE.BoxGeometry(0.5, 10.5 * S, 18 * S), boardMat);
        backboard.position.set((L - 12 * S) * sign, 15, 0);
        scene.add(backboard);

        const rimMat = new THREE.MeshStandardMaterial({ color: 0xeb5314 });
        const rim = new THREE.Mesh(new THREE.TorusGeometry(2.25 * S, 0.3, 8, 24), rimMat);
        rim.rotation.x = Math.PI / 2; 
        rim.position.set(hoopX, 14, 0); 
        scene.add(rim);
    });

    scene.add(linesGroup);
}
drawCourtLines();

// --- ΓΚΛΟΜΠΑΛ ΜΕΤΑΒΛΗΤΕΣ ΓΙΑ ΤΟ 3D ---
let shotMeshes = [];
const raycaster = new THREE.Raycaster();
const mouse = new THREE.Vector2();

// Βελτιστοποίηση: Φτιάχνουμε τα σχήματα μία φορά για να μην κρασάρει η κάρτα γραφικών
const sphereGeo = new THREE.SphereGeometry(2.0, 16, 16);
const torusGeo = new THREE.TorusGeometry(2.0, 0.5, 8, 16);
const matHome = new THREE.MeshStandardMaterial({ color: 0xea5314 }); 
const matRoad = new THREE.MeshStandardMaterial({ color: 0x9b59b6 }); 
const matMade = new THREE.MeshStandardMaterial({ color: 0x27ae60 }); 
const matMiss = new THREE.MeshStandardMaterial({ color: 0xc0392b }); 

function mapShotCoordinatesToCourt(shot, isHome) {
    const rawX = Number(shot.x);
    const rawY = Number(shot.y);
    if (!Number.isFinite(rawX) || !Number.isFinite(rawY)) return null;

    // The parser uses (-1, -1) when no coordinate exists.
    if (rawX === -1 && rawY === -1) return null;

    const lateralFromRim = THREE.MathUtils.clamp(
        rawX / SHOT_COORDS_PER_SCENE_UNIT,
        -FIBA_COURT.halfWidth,
        FIBA_COURT.halfWidth
    );
    const longitudinalFromRim = THREE.MathUtils.clamp(
        rawY / SHOT_COORDS_PER_SCENE_UNIT,
        -FIBA_COURT.basketFromBaseline,
        FIBA_COURT.halfLength - FIBA_COURT.basketFromBaseline
    );

    const basketX = (isHome ? -1 : 1)
        * (FIBA_COURT.halfLength - FIBA_COURT.basketFromBaseline)
        * S;
    const towardCenter = isHome ? 1 : -1;

    return {
        x: basketX + towardCenter * longitudinalFromRim * S,
        z: (isHome ? lateralFromRim : -lateralFromRim) * S
    };
}

// Exposed for deterministic coordinate checks without depending on rendering.
window.mapShotCoordinatesToCourt = mapShotCoordinatesToCourt;

// --- 4. ΣΟΥΤ & ΛΟΓΙΚΗ ΓΙΑ TA MODES ---
window.drawShots = function(shots) {
    shotMeshes.forEach(mesh => scene.remove(mesh));
    shotMeshes = [];

    const mode = document.getElementById("mainModeSelect").value;
    
    shots.forEach(shot => {
        let isHome = shot.teamType === "home" || (
            !shot.teamType && window.homePlayersSet && window.homePlayersSet.has(shot.playerName)
        );
        let finalMat, colorHex;

        if (mode === "euro-chart") {
            finalMat = isHome ? matHome : matRoad;
            colorHex = isHome ? 0xea5314 : 0x9b59b6;
        } else {
            finalMat = shot.isMade ? matMade : matMiss;
            colorHex = shot.isMade ? 0x27ae60 : 0xc0392b;
        }

        const courtPosition = mapShotCoordinatesToCourt(shot, isHome);
        if (!courtPosition) return;
        
        let mesh = shot.isMade ? new THREE.Mesh(sphereGeo, finalMat) : new THREE.Mesh(torusGeo, finalMat);
        if (!shot.isMade) mesh.rotation.x = Math.PI / 2;

        mesh.position.set(courtPosition.x, 1.5, courtPosition.z);
        
        mesh.userData = {
            isMade: shot.isMade,
            playerName: shot.playerName,
            playTime: shot.playTime,
            quarter: shot.quarter,
            actionType: shot.action_type,
            teamType: shot.teamType,
            homeScore: shot.homeScore,
            roadScore: shot.roadScore,
            rawX: shot.x,
            rawY: shot.y,
            videoSeconds: shot.videoSeconds,
            homeLineup: shot.runningHomeTeamLineup,
            roadLineup: shot.runningRoadTeamLineup,
            colorHex: colorHex
        };      
        
        scene.add(mesh);
        shotMeshes.push(mesh); 
    });

};

// --- 5. ΚΛΙΚ & HOVER ΣΤΑ ΣΟΥΤ ---
container.addEventListener('click', (event) => {
    const rect = renderer.domElement.getBoundingClientRect();
    mouse.x = ((event.clientX - rect.left) / rect.width) * 2 - 1;
    mouse.y = -((event.clientY - rect.top) / rect.height) * 2 + 1; 
    
    raycaster.setFromCamera(mouse, camera);
    const intersects = raycaster.intersectObjects(shotMeshes);
    
    if (intersects.length > 0) {
        const shot = intersects[0].object.userData;
        const mode = document.getElementById("mainModeSelect").value;
        if (mode === "euro-chart" && window.updateCurrentLineups) {
            window.updateCurrentLineups(shot.homeLineup, shot.roadLineup);
        }
        if (mode === "video-shots" && shot.videoSeconds && typeof window.playVideoAt === "function") {
            window.playVideoAt(shot.videoSeconds);
        }
    }
});

const tooltip = document.getElementById("shotTooltip");

container.addEventListener('mousemove', (event) => {
    const rect = renderer.domElement.getBoundingClientRect();
    mouse.x = ((event.clientX - rect.left) / rect.width) * 2 - 1;
    mouse.y = -((event.clientY - rect.top) / rect.height) * 2 + 1; 
    
    raycaster.setFromCamera(mouse, camera);
    const intersects = raycaster.intersectObjects(shotMeshes);
    
    if (intersects.length > 0) {
        const shot = intersects[0].object.userData;
        const status = shot.isMade ? "Εύστοχο" : "Άστοχο";
        const time = shot.playTime || "--:--";
        const quarter = (shot.quarter || "-").toUpperCase();
        const pName = shot.playerName || "Άγνωστος Παίκτης";
        const tColor = "#" + shot.colorHex.toString(16).padStart(6, '0');
        
        tooltip.style.display = "block";
        tooltip.style.left = (event.pageX + 15) + "px";
        tooltip.style.top = (event.pageY + 15) + "px";
        tooltip.innerHTML = `
            <div style="font-weight: 900; margin-bottom: 5px; color: ${tColor}; font-size: 14px;">${pName}</div>
            Περίοδος: ${quarter} · Χρόνος: ${time}<br>
            Κατάσταση: <b>${status}</b> · Σκορ: ${shot.homeScore ?? 0}-${shot.roadScore ?? 0}`;
        document.body.style.cursor = "pointer";
    } else {
        tooltip.style.display = "none";
        document.body.style.cursor = "default";
    }
});

function animate() {
    requestAnimationFrame(animate);
    controls.update(); 
    renderer.render(scene, camera);
}
animate();

const ACTION_CATEGORIES = [
    { id: "shots", label: "Shots", matches: type => /PointShot/.test(type) },
    { id: "free-throws", label: "Free Throws", matches: type => /FreeThrow/.test(type) },
    { id: "rebounds", label: "Rebounds", matches: type => /Rebound/.test(type) },
    { id: "assists", label: "Assists", matches: type => /Assist/.test(type) },
    { id: "turnovers", label: "Turnovers", matches: type => /Turnover/.test(type) },
    { id: "fouls", label: "Fouls", matches: type => /Foul/.test(type) },
    { id: "steals", label: "Steals", matches: type => /Steal/.test(type) },
    { id: "blocks", label: "Blocks", matches: type => /Block|ShotRejected/.test(type) },
    { id: "substitutions", label: "Substitutions", matches: type => /Substitution|PlayerIn|PlayerOut/.test(type) },
    { id: "timeouts", label: "Timeouts", matches: type => /Timeout/.test(type) },
    { id: "jump-balls", label: "Jump Balls", matches: type => /JumpBall/.test(type) },
    { id: "periods", label: "Periods", matches: type => /BeginPeriod|EndPeriod|PeriodStart|PeriodEnd|GameEnd|EndGame/.test(type) },
    { id: "other", label: "Other", matches: () => true }
];

window.currentPlayByPlayData = [];
window.activePbpCategories = new Set();
window.aiPbpActionUris = null;
window.aiPbpFilterLabel = "";
window.lastAiPbpMatches = [];
window.pbpVisibleCount = 80;
const PBP_RENDER_BATCH_SIZE = 80;

function resetPlayByPlayWindow() {
    window.pbpVisibleCount = PBP_RENDER_BATCH_SIZE;
    const container = document.getElementById("pbpContainer");
    if (container) container.scrollTop = 0;
}

function getActionCategory(action) {
    const type = String(action.action_type || "");
    return ACTION_CATEGORIES.find(category => category.matches(type));
}

function getAiFilteredActions(actions) {
    if (!(window.aiPbpActionUris instanceof Set)) return actions;
    return actions.filter(action => window.aiPbpActionUris.has(action.uri));
}

function renderAiPlayByPlayControl(container, matchCount) {
    if (!(window.aiPbpActionUris instanceof Set)) return;

    const control = document.createElement("div");
    control.className = "pbp-ai-filter-control";
    const label = document.createElement("span");
    const searchLabel = window.aiPbpFilterLabel ? ` · ${window.aiPbpFilterLabel}` : "";
    label.textContent = `✦ AI FILTER: ${matchCount} actions${searchLabel}`;

    const clearButton = document.createElement("button");
    clearButton.type = "button";
    clearButton.textContent = "CLEAR AI FILTER";
    clearButton.addEventListener("click", window.clearAiPlayByPlayFilter);

    control.append(label, clearButton);
    container.appendChild(control);
}

function renderActionTypeFilters(actions) {
    const container = document.getElementById("pbpActionFilters");
    if (!container) return;
    container.innerHTML = "";

    const availableActions = getAiFilteredActions(actions);
    const counts = new Map();
    availableActions.forEach(action => {
        const category = getActionCategory(action);
        counts.set(category.id, (counts.get(category.id) || 0) + 1);
    });

    renderAiPlayByPlayControl(container, availableActions.length);

    ACTION_CATEGORIES.filter(category => counts.has(category.id)).forEach(category => {
        const label = document.createElement("label");
        label.className = "pbp-filter-chip";
        label.innerHTML = `
            <input type="checkbox" value="${category.id}" ${window.activePbpCategories.has(category.id) ? "checked" : ""}>
            <span>${category.label} (${counts.get(category.id)})</span>`;
        label.querySelector("input").addEventListener("change", event => {
            if (event.target.checked) window.activePbpCategories.add(category.id);
            else window.activePbpCategories.delete(category.id);
            resetPlayByPlayWindow();
            renderPlayByPlay(window.currentPlayByPlayData);
        });
        container.appendChild(label);
    });

    const createCommand = (text, selectAll) => {
        const button = document.createElement("button");
        button.type = "button";
        button.className = "pbp-filter-command";
        button.textContent = text;
        button.addEventListener("click", () => {
            window.activePbpCategories = selectAll ? new Set(counts.keys()) : new Set();
            container.querySelectorAll("input[type='checkbox']").forEach(checkbox => {
                checkbox.checked = selectAll;
            });
            resetPlayByPlayWindow();
            renderPlayByPlay(window.currentPlayByPlayData);
        });
        container.appendChild(button);
    };
    if (counts.size > 1) {
        createCommand("All", true);
        createCommand("Clear", false);
    }
}

window.setPlayByPlayActions = function(actions) {
    window.currentPlayByPlayData = Array.isArray(actions) ? actions : [];
    window.aiPbpActionUris = null;
    window.aiPbpFilterLabel = "";
    window.lastAiPbpMatches = [];
    window.activePbpCategories = new Set(
        window.currentPlayByPlayData.map(action => getActionCategory(action).id)
    );
    resetPlayByPlayWindow();
    renderActionTypeFilters(window.currentPlayByPlayData);
    renderPlayByPlay(window.currentPlayByPlayData);
};

window.applyAiPlayByPlayFilter = function(actionUris, label = "", actionKind = "") {
    const requestedUris = new Set((Array.isArray(actionUris) ? actionUris : []).filter(Boolean));
    const exactMatches = window.currentPlayByPlayData.filter(action => requestedUris.has(action.uri));
    let matchingActions = exactMatches;

    // Older/generated queries may return the assisted shot URI. For assist questions,
    // display the linked PBP-style Assist event at the same clock/sequence instead.
    if (actionKind === "assists") {
        const assistActions = window.currentPlayByPlayData.filter(action => getActionCategory(action).id === "assists");
        const directlyMatchedAssists = exactMatches.filter(action => getActionCategory(action).id === "assists");
        const nearbyAssists = exactMatches
            .filter(action => getActionCategory(action).id !== "assists")
            .map(action => {
                const actionSequence = Number(action.sequence || 0);
                const candidates = assistActions.filter(assist =>
                    String(assist.quarter || "").toUpperCase() === String(action.quarter || "").toUpperCase()
                    && (assist.playTime === action.playTime || Math.abs(Number(assist.sequence || 0) - actionSequence) <= 3)
                );
                return candidates.sort((a, b) => {
                    const sameClockA = a.playTime === action.playTime ? 0 : 1;
                    const sameClockB = b.playTime === action.playTime ? 0 : 1;
                    return sameClockA - sameClockB
                        || Math.abs(Number(a.sequence || 0) - actionSequence) - Math.abs(Number(b.sequence || 0) - actionSequence);
                })[0];
            })
            .filter(Boolean);
        matchingActions = [...new Map(
            [...directlyMatchedAssists, ...nearbyAssists].map(action => [action.uri, action])
        ).values()];
    }

    window.aiPbpActionUris = new Set(matchingActions.map(action => action.uri));
    window.aiPbpFilterLabel = label;
    window.lastAiPbpMatches = matchingActions;
    matchingActions.forEach(action => window.activePbpCategories.add(getActionCategory(action).id));
    resetPlayByPlayWindow();
    renderActionTypeFilters(window.currentPlayByPlayData);
    renderPlayByPlay(window.currentPlayByPlayData);
    document.getElementById("pbpContainer")?.scrollIntoView({ behavior: "smooth", block: "start" });
    return matchingActions.length;
};

window.clearAiPlayByPlayFilter = function() {
    window.aiPbpActionUris = null;
    window.aiPbpFilterLabel = "";
    window.lastAiPbpMatches = [];
    window.activePbpCategories = new Set(
        window.currentPlayByPlayData.map(action => getActionCategory(action).id)
    );
    resetPlayByPlayWindow();
    renderActionTypeFilters(window.currentPlayByPlayData);
    renderPlayByPlay(window.currentPlayByPlayData);
};

function renderPlayByPlay(actions) {
    const list = document.getElementById("pbpList");
    if (!list) return;
    list.innerHTML = ""; 

    if (actions.length === 0) {
        list.innerHTML = "<li class='pbp-filter-empty'>Δεν βρέθηκαν ενέργειες.</li>";
        return;
    }

    const quarterOrder = (quarter) => {
        const normalized = String(quarter || "").trim().toLowerCase();
        const baseOrder = { "1st": 0, "2nd": 1, "3rd": 2, "4th": 3, "ot": 4 };
        if (normalized in baseOrder) return baseOrder[normalized];
        const overtimeMatch = normalized.match(/^(\d+)ot$/);
        return overtimeMatch ? 3 + Number(overtimeMatch[1]) : 99;
    };
    const clockSeconds = (clock) => {
        const parts = String(clock || "").split(":").map(Number);
        return parts.length === 2 && parts.every(Number.isFinite) ? parts[0] * 60 + parts[1] : -1;
    };
    const escapeHtml = (value) => String(value ?? "").replace(/[&<>'"]/g, char => ({
        "&": "&amp;", "<": "&lt;", ">": "&gt;", "'": "&#39;", "\"": "&quot;"
    })[char]);
    const readableAction = (actionType) => String(actionType || "Action")
        .replace(/([a-z])([A-Z])/g, "$1 $2")
        .replace(/Three Point/g, "3-Point")
        .replace(/Two Point/g, "2-Point");

    const aiFilteredActions = getAiFilteredActions(actions);
    const filteredActions = aiFilteredActions.filter(action =>
        window.activePbpCategories.has(getActionCategory(action).id)
    );
    if (filteredActions.length === 0) {
        list.innerHTML = window.aiPbpActionUris instanceof Set
            ? "<li class='pbp-filter-empty'>Δεν βρέθηκαν Play-by-Play ενέργειες για το AI Search.</li>"
            : "<li class='pbp-filter-empty'>Επίλεξε τουλάχιστον έναν τύπο ενέργειας.</li>";
        return;
    }

    const sortedActions = [...filteredActions].sort((a, b) => {
        const quarterDifference = quarterOrder(a.quarter) - quarterOrder(b.quarter);
        const timeDifference = clockSeconds(b.playTime) - clockSeconds(a.playTime);
        return quarterDifference || timeDifference || Number(a.sequence || 0) - Number(b.sequence || 0);
    });
    const visibleActions = sortedActions.slice(0, Math.max(PBP_RENDER_BATCH_SIZE, window.pbpVisibleCount));
    const homeTeamName = document.getElementById("homeTeamTitle")?.textContent?.trim() || "HOME TEAM";
    const roadTeamName = document.getElementById("roadTeamTitle")?.textContent?.trim() || "ROAD TEAM";

    const headings = document.createElement("li");
    headings.className = "pbp-team-headings";
    headings.innerHTML = `
        <span class="home-heading">${escapeHtml(homeTeamName)}</span>
        <span class="clock-heading">Quarter / Time</span>
        <span class="road-heading">${escapeHtml(roadTeamName)}</span>`;
    list.appendChild(headings);

    let renderedQuarter = null;
    visibleActions.forEach(action => {
        const quarter = String(action.quarter || "-").toUpperCase();
        if (quarter !== renderedQuarter) {
            renderedQuarter = quarter;
            const divider = document.createElement("li");
            divider.className = "pbp-quarter-divider";
            divider.textContent = `${quarter} QUARTER`;
            list.appendChild(divider);
        }

        const isNeutral = action.teamType === "neutral" || !action.teamType;
        const isHome = action.teamType === "home" || (
            !action.teamType && window.homePlayersSet && window.homePlayersSet.has(action.playerName)
        );
        const side = isNeutral ? "neutral" : (isHome ? "home" : "road");
        const actionType = String(action.action_type || "Action");
        const isShot = /PointShot/.test(actionType);
        const isFreeThrow = /FreeThrow/.test(actionType);
        const isScoringAttempt = isShot || isFreeThrow;
        const isMade = /Made/.test(actionType) || action.isMade === true;
        const attemptType = isFreeThrow ? "FT" : (actionType.includes("ThreePoint") ? "3PT" : "2PT");
        const resultLabel = isScoringAttempt
            ? `${isMade ? "MADE" : "MISSED"} ${attemptType}`
            : getActionCategory(action).label.toUpperCase();
        const meta = [`SCORE ${action.homeScore ?? 0}-${action.roadScore ?? 0}`];
        if (action.isFastBreak) meta.push("FAST BREAK");
        if (action.isSecondChance) meta.push("2ND CHANCE");
        if (action.isFromTurnover) meta.push("OFF TURNOVER");
        const metaHtml = meta.map(item => `<span>${escapeHtml(item)}</span>`).join("");

        const li = document.createElement("li");
        li.className = `pbp-event-row${isNeutral ? " neutral" : ""}`;
        const playerName = action.playerName || "";
        const time = action.playTime || "00:00";

        const actionCard = `
            <article class="pbp-action-card ${side}${action.videoSeconds > 0 ? " clickable" : ""}">
                ${playerName ? `<strong class="pbp-player">${escapeHtml(playerName)}</strong>` : ""}
                <div class="pbp-action-name">${escapeHtml(readableAction(actionType))}</div>
                <span class="pbp-result ${isScoringAttempt ? (isMade ? "made" : "missed") : "neutral"}">${resultLabel}</span>
                <div class="pbp-meta">${metaHtml}</div>
            </article>`;
        const emptySide = `<div aria-hidden="true"></div>`;
        li.innerHTML = isNeutral ? actionCard : `
                ${isHome ? actionCard : emptySide}
                <div class="pbp-clock"><span>${escapeHtml(quarter)}</span><strong>${escapeHtml(time)}</strong></div>
                ${isHome ? emptySide : actionCard}`;

        if (isNeutral) {
            const neutralMeta = li.querySelector(".pbp-meta");
            neutralMeta.insertAdjacentHTML("afterbegin", `<span>${escapeHtml(quarter)} · ${escapeHtml(time)}</span>`);
        }

        const card = li.querySelector(".pbp-action-card");
        card.addEventListener("click", () => {
            if (action.videoSeconds && typeof window.playVideoAt === "function") {
                window.playVideoAt(action.videoSeconds, action.playbackLeadSeconds);
            }
        });
        list.appendChild(li);
    });

    if (visibleActions.length < sortedActions.length) {
        const pagination = document.createElement("li");
        pagination.className = "pbp-pagination";

        const status = document.createElement("span");
        status.textContent = `Showing ${visibleActions.length} of ${sortedActions.length} actions`;

        const loadMore = document.createElement("button");
        loadMore.type = "button";
        loadMore.className = "pbp-load-more";
        loadMore.textContent = `SHOW ${Math.min(PBP_RENDER_BATCH_SIZE, sortedActions.length - visibleActions.length)} MORE`;
        loadMore.addEventListener("click", () => {
            const container = document.getElementById("pbpContainer");
            const previousScrollTop = container?.scrollTop || 0;
            window.pbpVisibleCount += PBP_RENDER_BATCH_SIZE;
            renderPlayByPlay(window.currentPlayByPlayData);
            if (container) container.scrollTop = previousScrollTop;
        });

        pagination.append(status, loadMore);
        list.appendChild(pagination);
    }
}
