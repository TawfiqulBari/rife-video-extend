# RIFE Video Extender

## Project Overview
A Windows GUI application for creating slow-motion videos using RIFE (Real-Time Intermediate Flow Estimation) AI frame interpolation.

**Purpose:** Extend AI-generated videos by inserting AI-interpolated frames between existing frames, creating smooth slow-motion effects.

**Target Use Case:**
- Input: 6-second AI-generated videos (1080p MP4)
- Output: 24-48 second slow-motion videos (4x-8x slower)
- Platform: Windows 11 with NVIDIA GPU (RTX 3060 12GB)

## Architecture

### Tech Stack
| Component | Technology | Purpose |
|-----------|------------|---------|
| GUI | Python + CustomTkinter | Modern dark-themed interface |
| Frame Interpolation | rife-ncnn-vulkan | Standalone RIFE binary using Vulkan/NCNN |
| Video Processing | FFmpeg | Frame extraction and video reassembly |
| Packaging | PyInstaller | Future single .exe distribution |

### File Structure
```
rife_extender/
├── main.py              # Entry point (GUI or CLI mode)
├── gui.py               # CustomTkinter GUI application
├── processor.py         # Video processing pipeline (FFmpeg)
├── rife_wrapper.py      # RIFE binary wrapper
├── config.py            # Configuration and paths
├── requirements.txt     # Python dependencies
└── bin/                 # External binaries (not in git)
    ├── rife-ncnn-vulkan/
    │   ├── rife-ncnn-vulkan.exe
    │   └── models/
    └── ffmpeg/
        ├── ffmpeg.exe
        └── ffprobe.exe
```

### Processing Pipeline
```
Input MP4 → FFmpeg extract frames → RIFE interpolation (multi-pass) → FFmpeg reassemble → Output MP4
```

**Multiplier Logic:**
- 2x = 1 RIFE pass (doubles frames)
- 4x = 2 RIFE passes (2x2)
- 8x = 3 RIFE passes (2x2x2)

## Key Functions

### config.py
- `check_dependencies()` - Verify RIFE and FFmpeg binaries exist
- `ensure_directories()` - Create temp/output directories

### processor.py
- `get_video_info(path)` - Extract video metadata via FFprobe
- `extract_frames(video, output_dir)` - FFmpeg frame extraction
- `reassemble_video(frames_dir, output, fps)` - FFmpeg video encoding
- `process_video(input, output, multiplier)` - Full pipeline orchestration

### rife_wrapper.py
- `run_rife(input_dir, output_dir, model)` - Execute single RIFE pass
- `interpolate_multi_pass(input, output, multiplier)` - Chain multiple passes

### gui.py
- `RIFEExtenderApp` - Main CustomTkinter application class
- File selection, multiplier options (2x/4x/8x), progress tracking

## Usage

### GUI Mode (Default)
```bash
python main.py
```

### CLI Mode
```bash
python main.py input.mp4 --cli                 # 4x default
python main.py input.mp4 -m 8 --cli            # 8x slow-motion
python main.py input.mp4 output.mp4 -m 4 --cli # Custom output path
```

## Dependencies

### Python Packages
- customtkinter >= 5.2.0
- Pillow >= 10.0.0

### External Binaries (Download Separately)
1. **rife-ncnn-vulkan**: https://github.com/nihui/rife-ncnn-vulkan/releases
2. **FFmpeg**: https://www.gyan.dev/ffmpeg/builds/

Place binaries in `bin/` directory as shown in file structure above.

## Development Notes

- Audio is intentionally removed (AI-generated videos typically have no meaningful audio)
- Temp frames are cleaned up after processing
- Progress callbacks used for real-time UI updates
- Threading used to keep GUI responsive during processing
