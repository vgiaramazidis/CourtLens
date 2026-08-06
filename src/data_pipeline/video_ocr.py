"""Generate a game-clock-to-video timeline from a full-game broadcast.

OCR layout details live in ``ocr_profiles.json`` and game-specific details live
in ``video_games.json``. A new game that uses an existing broadcast layout only
needs a catalog entry; it does not need Python code changes.
"""

from __future__ import annotations

import argparse
import csv
import json
import re
import shutil
from dataclasses import dataclass
from pathlib import Path
from typing import Any


SCRIPT_DIR = Path(__file__).resolve().parent
REPO_ROOT = SCRIPT_DIR.parents[1]
DEFAULT_PROFILES_FILE = SCRIPT_DIR / "ocr_profiles.json"
DEFAULT_CATALOG_FILE = SCRIPT_DIR / "video_games.json"


def clock_to_seconds(clock: str | None) -> float | None:
    if not clock:
        return None
    try:
        if ":" in clock:
            minutes, seconds = clock.split(":", 1)
            value = int(minutes) * 60 + int(seconds)
            return float(value) if 0 <= int(seconds) < 60 else None
        if "." in clock:
            return float(clock)
    except (TypeError, ValueError):
        return None
    return None


def parse_clock(text: str) -> str | None:
    normalized = (
        text.upper()
        .strip()
        .replace("O", "0")
        .replace("I", "1")
        .replace("S", "5")
        .replace("B", "8")
        .replace("Z", "2")
    )
    # Some scorebug fonts make ':' look like '.', so 7.24 is also 7:24.
    # A single digit after the separator (for example 15.9) remains a decimal clock.
    match_mmss = re.search(r"(?<!\d)(\d{1,2})[\.:](\d{2})(?!\d)", normalized)
    if match_mmss:
        clock = f"{match_mmss.group(1)}:{match_mmss.group(2)}"
        return clock if clock_to_seconds(clock) is not None else None

    match_decimal = re.search(r"(?<!\d)(\d{1,2}[\.:]\d)(?!\d)", normalized)
    if match_decimal:
        clock = match_decimal.group(1).replace(":", ".")
        seconds = clock_to_seconds(clock)
        return clock if seconds is not None and seconds < 60 else None
    return None


def load_json(path: Path) -> dict[str, Any]:
    try:
        with path.open(encoding="utf-8") as handle:
            payload = json.load(handle)
    except FileNotFoundError as exc:
        raise ValueError(f"Configuration file not found: {path}") from exc
    except json.JSONDecodeError as exc:
        raise ValueError(f"Invalid JSON in {path}: {exc}") from exc
    if not isinstance(payload, dict):
        raise ValueError(f"Configuration root must be an object: {path}")
    return payload


def load_profiles(path: Path) -> dict[str, dict[str, Any]]:
    profiles = load_json(path).get("profiles")
    if not isinstance(profiles, dict) or not profiles:
        raise ValueError(f"No OCR profiles found in {path}")

    for name, profile in profiles.items():
        if not isinstance(profile, dict):
            raise ValueError(f"OCR profile '{name}' must be an object")
        roi = profile.get("roi", {})
        for field in ("x", "y", "width", "height"):
            value = roi.get(field)
            if not isinstance(value, (int, float)) or not 0 <= value <= 1:
                raise ValueError(f"Profile '{name}' ROI '{field}' must be between 0 and 1")
        if roi["width"] <= 0 or roi["height"] <= 0:
            raise ValueError(f"Profile '{name}' ROI width and height must be positive")
        if roi["x"] + roi["width"] > 1 or roi["y"] + roi["height"] > 1:
            raise ValueError(f"Profile '{name}' ROI extends outside the frame")
    return profiles


def load_game_catalog(path: Path) -> list[dict[str, Any]]:
    games = load_json(path).get("games")
    if not isinstance(games, list):
        raise ValueError(f"Game catalog must contain a 'games' list: {path}")
    return [game for game in games if isinstance(game, dict)]


def find_game_config(
    games: list[dict[str, Any]], season_code: str, game_code: str
) -> dict[str, Any] | None:
    return next(
        (
            game
            for game in games
            if str(game.get("season_code")) == season_code
            and str(game.get("game_code")) == game_code
        ),
        None,
    )


def resolve_repo_path(value: str | Path) -> Path:
    path = Path(value).expanduser()
    return path if path.is_absolute() else REPO_ROOT / path


def youtube_url_from_id(video_id: str) -> str:
    return f"https://www.youtube.com/watch?v={video_id}"


