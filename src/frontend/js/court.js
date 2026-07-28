// court.js
/**
 * ΓΕΝΙΚΗ ΣΥΝΑΡΤΗΣΗ: Εξάγει τα IDs, φτιάχνει τις κάρτες 
 * και ρωτάει δυναμικά τον server για το όνομα του κάθε παίκτη!
 */
const playerCache = {};
async function renderPlayerCards(lineupUrl, containerId) {
    const containerEl = document.getElementById(containerId);
    containerEl.innerHTML = "Φόρτωση πεντάδας..."; // Δείχνουμε άμεσα Feedback

    if (!lineupUrl || !lineupUrl.includes("Lineup_")) {
        containerEl.innerHTML = "Δεν υπάρχουν δεδομένα πεντάδας";
        return;
    }

    const parts = lineupUrl.split("Lineup_");
    if (parts.length < 2) return;
    
    const playerIds = parts[1].split("_").map(id => id.trim()).filter(id => id);
    containerEl.innerHTML = "";

    // Δημιουργούμε τα DOM elements για όλους τους παίκτες από τώρα
    const cardElements = playerIds.map(cleanId => {
        const playerCard = document.createElement("div");
        playerCard.style.display = "flex";
        playerCard.style.alignItems = "center";
        playerCard.style.gap = "8px";
        playerCard.style.background = "#f9f9f9";
        playerCard.style.padding = "4px 8px";
        playerCard.style.borderRadius = "4px";
        playerCard.style.fontSize = "13px";

        const img = document.createElement("img");
        img.width = 24;
        img.height = 24;
        img.style.borderRadius = "50%";
        img.style.objectFit = "cover";
        img.src = "https://www.euroleaguebasketball.net/media/com_easysocial/avatars/users/default_avatar.png"; // Default μέχρι να φορτώσει

        const nameSpan = document.createElement("span");
        nameSpan.innerText = "Φόρτωση..."; 

        playerCard.appendChild(img);
        playerCard.appendChild(nameSpan);
        containerEl.appendChild(playerCard);

        return { cleanId, nameSpan, img };
    });

    // --- ΠΑΡΑΛΛΗΛΗ ΦΟΡΤΩΣΗ ΟΛΩΝ ΤΩΝ ΠΑΙΚΤΩΝ (Promise.all) ---
    // Αντί για for...of loop που περιμένει έναν-ένα, τους τρεχουμε ΟΛΟΥΣ μαζί!
    await Promise.all(cardElements.map(async ({ cleanId, nameSpan, img }) => {
        try {
            // 1. Ελέγχουμε αν τον έχουμε αποθηκευμένο στη μνήμη (Cache)
            if (playerCache[cleanId]) {
                nameSpan.innerText = playerCache[cleanId].name;
                if (playerCache[cleanId].img) img.src = playerCache[cleanId].img;
                return;
            }

            // 2. Αλλιώς κάνουμε fetch από το backend
            const response = await fetch(`http://localhost:8000/api/player?player=${cleanId}`);
            const data = await response.json();
            const playerData = data.player;

            if (playerData) {
                const playerName = playerData.name || `ID: ${cleanId}`;
                const playerImg = playerData.img || "https://www.euroleaguebasketball.net/media/com_easysocial/avatars/users/default_avatar.png";

                // Αποθήκευση στη cache
                playerCache[cleanId] = { name: playerName, img: playerImg };

                nameSpan.innerText = playerName;
                img.src = playerImg;
            } else {
                nameSpan.innerText = `ID: ${cleanId}`;
            }
        } catch (err) {
            console.error(`Σφάλμα για τον παίκτη ${cleanId}:`, err);
            nameSpan.innerText = `ID: ${cleanId}`;
        }
    }));
}
const container = document.getElementById("courtContainer");

// --- 1. Βασικό στήσιμο της 3D σκηνής ---
const scene = new THREE.Scene();
// Αλλαγή από το αρχικό ανοιχτό γκρι σε ένα σκούρο γκρι/μπλε που θυμίζει κλειστό γήπεδο
scene.background = new THREE.Color(0x1a1a24); 

