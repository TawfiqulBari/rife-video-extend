"""
RunPod API client for CogVideoX video continuation.

Handles API authentication, async job submission, polling, and response downloading.
"""

import base64
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Optional, Callable

import runpod
import requests

from config import COGVIDEO_DEFAULTS


class RunPodAPIError(Exception):
    """Base exception for RunPod API errors"""
    pass


class AuthenticationError(RunPodAPIError):
    """Invalid API key"""
    pass


class EndpointNotFoundError(RunPodAPIError):
    """Invalid endpoint ID"""
    pass


class JobTimeoutError(RunPodAPIError):
    """Job timed out"""
    pass


class JobFailedError(RunPodAPIError):
    """Job failed on server"""
    pass


@dataclass
class ContinuationConfig:
    """Configuration for video continuation request"""
    prompt: str = ""
    negative_prompt: str = "blurry, low quality, distorted, inconsistent"
    num_frames: int = COGVIDEO_DEFAULTS["num_frames"]
    num_inference_steps: int = COGVIDEO_DEFAULTS["num_inference_steps"]
    guidance_scale: float = COGVIDEO_DEFAULTS["guidance_scale"]


@dataclass
class ContinuationResult:
    """Result from video continuation"""
    success: bool
    video_path: Optional[Path] = None
    error_message: Optional[str] = None
    generation_time: float = 0.0


class RunPodCogVideoClient:
    """Client for CogVideoX on RunPod serverless"""

    def __init__(
        self,
        api_key: str,
        endpoint_id: str,
        timeout: int = 300  # 5 minutes default timeout
    ):
        self.api_key = api_key
        self.endpoint_id = endpoint_id
        self.timeout = timeout
        self._endpoint = None

    def validate_credentials(self) -> tuple:
        """
        Validate API key and endpoint ID are set and valid.
        Returns (success: bool, message: str)
        """
        if not self.api_key:
            return False, "RunPod API key is not set"
        if not self.endpoint_id:
            return False, "RunPod endpoint ID is not set"

        # Set the API key
        runpod.api_key = self.api_key

        # Try to create endpoint
        try:
            self._endpoint = runpod.Endpoint(self.endpoint_id)
            return True, "Credentials validated"
        except Exception as e:
            return False, f"Failed to connect to endpoint: {str(e)}"

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
        start_time = time.time()

        # Validate credentials
        valid, message = self.validate_credentials()
        if not valid:
            return ContinuationResult(
                success=False,
                error_message=message
            )

        # Encode image to base64
        if progress_callback:
            progress_callback("Encoding image...", 0.05)

        try:
            image_b64 = self._encode_image_base64(conditioning_image)
        except Exception as e:
            return ContinuationResult(
                success=False,
                error_message=f"Failed to encode image: {str(e)}"
            )

        # Prepare request payload
        payload = {
            "input": {
                "image": image_b64,
                "prompt": config.prompt,
                "negative_prompt": config.negative_prompt,
                "num_frames": config.num_frames,
                "num_inference_steps": config.num_inference_steps,
                "guidance_scale": config.guidance_scale,
            }
        }

        # Submit job
        if progress_callback:
            progress_callback("Submitting to RunPod...", 0.10)

        try:
            job = self._endpoint.run(payload["input"])
        except Exception as e:
            return ContinuationResult(
                success=False,
                error_message=f"Failed to submit job: {str(e)}"
            )

        # Poll for completion
        try:
            result = self._poll_job_status(job, progress_callback)
        except JobTimeoutError:
            return ContinuationResult(
                success=False,
                error_message=f"Job timed out after {self.timeout} seconds"
            )
        except JobFailedError as e:
            return ContinuationResult(
                success=False,
                error_message=str(e)
            )

        # Download/save result
        if progress_callback:
            progress_callback("Downloading result...", 0.90)

        try:
            self._save_video_result(result, output_path)
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

    def _encode_image_base64(self, image_path: Path) -> str:
        """Encode image file to base64 string"""
        with open(image_path, "rb") as f:
            return base64.b64encode(f.read()).decode("utf-8")

    def _poll_job_status(
        self,
        job,
        progress_callback: Optional[Callable[[str, float], None]] = None
    ) -> dict:
        """Poll job status until completion or timeout"""
        poll_interval = 2  # seconds
        elapsed = 0
        last_status = ""

        while elapsed < self.timeout:
            status = job.status()

            if status == "COMPLETED":
                return job.output()
            elif status == "FAILED":
                error = job.output()
                error_msg = error.get("error", "Unknown error") if isinstance(error, dict) else str(error)
                raise JobFailedError(f"Job failed: {error_msg}")
            elif status == "CANCELLED":
                raise JobFailedError("Job was cancelled")

            # Update progress
            if progress_callback and status != last_status:
                # Estimate progress based on elapsed time (generation typically takes 30-120s)
                estimated_progress = min(0.85, 0.15 + (elapsed / 120) * 0.70)
                progress_callback(f"Generating ({status})...", estimated_progress)
                last_status = status

            time.sleep(poll_interval)
            elapsed += poll_interval

        raise JobTimeoutError()

    def _save_video_result(self, result: dict, output_path: Path):
        """Save video from API response to file"""
        # Handle different response formats
        if isinstance(result, dict):
            # Check for video URL
            if "video_url" in result:
                self._download_from_url(result["video_url"], output_path)
            # Check for base64 video
            elif "video" in result:
                video_bytes = base64.b64decode(result["video"])
                with open(output_path, "wb") as f:
                    f.write(video_bytes)
            # Check for base64 output
            elif "output" in result:
                if isinstance(result["output"], str):
                    video_bytes = base64.b64decode(result["output"])
                    with open(output_path, "wb") as f:
                        f.write(video_bytes)
                elif isinstance(result["output"], dict) and "video" in result["output"]:
                    video_bytes = base64.b64decode(result["output"]["video"])
                    with open(output_path, "wb") as f:
                        f.write(video_bytes)
                else:
                    raise ValueError(f"Unexpected output format: {type(result['output'])}")
            else:
                raise ValueError(f"Unknown response format. Keys: {result.keys()}")
        elif isinstance(result, str):
            # Assume base64 encoded video
            video_bytes = base64.b64decode(result)
            with open(output_path, "wb") as f:
                f.write(video_bytes)
        else:
            raise ValueError(f"Unexpected result type: {type(result)}")

    def _download_from_url(self, url: str, output_path: Path):
        """Download video from URL"""
        response = requests.get(url, timeout=60)
        response.raise_for_status()
        with open(output_path, "wb") as f:
            f.write(response.content)