@dataclass
class ClockTracker:
    periods: list[str]
    regular_period_seconds: int = 600
    overtime_period_seconds: int = 300
    period_end_max_seconds: float = 15
    period_start_min_ratio: float = 0.9
    max_upward_jump_seconds: float = 3
    max_downward_jump_seconds: float = 15
    period_index: int = 0
    last_clock: str | None = None
    last_video_time: float | None = None

    @classmethod
    def from_profile(cls, profile: dict[str, Any]) -> "ClockTracker":
        config = profile.get("clock_tracking", {})
        periods = config.get("periods") or ["1st", "2nd", "3rd", "4th", "OT"]
        return cls(
            periods=[str(period) for period in periods],
            regular_period_seconds=int(config.get("regular_period_seconds", 600)),
            overtime_period_seconds=int(config.get("overtime_period_seconds", 300)),
            period_end_max_seconds=float(config.get("period_end_max_seconds", 15)),
            period_start_min_ratio=float(config.get("period_start_min_ratio", 0.9)),
            max_upward_jump_seconds=float(config.get("max_upward_jump_seconds", 3)),
            max_downward_jump_seconds=float(config.get("max_downward_jump_seconds", 15)),
        )

    @property
    def period(self) -> str:
        return self.periods[self.period_index]

    def period_duration(self, index: int | None = None) -> int:
        target_index = self.period_index if index is None else index
        return self.regular_period_seconds if target_index < 4 else self.overtime_period_seconds

    def accept(self, clock: str, video_time: float | None = None) -> tuple[str, str] | None:
        current_seconds = clock_to_seconds(clock)
        if current_seconds is None or clock == self.last_clock:
            return None
        if current_seconds > self.period_duration() + 1:
            return None

        previous_seconds = clock_to_seconds(self.last_clock)
        if previous_seconds is not None:
            next_index = min(self.period_index + 1, len(self.periods) - 1)
            next_period_start = self.period_duration(next_index) * self.period_start_min_ratio
            is_period_reset = (
                self.period_index < len(self.periods) - 1
                and previous_seconds <= self.period_end_max_seconds
                and current_seconds >= next_period_start
                and current_seconds <= self.period_duration(next_index) + 1
            )
            if is_period_reset:
                self.period_index += 1
            else:
                change = current_seconds - previous_seconds
                if change > self.max_upward_jump_seconds:
                    return None
                allowed_downward_jump = self.max_downward_jump_seconds
                if video_time is not None and self.last_video_time is not None:
                    elapsed_video_time = max(0.0, video_time - self.last_video_time)
                    allowed_downward_jump = min(
                        allowed_downward_jump,
                        elapsed_video_time + 5,
                    )
                if -change > allowed_downward_jump:
                    return None

        self.last_clock = clock
        self.last_video_time = video_time
        return self.period, clock


def roi_pixels(profile: dict[str, Any], frame_width: int, frame_height: int) -> tuple[int, int, int, int]:
    roi = profile["roi"]
    x = max(0, min(frame_width - 1, round(float(roi["x"]) * frame_width)))
    y = max(0, min(frame_height - 1, round(float(roi["y"]) * frame_height)))
    width = max(1, round(float(roi["width"]) * frame_width))
    height = max(1, round(float(roi["height"]) * frame_height))
    return x, y, min(width, frame_width - x), min(height, frame_height - y)


def sanitize_timeline_results(
    results: list[tuple[float, str, str]],
) -> tuple[list[tuple[float, str, str]], int]:
    """Keep each period monotonic and prefer the latest duplicate clock reading.

    Broadcast replays and official clock corrections can briefly reintroduce a
    higher clock value. Removing the conflicting older tail prevents play links
    from seeking to a replay or pre-correction timestamp.
    """
    sanitized: list[tuple[float, str, str]] = []
    removed = 0
    for result in results:
        _video_time, period, clock = result
        current_seconds = clock_to_seconds(clock)
        if current_seconds is None:
            removed += 1
            continue

        while sanitized and sanitized[-1][1] == period:
            previous_seconds = clock_to_seconds(sanitized[-1][2])
            if previous_seconds is None or current_seconds > previous_seconds:
                sanitized.pop()
                removed += 1
                continue
            if current_seconds == previous_seconds:
                sanitized[-1] = result
                removed += 1
                break
            sanitized.append(result)
            break
        else:
            sanitized.append(result)
    return sanitized, removed


