package com.example;

import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;

import java.io.InputStream;
import java.util.ArrayList;
import java.util.List;

public class GameProcessor {

    // Η "Μνήμη" της κατάστασης (State)
    private int currentScoreA = 0;
    private int currentScoreB = 0;
    private List<String> currentLineupA = new ArrayList<>();
    private List<String> currentLineupB = new ArrayList<>();
    
    // Η τελική λίστα με το Ιδανικό Output
    private List<PlayEvent> finalPlayEvents = new ArrayList<>();

    public void loadAndProcessData() {
        ObjectMapper mapper = new ObjectMapper();

        try {
            // 1. Φορτώνουμε τα αρχεία. Επειδή είναι στον ίδιο φάκελο, τα διαβάζουμε ως Stream
            InputStream pbpStream = getClass().getResourceAsStream("/PlaybyPlay.json");
            InputStream pointsStream = getClass().getResourceAsStream("/Points.json");
            InputStream boxStream = getClass().getResourceAsStream("/Boxscore.json");

            if (pbpStream == null || pointsStream == null || boxStream == null) {
                System.out.println("Σφάλμα: Δεν βρέθηκαν τα αρχεία JSON στον φάκελο resources!");
                return;
            }

            JsonNode playByPlayRoot = mapper.readTree(pbpStream);
            JsonNode pointsRoot = mapper.readTree(pointsStream);
            JsonNode boxscoreRoot = mapper.readTree(boxStream);

            // 2. Αρχικοποίηση των Starting Lineups από το Boxscore
            initializeStartingLineups(boxscoreRoot);

            // 3. Ξεκινάμε τη λούπα στα events του Play-by-Play
            String[] quarters = {"FirstQuarter", "SecondQuarter", "ThirdQuarter", "ForthQuarter", "ExtraTime"};
            JsonNode pointsRows = pointsRoot.has("Rows") ? pointsRoot.get("Rows") : null;

            for (String q : quarters) {
                JsonNode quarterData = playByPlayRoot.get(q);
                if (quarterData != null && quarterData.isArray()) {
                    
                    for (JsonNode play : quarterData) {
                        processSinglePlay(play, pointsRows);
                    }
                }
            }

            // 4. Τύπωμα Αποτελεσμάτων για επιβεβαίωση!
            System.out.println("Επεξεργασία ολοκληρώθηκε! Βρέθηκαν συνολικά " + finalPlayEvents.size() + " events.");
            System.out.println("-------------------------------------------------");
            System.out.println("Εκτύπωση των 10 πρώτων Events για έλεγχο:");
            for (int i = 0; i < Math.min(10, finalPlayEvents.size()); i++) {
                System.out.println(finalPlayEvents.get(i).toString());
            }

        } catch (Exception e) {
            System.out.println("Κάτι πήγε στραβά κατά την ανάγνωση των JSON:");
            e.printStackTrace();
        }
    }

