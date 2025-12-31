# RIFE Video Extender

## Project Overview
A Windows GUI/CLI application with two main features:
1. **Slow-Motion**: Create slow-motion videos using RIFE AI frame interpolation
2. **AI Continuation**: Extend videos with AI-generated content using CogVideoX on RunPod

**Target Use Case:**
- Input: 6-second AI-generated videos (1080p MP4)
- Output: Extended or slow-motion videos
- Platform: Windows 11 with NVIDIA GPU (RTX 3060 12GB)

## Architecture

### Tech Stack
| Component | Technology | Purpose |
|-----------|------------|---------|
| GUI | Python + CustomTkinter | Modern dark-themed tabbed interface |
| Frame Interpolation | rife-ncnn-vulkan | Standalone RIFE binary using Vulkan/NCNN |
| AI Continuation | CogVideoX on RunPod | Serverless video generation API |
| Video Processing | FFmpeg | Frame extraction and video reassembly |
| Packaging | PyInstaller | Future single .exe distribution |

### File Structure
```
rife_extender/
├── main.py                    # Entry point (GUI or CLI mode)
├── gui.py                     # CustomTkinter GUI with tabbed interface
├── processor.py               # Slow-motion pipeline (FFmpeg + RIFE)
├── rife_wrapper.py            # RIFE binary wrapper
├── continuation_processor.py  # AI continuation pipeline
├── runpod_client.py           # RunPod API client for CogVideoX
├── config.py                  # Configuration, paths, credentials
├── requirements.txt           # Python dependencies
└── bin/                       # External binaries (not in git)
    ├── rife-ncnn-vulkan/
    │   ├── rife-ncnn-vulkan.exe
    │   └── models/
    └── ffmpeg/
        ├── ffmpeg.exe
        └── ffprobe.exe
```

### Processing Pipelines

**Slow-Motion Pipeline:**
```
Input MP4 → FFmpeg extract frames → RIFE interpolation (multi-pass) → FFmpeg reassemble → Output MP4
```
Multiplier Logic: 2x=1 pass, 4x=2 passes, 8x=3 passes (each pass doubles frames)

**AI Continuation Pipeline:**
```
Input MP4 → Extract last frame → RunPod CogVideoX API → Re-encode → Concatenate → Output MP4
```

## Key Functions

### config.py
- `check_dependencies()` - Verify RIFE and FFmpeg binaries exist
- `ensure_directories()` - Create temp/output directories
- `get_runpod_api_key()` / `get_runpod_endpoint_id()` - Credential management
- `save_runpod_config()` - Save credentials locally

### processor.py
- `get_video_info(path)` - Extract video metadata via FFprobe
- `extract_frames(video, output_dir)` - FFmpeg frame extraction
- `reassemble_video(frames_dir, output, fps)` - FFmpeg video encoding
- `process_video(input, output, multiplier)` - Full slow-motion pipeline

### rife_wrapper.py
- `run_rife(input_dir, output_dir, model)` - Execute single RIFE pass
- `interpolate_multi_pass(input, output, multiplier)` - Chain multiple passes

### continuation_processor.py
- `extract_last_frame(video, output)` - Extract conditioning frame
- `continue_video(input, output, api_key, endpoint_id, options)` - Full continuation pipeline
- `concatenate_videos(original, continuation, output)` - FFmpeg concat

### runpod_client.py
- `RunPodCogVideoClient` - API client class
- `generate_continuation(image, config, output)` - Submit job, poll, download result

### gui.py
- `RIFEExtenderApp` - Main CustomTkinter application with tabbed interface
- Slow-Motion tab: multiplier options (2x/4x/8x)
- AI Continuation tab: API credentials, prompt, duration options

## Usage

### GUI Mode (Default)
```bash
python main.py
```

### CLI Mode - Slow-Motion
```bash
python main.py input.mp4 --cli                 # 4x default
python main.py input.mp4 -m 8 --cli            # 8x slow-motion
python main.py input.mp4 output.mp4 -m 4 --cli # Custom output path
```

### CLI Mode - AI Continuation
```bash
python main.py input.mp4 --continue --cli                    # Generate continuation
python main.py input.mp4 --continue --prompt "..." --cli     # With text prompt
python main.py input.mp4 --continue --no-concat --cli        # Output continuation only
python main.py input.mp4 --continue --duration 4.0 --cli     # 4 second continuation
```

## Dependencies

### Python Packages
- customtkinter >= 5.2.0
- Pillow >= 10.0.0
- runpod >= 1.6.0 (for AI continuation)
- requests >= 2.28.0 (for AI continuation)

### External Binaries (Download Separately)
1. **rife-ncnn-vulkan**: https://github.com/nihui/rife-ncnn-vulkan/releases
2. **FFmpeg**: https://www.gyan.dev/ffmpeg/builds/

Place binaries in `bin/` directory as shown in file structure above.

### RunPod Setup (for AI Continuation)
1. Create RunPod account at https://runpod.io
2. Deploy CogVideoX serverless endpoint (https://github.com/runpod-workers/worker-cogvideox)
3. Set credentials via environment variables or GUI:
   - `RUNPOD_API_KEY` - Your RunPod API key
   - `RUNPOD_ENDPOINT_ID` - Your endpoint ID

## Development Notes

- Audio is intentionally removed (AI-generated videos typically have no meaningful audio)
- Temp frames are cleaned up after processing
- Progress callbacks used for real-time UI updates
- Threading used to keep GUI responsive during processing
- RunPod credentials can be saved locally in `.runpod_config` (excluded from git)