const camera = new THREE.PerspectiveCamera(45, 600 / 500, 0.1, 1000);
camera.position.set(0, 60, 80); 

const renderer = new THREE.WebGLRenderer({ antialias: true });
renderer.setSize(600, 500);
container.appendChild(renderer.domElement);

const controls = new THREE.OrbitControls(camera, renderer.domElement);
controls.target.set(0, 0, -20);
controls.update();

const ambientLight = new THREE.AmbientLight(0xffffff, 0.7);
scene.add(ambientLight);

const dirLight = new THREE.DirectionalLight(0xffffff, 0.5);
dirLight.position.set(50, 100, 50);
scene.add(dirLight);

// --- 2. Παρκέ & Πλέγμα ---
const courtWidth = 150; 
const courtLength = 140; 

const courtGeometry = new THREE.PlaneGeometry(courtWidth, courtLength);
// Ρεαλιστικό χρώμα ξύλου (maple hardwood)
const courtMaterial = new THREE.MeshStandardMaterial({ 
    color: 0xcba073, 
    side: THREE.DoubleSide,
    roughness: 0.6, // Προσθέτει την αίσθηση του βερνικωμένου αλλά όχι καθρέφτη ξύλου
    metalness: 0.1
});
const court = new THREE.Mesh(courtGeometry, courtMaterial);
court.rotation.x = -Math.PI / 2; 
court.position.z = -courtLength / 2; 
scene.add(court);

// Πιο διακριτικό πλέγμα για να μοιάζει με τις γραμμές του γηπέδου
const gridHelper = new THREE.GridHelper(courtWidth, 15, 0xffffff, 0xdddddd);
gridHelper.position.z = -courtLength / 2;
gridHelper.position.y = 0.1; 
// Μειώνουμε λίγο τη φωτεινότητα του πλέγματος για να μην "χτυπάει" στο μάτι
gridHelper.material.opacity = 0.5;
gridHelper.material.transparent = true;
scene.add(gridHelper);

// --- ΚΛΙΜΑΚΑ & ΣΥΝΤΕΤΑΓΜΕΝΕΣ FIBA / EUROLEAGUE ---
const S = 0.92; // Scale factor για να γίνουν όλες οι γραμμές πιο "στενές" και να αγκαλιάζουν τα σουτ
// Η Euroleague έχει το στεφάνι στο 0,0! Άρα η baseline πάει προς τα πίσω κατά 1.575m
const OFFSET_Z = 15.75 * S; 