    private void processSinglePlay(JsonNode play, JsonNode pointsRows) {
        PlayEvent event = new PlayEvent();

        // Σκορ ΠΡΙΝ το play
        event.setScoreTeamABefore(currentScoreA);
        event.setScoreTeamBBefore(currentScoreB);

        // Βασικά στοιχεία
        int playId = play.hasNonNull("NUMBEROFPLAY") ? play.get("NUMBEROFPLAY").asInt() : 0;
        String playType = play.hasNonNull("PLAYTYPE") ? play.get("PLAYTYPE").asText() : "";
        // Κάνουμε trim() γιατί τα JSON έχουν κενά, π.χ. "PAN       "
        String team = play.hasNonNull("CODETEAM") ? play.get("CODETEAM").asText().trim() : ""; 
        String playerId = play.hasNonNull("PLAYER_ID") ? play.get("PLAYER_ID").asText().trim() : "";

        event.setPlayId(playId);
        event.setPlayType(playType);
        event.setTeam(team);
        event.setPlayerId(playerId);
        if (play.hasNonNull("MARKERTIME")) event.setTimeLeft(play.get("MARKERTIME").asText());

        // Ενημέρωση Πεντάδων (Substitutions)
        if (playType.equals("IN")) {
            addPlayerToLineup(team, playerId);
        } else if (playType.equals("OUT")) {
            removePlayerFromLineup(team, playerId);
        }

        // Ενημέρωση Σκορ ΜΕΤΑ το play
        if (play.hasNonNull("POINTS_A")) currentScoreA = play.get("POINTS_A").asInt();
        if (play.hasNonNull("POINTS_B")) currentScoreB = play.get("POINTS_B").asInt();

        event.setScoreTeamAAfter(currentScoreA);
        event.setScoreTeamBAfter(currentScoreB);

        // Αντιγραφή της τρέχουσας πεντάδας στο event
        event.setTeamALineup(new ArrayList<>(currentLineupA));
        event.setTeamBLineup(new ArrayList<>(currentLineupB));

        // Ένωση με το Points.json αν το event είναι σουτ
        if (playType.contains("FGM") || playType.contains("FGA") || playType.contains("FTM") || playType.contains("FTA")) {
            ShotDetails shot = findShotInPointsJson(playId, pointsRows);
            event.setShotDetails(shot);
        }

        finalPlayEvents.add(event);
    }

    private void initializeStartingLineups(JsonNode boxscoreRoot) {
        JsonNode stats = boxscoreRoot.get("Stats");
        if (stats != null && stats.isArray()) {
            // Ο Παναθηναϊκός (Team A) είναι στο index 0
            JsonNode teamA = stats.get(0).get("PlayersStats");
            if (teamA != null) {
                for (JsonNode player : teamA) {
                    if (player.get("IsStarter").asInt() == 1) {
                        currentLineupA.add(player.get("Player_ID").asText().trim());
                    }
                }
            }
            // Η Ζαλγκίρις (Team B) είναι στο index 1
            JsonNode teamB = stats.get(1).get("PlayersStats");
            if (teamB != null) {
                for (JsonNode player : teamB) {
                    if (player.get("IsStarter").asInt() == 1) {
                        currentLineupB.add(player.get("Player_ID").asText().trim());
                    }
                }
            }
        }
    }

    private void addPlayerToLineup(String team, String playerId) {
        if (team.equals("PAN") && !currentLineupA.contains(playerId)) {
            currentLineupA.add(playerId);
        } else if (team.equals("ZAL") && !currentLineupB.contains(playerId)) {
            currentLineupB.add(playerId);
        }
    }

    private void removePlayerFromLineup(String team, String playerId) {
        if (team.equals("PAN")) currentLineupA.remove(playerId);
        else if (team.equals("ZAL")) currentLineupB.remove(playerId);
    }

    private ShotDetails findShotInPointsJson(int playId, JsonNode pointsRows) {
        if (pointsRows == null) return null;
        
        for (JsonNode row : pointsRows) {
            // Κλειδί Ένωσης: NUM_ANOT == NUMBEROFPLAY
            if (row.get("NUM_ANOT").asInt() == playId) {
                ShotDetails shot = new ShotDetails();
                if (row.hasNonNull("COORD_X")) shot.setCoordX(row.get("COORD_X").asDouble());
                if (row.hasNonNull("COORD_Y")) shot.setCoordY(row.get("COORD_Y").asDouble());
                if (row.hasNonNull("ZONE")) shot.setZone(row.get("ZONE").asText());
                if (row.hasNonNull("FASTBREAK")) shot.setFastbreak(row.get("FASTBREAK").asText().equals("1"));
                if (row.hasNonNull("SECOND_CHANCE")) shot.setSecondChance(row.get("SECOND_CHANCE").asText().equals("1"));
                return shot;
            }
        }
        return null;
    }
}