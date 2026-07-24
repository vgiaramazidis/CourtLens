// court.js

const canvas = document.getElementById("basketballCourt");
const ctx = canvas.getContext("2d");

// Φορτώνουμε την εικόνα του γηπέδου
const courtImage = new Image();
courtImage.src = "assets/half_court.png"; // Βάλε εδώ μια εικόνα μισού γηπέδου (κάτοψη)

courtImage.onload = () => {
    // Ζωγραφίζουμε το γήπεδο μόλις φορτώσει
    ctx.drawImage(courtImage, 0, 0, canvas.width, canvas.height);
};

/**
 * Ζωγραφίζει τα σουτ πάνω στον καμβά
 * @param {Array} shots - Πίνακας με αντικείμενα { x, y, isMade }
 */
function drawShots(shots) {
    // Καθαρίζουμε τον καμβά και ξαναζωγραφίζουμε το γήπεδο
    ctx.clearRect(0, 0, canvas.width, canvas.height);
    ctx.drawImage(courtImage, 0, 0, canvas.width, canvas.height);

    shots.forEach(shot => {
        // ΣΗΜΕΙΩΣΗ: Πιθανότατα θα χρειαστεί να κάνεις scale (πολλαπλασιασμό) τις 
        // συντεταγμένες της Euroleague για να ταιριάζουν ακριβώς στα pixels του καμβά σου.
        const mappedX = shot.x; 
        const mappedY = shot.y;

        ctx.beginPath();
        ctx.arc(mappedX, mappedY, 6, 0, 2 * Math.PI); // 6 είναι η ακτίνα της κουκκίδας
        
        // Πράσινο για εύστοχα, Κόκκινο για άστοχα
        ctx.fillStyle = shot.isMade ? "rgba(46, 204, 113, 0.8)" : "rgba(231, 76, 60, 0.8)";
        ctx.fill();
        
        ctx.lineWidth = 1;
        ctx.strokeStyle = "#fff";
        ctx.stroke();
    });
}