# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

RIFE Video Extender is a Windows GUI/CLI application with two main features:
1. **Slow-Motion**: Create slow-motion videos using RIFE AI frame interpolation
2. **AI Continuation**: Extend videos with AI-generated content using Wan 2.2 I2V Fast on Replicate

**Target Platform:** Windows 11 with NVIDIA GPU

## Commands

### Run Application
```bash
cd rife_extender
python main.py                           # Launch GUI (default)

# Slow-motion mode
python main.py input.mp4 --cli           # Process via CLI with 4x multiplier
python main.py input.mp4 -m 8 --cli      # 8x slow-motion
python main.py input.mp4 -m 16 --cli     # 16x slow-motion (4 RIFE passes)
python main.py input.mp4 --model rife-v4.6 --gpu 0 --cli  # Specify model and GPU

# AI Continuation mode (requires Replicate)
python main.py input.mp4 --continue --cli                    # Generate continuation
python main.py input.mp4 --continue --prompt "..." --cli     # With text prompt
python main.py input.mp4 --continue --no-concat --cli        # Output continuation only
python main.py input.mp4 --continue --duration 4.0 --cli     # 4 second continuation
python main.py input.mp4 --continue --api-token TOKEN --cli  # Override API token

python main.py input.mp4 --info          # Show video info only
```

### Install Dependencies
```bash
cd rife_extender
pip install -r requirements.txt
```

### External Binaries (Not in Git)
Place in `rife_extender/bin/`:
- **rife-ncnn-vulkan**: Download from https://github.com/nihui/rife-ncnn-vulkan/releases -> `bin/rife-ncnn-vulkan/`
- **FFmpeg**: Download from https://www.gyan.dev/ffmpeg/builds/ -> `bin/ffmpeg/`

## Architecture

### Tech Stack
- **GUI**: Python + CustomTkinter (dark theme)
- **Frame Interpolation**: rife-ncnn-vulkan binary (Vulkan/NCNN)
- **Video Processing**: FFmpeg for frame extraction and reassembly

### Module Responsibilities
- `main.py` - Entry point, CLI argument parsing, launches GUI or CLI mode
- `gui.py` - CustomTkinter GUI with tabs for Slow-Motion and AI Continuation modes
- `processor.py` - Slow-motion pipeline: frame extraction, reassembly, orchestration
- `rife_wrapper.py` - Wrapper for rife-ncnn-vulkan binary execution
- `continuation_processor.py` - AI continuation pipeline: extract last frame, Replicate API, concatenate
- `replicate_client.py` - Replicate API client for Wan 2.2 I2V Fast model
- `config.py` - Paths, settings, credential management, dependency checking

### Processing Pipelines

**Slow-Motion Pipeline:**
```
Input MP4 -> FFmpeg extract frames -> RIFE multi-pass interpolation -> FFmpeg reassemble -> Output MP4
```
Multiplier determines RIFE passes: 2x=1 pass, 4x=2 passes, 8x=3 passes, 16x=4 passes (each pass doubles frame count)

**AI Continuation Pipeline:**
```
Input MP4 -> Extract last frame -> Replicate Wan 2.2 API -> Re-encode -> Concatenate -> Output MP4
```
Requires Replicate account with API token

### Key Patterns
- **Progress callbacks**: `progress_callback(stage: str, progress: float)` where progress is 0.0-1.0
- **Threading**: GUI runs processing in background thread, uses `self.after()` for UI updates
- **Temp directories**: Per-job isolation in `temp/{job_id}_input`, `temp/{job_id}_output`, cleaned after processing
- **VideoInfo dataclass**: Contains width, height, fps, duration, frame_count, codec, resolution (computed property)
- **Credential hierarchy**: Environment variable (`REPLICATE_API_TOKEN`) takes precedence over `.replicate_config` file

### Key Functions

**processor.py**
- `get_video_info(path)` → `VideoInfo` - Extract metadata via FFprobe
- `extract_frames(video, output_dir)` - FFmpeg frame extraction to numbered PNGs
- `reassemble_video(frames_dir, output, fps)` - FFmpeg H.264 encoding
- `process_video(input, output, multiplier)` - Full slow-motion pipeline

**rife_wrapper.py**
- `run_rife(input_dir, output_dir, model)` - Single RIFE pass (doubles frames)
- `interpolate_multi_pass(input, output, multiplier)` - Chain passes for 4x/8x/16x

**continuation_processor.py**
- `extract_last_frame(video, output)` - Get conditioning frame for AI
- `continue_video(input, output, api_token, options)` - Full pipeline
- `concatenate_videos(original, continuation, output)` - FFmpeg concat demuxer

**replicate_client.py**
- `ReplicateCogVideoClient.generate_continuation(image, config, output)` - Submit prediction, poll, download

## Development Notes

- Audio is intentionally stripped (AI-generated videos typically have no meaningful audio)
- Output is always MP4 with H.264 codec, CRF 18 quality
- GUI window: 500x750, dark theme with blue accents, tabbed interface
- Supported input formats: .mp4, .avi, .mov, .mkv, .webm
- Frame numbering: 8-digit zero-padded (`%08d.png`)

### Replicate Configuration (for AI Continuation)
- API token via environment variable: `REPLICATE_API_TOKEN`
- Or saved locally in `.replicate_config` (excluded from git)
- Uses Wan 2.2 I2V Fast model: `wan-video/wan-2.2-i2v-fast`
- Generates 81 frames at 24fps (~3.4 seconds of video)
- Cost: ~$0.05 per generation (much cheaper than CogVideoX)
- Safety checker disabled by default
