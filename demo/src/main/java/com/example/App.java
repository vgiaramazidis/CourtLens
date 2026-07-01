package com.example;

public class App {
    public static void main(String[] args) {
        System.out.println("Ξεκινάει η ανάλυση του αγώνα...");
        
        // Δημιουργούμε τον Processor και τον βάζουμε να τρέξει
        GameProcessor processor = new GameProcessor();
        processor.loadAndProcessData();
    }
}
