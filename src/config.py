"""Paths and constants shared by the Phase 1 pipeline."""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "data" / "raw"
PROCESSED = ROOT / "data" / "processed"
QA_DIR = PROCESSED / "qa"

SKILLCORNER_DIR = RAW / "skillcorner_opendata" / "data" / "matches"
SKILLCORNER_MATCHES_JSON = RAW / "skillcorner_opendata" / "data" / "matches.json"
METRICA_DIR = RAW / "metrica_sample_data" / "data"

SKILLCORNER_FPS = 10  # README: "the frame of the video the data comes from at 10 fps"
METRICA_FPS = 25      # Sample_Game_3_metadata.xml <FrameRate>25</FrameRate>; CSV Time[s] == Frame * 0.04

# Metrica README: "The dimensions of the field are the same for both games: 105x68 meters."
# Game 3 metadata <FieldSize><Width>105</Width><Height>68</Height> agrees (read from XML at runtime).
METRICA_CSV_PITCH = (105.0, 68.0)

METRICA_GAMES = {1: "csv", 2: "csv", 3: "epts"}

# Column order of the common frame schema
SCHEMA_COLUMNS = [
    "match_id", "source", "period", "frame_id", "timestamp_s",
    "object_type", "player_id", "team_id", "team_side", "jersey_number", "position",
    "x_raw", "y_raw", "x_m", "y_m", "is_detected", "ball_z",
    "possession_group", "possession_player_id",
    "x_home_m", "y_home_m", "x_att_m", "y_att_m",
    "status_conflict",
]
