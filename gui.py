"""
RIFE Video Extender - GUI Application
"""
import customtkinter as ctk
from tkinter import filedialog
from pathlib import Path
import threading
from typing import Optional

from config import (
    SUPPORTED_FORMATS, check_dependencies, ensure_directories,
    get_runpod_api_key, get_runpod_endpoint_id, save_runpod_config,
    check_continuation_dependencies
)
from processor import get_video_info, process_video, VideoInfo


class RIFEExtenderApp(ctk.CTk):
    def __init__(self):
        super().__init__()

        # Window setup
        self.title("RIFE Video Extender")
        self.geometry("500x750")
        self.minsize(450, 700)

        # Set theme
        ctk.set_appearance_mode("dark")
        ctk.set_default_color_theme("blue")

        # Common state
        self.input_path: Optional[Path] = None
        self.video_info: Optional[VideoInfo] = None
        self.is_processing = False
        self.cancel_requested = False

        # Slow-motion state
        self.multiplier = ctk.IntVar(value=4)

        # Continuation state
        self.continuation_duration = ctk.DoubleVar(value=2.0)
        self.concat_original = ctk.BooleanVar(value=True)
        self.save_credentials = ctk.BooleanVar(value=False)

        # Build UI
        self._create_widgets()
        self._check_dependencies()
        self._load_saved_credentials()

    def _create_widgets(self):
        # Main container with padding
        self.main_frame = ctk.CTkFrame(self, fg_color="transparent")
        self.main_frame.pack(fill="both", expand=True, padx=20, pady=20)

        # Title
        self.title_label = ctk.CTkLabel(
            self.main_frame,
            text="RIFE Video Extender",
            font=ctk.CTkFont(size=24, weight="bold")
        )
        self.title_label.pack(pady=(0, 5))

        self.subtitle_label = ctk.CTkLabel(
            self.main_frame,
            text="AI-powered video enhancement",
            font=ctk.CTkFont(size=12),
            text_color="gray"
        )
        self.subtitle_label.pack(pady=(0, 15))

        # File selection area
        self.file_frame = ctk.CTkFrame(self.main_frame, height=100)
        self.file_frame.pack(fill="x", pady=(0, 10))
        self.file_frame.pack_propagate(False)

        self.file_button = ctk.CTkButton(
            self.file_frame,
            text="Click to Select Video\nor Drag & Drop",
            font=ctk.CTkFont(size=14),
            height=80,
            command=self._select_file,
            fg_color="transparent",
            border_width=2,
            border_color=("gray50", "gray30"),
            hover_color=("gray70", "gray25")
        )
        self.file_button.pack(fill="both", expand=True, padx=10, pady=10)

        # Video info display
        self.info_frame = ctk.CTkFrame(self.main_frame)
        self.info_frame.pack(fill="x", pady=(0, 10))

        self.info_label = ctk.CTkLabel(
            self.info_frame,
            text="No video selected",
            font=ctk.CTkFont(size=12),
            text_color="gray"
        )
        self.info_label.pack(pady=10)

        # Mode selection tabs
        self.mode_tabview = ctk.CTkTabview(self.main_frame, height=280)
        self.mode_tabview.pack(fill="x", pady=(0, 10))

        # Create tabs
        self.slowmo_tab = self.mode_tabview.add("Slow-Motion")
        self.continue_tab = self.mode_tabview.add("AI Continuation")

        # Build tab contents
        self._create_slowmo_controls(self.slowmo_tab)
        self._create_continuation_controls(self.continue_tab)

        # Progress section
        self.progress_frame = ctk.CTkFrame(self.main_frame)
        self.progress_frame.pack(fill="x", pady=(0, 10))

        self.progress_bar = ctk.CTkProgressBar(self.progress_frame)
        self.progress_bar.pack(fill="x", padx=20, pady=(15, 8))
        self.progress_bar.set(0)

        self.status_label = ctk.CTkLabel(
            self.progress_frame,
            text="Ready",
            font=ctk.CTkFont(size=12)
        )
        self.status_label.pack(pady=(0, 10))

        # Action button
        self.action_button = ctk.CTkButton(
            self.main_frame,
            text="Start Processing",
            font=ctk.CTkFont(size=16, weight="bold"),
            height=50,
            command=self._start_processing,
            state="disabled"
        )
        self.action_button.pack(fill="x", pady=(0, 10))

        # Dependencies warning (hidden by default)
        self.warning_label = ctk.CTkLabel(
            self.main_frame,
            text="",
            font=ctk.CTkFont(size=11),
            text_color="red",
            wraplength=450
        )
        self.warning_label.pack()

        # Enable drag and drop using tkinter dnd
        self._setup_drag_drop()

    def _create_slowmo_controls(self, parent):
        """Create slow-motion specific controls"""
        # Multiplier selection
        self.mult_label = ctk.CTkLabel(
            parent,
            text="Slow-Motion Multiplier:",
            font=ctk.CTkFont(size=14, weight="bold")
        )
        self.mult_label.pack(pady=(10, 10))

        self.mult_buttons_frame = ctk.CTkFrame(parent, fg_color="transparent")
        self.mult_buttons_frame.pack(pady=(0, 10))

        self.mult_buttons = {}
        for mult in [2, 4, 8]:
            btn = ctk.CTkRadioButton(
                self.mult_buttons_frame,
                text=f"{mult}x",
                variable=self.multiplier,
                value=mult,
                font=ctk.CTkFont(size=14),
                command=self._update_output_preview
            )
            btn.pack(side="left", padx=20)
            self.mult_buttons[mult] = btn

        # Output preview
        self.slowmo_preview_label = ctk.CTkLabel(
            parent,
            text="",
            font=ctk.CTkFont(size=11),
            text_color="gray"
        )
        self.slowmo_preview_label.pack(pady=(0, 10))

    def _create_continuation_controls(self, parent):
        """Create video continuation specific controls"""
        # API Configuration
        api_frame = ctk.CTkFrame(parent, fg_color="transparent")
        api_frame.pack(fill="x", padx=5, pady=(5, 5))

        # API Key
        api_key_label = ctk.CTkLabel(api_frame, text="RunPod API Key:", font=ctk.CTkFont(size=12))
        api_key_label.grid(row=0, column=0, sticky="w", pady=(0, 5))

        self.api_key_entry = ctk.CTkEntry(api_frame, show="*", width=300)
        self.api_key_entry.grid(row=0, column=1, padx=(10, 0), pady=(0, 5))

        # Endpoint ID
        endpoint_label = ctk.CTkLabel(api_frame, text="Endpoint ID:", font=ctk.CTkFont(size=12))
        endpoint_label.grid(row=1, column=0, sticky="w", pady=(0, 5))

        self.endpoint_entry = ctk.CTkEntry(api_frame, width=300)
        self.endpoint_entry.grid(row=1, column=1, padx=(10, 0), pady=(0, 5))

        # Save credentials checkbox
        self.save_creds_check = ctk.CTkCheckBox(
            api_frame,
            text="Save credentials locally",
            variable=self.save_credentials,
            font=ctk.CTkFont(size=11)
        )
        self.save_creds_check.grid(row=2, column=1, sticky="w", padx=(10, 0), pady=(0, 5))

        # Prompt
        prompt_frame = ctk.CTkFrame(parent, fg_color="transparent")
        prompt_frame.pack(fill="x", padx=5, pady=(0, 5))

        prompt_label = ctk.CTkLabel(prompt_frame, text="Prompt (optional):", font=ctk.CTkFont(size=12))
        prompt_label.pack(anchor="w")

        self.prompt_textbox = ctk.CTkTextbox(prompt_frame, height=50)
        self.prompt_textbox.pack(fill="x", pady=(5, 0))

        # Options frame
        options_frame = ctk.CTkFrame(parent, fg_color="transparent")
        options_frame.pack(fill="x", padx=5, pady=(5, 5))

        # Duration selection
        duration_label = ctk.CTkLabel(options_frame, text="Duration:", font=ctk.CTkFont(size=12))
        duration_label.pack(side="left")

        self.duration_2s = ctk.CTkRadioButton(
            options_frame,
            text="~2s",
            variable=self.continuation_duration,
            value=2.0,
            font=ctk.CTkFont(size=12)
        )
        self.duration_2s.pack(side="left", padx=(10, 5))

        self.duration_4s = ctk.CTkRadioButton(
            options_frame,
            text="~4s",
            variable=self.continuation_duration,
            value=4.0,
            font=ctk.CTkFont(size=12)
        )
        self.duration_4s.pack(side="left", padx=(5, 20))

        # Concatenation checkbox
        self.concat_check = ctk.CTkCheckBox(
            options_frame,
            text="Append to original",
            variable=self.concat_original,
            font=ctk.CTkFont(size=12)
        )
        self.concat_check.pack(side="left")

    def _load_saved_credentials(self):
        """Load saved RunPod credentials if available"""
        api_key = get_runpod_api_key()
        endpoint_id = get_runpod_endpoint_id()

        if api_key:
            self.api_key_entry.insert(0, api_key)
        if endpoint_id:
            self.endpoint_entry.insert(0, endpoint_id)

    def _setup_drag_drop(self):
        """Setup drag and drop functionality"""
        # Placeholder for future tkinterdnd2 integration
        # The button already has command=self._select_file, so no extra binding needed
        self.drop_target_register = None

    def _check_dependencies(self):
        """Check if required binaries are present"""
        ensure_directories()
        missing = check_dependencies()
        if missing:
            self.warning_label.configure(
                text="Missing dependencies:\n" + "\n".join(missing)
            )
            self.action_button.configure(state="disabled")

    def _select_file(self):
        """Open file dialog to select video"""
        if self.is_processing:
            return

        filetypes = [
            ("Video files", " ".join(f"*{ext}" for ext in SUPPORTED_FORMATS)),
            ("All files", "*.*")
        ]

        filepath = filedialog.askopenfilename(
            title="Select Video File",
            filetypes=filetypes
        )

        if filepath:
            self._load_video(Path(filepath))

    def _load_video(self, path: Path):
        """Load video and display info"""
        try:
            self.video_info = get_video_info(path)
            self.input_path = path

            # Update file button
            self.file_button.configure(
                text=f"{path.name}",
                border_color=("green", "green")
            )

            # Update info display
            info_text = (
                f"Resolution: {self.video_info.resolution}  |  "
                f"FPS: {self.video_info.fps:.1f}  |  "
                f"Duration: {self.video_info.duration:.1f}s  |  "
                f"Frames: {self.video_info.frame_count}"
            )
            self.info_label.configure(text=info_text, text_color="white")

            # Update output preview
            self._update_output_preview()

            # Enable action button
            self.action_button.configure(state="normal")
            self.status_label.configure(text="Ready to process")

        except Exception as e:
            self.info_label.configure(
                text=f"Error loading video: {str(e)}",
                text_color="red"
            )
            self.action_button.configure(state="disabled")

    def _update_output_preview(self):
        """Update the output duration preview for slow-motion"""
        if self.video_info:
            mult = self.multiplier.get()
            output_duration = self.video_info.duration * mult
            output_frames = self.video_info.frame_count * mult

            mins = int(output_duration // 60)
            secs = output_duration % 60

            if mins > 0:
                duration_str = f"{mins}m {secs:.1f}s"
            else:
                duration_str = f"{secs:.1f}s"

            self.slowmo_preview_label.configure(
                text=f"Output: {duration_str} ({output_frames:,} frames)"
            )

    def _get_current_mode(self) -> str:
        """Get the currently selected mode tab"""
        return self.mode_tabview.get()

    def _start_processing(self):
        """Start or cancel video processing"""
        if self.is_processing:
            # Cancel requested
            self.cancel_requested = True
            self.action_button.configure(text="Cancelling...")
            self.status_label.configure(text="Cancelling...")
            return

        if not self.input_path:
            return

        current_mode = self._get_current_mode()

        if current_mode == "AI Continuation":
            self._start_continuation_processing()
        else:
            self._start_slowmo_processing()

    def _start_slowmo_processing(self):
        """Start slow-motion processing"""
        # Generate output path
        mult = self.multiplier.get()
        output_path = self.input_path.parent / f"{self.input_path.stem}_slomo{mult}x.mp4"

        # Ask for output location
        output_file = filedialog.asksaveasfilename(
            title="Save Output Video As",
            defaultextension=".mp4",
            initialfile=output_path.name,
            initialdir=str(output_path.parent),
            filetypes=[("MP4 Video", "*.mp4")]
        )

        if not output_file:
            return

        output_path = Path(output_file)

        # Start processing
        self.is_processing = True
        self.cancel_requested = False
        self.action_button.configure(text="Cancel", fg_color="red", hover_color="darkred")
        self.file_button.configure(state="disabled")
        for btn in self.mult_buttons.values():
            btn.configure(state="disabled")

        # Run in thread
        thread = threading.Thread(
            target=self._process_video_thread,
            args=(output_path,),
            daemon=True
        )
        thread.start()

    def _start_continuation_processing(self):
        """Start AI continuation processing"""
        # Validate credentials
        api_key = self.api_key_entry.get().strip()
        endpoint_id = self.endpoint_entry.get().strip()

        if not api_key:
            self.status_label.configure(text="Error: RunPod API key required", text_color="red")
            return
        if not endpoint_id:
            self.status_label.configure(text="Error: Endpoint ID required", text_color="red")
            return

        # Save credentials if requested
        if self.save_credentials.get():
            save_runpod_config(api_key, endpoint_id)

        # Generate output path
        suffix = "_extended" if self.concat_original.get() else "_continued"
        output_path = self.input_path.parent / f"{self.input_path.stem}{suffix}.mp4"

        # Ask for output location
        output_file = filedialog.asksaveasfilename(
            title="Save Output Video As",
            defaultextension=".mp4",
            initialfile=output_path.name,
            initialdir=str(output_path.parent),
            filetypes=[("MP4 Video", "*.mp4")]
        )

        if not output_file:
            return

        output_path = Path(output_file)

        # Get options
        prompt = self.prompt_textbox.get("1.0", "end-1c").strip()
        duration = self.continuation_duration.get()
        concat = self.concat_original.get()

        # Start processing
        self.is_processing = True
        self.cancel_requested = False
        self.action_button.configure(text="Cancel", fg_color="red", hover_color="darkred")
        self.file_button.configure(state="disabled")

        # Run in thread
        thread = threading.Thread(
            target=self._process_continuation_thread,
            args=(output_path, api_key, endpoint_id, prompt, duration, concat),
            daemon=True
        )
        thread.start()

    def _process_video_thread(self, output_path: Path):
        """Process video in background thread"""
        try:
            def progress_callback(stage: str, progress: float):
                if self.cancel_requested:
                    raise InterruptedError("Cancelled by user")
                self.after(0, lambda: self._update_progress(stage, progress))

            success = process_video(
                input_path=self.input_path,
                output_path=output_path,
                multiplier=self.multiplier.get(),
                progress_callback=progress_callback
            )

            if success:
                self.after(0, lambda: self._processing_complete(output_path))
            else:
                self.after(0, lambda: self._processing_failed("Processing failed"))

        except InterruptedError:
            self.after(0, lambda: self._processing_cancelled())
        except Exception as e:
            self.after(0, lambda: self._processing_failed(str(e)))

    def _process_continuation_thread(
        self,
        output_path: Path,
        api_key: str,
        endpoint_id: str,
        prompt: str,
        duration: float,
        concat: bool
    ):
        """Process video continuation in background thread"""
        from continuation_processor import continue_video, ContinuationOptions

        try:
            def progress_callback(stage: str, progress: float):
                if self.cancel_requested:
                    raise InterruptedError("Cancelled by user")
                self.after(0, lambda: self._update_progress(stage, progress))

            options = ContinuationOptions(
                prompt=prompt,
                duration_seconds=duration,
                concatenate_original=concat,
            )

            success = continue_video(
                input_path=self.input_path,
                output_path=output_path,
                api_key=api_key,
                endpoint_id=endpoint_id,
                options=options,
                progress_callback=progress_callback
            )

            if success:
                self.after(0, lambda: self._processing_complete(output_path))
            else:
                self.after(0, lambda: self._processing_failed("Continuation failed"))

        except InterruptedError:
            self.after(0, lambda: self._processing_cancelled())
        except Exception as e:
            self.after(0, lambda: self._processing_failed(str(e)))

    def _update_progress(self, stage: str, progress: float):
        """Update progress bar and status"""
        self.progress_bar.set(progress)
        self.status_label.configure(text=stage)

    def _processing_complete(self, output_path: Path):
        """Handle successful completion"""
        self.is_processing = False
        self.progress_bar.set(1.0)
        self.status_label.configure(
            text=f"Complete! Saved to: {output_path.name}",
            text_color="green"
        )
        self._reset_ui()

    def _processing_failed(self, error: str):
        """Handle processing failure"""
        self.is_processing = False
        self.status_label.configure(
            text=f"Error: {error}",
            text_color="red"
        )
        self._reset_ui()

    def _processing_cancelled(self):
        """Handle cancellation"""
        self.is_processing = False
        self.progress_bar.set(0)
        self.status_label.configure(text="Cancelled")
        self._reset_ui()

    def _reset_ui(self):
        """Reset UI after processing"""
        self.action_button.configure(
            text="Start Processing",
            fg_color=["#3B8ED0", "#1F6AA5"],
            hover_color=["#36719F", "#144870"]
        )
        self.file_button.configure(state="normal")
        for btn in self.mult_buttons.values():
            btn.configure(state="normal")


def run_gui():
    """Run the GUI application"""
    app = RIFEExtenderApp()
    app.mainloop()


if __name__ == "__main__":
    run_gui()
