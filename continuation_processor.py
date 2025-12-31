"""
Video continuation pipeline using CogVideoX via RunPod.

Pipeline:
1. Extract last frame from input video (conditioning image)
2. Call RunPod CogVideoX endpoint to generate continuation
3. Optionally concatenate with original video
"""

import subprocess
import shutil
from dataclasses import dataclass
from pathlib import Path
from typing import Optional, Callable

from config import FFMPEG_EXE, FFPROBE_EXE, TEMP_DIR, ensure_directories
from processor import get_video_info
from runpod_client import RunPodCogVideoClient, ContinuationConfig


@dataclass
class ContinuationOptions:
    """Options for video continuation"""
    prompt: str = ""
    negative_prompt: str = "blurry, low quality, distorted, inconsistent"
    duration_seconds: float = 2.0  # 2-4 seconds
    concatenate_original: bool = True
    num_inference_steps: int = 50
    guidance_scale: float = 6.0


def extract_last_frame(
    video_path: Path,
    output_path: Path,
) -> bool:
    """
    Extract the last frame from video for conditioning.

    Args:
        video_path: Path to input video
        output_path: Path to save last frame PNG

    Returns:
        True if successful
    """
    if not FFMPEG_EXE.exists():
        raise FileNotFoundError(f"FFmpeg not found: {FFMPEG_EXE}")

    # Ensure output directory exists
    output_path.parent.mkdir(parents=True, exist_ok=True)

    # Use sseof to seek from end (-1 means last second)
    cmd = [
        str(FFMPEG_EXE),
        "-y",  # Overwrite
        "-sseof", "-1",  # Seek to 1 second before end
        "-i", str(video_path),
        "-vframes", "1",  # Extract 1 frame
        "-q:v", "2",  # High quality
        str(output_path),
    ]

    result = subprocess.run(cmd, capture_output=True, text=True)
    return result.returncode == 0 and output_path.exists()


def concatenate_videos(
    original: Path,
    continuation: Path,
    output: Path,
) -> bool:
    """
    Concatenate original video with continuation video.

    Args:
        original: Path to original video
        continuation: Path to continuation video
        output: Path for output concatenated video

    Returns:
        True if successful
    """
    if not FFMPEG_EXE.exists():
        raise FileNotFoundError(f"FFmpeg not found: {FFMPEG_EXE}")

    # Ensure output directory exists
    output.parent.mkdir(parents=True, exist_ok=True)

    # Create concat list file
    concat_list = output.parent / f"{output.stem}_concat.txt"
    try:
        with open(concat_list, "w") as f:
            f.write(f"file '{original.resolve()}'\n")
            f.write(f"file '{continuation.resolve()}'\n")

        # Run FFmpeg concat
        cmd = [
            str(FFMPEG_EXE),
            "-y",  # Overwrite
            "-f", "concat",
            "-safe", "0",  # Allow absolute paths
            "-i", str(concat_list),
            "-c", "copy",  # Stream copy (fast, no re-encoding)
            str(output),
        ]

        result = subprocess.run(cmd, capture_output=True, text=True)
        return result.returncode == 0

    finally:
        # Clean up concat list
        if concat_list.exists():
            concat_list.unlink()


def reencode_video(
    input_path: Path,
    output_path: Path,
    target_fps: Optional[float] = None,
    target_resolution: Optional[tuple] = None,
) -> bool:
    """
    Re-encode video to match target parameters.

    Args:
        input_path: Path to input video
        output_path: Path for output video
        target_fps: Target framerate (None to keep original)
        target_resolution: Target (width, height) tuple (None to keep original)

    Returns:
        True if successful
    """
    if not FFMPEG_EXE.exists():
        raise FileNotFoundError(f"FFmpeg not found: {FFMPEG_EXE}")

    output_path.parent.mkdir(parents=True, exist_ok=True)

    cmd = [
        str(FFMPEG_EXE),
        "-y",
        "-i", str(input_path),
        "-c:v", "libx264",
        "-preset", "medium",
        "-crf", "18",
        "-pix_fmt", "yuv420p",
    ]

    if target_fps:
        cmd.extend(["-r", str(target_fps)])

    if target_resolution:
        w, h = target_resolution
        cmd.extend(["-vf", f"scale={w}:{h}"])

    cmd.append(str(output_path))

    result = subprocess.run(cmd, capture_output=True, text=True)
    return result.returncode == 0


