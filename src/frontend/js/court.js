// court.js

// --- Βοηθητική Συνάρτηση για Κάρτες Παικτών ---
async function renderPlayerCards(lineupUrl, containerId) {
    const containerEl = document.getElementById(containerId);
    containerEl.innerHTML = ""; 

    if (!lineupUrl || !lineupUrl.includes("Lineup_")) {
        containerEl.innerHTML = "<div style='color:#7f8c8d; font-style:italic;'>Δεν βρέθηκε πεντάδα</div>";
        return;
    }
    const parts = lineupUrl.split("Lineup_");
    if (parts.length < 2) return;
    
    const playerIds = parts[1].split("_");
    for (const id of playerIds) {
        const cleanId = id.trim();
        if (!cleanId) continue;
        
        const playerCard = document.createElement("div");
        playerCard.style.display = "flex";
        playerCard.style.alignItems = "center";
        playerCard.style.gap = "8px";
        playerCard.style.background = "#f9f9f9";
        playerCard.style.padding = "4px 8px";
        playerCard.style.borderRadius = "4px";
        playerCard.style.fontSize = "13px";
        
        const img = document.createElement("img");
        img.src = `https://media-api.euroleague.net/images/players/${cleanId}.png`;
        img.onerror = function() {
            this.src = "https://www.euroleaguebasketball.net/media/com_easysocial/avatars/users/default_avatar.png";
        };
        img.width = 24;
        img.height = 24;
        img.style.borderRadius = "50%";
        img.style.objectFit = "cover";
        
        const nameSpan = document.createElement("span");
        nameSpan.innerText = "Φόρτωση..."; 
        playerCard.appendChild(img);
        playerCard.appendChild(nameSpan);
        containerEl.appendChild(playerCard);
        
        try {
            const response = await fetch(`http://localhost:8000/api/player/${cleanId}`);
            const data = await response.json();
            nameSpan.innerText = data.name; 
        } catch (err) {
            console.error("Σφάλμα:", err);
            nameSpan.innerText = `ID: ${cleanId}`;
        }
    }
}

// --- 1. Αρχικοποίηση Σκηνής 3D ---
const container = document.getElementById("courtContainer"); 

const scene = new THREE.Scene();
scene.background = new THREE.Color(0x121218); // Το σκούρο φόντο από το body του CSS σου

const camera = new THREE.PerspectiveCamera(45, container.clientWidth / container.clientHeight, 0.1, 1000);
camera.position.set(0, 65, 75); // Ιδανική γωνία θέασης

const renderer = new THREE.WebGLRenderer({ antialias: true });
renderer.setSize(container.clientWidth, container.clientHeight);
renderer.shadowMap.enabled = true;
container.appendChild(renderer.domElement);

window.addEventListener('resize', () => {
    const width = container.clientWidth;
    const height = container.clientHeight;
    renderer.setSize(width, height);
    camera.aspect = width / height;
    camera.updateProjectionMatrix();
});

const controls = new THREE.OrbitControls(camera, renderer.domElement);
controls.target.set(0, 0, -25);
controls.update();

// Φωτισμός
const ambientLight = new THREE.AmbientLight(0xffffff, 0.8);
scene.add(ambientLight);
const dirLight = new THREE.DirectionalLight(0xffffff, 0.5);
dirLight.position.set(0, 100, 50);
scene.add(dirLight);

// --- 2. Δημιουργία Γηπέδου βάσει του CSS Σχεδίου σου ---
const courtWidth = 150; 
const courtLength = 140; 

const courtGeometry = new THREE.PlaneGeometry(courtWidth, courtLength);

