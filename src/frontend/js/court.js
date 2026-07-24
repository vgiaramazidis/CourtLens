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

// --- 3. Δημιουργία Μπασκέτας ---
// Ταμπλό - Πιο ρεαλιστικό "γυαλί"
const boardGeo = new THREE.BoxGeometry(18, 10.5, 0.5); 
const boardMat = new THREE.MeshStandardMaterial({ 
    color: 0xe6f2ff, // Ελαφριά γαλάζια απόχρωση γυαλιού
    transparent: true, 
    opacity: 0.35, // Πιο διάφανο
    roughness: 0.1
});
const backboard = new THREE.Mesh(boardGeo, boardMat);
backboard.position.set(0, 15, 0); 
scene.add(backboard);

// Στεφάνι (Torus) - Το αυθεντικό πορτοκαλί-κόκκινο χρώμα (Basketball Rim Orange)
const rimGeo = new THREE.TorusGeometry(2.25, 0.3, 8, 24); 
const rimMat = new THREE.MeshStandardMaterial({ color: 0xeb5314 }); 
const rim = new THREE.Mesh(rimGeo, rimMat);
rim.rotation.x = Math.PI / 2; 
rim.position.set(0, 14, -2.5); 
scene.add(rim);

const hoopPosition = new THREE.Vector3(0, 14, -2.5);

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
    // Κρατάμε το πράσινο και το κόκκινο για Data Visualization, αλλά τα κάνουμε λίγο πιο "παστέλ" για να δένουν με τον φωτισμό
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
            videoSeconds: shot.videoSeconds // <-- ΝΕΟ
        };      
        scene.add(sphere);
        shotMeshes.push(sphere); 
    });
}

// --- 5. Η λούπα κίνησης ---
function animate() {
    requestAnimationFrame(animate);
    controls.update(); 
    renderer.render(scene, camera);
}
animate();
