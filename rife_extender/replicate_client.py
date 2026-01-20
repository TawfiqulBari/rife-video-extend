"""
Replicate API client for CogVideoX video continuation.

Handles API authentication, model execution, and response downloading.
"""

import base64
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Optional, Callable

import replicate
import requests

from config import WAN_VIDEO_DEFAULTS, REPLICATE_VIDEO_MODEL


class ReplicateAPIError(Exception):
    """Base exception for Replicate API errors"""
    pass


class AuthenticationError(ReplicateAPIError):
    """Invalid API token"""
    pass


class ModelNotFoundError(ReplicateAPIError):
    """Model not found"""
    pass


class PredictionFailedError(ReplicateAPIError):
    """Prediction failed on server"""
    pass


@dataclass
class ContinuationConfig:
    """Configuration for video continuation request (Wan 2.2 I2V Fast)"""
    prompt: str = ""
    num_frames: int = WAN_VIDEO_DEFAULTS["num_frames"]
    frames_per_second: int = WAN_VIDEO_DEFAULTS["frames_per_second"]
    resolution: str = WAN_VIDEO_DEFAULTS["resolution"]  # "480p" or "720p"
    disable_safety_checker: bool = WAN_VIDEO_DEFAULTS["disable_safety_checker"]
    seed: Optional[int] = None


@dataclass
class ContinuationResult:
    """Result from video continuation"""
    success: bool
    video_path: Optional[Path] = None
    error_message: Optional[str] = None
    generation_time: float = 0.0


