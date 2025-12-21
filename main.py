"""
RIFE Video Extender - Main Entry Point

Usage:
    python main.py                           # Launch GUI
    python main.py input.mp4                 # Launch GUI with file
    python main.py input.mp4 --cli           # Process via CLI
    python main.py input.mp4 -m 8 --cli      # 8x slow-motion via CLI
"""
import argparse
import sys
from pathlib import Path

from config import check_dependencies, ensure_directories, SUPPORTED_FORMATS
from processor import process_video, get_video_info


def print_progress(stage: str, progress: float):
    """Print progress to console"""
    bar_width = 40
    filled = int(bar_width * progress)
    bar = "=" * filled + "-" * (bar_width - filled)
    print(f"\r[{bar}] {progress*100:.1f}% - {stage}", end="", flush=True)
    if progress >= 1.0:
        print()  # New line when complete


def run_cli(args):
    """Run in CLI mode"""
    # Ensure directories exist
    ensure_directories()

    # Check dependencies
    missing = check_dependencies()
    if missing:
        print("ERROR: Missing dependencies:")
        for m in missing:
            print(f"  - {m}")
        print("\nPlease download the required binaries:")
        print("  1. rife-ncnn-vulkan: https://github.com/nihui/rife-ncnn-vulkan/releases")
        print("  2. FFmpeg: https://www.gyan.dev/ffmpeg/builds/")
        sys.exit(1)

    # Validate input
    if not args.input.exists():
        print(f"ERROR: Input file not found: {args.input}")
        sys.exit(1)

    if args.input.suffix.lower() not in SUPPORTED_FORMATS:
        print(f"ERROR: Unsupported format: {args.input.suffix}")
        print(f"Supported formats: {', '.join(SUPPORTED_FORMATS)}")
        sys.exit(1)

    # Show video info
    try:
        info = get_video_info(args.input)
        print(f"\nInput Video: {args.input.name}")
        print(f"  Resolution: {info.resolution}")
        print(f"  FPS: {info.fps:.2f}")
        print(f"  Duration: {info.duration:.2f}s")
        print(f"  Frames: {info.frame_count}")
        print(f"  Codec: {info.codec}")

        if args.info:
            sys.exit(0)

        # Calculate output duration
        output_duration = info.duration * args.multiplier
        output_frames = info.frame_count * args.multiplier
        print(f"\nOutput Preview:")
        print(f"  Multiplier: {args.multiplier}x")
        print(f"  Duration: {output_duration:.2f}s")
        print(f"  Frames: {output_frames}")

    except Exception as e:
        print(f"ERROR: Could not read video info: {e}")
        sys.exit(1)

    # Set output path
    if args.output is None:
        args.output = args.input.parent / f"{args.input.stem}_slomo{args.multiplier}x.mp4"

    print(f"\nOutput: {args.output}")
    print()

    # Process video
    try:
        success = process_video(
            input_path=args.input,
            output_path=args.output,
            multiplier=args.multiplier,
            model=args.model,
            gpu_id=args.gpu,
            progress_callback=print_progress,
        )

        if success:
            print(f"\nSuccess! Output saved to: {args.output}")
        else:
            print("\nProcessing failed!")
            sys.exit(1)

    except KeyboardInterrupt:
        print("\n\nCancelled by user")
        sys.exit(1)
    except Exception as e:
        print(f"\nERROR: {e}")
        sys.exit(1)


def main():
    parser = argparse.ArgumentParser(
        description="RIFE Video Extender - Create slow-motion videos using AI frame interpolation"
    )
    parser.add_argument("input", type=Path, nargs="?", help="Input video file (optional, launches GUI if not provided)")
    parser.add_argument("output", type=Path, nargs="?", help="Output video file (default: input_slomo.mp4)")
    parser.add_argument(
        "-m", "--multiplier",
        type=int,
        choices=[2, 4, 8, 16],
        default=4,
        help="Slow-motion multiplier (default: 4)"
    )
    parser.add_argument(
        "--model",
        type=str,
        default="rife-v4.6",
        help="RIFE model to use (default: rife-v4.6)"
    )
    parser.add_argument(
        "--gpu",
        type=int,
        default=0,
        help="GPU device ID (default: 0)"
    )
    parser.add_argument(
        "--info",
        action="store_true",
        help="Just show video info, don't process"
    )
    parser.add_argument(
        "--cli",
        action="store_true",
        help="Force CLI mode (no GUI)"
    )

    args = parser.parse_args()

    # If no input provided, launch GUI
    if args.input is None:
        from gui import run_gui
        run_gui()
        return

    # If CLI flag or --info, use CLI mode
    if args.cli or args.info:
        run_cli(args)
        return

    # Otherwise, launch GUI (could preload file in future)
    from gui import run_gui
    run_gui()


if __name__ == "__main__":
    main()
