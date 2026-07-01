package com.example;
 import java.util.List;

// Κλάση που θα κρατάει τα έξτρα δεδομένα αν το play είναι σουτ (από το points json)
class ShotDetails {
    private double coordX;      // COORD_X
    private double coordY;      // COORD_Y
    private String zone;        // ZONE (π.χ. "B", "I")
    private boolean isFastbreak; // FASTBREAK (από "0" ή "1" σε boolean)
    private boolean isSecondChance; // SECOND_CHANCE
    private boolean isPointsOffTurnover; // POINTS_OFF_TURNOVER

    public ShotDetails() {}
    // Constructors, Getters, Setters
    public double getCoordX() {
        return coordX;
    }
    public void setCoordX(double coordX) {
        this.coordX = coordX;   
    }
    public double getCoordY() {
        return coordY;
    }
    public void setCoordY(double coordY) {
        this.coordY = coordY;
    }
    public String getZone() {
        return zone;
    }
    public void setZone(String zone) {
        this.zone = zone;
    }
    public boolean isFastbreak() {
        return isFastbreak;
    }
    public void setFastbreak(boolean fastbreak) {
        isFastbreak = fastbreak;    
    }
    public boolean isSecondChance() {
        return isSecondChance;
    }
    public void setSecondChance(boolean secondChance) {
        isSecondChance = secondChance;
    }
    public boolean isPointsOffTurnover() {
        return isPointsOffTurnover;
    }
    public void setPointsOffTurnover(boolean pointsOffTurnover) {
        isPointsOffTurnover = pointsOffTurnover;
    }
}

// Το "Ιδανικό Output" για κάθε Play
public class PlayEvent {
// Κλειδί Ένωσης
    private int playId; // NUMBEROFPLAY (PlaybyPlay) == NUM_ANOT (Points)
    
    // Βασικά στοιχεία
    private String playType; // PLAYTYPE (π.χ. "2FGM", "CM", "IN")
    private String team; // CODETEAM (π.χ. "PAN", "ZAL")
    private String playerId; // PLAYER_ID (π.χ. "P012774")
    private String playerName; // PLAYER
    private int minute; // MINUTE
    private String timeLeft; // MARKERTIME (π.χ. "09:12")
    
    // Σκορ πριν και μετά (Το JSON έχει μόνο το 'μετά', το 'πριν' θα το υπολογίζουμε εμείς)
    private Integer scoreTeamABefore; // Team A = Γηπεδούχος
    private Integer scoreTeamBBefore; // Team B = Φιλοξενούμενος
    private Integer scoreTeamAAfter;  // POINTS_A
    private Integer scoreTeamBAfter;  // POINTS_B
    
    // Πεντάδες τη στιγμή του Play
    private List<String> teamALineup; // Λίστα με τα PLAYER_IDs
    private List<String> teamBLineup;
    
    // Εξτρά πληροφορίες αν είναι Σουτ
    private ShotDetails shotDetails;

    // Constructors
    public PlayEvent() {}

    // ... Εδώ θα μπουν τα Getters και τα Setters για όλα τα πεδία ...
    
    public void setScoreTeamABefore(int score) {
        this.scoreTeamABefore = score;
    }

    public void setScoreTeamBBefore(int score) {
        this.scoreTeamBBefore = score;
    }

    public void setScoreTeamAAfter(int score) {
        this.scoreTeamAAfter = score;
    }
    public void setScoreTeamBAfter(int score) {
        this.scoreTeamBAfter = score;
    }

    public void setTeamALineup(List<String> lineup) {
        this.teamALineup = lineup;
    }

    public void setTeamBLineup(List<String> lineup) {
        this.teamBLineup = lineup;
    }

    public void setShotDetails(ShotDetails shot) {
        this.shotDetails = shot;
    }

    public void setPlayType(String playType) {
        this.playType = playType;
    }
    public void setTimeLeft(String timeLeft) {
        this.timeLeft = timeLeft;
    }
    
    public void setPlayId(int playId) {
        this.playId = playId;
    }
    public void setTeam(String team) {
        this.team = team;
    }
    public void setPlayerId(String playerId) {
        this.playerId = playerId;
    }
    public void setPlayerName(String playerName) {
        this.playerName = playerName;
    }
    public void setMinute(int minute) {
        this.minute = minute;
    }

    public int getPlayId() {
        return playId;
    }
    public String getPlayType() {
        return playType;
    }
    public String getTeam() {
        return team;
    }
    public String getPlayerId() {
        return playerId;
    }
    public String getPlayerName() {
        return playerName;
    }
    public int getMinute() {
        return minute;
    }
    public String getTimeLeft() {
        return timeLeft;
    }
    public Integer getScoreTeamABefore() {
        return scoreTeamABefore;
    }
    public Integer getScoreTeamBBefore() {
        return scoreTeamBBefore;
    }
    public Integer getScoreTeamAAfter() {
        return scoreTeamAAfter;
    }
    public Integer getScoreTeamBAfter() {
        return scoreTeamBAfter;
    }
    public List<String> getTeamALineup() {
        return teamALineup;
    }
    public List<String> getTeamBLineup() {
        return teamBLineup;
    }
    public ShotDetails getShotDetails() {
        return shotDetails;
    }

    @Override
    public String toString() {
        String shotInfo = (shotDetails != null) ? " | Shot[X:" + shotDetails.getCoordX() + ", Y:" + shotDetails.getCoordY() + ", Zone:" + shotDetails.getZone() + "]" : "";
        return "PlayEvent{" +
                "Time='" + timeLeft + '\'' +
                ", Type='" + playType + '\'' +
                ", Player='" + playerId + '\'' +
                ", ScoreBefore=" + scoreTeamABefore + "-" + scoreTeamBBefore +
                ", ScoreAfter=" + scoreTeamAAfter + "-" + scoreTeamBAfter +
                ", TeamA_Lineup=" + teamALineup +
                ", TeamB_Lineup=" + teamBLineup +
                shotInfo +
                '}';
    }
}