def remove_temporally_impossible_results(
    results: list[tuple[float, str, str]],
    grace_seconds: float = 5,
) -> tuple[list[tuple[float, str, str]], int]:
    """Reject clock drops that are faster than the elapsed video time."""
    sanitized: list[tuple[float, str, str]] = []
    removed = 0
    for result in results:
        video_time, period, clock = result
        if sanitized and sanitized[-1][1] == period:
            previous_video_time, _previous_period, previous_clock = sanitized[-1]
            previous_seconds = clock_to_seconds(previous_clock)
            current_seconds = clock_to_seconds(clock)
            if (
                previous_seconds is not None
                and current_seconds is not None
                and previous_seconds - current_seconds
                > video_time - previous_video_time + grace_seconds
            ):
                removed += 1
                continue
        sanitized.append(result)
    return sanitized, removed


def get_stream_url(
    url: str,
    yt_dlp_module: Any,
    cookies_from_browser: str | None = None,
) -> str:
    options: dict[str, Any] = {
        # OpenCV needs a progressive HTTP file for reliable random frame seeks;
        # authenticated YouTube sessions otherwise prefer an HLS manifest.
        "format": "18/best[protocol=https][ext=mp4]/best[protocol=https]",
        "quiet": True,
        "extractor_retries": 5,
        "remote_components": {"ejs:github"},
    }
    if node_path := shutil.which("node"):
        options["js_runtimes"] = {"node": {"path": node_path}}
    if cookies_from_browser:
        options["cookiesfrombrowser"] = (cookies_from_browser, None, None, None)
    with yt_dlp_module.YoutubeDL(options) as downloader:
        info = downloader.extract_info(url, download=False)
        return str(info["url"])


def preprocess_roi(roi: Any, profile: dict[str, Any], cv2_module: Any) -> Any:
    config = profile.get("preprocess", {})
    gray = cv2_module.cvtColor(roi, cv2_module.COLOR_BGR2GRAY)
    scale = float(config.get("scale", 3.0))
    if scale != 1:
        gray = cv2_module.resize(
            gray, None, fx=scale, fy=scale, interpolation=cv2_module.INTER_CUBIC
        )

    threshold = str(config.get("threshold", "otsu"))
    invert_flag = cv2_module.THRESH_BINARY_INV if config.get("invert") else cv2_module.THRESH_BINARY
    if threshold == "otsu":
        _, gray = cv2_module.threshold(gray, 0, 255, invert_flag + cv2_module.THRESH_OTSU)
    elif threshold == "adaptive":
        gray = cv2_module.adaptiveThreshold(
            gray,
            255,
            cv2_module.ADAPTIVE_THRESH_GAUSSIAN_C,
            invert_flag,
            21,
            5,
        )
    elif threshold != "none":
        raise ValueError(f"Unsupported threshold mode: {threshold}")
    return gray