// Δημιουργία Texture με το μοτίβο και τα χρώματα του CSS σου
function createCustomCourtTexture() {
    const canvas = document.createElement('canvas');
    canvas.width = 1200;
    canvas.height = 1120; // 600x560 αναλογία
    const ctx = canvas.getContext('2d');

    // Α. Χρώμα Παρκέ (#e5a463)
    ctx.fillStyle = '#e5a463';
    ctx.fillRect(0, 0, canvas.width, canvas.height);

    // Β. Ρίγες ξύλου (repeating-linear-gradient)
    ctx.fillStyle = 'rgba(0, 0, 0, 0.04)';
    for (let x = 0; x < canvas.width; x += 50) {
        ctx.fillRect(x, 0, 25, canvas.height);
    }

    // Γ. Μπλε Ρακέτα (#2b528a)
    const paintWidth = 392;  // ~196px * 2
    const paintHeight = 464; // ~232px * 2
    const paintX = (canvas.width - paintWidth) / 2;
    const paintY = canvas.height - paintHeight;
    
    ctx.fillStyle = '#2b528a';
    ctx.fillRect(paintX, paintY, paintWidth, paintHeight);

    // Δ. Λευκές Γραμμές
    ctx.strokeStyle = '#ffffff';
    ctx.lineWidth = 8;

    // Εξωτερικό περίγραμμα
    ctx.strokeRect(8, 8, canvas.width - 16, canvas.height - 16);

    // Περίγραμμα ρακέτας
    ctx.strokeRect(paintX, paintY, paintWidth, paintHeight);

    // Ημικύκλιο Ελεύθερων Βολών (Συμπαγές πάνω)
    ctx.beginPath();
    ctx.arc(canvas.width / 2, paintY, 144, Math.PI, 0);
    ctx.stroke();

    // Διακεκομμένο ημικύκλιο μέσα στη ρακέτα (paint::before)
    ctx.beginPath();
    ctx.setLineDash([15, 12]);
    ctx.arc(canvas.width / 2, paintY, 144, 0, Math.PI);
    ctx.stroke();
    ctx.setLineDash([]); // Επαναφορά σε συμπαγή γραμμή

    // Restricted Area (Ημικύκλιο κάτω από το καλάθι)
    ctx.beginPath();
    ctx.arc(canvas.width / 2, canvas.height - 96, 100, Math.PI, 0);
    ctx.stroke();

    // Γραμμή 3 Πόντων
    // Πλευρικές ευθείες
    ctx.beginPath(); ctx.moveTo(110, canvas.height); ctx.lineTo(110, canvas.height - 200); ctx.stroke();
    ctx.beginPath(); ctx.moveTo(canvas.width - 110, canvas.height); ctx.lineTo(canvas.width - 110, canvas.height - 200); ctx.stroke();
    // Τόξο
    ctx.beginPath();
    ctx.arc(canvas.width / 2, canvas.height - 96, 540, Math.PI + 0.28, Math.PI * 2 - 0.28);
    ctx.stroke();

    // Κεντρικό Ημικύκλιο (Στο πάνω μέρος του μισού γηπέδου)
    ctx.beginPath();
    ctx.arc(canvas.width / 2, 0, 144, 0, Math.PI);
    ctx.stroke();

    return new THREE.CanvasTexture(canvas);
}

const courtMaterial = new THREE.MeshStandardMaterial({ 
    map: createCustomCourtTexture(),
    side: THREE.DoubleSide,
    roughness: 0.4,
    metalness: 0.1
});

const court = new THREE.Mesh(courtGeometry, courtMaterial);
court.rotation.x = -Math.PI / 2; 
court.position.z = -courtLength / 2; 
scene.add(court);


// --- 3. Δημιουργία 3D Μπασκέτας (Βάσει του CSS σου) ---
const hoopGroup = new THREE.Group();

// Α. Ο Στύλος (Pole: linear-gradient #777 -> #333)
const poleGeo = new THREE.CylinderGeometry(1.2, 1.2, 22, 16);
const poleMat = new THREE.MeshStandardMaterial({ color: 0x444444, metalness: 0.8, roughness: 0.3 });
const pole = new THREE.Mesh(poleGeo, poleMat);
pole.position.set(0, 9, 3);
hoopGroup.add(pole);

// Βασικός οριζόντιος βραχίονας
const armGeo = new THREE.BoxGeometry(1.5, 1.5, 6);
const arm = new THREE.Mesh(armGeo, poleMat);
arm.position.set(0, 16, 0);
hoopGroup.add(arm);