// --- ΠΡΟΣΘΗΚΗ: ΖΩΓΡΑΦΙΖΟΝΤΑΣ ΤΟ ΓΗΠΕΔΟ (FIBA LINES) ---
function drawCourtLines() {
    const lineMaterial = new THREE.LineBasicMaterial({ color: 0xffffff, linewidth: 2 });
    const linesGroup = new THREE.Group();
    linesGroup.position.y = 0.2; 

    function createLine(points) {
        const geometry = new THREE.BufferGeometry().setFromPoints(points);
        return new THREE.Line(geometry, lineMaterial);
    }

    // 1. Εξωτερικές Γραμμές (Μισό Γήπεδο)
    const w = 75 * S; 
    const halfCourtZ = OFFSET_Z - (140 * S); 
    linesGroup.add(createLine([
        new THREE.Vector3(-w, 0, OFFSET_Z),
        new THREE.Vector3(w, 0, OFFSET_Z),
        new THREE.Vector3(w, 0, halfCourtZ),
        new THREE.Vector3(-w, 0, halfCourtZ),
        new THREE.Vector3(-w, 0, OFFSET_Z)
    ]));

    // 2. Ρακέτα (Paint) 
    const pw = 24.5 * S;
    const pl = OFFSET_Z - (58 * S); 
    linesGroup.add(createLine([
        new THREE.Vector3(-pw, 0, OFFSET_Z),
        new THREE.Vector3(-pw, 0, pl),
        new THREE.Vector3(pw, 0, pl),
        new THREE.Vector3(pw, 0, OFFSET_Z)
    ]));

    // 3. Ημικύκλιο Βολών
    const rFT = 18 * S;
    const ftCurve = new THREE.EllipseCurve(0, pl, rFT, rFT, 0, Math.PI, false, 0);
    const ftPoints = ftCurve.getPoints(50).map(p => new THREE.Vector3(p.x, 0, p.y));
    linesGroup.add(createLine(ftPoints));

    const ftCurveBottom = new THREE.EllipseCurve(0, pl, rFT, rFT, Math.PI, Math.PI * 2, false, 0);
    const ftPointsBottom = ftCurveBottom.getPoints(50).map(p => new THREE.Vector3(p.x, 0, p.y));
    const dashedMaterial = new THREE.LineDashedMaterial({ color: 0xffffff, dashSize: 2, gapSize: 2 });
    const ftBottomGeo = new THREE.BufferGeometry().setFromPoints(ftPointsBottom);
    const ftBottomLine = new THREE.Line(ftBottomGeo, dashedMaterial);
    ftBottomLine.computeLineDistances(); 
    linesGroup.add(ftBottomLine);

    // 4. Γραμμή Τριπόντου (Το τρίποντο ξεκινάει με κέντρο το στεφάνι στο 0,0!)
    const r3P = 67.5 * S;
    const cornerW = 66 * S;
    const cornerDepth = OFFSET_Z - (29.9 * S); 

    linesGroup.add(createLine([
        new THREE.Vector3(-cornerW, 0, OFFSET_Z),
        new THREE.Vector3(-cornerW, 0, cornerDepth) 
    ]));
    linesGroup.add(createLine([
        new THREE.Vector3(cornerW, 0, OFFSET_Z),
        new THREE.Vector3(cornerW, 0, cornerDepth)
    ]));

    // Τέλεια μαθηματική ένωση του τόξου με τις γωνίες
    const angleOffset = Math.atan2(Math.abs(cornerDepth), cornerW);
    const tpCurve = new THREE.EllipseCurve(
        0, 0,                      // Κέντρο είναι πλέον το (0,0)
        r3P, r3P,                
        Math.PI + angleOffset,     
        Math.PI * 2 - angleOffset, 
        false,                     
        0
    );
    const tpPoints = tpCurve.getPoints(50).map(p => new THREE.Vector3(p.x, 0, p.y));
    linesGroup.add(createLine(tpPoints));

    // 5. Κέντρο Γηπέδου 
    const centerCurve = new THREE.EllipseCurve(0, halfCourtZ, rFT, rFT, 0, Math.PI, true, 0);
    const centerPoints = centerCurve.getPoints(50).map(p => new THREE.Vector3(p.x, 0, p.y));
    linesGroup.add(createLine(centerPoints));

    scene.add(linesGroup);
}
drawCourtLines();

// --- 3. ΤΑΜΠΛΟ & ΣΤΕΦΑΝΙ (Τέλεια προσαρμοσμένα) ---
const boardGeo = new THREE.BoxGeometry(18 * S, 10.5 * S, 0.5); 
const boardMat = new THREE.MeshStandardMaterial({ 
    color: 0xe6f2ff, transparent: true, opacity: 0.35, roughness: 0.1 
});
const backboard = new THREE.Mesh(boardGeo, boardMat);
backboard.position.set(0, 15, OFFSET_Z - (12 * S)); // 1.2m μπροστά από τη baseline
scene.add(backboard);

const rimGeo = new THREE.TorusGeometry(2.25 * S, 0.3, 8, 24); 
const rimMat = new THREE.MeshStandardMaterial({ color: 0xeb5314 }); 
const rim = new THREE.Mesh(rimGeo, rimMat);
rim.rotation.x = Math.PI / 2; 
rim.position.set(0, 14, 0); // Το στεφάνι είναι πλέον ακριβώς στο 0,0!
scene.add(rim);

