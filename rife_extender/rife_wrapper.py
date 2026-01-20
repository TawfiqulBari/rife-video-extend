"""
Wrapper for rife-ncnn-vulkan binary
"""
import subprocess
import os
from pathlib import Path
from typing import Callable, Optional
import re

from config import RIFE_EXE, RIFE_MODELS_DIR


def get_available_models() -> list[str]:
    """Get list of available RIFE models"""
    models = []
    if RIFE_MODELS_DIR.exists():
        for item in RIFE_MODELS_DIR.iterdir():
            if item.is_dir() and item.name.startswith("rife"):
                models.append(item.name)
    return sorted(models)


def run_rife(
    input_dir: Path,
    output_dir: Path,
    model: str = "rife-v4.6",
    gpu_id: int = 0,
    uhd_mode: bool = False,
    progress_callback: Optional[Callable[[int, int], None]] = None,
) -> bool:
    """
    Run RIFE interpolation on a directory of frames.

    RIFE doubles frames per pass. For higher multipliers, we run multiple passes.

    Args:
        input_dir: Directory containing input frames (named 00000.png, 00001.png, etc.)
        output_dir: Directory to write interpolated frames
        model: RIFE model to use (e.g., "rife-v4.6")
        gpu_id: GPU device ID
        uhd_mode: Enable UHD mode for 4K+ content
        progress_callback: Optional callback(current_frame, total_frames)

    Returns:
        True if successful, False otherwise
    """
    if not RIFE_EXE.exists():
        raise FileNotFoundError(f"RIFE executable not found: {RIFE_EXE}")

    # Ensure output directory exists
    output_dir.mkdir(parents=True, exist_ok=True)

    # Build command
    cmd = [
        str(RIFE_EXE),
        "-i", str(input_dir),
        "-o", str(output_dir),
        "-m", model,
        "-g", str(gpu_id),
        "-f", "%08d.png",  # Output filename pattern
    ]

    if uhd_mode:
        cmd.append("-x")  # UHD mode

    # Run RIFE
    try:
        process = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1,
            cwd=str(RIFE_MODELS_DIR),
        )

        # Parse output for progress
        frame_pattern = re.compile(r"(\d+)/(\d+)")

        for line in iter(process.stdout.readline, ""):
            line = line.strip()
            if line:
                # Try to extract progress
                match = frame_pattern.search(line)
                if match and progress_callback:
                    current = int(match.group(1))
                    total = int(match.group(2))
                    progress_callback(current, total)

        process.wait()
        return process.returncode == 0

    except Exception as e:
        print(f"RIFE error: {e}")
        return False


def interpolate_multi_pass(
    input_dir: Path,
    output_dir: Path,
    multiplier: int = 4,
    model: str = "rife-v4.6",
    gpu_id: int = 0,
    progress_callback: Optional[Callable[[int, int, int], None]] = None,
) -> bool:
    """
    Run multiple RIFE passes to achieve higher interpolation multipliers.

    Args:
        input_dir: Directory with original frames
        output_dir: Final output directory
        multiplier: Target multiplier (2, 4, 8, 16, etc.)
        model: RIFE model name
        gpu_id: GPU device ID
        progress_callback: Optional callback(pass_num, current_frame, total_frames)

    Returns:
        True if successful
    """
    import shutil
    import math

    # Calculate number of passes needed (each pass doubles frames)
    num_passes = int(math.log2(multiplier))
    if 2 ** num_passes != multiplier:
        print(f"Warning: multiplier {multiplier} is not a power of 2, rounding down")
        num_passes = int(math.log2(multiplier))

    current_input = input_dir
    temp_dirs = []

    for pass_num in range(num_passes):
        is_last_pass = (pass_num == num_passes - 1)

        if is_last_pass:
            current_output = output_dir
        else:
            # Create temp directory for intermediate pass
            temp_output = output_dir.parent / f"temp_pass_{pass_num}"
            temp_output.mkdir(parents=True, exist_ok=True)
            temp_dirs.append(temp_output)
            current_output = temp_output

        print(f"Pass {pass_num + 1}/{num_passes}: {current_input} -> {current_output}")

        # Create a wrapper callback for this pass
        def pass_callback(current: int, total: int, pn=pass_num):
            if progress_callback:
                progress_callback(pn + 1, current, total)

        success = run_rife(
            input_dir=current_input,
            output_dir=current_output,
            model=model,
            gpu_id=gpu_id,
            progress_callback=pass_callback,
        )

        if not success:
            # Cleanup temp dirs
            for temp_dir in temp_dirs:
                if temp_dir.exists():
                    shutil.rmtree(temp_dir)
            return False

        # Next pass uses this output as input
        current_input = current_output

    # Cleanup intermediate temp directories
    for temp_dir in temp_dirs:
        if temp_dir.exists():
            shutil.rmtree(temp_dir)

    return True
