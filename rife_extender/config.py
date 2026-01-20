"""
Configuration and paths for RIFE Video Extender
"""
import os
import json
from pathlib import Path
from typing import Optional

# Base directories
APP_DIR = Path(__file__).parent.resolve()
BIN_DIR = APP_DIR / "bin"

# External binary paths
RIFE_DIR = BIN_DIR / "rife-ncnn-vulkan"
RIFE_EXE = RIFE_DIR / "rife-ncnn-vulkan.exe"
RIFE_MODELS_DIR = RIFE_DIR  # Models are in the same directory

FFMPEG_DIR = BIN_DIR / "ffmpeg"
FFMPEG_EXE = FFMPEG_DIR / "ffmpeg.exe"
FFPROBE_EXE = FFMPEG_DIR / "ffprobe.exe"

# Temp directory for frame processing
TEMP_DIR = APP_DIR / "temp"

# Default settings
DEFAULT_SETTINGS = {
    "multiplier": 4,  # 2, 4, or 8
    "model": "rife-v4.6",  # Default RIFE model
    "output_fps": None,  # None = match input, or specify like 30, 60
    "gpu_id": 0,  # GPU device ID
}

# Supported video formats
SUPPORTED_FORMATS = [".mp4", ".avi", ".mov", ".mkv", ".webm"]

def ensure_directories():
    """Create necessary directories if they don't exist"""
    TEMP_DIR.mkdir(exist_ok=True)
    BIN_DIR.mkdir(exist_ok=True)
    RIFE_DIR.mkdir(exist_ok=True)
    FFMPEG_DIR.mkdir(exist_ok=True)

def check_dependencies():
    """Check if required binaries are present"""
    missing = []

    if not RIFE_EXE.exists():
        missing.append(f"RIFE executable not found at: {RIFE_EXE}")

    if not FFMPEG_EXE.exists():
        missing.append(f"FFmpeg executable not found at: {FFMPEG_EXE}")

    if not FFPROBE_EXE.exists():
        missing.append(f"FFprobe executable not found at: {FFPROBE_EXE}")

    return missing


# === Video Continuation (Replicate) Settings ===
REPLICATE_API_TOKEN_ENV = "REPLICATE_API_TOKEN"
API_KEY_FILE = APP_DIR / ".replicate_config"

# Default Wan 2.2 I2V settings for Replicate
WAN_VIDEO_DEFAULTS = {
    "num_frames": 81,  # 81-121, 81 gives best results
    "frames_per_second": 24,
    "resolution": "480p",  # 480p or 720p
    "disable_safety_checker": True,
}

# Replicate model identifier (with version hash)
REPLICATE_VIDEO_MODEL = "wan-video/wan-2.2-i2v-fast:4eaf2b01d3bf70d8a2e00b219efeb7cb415855ad18b7dacdc4cae664a73a6eea"


def get_replicate_api_token() -> Optional[str]:
    """Get Replicate API token from environment or config file"""
    # 1. Check environment variable (preferred)
    token = os.environ.get(REPLICATE_API_TOKEN_ENV)
    if token:
        return token
    # 2. Check config file
    if API_KEY_FILE.exists():
        try:
            with open(API_KEY_FILE, "r") as f:
                config = json.load(f)
                return config.get("api_token")
        except (json.JSONDecodeError, IOError):
            pass
    return None


def save_replicate_config(api_token: str) -> bool:
    """Save Replicate API token to config file"""
    try:
        config = {"api_token": api_token}
        with open(API_KEY_FILE, "w") as f:
            json.dump(config, f, indent=2)
        return True
    except IOError:
        return False


def check_continuation_dependencies() -> list:
    """Check if continuation feature dependencies are available"""
    missing = []

    # Check replicate package
    try:
        import replicate
    except ImportError:
        missing.append("replicate package not installed (pip install replicate)")

    # Check requests package
    try:
        import requests
    except ImportError:
        missing.append("requests package not installed (pip install requests)")

    return missing
