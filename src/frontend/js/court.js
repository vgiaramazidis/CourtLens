/* 3D court geometry and pointer interaction. Text equivalents live in main.js. */
(() => {
try {

const container = document.getElementById("courtContainer");

const scene = new THREE.Scene();
scene.background = new THREE.Color(0xf6f7f8);

const camera = new THREE.PerspectiveCamera(45, Math.max(1, container.clientWidth) / Math.max(1, container.clientHeight), 0.1, 1000);
camera.position.set(0, 220, 185);

const renderer = new THREE.WebGLRenderer({ antialias: true });
renderer.outputEncoding = THREE.sRGBEncoding;
renderer.setSize(Math.max(1, container.clientWidth), Math.max(1, container.clientHeight));
renderer.setPixelRatio(Math.min(window.devicePixelRatio || 1, 2));
container.appendChild(renderer.domElement);

const controls = new THREE.OrbitControls(camera, renderer.domElement);
controls.target.set(0, 0, 0);
controls.minDistance=100; controls.maxDistance=450; controls.maxPolarAngle=Math.PI/2-.05;
controls.enableDamping=false;
controls.enableRotate=false;
controls.touches = { ONE: THREE.TOUCH.PAN, TWO: THREE.TOUCH.DOLLY_PAN };
controls.mouseButtons = { LEFT: THREE.MOUSE.PAN, MIDDLE: THREE.MOUSE.DOLLY, RIGHT: THREE.MOUSE.PAN };
controls.update();

const ambientLight = new THREE.AmbientLight(0xffffff, 0.8);
scene.add(ambientLight);

window.resizeCourt = function() {
    if (!container.clientWidth) return;
    renderer.setSize(Math.max(1, container.clientWidth), Math.max(1, container.clientHeight));
    camera.aspect = Math.max(1, container.clientWidth) / Math.max(1, container.clientHeight);
    camera.updateProjectionMatrix();
    render();
};
window.addEventListener('resize', window.resizeCourt);

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
const courtMaterial = new THREE.MeshStandardMaterial({ color: 0xe4c696, side: THREE.DoubleSide, roughness: 0.8 });
courtMaterial.color.convertSRGBToLinear();
const court = new THREE.Mesh(courtGeometry, courtMaterial);
court.rotation.x = -Math.PI / 2;
scene.add(court);

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

let shotMeshes = [];
let selectedShotUri = null;
const raycaster = new THREE.Raycaster();
const mouse = new THREE.Vector2();

const sphereGeo = new THREE.SphereGeometry(2.0, 16, 16);
const torusGeo = new THREE.TorusGeometry(2.0, 0.5, 8, 16);


const matMade = new THREE.MeshStandardMaterial({ color: 0xc64013 });
const matMiss = new THREE.MeshStandardMaterial({ color: 0x344a51 });
matMade.color.convertSRGBToLinear();matMiss.color.convertSRGBToLinear();
// Share four materials rather than allocating a new material on each selection.
const matMadeDim = matMade.clone();
const matMissDim = matMiss.clone();
[matMadeDim, matMissDim].forEach(material=>{
    material.transparent=true;material.opacity=.16;material.depthWrite=false;
});
const focusRing = new THREE.Mesh(
    new THREE.TorusGeometry(4.7,.35,8,48),
    new THREE.MeshBasicMaterial({color:0x172431,depthTest:false})
);
focusRing.rotation.x=Math.PI/2;focusRing.visible=false;focusRing.renderOrder=20;scene.add(focusRing);

function applyShotFocus() {
    const selected=selectedShotUri && shotMeshes.find(mesh=>mesh.userData.action_uri===selectedShotUri);
    shotMeshes.forEach(mesh=>{
        const focused=mesh===selected;
        mesh.material=selected && !focused
            ? (mesh.userData.isMade?matMadeDim:matMissDim)
            : (mesh.userData.isMade?matMade:matMiss);
        mesh.scale.setScalar(focused?1.6:1);
        mesh.renderOrder=focused?10:0;
    });
    focusRing.visible=Boolean(selected);
    if(selected)focusRing.position.copy(selected.position);
}

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

window.drawShots = function(shots) {
    shotMeshes.forEach(mesh => scene.remove(mesh));
    shotMeshes = [];



    shots.forEach(shot => {
        let isHome = shot.teamType === "home" || (
            !shot.teamType && window.homePlayersSet && window.homePlayersSet.has(shot.playerName)
        );
        const finalMat = shot.isMade ? matMade : matMiss;
        const colorHex = shot.isMade ? 0xc64013 : 0x344a51;

        const courtPosition = mapShotCoordinatesToCourt(shot, isHome);
        if (!courtPosition) return;

        let mesh = shot.isMade ? new THREE.Mesh(sphereGeo, finalMat) : new THREE.Mesh(torusGeo, finalMat);
        if (!shot.isMade) mesh.rotation.x = Math.PI / 2;

        mesh.position.set(courtPosition.x, 1.5, courtPosition.z);

        mesh.userData = {
            ...shot,
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
    applyShotFocus();render();

};

function render() { if (container.clientWidth && !document.hidden) renderer.render(scene,camera); }
controls.addEventListener('change',render);
new ResizeObserver(window.resizeCourt).observe(container);
window.resetCourtView = function() { camera.position.set(0,220,185); controls.target.set(0,0,0); controls.update(); render(); };
window.highlightShot = function(uri) { selectedShotUri=uri || null;applyShotFocus();render(); };
document.getElementById('resetCourt').onclick=window.resetCourtView;
document.getElementById('rotateCourt').onclick=()=>{const x=camera.position.x,z=camera.position.z;camera.position.x=z;camera.position.z=-x;controls.update();render();};
document.getElementById('zoomInCourt').onclick=()=>{if(camera.position.length()>115)camera.position.multiplyScalar(.85);controls.update();render();};
document.getElementById('zoomOutCourt').onclick=()=>{if(camera.position.length()<390)camera.position.multiplyScalar(1.15);controls.update();render();};
document.getElementById('topCourt').onclick=()=>{camera.position.set(0,310,.1);controls.update();render();};
function hitAt(event) {
    const rect=renderer.domElement.getBoundingClientRect();
    mouse.x=((event.clientX-rect.left)/rect.width)*2-1;
    mouse.y=-((event.clientY-rect.top)/rect.height)*2+1;
    raycaster.setFromCamera(mouse,camera);
    return raycaster.intersectObjects(shotMeshes)[0]?.object.userData;
}
let pointerStart=null;
container.addEventListener('pointerdown',event=>{pointerStart={x:event.clientX,y:event.clientY};});
container.addEventListener('pointerup',event=>{
    if(!pointerStart || Math.hypot(event.clientX-pointerStart.x,event.clientY-pointerStart.y)>8) {
        pointerStart=null;
        return;
    }
    pointerStart=null;
    const shot=hitAt(event);
    if(shot) window.App?.selectShot(shot);
    else window.App?.clearShotSelection();
});
const tooltip=document.getElementById('shotTooltip');
container.addEventListener('pointermove',event=>{
    if(event.pointerType==='touch')return;
    const shot=hitAt(event);tooltip.hidden=!shot;
    renderer.domElement.style.cursor=shot?'pointer':'grab';
    if(!shot)return;
    tooltip.textContent=`${shot.playerName || 'Unknown player'} · ${shot.isMade?'Made':'Missed'} · ${String(shot.quarter || '').toUpperCase()} · ${shot.playTime || '—'} remaining`;
    tooltip.style.left=`${Math.max(8,Math.min(event.clientX+12,window.innerWidth-272))}px`;
    tooltip.style.top=`${Math.max(8,Math.min(event.clientY+12,window.innerHeight-90))}px`;
});
container.addEventListener('pointerleave',()=>{tooltip.hidden=true;});
document.addEventListener('visibilitychange',render);
render();

} catch (error) {
    console.warn('3D court unavailable:',error);
    const element=document.getElementById('courtContainer');
    element.textContent='The 3D court could not load. All shot details remain available in Results or Play-by-Play.';
    element.classList.add('empty-message');
    window.drawShots=()=>{};
    window.resizeCourt=()=>{};
}
})();
