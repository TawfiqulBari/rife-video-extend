"""
Video processing pipeline using FFmpeg
"""
import subprocess
import json
import shutil
from pathlib import Path
from typing import Optional, Callable
from dataclasses import dataclass

from config import FFMPEG_EXE, FFPROBE_EXE, TEMP_DIR, ensure_directories


@dataclass
class VideoInfo:
    """Video metadata"""
    width: int
    height: int
    fps: float
    duration: float
    frame_count: int
    codec: str

    @property
    def resolution(self) -> str:
        return f"{self.width}x{self.height}"


def get_video_info(video_path: Path) -> VideoInfo:
    """
    Extract video metadata using FFprobe.

    Args:
        video_path: Path to video file

    Returns:
        VideoInfo dataclass with video properties
    """
    if not FFPROBE_EXE.exists():
        raise FileNotFoundError(f"FFprobe not found: {FFPROBE_EXE}")

    cmd = [
        str(FFPROBE_EXE),
        "-v", "quiet",
        "-print_format", "json",
        "-show_streams",
        "-show_format",
        str(video_path),
    ]

    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        raise RuntimeError(f"FFprobe failed: {result.stderr}")

    data = json.loads(result.stdout)

    # Find video stream
    video_stream = None
    for stream in data.get("streams", []):
        if stream.get("codec_type") == "video":
            video_stream = stream
            break

    if not video_stream:
        raise ValueError("No video stream found")

    # Parse FPS (can be "30/1" or "29.97")
    fps_str = video_stream.get("r_frame_rate", "30/1")
    if "/" in fps_str:
        num, den = map(float, fps_str.split("/"))
        fps = num / den if den != 0 else 30.0
    else:
        fps = float(fps_str)

    # Get duration
    duration = float(video_stream.get("duration", 0))
    if duration == 0:
        duration = float(data.get("format", {}).get("duration", 0))

    # Calculate frame count
    frame_count = int(video_stream.get("nb_frames", 0))
    if frame_count == 0:
        frame_count = int(fps * duration)

    return VideoInfo(
        width=int(video_stream.get("width", 0)),
        height=int(video_stream.get("height", 0)),
        fps=fps,
        duration=duration,
        frame_count=frame_count,
        codec=video_stream.get("codec_name", "unknown"),
    )


def extract_frames(
    video_path: Path,
    output_dir: Path,
    progress_callback: Optional[Callable[[int, int], None]] = None,
) -> int:
    """
    Extract all frames from video using FFmpeg.

    Args:
        video_path: Path to input video
        output_dir: Directory to save frames (as 00000000.png, 00000001.png, etc.)
        progress_callback: Optional callback(current_frame, total_frames)

    Returns:
        Number of frames extracted
    """
    if not FFMPEG_EXE.exists():
        raise FileNotFoundError(f"FFmpeg not found: {FFMPEG_EXE}")

    # Get video info for progress tracking
    info = get_video_info(video_path)
    total_frames = info.frame_count

    # Ensure output directory exists and is empty
    output_dir.mkdir(parents=True, exist_ok=True)

    # Build FFmpeg command
    cmd = [
        str(FFMPEG_EXE),
        "-i", str(video_path),
        "-vsync", "0",  # Preserve original timestamps
        "-q:v", "2",  # High quality PNG
        str(output_dir / "%08d.png"),
    ]

    # Run FFmpeg with progress monitoring
    process = subprocess.Popen(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
    )

    frame_count = 0
    for line in iter(process.stdout.readline, ""):
        # FFmpeg outputs frame count in stderr
        if "frame=" in line:
            try:
                # Parse "frame=  123" format
                parts = line.split("frame=")
                if len(parts) > 1:
                    frame_str = parts[1].split()[0].strip()
                    frame_count = int(frame_str)
                    if progress_callback:
                        progress_callback(frame_count, total_frames)
            except (ValueError, IndexError):
                pass

    process.wait()

    if process.returncode != 0:
        raise RuntimeError("FFmpeg frame extraction failed")

    # Count actual extracted frames
    actual_count = len(list(output_dir.glob("*.png")))
    return actual_count


