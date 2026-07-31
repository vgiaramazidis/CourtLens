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
const S = 0.92; 
const courtLength = 280 * S; 
const courtWidth = 150 * S;  

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

    const L = 140 * S; 
    const W = 75 * S;  

    linesGroup.add(createLine([
        new THREE.Vector3(-L, 0, -W), new THREE.Vector3(L, 0, -W),
        new THREE.Vector3(L, 0, W), new THREE.Vector3(-L, 0, W), new THREE.Vector3(-L, 0, -W)
    ]));
    linesGroup.add(createLine([new THREE.Vector3(0, 0, -W), new THREE.Vector3(0, 0, W)])); 
    
    const centerCurve = new THREE.EllipseCurve(0, 0, 18 * S, 18 * S, 0, Math.PI * 2, false, 0);
    linesGroup.add(createLine(centerCurve.getPoints(50).map(p => new THREE.Vector3(p.x, 0, p.y))));

    [-1, 1].forEach(sign => {
        const baselineX = L * sign;
        const hoopX = (L - 15.75 * S) * sign;
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

// --- 4. ΣΟΥΤ & ΛΟΓΙΚΗ ΓΙΑ TA MODES ---
window.drawShots = function(shots) {
    shotMeshes.forEach(mesh => scene.remove(mesh));
    shotMeshes = [];

    const mode = document.getElementById("mainModeSelect").value;
    
    shots.forEach(shot => {
        let isHome = window.homePlayersSet && window.homePlayersSet.has(shot.playerName);
        let finalMat, finalX, finalZ, colorHex;

        if (mode === "euro-chart") {
            finalMat = isHome ? matHome : matRoad;
            colorHex = isHome ? 0xea5314 : 0x9b59b6;
            if (isHome) {
                finalX = -140 * S + (shot.y / 10) * S; 
                finalZ = (shot.x / 10) * S;
            } else {
                finalX = 140 * S - (shot.y / 10) * S;  
                finalZ = -(shot.x / 10) * S; 
            }
        } else {
            finalMat = shot.isMade ? matMade : matMiss;
            colorHex = shot.isMade ? 0x27ae60 : 0xc0392b;
            finalX = -140 * S + (shot.y / 10) * S;
            finalZ = (shot.x / 10) * S;
        }
        
        let mesh = shot.isMade ? new THREE.Mesh(sphereGeo, finalMat) : new THREE.Mesh(torusGeo, finalMat);
        if (!shot.isMade) mesh.rotation.x = Math.PI / 2;

        mesh.position.set(finalX, 1.5, finalZ);
        
        mesh.userData = {
            isMade: shot.isMade,
            playerName: shot.playerName,
            playTime: shot.playTime,
            videoSeconds: shot.videoSeconds,
            homeLineup: shot.runningHomeTeamLineup,
            roadLineup: shot.runningRoadTeamLineup,
            colorHex: colorHex
        };      
        
        scene.add(mesh);
        shotMeshes.push(mesh); 
    });

    renderPlayByPlay(shots);
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
        if (mode === "video-shots" && window.updateVideoLineups) {
            window.updateVideoLineups(shot.homeLineup, shot.roadLineup);
        }
        if (shot.videoSeconds && shot.videoSeconds > 0 && typeof player !== 'undefined' && player.seekTo) {
            let jumpTime = shot.videoSeconds - 5;
            player.seekTo(jumpTime < 0 ? 0 : jumpTime, true);
            player.playVideo();
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
        const pName = shot.playerName || "Άγνωστος Παίκτης";
        const tColor = "#" + shot.colorHex.toString(16).padStart(6, '0');
        
        tooltip.style.display = "block";
        tooltip.style.left = (event.pageX + 15) + "px";
        tooltip.style.top = (event.pageY + 15) + "px";
        tooltip.innerHTML = `
            <div style="font-weight: 900; margin-bottom: 5px; color: ${tColor}; font-size: 14px;">${pName}</div>
            Χρόνος: ${time}<br>Κατάσταση: <b>${status}</b>`;
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

function renderPlayByPlay(shots) {
    const list = document.getElementById("pbpList");
    if (!list) return;
    list.innerHTML = ""; 

    if (shots.length === 0) {
        list.innerHTML = "<li style='color: #777; text-align: center;'>Δεν βρέθηκαν σουτ.</li>";
        return;
    }

    shots.forEach(shot => {
        const li = document.createElement("li");
        li.style.padding = "8px";
        li.style.borderBottom = "1px solid #eee";
        li.style.cursor = "pointer";
        li.style.fontSize = "13px";
        const statusIcon = shot.isMade ? "🟢" : "🔴";
        const playerName = shot.playerName || "Άγνωστος";
        const time = shot.playTime || "00:00";
        
        li.innerHTML = `<strong>${time}</strong> - ${statusIcon} <b>${playerName}</b>`;
        li.onclick = () => {
            if (shot.videoSeconds && shot.videoSeconds > 0 && typeof player !== 'undefined' && player.seekTo) {
                let jumpTime = shot.videoSeconds - 5;
                player.seekTo(jumpTime < 0 ? 0 : jumpTime, true);
                player.playVideo();
            }
        };
        list.appendChild(li);
    });
}