class ReplicateCogVideoClient:
    """Client for Wan 2.2 I2V Fast on Replicate"""

    def __init__(
        self,
        api_token: str,
        model: str = REPLICATE_VIDEO_MODEL,
    ):
        self.api_token = api_token
        self.model = model

    def validate_credentials(self) -> tuple:
        """
        Validate API token is set and valid.
        Returns (success: bool, message: str)
        """
        if not self.api_token:
            return False, "Replicate API token is not set"

        # Set the API token for the replicate client
        client = replicate.Client(api_token=self.api_token)

        # Try a lightweight API call to validate
        try:
            # Get account info to validate token
            client.models.get("replicate/hello-world")
            return True, "Credentials validated"
        except replicate.exceptions.ReplicateError as e:
            if "401" in str(e) or "Unauthorized" in str(e):
                return False, "Invalid API token"
            # Other errors might be OK (model not found, etc.)
            return True, "Credentials validated"
        except Exception as e:
            return False, f"Failed to validate credentials: {str(e)}"

    def generate_continuation(
        self,
        conditioning_image: Path,
        config: ContinuationConfig,
        output_path: Path,
        progress_callback: Optional[Callable[[str, float], None]] = None
    ) -> ContinuationResult:
        """
        Generate video continuation from conditioning image.

        Args:
            conditioning_image: Path to last frame PNG
            config: Generation configuration
            output_path: Path to save output video
            progress_callback: Optional callback(stage, progress 0-1)

        Returns:
            ContinuationResult with video path or error
        """
        import os
        start_time = time.time()

        # Set the API token as environment variable for replicate.run()
        os.environ["REPLICATE_API_TOKEN"] = self.api_token

        # Open image file directly (more efficient than base64)
        if progress_callback:
            progress_callback("Preparing image...", 0.05)

        try:
            image_file = open(conditioning_image, "rb")
        except Exception as e:
            return ContinuationResult(
                success=False,
                error_message=f"Failed to open image: {str(e)}"
            )

        # Prepare input parameters for Wan 2.2 I2V Fast
        input_params = {
            "image": image_file,
            "prompt": config.prompt if config.prompt else "Continuous natural motion",
            "num_frames": config.num_frames,
            "frames_per_second": config.frames_per_second,
            "resolution": config.resolution,
            "disable_safety_checker": config.disable_safety_checker,
        }

        if config.seed is not None:
            input_params["seed"] = config.seed

        # Run the model
        if progress_callback:
            progress_callback("Generating video on Replicate...", 0.15)

        try:
            # Use replicate.run() which handles everything automatically
            # This blocks until completion
            output = replicate.run(
                self.model,
                input=input_params
            )
        except Exception as e:
            image_file.close()
            return ContinuationResult(
                success=False,
                error_message=f"Failed to run model: {str(e)}"
            )
        finally:
            image_file.close()

        # Process output - can be URL string or FileOutput object
        if progress_callback:
            progress_callback("Downloading result...", 0.90)

        try:
            self._save_output(output, output_path)
        except Exception as e:
            return ContinuationResult(
                success=False,
                error_message=f"Failed to save video: {str(e)}"
            )

        generation_time = time.time() - start_time

        if progress_callback:
            progress_callback("Complete!", 1.0)

        return ContinuationResult(
            success=True,
            video_path=output_path,
            generation_time=generation_time
        )

    def _save_output(self, output, output_path: Path):
        """Save output from replicate.run() to file"""
        output_path.parent.mkdir(parents=True, exist_ok=True)

        # Output can be various types
        if isinstance(output, str):
            # It's a URL - download it
            self._download_video(output, output_path)
        elif isinstance(output, list) and len(output) > 0:
            # List of outputs - take first one
            first = output[0]
            if isinstance(first, str):
                self._download_video(first, output_path)
            elif hasattr(first, 'read'):
                # FileOutput object
                with open(output_path, 'wb') as f:
                    f.write(first.read())
            else:
                raise ValueError(f"Unexpected output item type: {type(first)}")
        elif hasattr(output, 'read'):
            # FileOutput object
            with open(output_path, 'wb') as f:
                f.write(output.read())
        else:
            raise ValueError(f"Unexpected output type: {type(output)}")

    def _encode_image_data_uri(self, image_path: Path) -> str:
        """Encode image file to data URI"""
        with open(image_path, "rb") as f:
            image_data = f.read()

        # Determine MIME type
        suffix = image_path.suffix.lower()
        mime_types = {
            ".png": "image/png",
            ".jpg": "image/jpeg",
            ".jpeg": "image/jpeg",
            ".webp": "image/webp",
        }
        mime_type = mime_types.get(suffix, "image/png")

        b64_data = base64.b64encode(image_data).decode("utf-8")
        return f"data:{mime_type};base64,{b64_data}"

    def _poll_prediction(
        self,
        client: replicate.Client,
        prediction,
        progress_callback: Optional[Callable[[str, float], None]] = None
    ) -> str:
        """Poll prediction status until completion"""
        poll_interval = 2  # seconds
        start_time = time.time()

        while True:
            # Reload prediction to get latest status
            prediction.reload()
            status = prediction.status

            if status == "succeeded":
                output = prediction.output
                # Output is typically a URL or list of URLs
                if isinstance(output, list):
                    return output[0]
                elif isinstance(output, str):
                    return output
                else:
                    raise PredictionFailedError(f"Unexpected output format: {type(output)}")

            elif status == "failed":
                error = prediction.error or "Unknown error"
                raise PredictionFailedError(f"Prediction failed: {error}")

            elif status == "canceled":
                raise PredictionFailedError("Prediction was canceled")

            # Update progress (estimate based on typical ~9 minute runtime)
            if progress_callback:
                elapsed = time.time() - start_time
                # Estimate progress: ramp from 15% to 85% over ~10 minutes
                estimated_progress = min(0.85, 0.15 + (elapsed / 600) * 0.70)
                progress_callback(f"Generating video ({status})...", estimated_progress)

            time.sleep(poll_interval)

    def _download_video(self, url: str, output_path: Path):
        """Download video from URL"""
        output_path.parent.mkdir(parents=True, exist_ok=True)

        response = requests.get(url, timeout=120, stream=True)
        response.raise_for_status()

        with open(output_path, "wb") as f:
            for chunk in response.iter_content(chunk_size=8192):
                f.write(chunk)
