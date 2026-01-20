# RIFE Video Extender

## Project Overview
A Windows GUI/CLI application with two main features:
1. **Slow-Motion**: Create slow-motion videos using RIFE AI frame interpolation
2. **AI Continuation**: Extend videos with AI-generated content using Wan 2.2 I2V Fast on Replicate

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
| AI Continuation | Wan 2.2 I2V Fast on Replicate | Cloud video generation API (~39s, ~$0.05) |
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
├── replicate_client.py        # Replicate API client for Wan 2.2
├── config.py                  # Configuration, paths, credentials, prompts
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
Multiplier Logic: 2x=1 pass, 4x=2 passes, 8x=3 passes, 16x=4 passes (each pass doubles frames)

**AI Continuation Pipeline:**
```
Input MP4 → Extract last frame → Replicate Wan 2.2 API → Re-encode → Concatenate → Output MP4
```

## Key Functions

### config.py
- `check_dependencies()` - Verify RIFE and FFmpeg binaries exist
- `ensure_directories()` - Create temp/output directories
- `get_replicate_api_token()` - Get API token from env or config file
- `save_replicate_config()` - Save API token locally
- `get_saved_prompts()` - Load saved prompts from JSON
- `save_prompt(name, text)` - Save/update a prompt
- `delete_prompt(name)` - Delete a saved prompt

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
- `continue_video(input, output, api_token, options)` - Full continuation pipeline
- `concatenate_videos(original, continuation, output)` - FFmpeg concat

### replicate_client.py
- `ReplicateCogVideoClient` - API client class for Wan 2.2 I2V Fast
- `generate_continuation(image, config, output)` - Run model, download result

### gui.py
- `RIFEExtenderApp` - Main CustomTkinter application with tabbed interface
- Slow-Motion tab: multiplier options (2x/4x/8x)
- AI Continuation tab: API token, prompt dropdown with save/delete, duration options

## Usage

### GUI Mode (Default)
```bash
python main.py
```

### CLI Mode - Slow-Motion
```bash
python main.py input.mp4 --cli                 # 4x default
python main.py input.mp4 -m 8 --cli            # 8x slow-motion
python main.py input.mp4 -m 16 --cli           # 16x slow-motion
python main.py input.mp4 output.mp4 -m 4 --cli # Custom output path
```

### CLI Mode - AI Continuation
```bash
python main.py input.mp4 --continue --cli                        # Generate continuation
python main.py input.mp4 --continue --prompt "..." --cli         # With text prompt
python main.py input.mp4 --continue --no-concat --cli            # Output continuation only
python main.py input.mp4 --continue --api-token TOKEN --cli      # With explicit token
```

## Dependencies

### Python Packages
- customtkinter >= 5.2.0
- Pillow >= 10.0.0
- replicate >= 0.25.0 (for AI continuation)
- requests >= 2.28.0 (for AI continuation)

### External Binaries (Download Separately)
1. **rife-ncnn-vulkan**: https://github.com/nihui/rife-ncnn-vulkan/releases
2. **FFmpeg**: https://www.gyan.dev/ffmpeg/builds/

Place binaries in `bin/` directory as shown in file structure above.

### Replicate Setup (for AI Continuation)
1. Create Replicate account at https://replicate.com
2. Get API token from https://replicate.com/account/api-tokens
3. Set via environment variable `REPLICATE_API_TOKEN` or enter in GUI
4. Model used: wan-video/wan-2.2-i2v-fast (~$0.05 per generation)

## Development Notes

- Audio is intentionally removed (AI-generated videos typically have no meaningful audio)
- Temp frames are cleaned up after processing
- Progress callbacks used for real-time UI updates
- Threading used to keep GUI responsive during processing
- Replicate API token can be saved locally in `.replicate_config` (excluded from git)
- Saved prompts stored in `.saved_prompts.json` (excluded from git)

## Key Patterns
- **Progress callbacks**: `progress_callback(stage: str, progress: float)` for pipeline stages
- **Threading**: GUI runs processing in background thread, uses `self.after()` for UI updates
- **Temp directories**: Per-job isolation in `temp/{job_id}_input`, cleaned after processing
- **VideoInfo dataclass**: Structured video metadata from FFprobe
- **Credential hierarchy**: Environment variables take precedence over config files