// Β. Γυάλινο Ταμπλό (Backboard: rgba(255, 255, 255, 0.25))
function createBackboardTexture() {
    const canvas = document.createElement('canvas');
    canvas.width = 400;
    canvas.height = 280;
    const ctx = canvas.getContext('2d');

    ctx.fillStyle = 'rgb(0, 0, 0)';
    ctx.fillRect(0, 0, canvas.width, canvas.height);

    ctx.strokeStyle = '#ffffff';
    ctx.lineWidth = 12;
    ctx.strokeRect(6, 6, canvas.width - 12, canvas.height - 12);

    // Εσωτερικό τετράγωνο (backboard::after)
    ctx.lineWidth = 8;
    ctx.strokeRect(140, 150, 120, 100);

    return new THREE.CanvasTexture(canvas);
}

const boardGeo = new THREE.BoxGeometry(20, 14, 0.4);
const boardMat = new THREE.MeshStandardMaterial({
    map: createBackboardTexture(),
    transparent: true,
    opacity: 0.75,
    roughness: 0.1,
    metalness: 0.2
});
const backboard = new THREE.Mesh(boardGeo, boardMat);
backboard.position.set(0, 18, -3);
hoopGroup.add(backboard);

// Γ. Στεφάνι (#f95c2b)
const rimGeo = new THREE.TorusGeometry(2.4, 0.35, 12, 32);
const rimMat = new THREE.MeshStandardMaterial({ color: 0xf95c2b, roughness: 0.3 });
const rim = new THREE.Mesh(rimGeo, rimMat);
rim.rotation.x = Math.PI / 2;
rim.position.set(0, 14.5, -5.5);
hoopGroup.add(rim);

// Δ. Δίχτυ (3D εφέ χιαστί)
const netGeo = new THREE.CylinderGeometry(2.4, 1.6, 3.8, 16, 4, true);
const netMat = new THREE.MeshBasicMaterial({ color: 0xffffff, wireframe: true, transparent: true, opacity: 0.7 });
const net = new THREE.Mesh(netGeo, netMat);
net.position.set(0, 12.6, -5.5);
hoopGroup.add(net);

scene.add(hoopGroup);
const hoopPosition = new THREE.Vector3(0, 14.5, -5.5);


// --- 4. Σύστημα Σουτ & Τροχιές ---
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
    }
});

function drawTrajectory(startPoint, endPoint) {
    if (currentTrajectory) {
        scene.remove(currentTrajectory);
    }
    const midX = (startPoint.x + endPoint.x) / 2;
    const midZ = (startPoint.z + endPoint.z) / 2;
    const distance = startPoint.distanceTo(endPoint);
    const midY = Math.max(startPoint.y, endPoint.y) + 12 + (distance * 0.25); 
    
    const controlPoint = new THREE.Vector3(midX, midY, midZ);
    const curve = new THREE.QuadraticBezierCurve3(startPoint, controlPoint, endPoint);
    const tubeGeo = new THREE.TubeGeometry(curve, 24, 0.45, 8, false);
    
    const tubeMat = new THREE.MeshStandardMaterial({ 
        color: 0xea5314, 
        emissive: 0x5a1800 
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
    const madeMat = new THREE.MeshStandardMaterial({ color: 0x27ae60, roughness: 0.3 }); 
    const missedMat = new THREE.MeshStandardMaterial({ color: 0xc0392b, roughness: 0.3 }); 
    
    shots.forEach(shot => {
        const mapX = shot.x / 10;
        const mapZ = -shot.y / 10; 
        
        const sphere = new THREE.Mesh(sphereGeo, shot.isMade ? madeMat : missedMat);
        sphere.position.set(mapX, 1.5, mapZ);
        
        sphere.userData = {
            isMade: shot.isMade,
            homeLineup: shot.runningHomeTeamLineup || "",
            roadLineup: shot.runningRoadTeamLineup || ""
        };
        
        scene.add(sphere);
        shotMeshes.push(sphere); 
    });
}

// --- 5. Animation Loop ---
function animate() {
    requestAnimationFrame(animate);
    controls.update(); 
    renderer.render(scene, camera);
}
animate();