def continue_video(
    input_path: Path,
    output_path: Path,
    api_key: str,
    endpoint_id: str,
    options: ContinuationOptions,
    progress_callback: Optional[Callable[[str, float], None]] = None,
) -> bool:
    """
    Main pipeline for video continuation.

    Stages:
    - Analyzing input video (0-5%)
    - Extracting conditioning frame (5-10%)
    - Generating continuation (10-80%)
    - Processing result (80-90%)
    - Concatenating videos (90-100%)

    Args:
        input_path: Path to input video
        output_path: Path for output video
        api_key: RunPod API key
        endpoint_id: RunPod endpoint ID
        options: Continuation options
        progress_callback: Optional callback(stage: str, progress: 0.0-1.0)

    Returns:
        True if successful
    """
    ensure_directories()

    # Create unique temp directory for this job
    job_id = input_path.stem
    temp_job_dir = TEMP_DIR / f"{job_id}_continuation"

    try:
        temp_job_dir.mkdir(parents=True, exist_ok=True)

        # Stage 1: Analyze input video
        if progress_callback:
            progress_callback("Analyzing video...", 0.0)

        info = get_video_info(input_path)
        print(f"Input: {info.resolution} @ {info.fps:.2f}fps, {info.duration:.2f}s")

        # Stage 2: Extract last frame
        if progress_callback:
            progress_callback("Extracting conditioning frame...", 0.05)

        conditioning_frame = temp_job_dir / "last_frame.png"
        if not extract_last_frame(input_path, conditioning_frame):
            raise RuntimeError("Failed to extract last frame")

        # Stage 3: Generate continuation via RunPod
        if progress_callback:
            progress_callback("Connecting to RunPod...", 0.10)

        client = RunPodCogVideoClient(
            api_key=api_key,
            endpoint_id=endpoint_id,
            timeout=300,  # 5 minute timeout
        )

        # Determine number of frames based on duration
        # CogVideoX generates 49 frames at 8fps (~6 seconds)
        # For 2 seconds at original fps: frames = 2 * fps
        # But we're limited by what CogVideoX outputs
        num_frames = 49  # CogVideoX default

        config = ContinuationConfig(
            prompt=options.prompt,
            negative_prompt=options.negative_prompt,
            num_frames=num_frames,
            num_inference_steps=options.num_inference_steps,
            guidance_scale=options.guidance_scale,
        )

        continuation_raw = temp_job_dir / "continuation_raw.mp4"

        def api_progress(stage: str, progress: float):
            if progress_callback:
                # Map API progress (0-1) to our range (10-80%)
                mapped_progress = 0.10 + progress * 0.70
                progress_callback(stage, mapped_progress)

        result = client.generate_continuation(
            conditioning_image=conditioning_frame,
            config=config,
            output_path=continuation_raw,
            progress_callback=api_progress,
        )

        if not result.success:
            raise RuntimeError(f"Continuation generation failed: {result.error_message}")

        print(f"Continuation generated in {result.generation_time:.1f}s")

        # Stage 4: Re-encode continuation to match original video
        if progress_callback:
            progress_callback("Processing continuation...", 0.80)

        continuation_matched = temp_job_dir / "continuation_matched.mp4"
        if not reencode_video(
            continuation_raw,
            continuation_matched,
            target_fps=info.fps,
            target_resolution=(info.width, info.height),
        ):
            raise RuntimeError("Failed to re-encode continuation")

        # Stage 5: Concatenate or just copy
        if options.concatenate_original:
            if progress_callback:
                progress_callback("Concatenating videos...", 0.90)

            # Need to re-encode original to ensure compatibility
            original_reencoded = temp_job_dir / "original_reencoded.mp4"
            if not reencode_video(input_path, original_reencoded, target_fps=info.fps):
                raise RuntimeError("Failed to re-encode original")

            if not concatenate_videos(original_reencoded, continuation_matched, output_path):
                raise RuntimeError("Failed to concatenate videos")
        else:
            # Just copy continuation as output
            if progress_callback:
                progress_callback("Saving output...", 0.90)
            shutil.copy(continuation_matched, output_path)

        if progress_callback:
            progress_callback("Complete!", 1.0)

        # Report output info
        output_info = get_video_info(output_path)
        print(f"Output: {output_info.resolution} @ {output_info.fps:.2f}fps, {output_info.duration:.2f}s")

        if options.concatenate_original:
            print(f"Extended: {info.duration:.1f}s -> {output_info.duration:.1f}s (+{output_info.duration - info.duration:.1f}s)")
        else:
            print(f"Continuation only: {output_info.duration:.1f}s")

        return True

    finally:
        # Cleanup temp directory
        if temp_job_dir.exists():
            shutil.rmtree(temp_job_dir)