// Ανανεώνουμε και τη μεταβλητή για το πού καταλήγει η τροχιά
const hoopPosition = new THREE.Vector3(0, 14, 0);

// --- 4. Σουτ & Αλληλεπίδραση (Κλικ) ---
let shotMeshes = [];
let currentTrajectory = null; 

const raycaster = new THREE.Raycaster();
const mouse = new THREE.Vector2();

container.addEventListener('click', (event) => {
    const rect = renderer.domElement.getBoundingClientRect();
    mouse.x = ((event.clientX - rect.left) / rect.width) * 2 - 1;
    mouse.y = -((event.clientY - rect.top) / rect.height) * 2 + 1;
    
    raycaster.setFromCamera(mouse, camera);
    const intersects = raycaster.intersectObjects(shotMeshes);
    
    if (intersects.length > 0) {
        const clickedShot = intersects[0].object;
        renderPlayerCards(clickedShot.userData.homeLineup, "homePlayersList");
        renderPlayerCards(clickedShot.userData.roadLineup, "roadPlayersList");
        
        if (clickedShot.userData.isMade) {
            drawTrajectory(clickedShot.position, hoopPosition);
        }

        // --- ΝΕΟ: THE VIDEO JUMP ---
        const seconds = clickedShot.userData.videoSeconds;
        console.log(`Geia ${seconds} `);
        // Αν έχουμε δευτερόλεπτα (δεν είναι 0) και ο player του YouTube έχει φορτώσει
        if (seconds && seconds > 0 && typeof player !== 'undefined' && player.seekTo) {
            // Πάμε 4 δευτερόλεπτα ΠΡΙΝ το σουτ για να δούμε τη φάση
            let jumpTime = seconds - 8; 
            if (jumpTime < 0) jumpTime = 0;
            
            console.log(`Jump on video: ${jumpTime} seconds`);
            player.seekTo(jumpTime, true);
            player.playVideo();
        }else{
            console.log("YouTube Player not ready or not found time for this play.");
        }
    }
});

function drawTrajectory(startPoint, endPoint) {
    if (currentTrajectory) {
        scene.remove(currentTrajectory);
    }

    const midX = (startPoint.x + endPoint.x) / 2;
    const midZ = (startPoint.z + endPoint.z) / 2;
    const distance = startPoint.distanceTo(endPoint);
    const midY = Math.max(startPoint.y, endPoint.y) + 15 + (distance * 0.3); 

    const controlPoint = new THREE.Vector3(midX, midY, midZ);
    const curve = new THREE.QuadraticBezierCurve3(startPoint, controlPoint, endPoint);

    const tubeGeo = new THREE.TubeGeometry(curve, 20, 0.4, 8, false);
    // Χρώμα τροχιάς που θυμίζει μπάλα μπάσκετ αντί για το αρχικό χρυσό
    const tubeMat = new THREE.MeshStandardMaterial({ 
        color: 0xca5816, 
        emissive: 0x3a1505 // Ελαφριά λάμψη στο ίδιο φάσμα
    }); 

    currentTrajectory = new THREE.Mesh(tubeGeo, tubeMat);
    scene.add(currentTrajectory);
}

function drawShots(shots) {
    shotMeshes.forEach(mesh => scene.remove(mesh));
    shotMeshes = [];
    if (currentTrajectory) {
        scene.remove(currentTrajectory);
        currentTrajectory = null;
    }

    const sphereGeo = new THREE.SphereGeometry(1.5, 16, 16);
    const madeMat = new THREE.MeshStandardMaterial({ color: 0x27ae60 }); 
    const missedMat = new THREE.MeshStandardMaterial({ color: 0xc0392b }); 

    shots.forEach(shot => {
        const mapX = shot.x / 10;
        const mapZ = -shot.y / 10; 

        const sphere = new THREE.Mesh(sphereGeo, shot.isMade ? madeMat : missedMat);
        sphere.position.set(mapX, 1.5, mapZ);
        
        sphere.userData = {
            isMade: shot.isMade,
            homeLineup: shot.runningHomeTeamLineup || "",
            roadLineup: shot.runningRoadTeamLineup || "",
            videoSeconds: shot.videoSeconds,
            playTime: shot.playTime,
            playerName: shot.playerName // <-- Αποθηκεύουμε το όνομα του παίκτη!
        };      
        scene.add(sphere);
        shotMeshes.push(sphere); 
    });

    // Καλούμε την συνάρτηση για να γεμίσει και η λίστα στα δεξιά
    renderPlayByPlay(shots);
}