def reassemble_video(
    frames_dir: Path,
    output_path: Path,
    fps: float,
    quality: int = 18,
    progress_callback: Optional[Callable[[int, int], None]] = None,
) -> bool:
    """
    Reassemble frames into a video using FFmpeg.

    Args:
        frames_dir: Directory containing frames (named 00000000.png, etc.)
        output_path: Path for output video
        fps: Output framerate
        quality: CRF value (lower = better quality, 18-23 recommended)
        progress_callback: Optional callback(current_frame, total_frames)

    Returns:
        True if successful
    """
    if not FFMPEG_EXE.exists():
        raise FileNotFoundError(f"FFmpeg not found: {FFMPEG_EXE}")

    # Count frames for progress
    total_frames = len(list(frames_dir.glob("*.png")))

    # Ensure output directory exists
    output_path.parent.mkdir(parents=True, exist_ok=True)

    # Build FFmpeg command
    cmd = [
        str(FFMPEG_EXE),
        "-y",  # Overwrite output
        "-framerate", str(fps),
        "-i", str(frames_dir / "%08d.png"),
        "-c:v", "libx264",
        "-preset", "medium",
        "-crf", str(quality),
        "-pix_fmt", "yuv420p",  # Wide compatibility
        str(output_path),
    ]

    # Run FFmpeg
    process = subprocess.Popen(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
    )

    for line in iter(process.stdout.readline, ""):
        if "frame=" in line:
            try:
                parts = line.split("frame=")
                if len(parts) > 1:
                    frame_str = parts[1].split()[0].strip()
                    frame_count = int(frame_str)
                    if progress_callback:
                        progress_callback(frame_count, total_frames)
            except (ValueError, IndexError):
                pass

    process.wait()
    return process.returncode == 0


def process_video(
    input_path: Path,
    output_path: Path,
    multiplier: int = 4,
    model: str = "rife-v4.6",
    gpu_id: int = 0,
    progress_callback: Optional[Callable[[str, float], None]] = None,
) -> bool:
    """
    Full video processing pipeline.

    Args:
        input_path: Input video path
        output_path: Output video path
        multiplier: Slow-motion multiplier (2, 4, 8)
        model: RIFE model name
        gpu_id: GPU device ID
        progress_callback: Optional callback(stage: str, progress: 0.0-1.0)

    Returns:
        True if successful
    """
    from rife_wrapper import interpolate_multi_pass

    ensure_directories()

    # Create unique temp directories for this job
    job_id = input_path.stem
    input_frames_dir = TEMP_DIR / f"{job_id}_input"
    output_frames_dir = TEMP_DIR / f"{job_id}_output"

    try:
        # Stage 1: Get video info
        if progress_callback:
            progress_callback("Analyzing video...", 0.0)

        info = get_video_info(input_path)
        print(f"Input: {info.resolution} @ {info.fps:.2f}fps, {info.duration:.2f}s, {info.frame_count} frames")

        # Stage 2: Extract frames
        if progress_callback:
            progress_callback("Extracting frames...", 0.05)

        def extract_progress(current: int, total: int):
            if progress_callback:
                pct = 0.05 + (current / max(total, 1)) * 0.25
                progress_callback(f"Extracting frame {current}/{total}", pct)

        frame_count = extract_frames(input_path, input_frames_dir, extract_progress)
        print(f"Extracted {frame_count} frames")

        # Stage 3: RIFE interpolation
        if progress_callback:
            progress_callback("Running RIFE interpolation...", 0.30)

        def rife_progress(pass_num: int, current: int, total: int):
            if progress_callback:
                # Interpolation is 30-90% of total
                base = 0.30
                range_pct = 0.60
                pass_pct = pass_num / max(1, multiplier.bit_length() - 1)
                frame_pct = current / max(total, 1)
                pct = base + range_pct * (pass_pct * 0.5 + frame_pct * 0.5)
                progress_callback(f"RIFE pass {pass_num}: {current}/{total}", pct)

        success = interpolate_multi_pass(
            input_dir=input_frames_dir,
            output_dir=output_frames_dir,
            multiplier=multiplier,
            model=model,
            gpu_id=gpu_id,
            progress_callback=rife_progress,
        )

        if not success:
            raise RuntimeError("RIFE interpolation failed")

        # Stage 4: Reassemble video
        # Output FPS stays the same, but we have more frames = longer duration
        output_fps = info.fps

        if progress_callback:
            progress_callback("Creating output video...", 0.90)

        def reassemble_progress(current: int, total: int):
            if progress_callback:
                pct = 0.90 + (current / max(total, 1)) * 0.10
                progress_callback(f"Encoding frame {current}/{total}", pct)

        success = reassemble_video(
            frames_dir=output_frames_dir,
            output_path=output_path,
            fps=output_fps,
            progress_callback=reassemble_progress,
        )

        if not success:
            raise RuntimeError("Video reassembly failed")

        if progress_callback:
            progress_callback("Complete!", 1.0)

        # Get output info
        output_info = get_video_info(output_path)
        print(f"Output: {output_info.resolution} @ {output_info.fps:.2f}fps, {output_info.duration:.2f}s")
        print(f"Slow-motion: {multiplier}x ({info.duration:.1f}s -> {output_info.duration:.1f}s)")

        return True

    finally:
        # Cleanup temp directories
        if input_frames_dir.exists():
            shutil.rmtree(input_frames_dir)
        if output_frames_dir.exists():
            shutil.rmtree(output_frames_dir)
