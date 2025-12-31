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


# === Video Continuation (RunPod) Settings ===
RUNPOD_API_KEY_ENV = "RUNPOD_API_KEY"
RUNPOD_ENDPOINT_ID_ENV = "RUNPOD_ENDPOINT_ID"
API_KEY_FILE = APP_DIR / ".runpod_config"

# Default CogVideoX settings
COGVIDEO_DEFAULTS = {
    "num_frames": 49,
    "num_inference_steps": 50,
    "guidance_scale": 6.0,
}


def get_runpod_api_key() -> Optional[str]:
    """Get RunPod API key from environment or config file"""
    # 1. Check environment variable (preferred)
    key = os.environ.get(RUNPOD_API_KEY_ENV)
    if key:
        return key
    # 2. Check config file
    if API_KEY_FILE.exists():
        try:
            with open(API_KEY_FILE, "r") as f:
                config = json.load(f)
                return config.get("api_key")
        except (json.JSONDecodeError, IOError):
            pass
    return None


def get_runpod_endpoint_id() -> Optional[str]:
    """Get RunPod endpoint ID from environment or config file"""
    # 1. Check environment variable (preferred)
    endpoint_id = os.environ.get(RUNPOD_ENDPOINT_ID_ENV)
    if endpoint_id:
        return endpoint_id
    # 2. Check config file
    if API_KEY_FILE.exists():
        try:
            with open(API_KEY_FILE, "r") as f:
                config = json.load(f)
                return config.get("endpoint_id")
        except (json.JSONDecodeError, IOError):
            pass
    return None


def save_runpod_config(api_key: str, endpoint_id: str) -> bool:
    """Save RunPod credentials to config file"""
    try:
        config = {"api_key": api_key, "endpoint_id": endpoint_id}
        with open(API_KEY_FILE, "w") as f:
            json.dump(config, f, indent=2)
        return True
    except IOError:
        return False


def check_continuation_dependencies() -> list:
    """Check if continuation feature dependencies are available"""
    missing = []

    # Check runpod package
    try:
        import runpod
    except ImportError:
        missing.append("runpod package not installed (pip install runpod)")

    # Check requests package
    try:
        import requests
    except ImportError:
        missing.append("requests package not installed (pip install requests)")

    return missing
