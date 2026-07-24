// main.js

document.getElementById("searchBtn").addEventListener("click", async () => {
    // 1. Παίρνουμε τις τιμές από τα φίλτρα του HTML
    const selectedPlayer = document.getElementById("playerSelect").value;
    const selectedAssistant = document.getElementById("assistSelect").value;

    // 2. Τραβάμε τα δεδομένα
    const shotsData = await fetchFilteredShots(selectedPlayer, selectedAssistant);

    // ΠΡΟΣΘΗΚΗ: Τυπώνουμε τα δεδομένα για να δούμε τι ήρθε!
    console.log("Δεδομένα που ήρθαν από τον Server:", shotsData);

    // 3. Ζωγραφίζουμε το γήπεδο
    drawShots(shotsData);
});