// --- ΝΕΟ: ΣΥΝΑΡΤΗΣΗ ΓΙΑ ΤΟ PLAY-BY-PLAY ---
function renderPlayByPlay(shots) {
    const list = document.getElementById("pbpList");
    if (!list) return;
    list.innerHTML = ""; // Καθάρισμα λίστας

    if (shots.length === 0) {
        list.innerHTML = "<li style='color: #777; text-align: center;'>Δεν βρέθηκαν σουτ.</li>";
        return;
    }

    shots.forEach(shot => {
        const li = document.createElement("li");
        li.style.padding = "10px";
        li.style.borderBottom = "1px solid #eee";
        li.style.cursor = "pointer";
        li.style.transition = "background 0.2s";
        li.style.fontSize = "13px";
        
        const statusIcon = shot.isMade ? "🟢" : "🔴";
        const playerName = shot.playerName || "Άγνωστος";
        const time = shot.playTime || "00:00";
        
        li.innerHTML = `<strong>${time}</strong> - ${statusIcon} <b>${playerName}</b>`;
        
        li.onmouseover = () => li.style.background = "#f0f8ff";
        li.onmouseout = () => li.style.background = "transparent";
        
        // ΟΤΑΝ ΚΑΝΕΙΣ ΚΛΙΚ ΣΤΗ ΛΙΣΤΑ, ΠΑΕΙ ΤΟ ΒΙΝΤΕΟ ΕΚΕΙ!
        li.onclick = () => {
            if (shot.videoSeconds && shot.videoSeconds > 0 && typeof player !== 'undefined' && player.seekTo) {
                let jumpTime = shot.videoSeconds - 5;
                if (jumpTime < 0) jumpTime = 0;
                player.seekTo(jumpTime, true);
                player.playVideo();
            }
        };
        
        list.appendChild(li);
    });
}

// --- 5. Η λούπα κίνησης ---
function animate() {
    requestAnimationFrame(animate);
    controls.update(); 
    renderer.render(scene, camera);
}
animate();

const tooltip = document.getElementById("shotTooltip");

container.addEventListener('mousemove', (event) => {
    const rect = renderer.domElement.getBoundingClientRect();
    mouse.x = ((event.clientX - rect.left) / rect.width) * 2 - 1;
    mouse.y = -((event.clientY - rect.top) / rect.height) * 2 + 1; 
    
    raycaster.setFromCamera(mouse, camera);
    const intersects = raycaster.intersectObjects(shotMeshes);
    
    if (intersects.length > 0) {
        const hoveredShot = intersects[0].object;
        const status = hoveredShot.userData.isMade ? "🟢 Εύστοχο" : "🔴 Άστοχο";
        const time = hoveredShot.userData.playTime || "Άγνωστος χρόνος";
        const pName = hoveredShot.userData.playerName || "Άγνωστος Παίκτης";
        
        tooltip.style.display = "block";
        tooltip.style.left = (event.pageX + 15) + "px";
        tooltip.style.top = (event.pageY + 15) + "px";
        
        // Το Tooltip τώρα δείχνει δυναμικά το όνομα του παίκτη!
        tooltip.innerHTML = `
            <div style="font-weight: 900; margin-bottom: 5px; color: #f1c40f; font-size: 16px;">${pName}</div>
            Χρόνος: ${time}<br>
            Κατάσταση: ${status}
        `;
        
        document.body.style.cursor = "pointer";
    } else {
        tooltip.style.display = "none";
        document.body.style.cursor = "default";
    }
});