def run_ocr(
    youtube_url: str,
    profile: dict[str, Any],
    start_seconds: float,
    output_path: Path,
    debug_dir: Path,
    save_debug_frames: bool,
    cookies_from_browser: str | None = None,
    video_file: Path | None = None,
) -> int:
    try:
        import cv2
        import easyocr
        import yt_dlp
    except ImportError as exc:
        raise RuntimeError(
            "OCR dependencies are missing. Install opencv-python, easyocr, and yt-dlp."
        ) from exc

    ocr_config = profile.get("ocr", {})
    reader = easyocr.Reader(ocr_config.get("languages", ["en"]), gpu=False)
    stream_url = (
        str(video_file.resolve())
        if video_file is not None
        else get_stream_url(youtube_url, yt_dlp, cookies_from_browser)
    )
    capture = cv2.VideoCapture(stream_url)
    if not capture.isOpened():
        raise RuntimeError("Could not open the YouTube video stream")

    fps = float(capture.get(cv2.CAP_PROP_FPS) or 25)
    frame_count = int(capture.get(cv2.CAP_PROP_FRAME_COUNT) or 0)
    frame_id = max(0, int(start_seconds * fps))
    interval_seconds = float(profile.get("sampling", {}).get("interval_seconds", 1.0))
    post_final_period_seconds = float(
        profile.get("sampling", {}).get("post_final_period_seconds", 900.0)
    )
    frame_step = max(1, round(fps * interval_seconds))
    confidence_threshold = float(ocr_config.get("confidence_threshold", 0.4))
    allowlist = str(ocr_config.get("allowlist", "0123456789:."))
    tracker = ClockTracker.from_profile(profile)
    results: list[tuple[float, str, str]] = []
    completed_period_index: int | None = None
    completed_period_video_time: float | None = None

    if save_debug_frames:
        debug_dir.mkdir(parents=True, exist_ok=True)

    print(f"Processing {youtube_url}")
    print(f"FPS: {fps:.2f}; starting at {start_seconds:.2f}s; sampling every {interval_seconds:.2f}s")

    while frame_count <= 0 or frame_id < frame_count:
        capture.set(cv2.CAP_PROP_POS_FRAMES, frame_id)
        ok, frame = capture.read()
        if not ok:
            break

        frame_height, frame_width = frame.shape[:2]
        x, y, width, height = roi_pixels(profile, frame_width, frame_height)
        roi = frame[y : y + height, x : x + width]
        if roi.size == 0:
            frame_id += frame_step
            continue

        processed = preprocess_roi(roi, profile, cv2)
        if save_debug_frames:
            cv2.imwrite(str(debug_dir / f"frame_{frame_id}.png"), processed)

        video_time = frame_id / fps
        for _bbox, text, probability in reader.readtext(processed, allowlist=allowlist):
            if float(probability) < confidence_threshold:
                continue
            clock = parse_clock(str(text))
            accepted = tracker.accept(clock, video_time) if clock else None
            if not accepted:
                continue
            period, accepted_clock = accepted
            results.append((video_time, period, accepted_clock))
            print(f"[{float(probability):.2f}] {video_time:.2f}s ({period}) -> {accepted_clock}")

            accepted_seconds = clock_to_seconds(accepted_clock)
            if completed_period_index is not None and tracker.period_index > completed_period_index:
                # A tied game continued into overtime, so wait for that period to finish.
                completed_period_index = None
                completed_period_video_time = None
            if (
                tracker.period_index >= 3
                and accepted_seconds is not None
                and accepted_seconds <= tracker.period_end_max_seconds
            ):
                completed_period_index = tracker.period_index
                completed_period_video_time = video_time

        frame_id += frame_step
        if (
            completed_period_index is not None
            and completed_period_video_time is not None
            and tracker.period_index == completed_period_index
            and frame_id / fps - completed_period_video_time >= post_final_period_seconds
        ):
            print(
                f"Stopping {post_final_period_seconds:.0f}s after "
                f"{tracker.period} reached its final seconds"
            )
            break

    capture.release()
    if not results:
        raise RuntimeError("No valid clock readings found. Check the selected OCR profile and start hint.")

    results, removed_points = sanitize_timeline_results(results)
    results, temporal_removed = remove_temporally_impossible_results(results)
    removed_points += temporal_removed
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle, lineterminator="\n")
        writer.writerow(["video_time_sec", "quarter", "game_clock"])
        writer.writerows((round(video, 2), period, clock) for video, period, clock in results)
    print(
        f"Saved {len(results)} timeline points to {output_path} "
        f"({removed_points} conflicting/duplicate points removed)"
    )
    return len(results)


