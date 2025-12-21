"""
Configuration and paths for RIFE Video Extender
"""
import os
from pathlib import Path

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
