# src/data_pipeline/video_ocr.py
import cv2
import yt_dlp
import re
import csv
import os
import numpy as np
import easyocr

# =========================
# CONFIG
# =========================
YOUTUBE_URL = "https://www.youtube.com/watch?v=xRuH1qSD2dE" # Το βίντεο του αγώνα

# Ορισμός του Skip σε λεπτά (Πόσα λεπτά στην αρχή του βίντεο είναι άχρηστα π.χ. pre-game)
SKIP_MINUTES = 16 

# ΣΥΝΤΕΤΑΓΜΕΝΕΣ ROI (Region of Interest) - ΕΔΩ ΘΑ ΚΑΝΕΙΣ ΤΙΣ ΔΟΚΙΜΕΣ ΣΟΥ!
ROI_X = 10
ROI_Y = 300
ROI_W = 100
ROI_H = 50

FRAME_SKIP = 25
CONFIDENCE_THRESHOLD = 0.4
# Το αποθηκεύουμε στον κεντρικό φάκελο για να το βρίσκει εύκολα το app.py
OUTPUT_CSV = "game_clock_map.csv" 
DEBUG_FOLDER = "debug_frames"

if not os.path.exists(DEBUG_FOLDER):
    os.makedirs(DEBUG_FOLDER)

# =========================
# GET STREAM URL
# =========================
def get_stream_url(url):
    ydl_opts = {
        "format": "best[ext=mp4]/best",
        "quiet": True
    }
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(url, download=False)
        return info["url"]

# =========================
# TIME PARSING
# =========================
def parse_clock(text):
    text = text.upper().strip()
    text = text.replace("O", "0").replace("I", "1").replace("S", "5").replace("B", "8").replace("Z", "2")
    print(text)
    # 1. Ψάχνει πρώτα για κλασική μορφή λεπτών:δευτερολέπτων (π.χ. 09:23 ή 9:23)
    match_mmss = re.search(r"(\d{1,2}:\d{2})", text)
    if match_mmss:
        return match_mmss.group(1)

    # 2. Ψάχνει για μορφή με δέκατα του δευτερολέπτου (π.χ. 10.0, 9.9, 5.2)
    match_dec = re.search(r"(\d{1,2}[\.\:]\d)", text)
    if match_dec:
# Παίρνουμε το string και αν τυχαίνει να έχει ':' το κάνουμε '.'
        return match_dec.group(1).replace(":", ".")
    return None

# =========================
# MAIN PROCESS
# =========================
def main():
    print("Loading OCR model...")
    reader = easyocr.Reader(['en'], gpu=False) # Στο Mac βάλε gpu=False εκτός αν έχεις σετάρει το MPS

    print("Getting stream...")
    stream_url = get_stream_url(YOUTUBE_URL)
    cap = cv2.VideoCapture(stream_url)

    fps = cap.get(cv2.CAP_PROP_FPS)
    if not fps or fps == 0:
        fps = 25
    print(f"FPS: {fps}")

    start_seconds = SKIP_MINUTES * 60
    frame_id = int(start_seconds * fps)

    cap.set(cv2.CAP_PROP_POS_FRAMES, frame_id)
    print(f"Skipped first {SKIP_MINUTES} minutes. Starting processing from frame {frame_id}...")

    results = []
    last_clock = None
    # --- ΝΕΟ: Αυτόματο tracking περιόδων ---
    quarters_list = ["1st", "2nd", "3rd", "4th", "OT","2OT","3OT","4OT"]
    quarter_index = 0  # Ξεκινάμε από το 1st quarter (μπορείς να το αλλάξεις αν ξεκινάς από άλλο λεπτό) 
    print(f"Processing video... Τα PNG αποθηκεύονται στο φάκελο '{DEBUG_FOLDER}'")

    while True:
        cap.set(cv2.CAP_PROP_POS_FRAMES, frame_id)

        ret, frame = cap.read()
        if not ret:
            break

        try:
            # Κόβουμε το καρέ εκεί που είναι το χρονόμετρο
            roi = frame[ROI_Y:ROI_Y+ROI_H, ROI_X:ROI_X+ROI_W]
            if roi.size == 0:
                frame_id += FRAME_SKIP
                continue

            gray = cv2.cvtColor(roi, cv2.COLOR_BGR2GRAY)
            gray = cv2.resize(gray, None, fx=3, fy=3, interpolation=cv2.INTER_CUBIC)
            _, binary = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)

            # --- ΑΠΟΘΗΚΕΥΣΗ ΕΙΚΟΝΑΣ ΓΙΑ DEBUG ---
            png_filename = os.path.join(DEBUG_FOLDER, f"frame_{frame_id}.png")
            cv2.imwrite(png_filename, binary)  # Αυτό θα σε βοηθήσει να βρεις το ROI!

            ocr_results = reader.readtext(binary, allowlist='0123456789:')

            for (bbox, text, prob) in ocr_results:
                if prob > CONFIDENCE_THRESHOLD:
                    clock = parse_clock(text)
                    if clock and clock != last_clock:
                        # Βοηθητική συνάρτηση για μετατροπή σε δευτερόλεπτα
                        def get_seconds(c_str):
                            if not c_str: return None
                            try:
                                if ":" in c_str:
                                    m, s = map(int, c_str.split(":"))
                                    return m * 60 + s
                                elif "." in c_str:
                                    return float(c_str) 
                            except:
                                return None

                        curr_sec = get_seconds(clock)
                        prev_sec = get_seconds(last_clock)

                        # --- ΝΕΟ: ΦΙΛΤΡΟ ΓΙΑ ΛΑΘΟΣ ΔΕΚΑΔΙΚΑ (π.χ. "4.1" αντί για "4:19") ---
                        # Αν το OCR βρήκε τελεία (δηλαδή δέκατα), αλλά ο προηγούμενος χρόνος
                        # ήταν πάνω από 1 λεπτό (60 δευτερόλεπτα), τότε είναι λάθος του OCR!
                        if "." in clock and prev_sec is not None and prev_sec >= 70:
                            continue  # Αγνοούμε αυτή τη μέτρηση και πάμε στο επόμενο καρέ

                        # --- ΕΞΥΠΝΟΣ ΕΛΕΓΧΟΣ ΑΛΛΑΓΗΣ ΠΕΡΙΟΔΟΥ ---
                        if prev_sec is not None and curr_sec is not None:
                            # Αν ο προηγούμενός μας χρόνος ήταν πολύ χαμηλός (π.χ. κάτω από 15s) 
                            # και ο τρέχων εκτινάχθηκε ξαναψηλά (πάνω από 9 λεπτά / 540s)
                            if prev_sec <= 15 and curr_sec >= 540:
                                if quarter_index < len(quarters_list) - 1:
                                    quarter_index += 1

                        current_quarter = quarters_list[quarter_index]
                        video_time = frame_id / fps
                        results.append((video_time, current_quarter, clock))
                        print(f"[{prob:.2f}] {video_time:.2f}s ({current_quarter}) -> {clock}")
                        last_clock = clock
        except Exception as e:
            print(f"Error at frame {frame_id}: {e}")

        frame_id += FRAME_SKIP

    cap.release()

    if results:
        print("Saving CSV...")
        with open(OUTPUT_CSV, "w", newline="") as f:
            writer = csv.writer(f)
            writer.writerow(["video_time_sec", "quarter", "game_clock"])
            for v, q, c in results:
                writer.writerow([round(v, 2), q , c])
        print("DONE ->", OUTPUT_CSV)
    else:
        print("No data found. Check your ROI dimensions!")

if __name__ == "__main__":
    main()