def probe_profiles(
    youtube_url: str,
    profiles: dict[str, dict[str, Any]],
    start_seconds: float,
    duration_seconds: float = 600,
    step_seconds: float = 30,
    cookies_from_browser: str | None = None,
    video_file: Path | None = None,
) -> dict[str, list[tuple[float, str, float]]]:
    """Sample a video and report which reusable layouts can read its clock."""
    try:
        import cv2
        import easyocr
        import yt_dlp
    except ImportError as exc:
        raise RuntimeError(
            "OCR dependencies are missing. Install opencv-python, easyocr, and yt-dlp."
        ) from exc

    stream_url = (
        str(video_file.resolve())
        if video_file is not None
        else get_stream_url(youtube_url, yt_dlp, cookies_from_browser)
    )
    capture = cv2.VideoCapture(stream_url)
    if not capture.isOpened():
        raise RuntimeError("Could not open the YouTube video stream")
    fps = float(capture.get(cv2.CAP_PROP_FPS) or 25)
    languages = next(iter(profiles.values())).get("ocr", {}).get("languages", ["en"])
    reader = easyocr.Reader(languages, gpu=False)
    matches: dict[str, list[tuple[float, str, float]]] = {
        profile_name: [] for profile_name in profiles
    }

    sample_count = max(1, int(duration_seconds / step_seconds) + 1)
    for sample_index in range(sample_count):
        video_seconds = start_seconds + sample_index * step_seconds
        capture.set(cv2.CAP_PROP_POS_FRAMES, int(video_seconds * fps))
        ok, frame = capture.read()
        if not ok:
            break
        frame_height, frame_width = frame.shape[:2]

        for profile_name, profile in profiles.items():
            x, y, width, height = roi_pixels(profile, frame_width, frame_height)
            roi = frame[y : y + height, x : x + width]
            if roi.size == 0:
                continue
            processed = preprocess_roi(roi, profile, cv2)
            ocr_config = profile.get("ocr", {})
            readings = reader.readtext(
                processed,
                allowlist=str(ocr_config.get("allowlist", "0123456789:.")),
            )
            threshold = float(ocr_config.get("confidence_threshold", 0.4))
            valid = [
                (parse_clock(str(text)), float(probability))
                for _bbox, text, probability in readings
                if float(probability) >= threshold
            ]
            valid = [(clock, confidence) for clock, confidence in valid if clock]
            if valid:
                clock, confidence = max(valid, key=lambda reading: reading[1])
                matches[profile_name].append((video_seconds, str(clock), confidence))

    capture.release()
    return matches


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--season-code", default="E2023")
    parser.add_argument("--game-code", default="333")
    parser.add_argument("--youtube-url")
    parser.add_argument("--youtube-id")
    parser.add_argument("--video-file", type=Path, help="Use a downloaded local video instead of YouTube")
    parser.add_argument("--profile", help="Override the OCR profile from the game catalog")
    parser.add_argument("--profiles-file", type=Path, default=DEFAULT_PROFILES_FILE)
    parser.add_argument("--catalog-file", type=Path, default=DEFAULT_CATALOG_FILE)
    parser.add_argument("--start-seconds", type=float)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--debug-dir", type=Path)
    parser.add_argument("--save-debug-frames", action="store_true")
    parser.add_argument(
        "--cookies-from-browser",
        help="Load authenticated YouTube cookies from this browser (for example: chrome)",
    )
    parser.add_argument("--probe-profiles", action="store_true")
    parser.add_argument("--probe-duration-seconds", type=float, default=600)
    parser.add_argument("--probe-step-seconds", type=float, default=30)
    parser.add_argument("--list-profiles", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    try:
        profiles = load_profiles(args.profiles_file.resolve())
        if args.list_profiles:
            for name, profile in profiles.items():
                print(f"{name}: {profile.get('description', '')}")
            return 0

        games = load_game_catalog(args.catalog_file.resolve())
        game = find_game_config(games, args.season_code, args.game_code) or {}
        profile_name = args.profile or game.get("ocr_profile")
        if not profile_name or profile_name not in profiles:
            parser.error(f"Unknown or missing OCR profile: {profile_name!r}")

        youtube_url = args.youtube_url or game.get("youtube_url")
        youtube_id = args.youtube_id or game.get("youtube_id")
        if not youtube_url and youtube_id:
            youtube_url = youtube_url_from_id(str(youtube_id))
        if not youtube_url and not args.video_file:
            parser.error("Provide --youtube-url/--youtube-id or add the game to video_games.json")

        output_value = args.output or game.get("timeline_file")
        output_path = resolve_repo_path(
            output_value or f"video_timelines/{args.season_code}_{args.game_code}.csv"
        )
        debug_dir = resolve_repo_path(
            args.debug_dir or f"debug_frames/{args.season_code}_{args.game_code}"
        )
        start_seconds = (
            args.start_seconds
            if args.start_seconds is not None
            else float(game.get("start_hint_seconds", 0))
        )
        if args.probe_profiles:
            matches = probe_profiles(
                youtube_url=str(youtube_url),
                profiles=profiles,
                start_seconds=start_seconds,
                duration_seconds=args.probe_duration_seconds,
                step_seconds=args.probe_step_seconds,
                cookies_from_browser=args.cookies_from_browser,
                video_file=args.video_file,
            )
            for candidate_name, readings in matches.items():
                preview = ", ".join(
                    f"{video_seconds:.0f}s={clock} ({confidence:.2f})"
                    for video_seconds, clock, confidence in readings[:8]
                )
                print(f"{candidate_name}: {len(readings)} valid samples{': ' + preview if preview else ''}")
            return 0
        run_ocr(
            youtube_url=str(youtube_url),
            profile=profiles[str(profile_name)],
            start_seconds=start_seconds,
            output_path=output_path,
            debug_dir=debug_dir,
            save_debug_frames=args.save_debug_frames,
            cookies_from_browser=args.cookies_from_browser,
            video_file=args.video_file,
        )
        return 0
    except (RuntimeError, ValueError) as exc:
        parser.exit(1, f"error: {exc}\n")


if __name__ == "__main__":
    raise SystemExit(main())
