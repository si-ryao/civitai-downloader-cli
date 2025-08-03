"""Configuration management for Civitai Downloader CLI."""

import os
from pathlib import Path
from typing import Dict, List


def _load_default_output_dir() -> str:
    """Load default output directory from external config file.
    
    Returns:
        Default output directory path. Falls back to './downloads' if config file not found.
    """
    config_file = Path("default_output_dir.txt")
    if config_file.exists():
        try:
            with open(config_file, 'r', encoding='utf-8') as f:
                path = f.read().strip()
                if path:
                    return path
        except Exception:
            pass  # Fall back to default if file read fails
    
    return "./downloads"


class DownloadConfig:
    """Configuration class for download settings."""

    def __init__(
        self,
        api_key: str | None = None,
        is_test: bool = False,
        production_root: str | None = None,
        test_root: str = "./test_downloads",
        max_user_images: int = 1000,
    ):
        self.api_key = api_key or os.getenv("CIVITAI_API_KEY")
        self.is_test = is_test
        self.production_root = production_root or _load_default_output_dir()
        self.test_root = test_root
        self.max_user_images = max_user_images

        # タグマッピング（完全一致を優先）
        self.tag_mappings: Dict[str, List[str]] = {
            "CONCEPT": ["concept", "concepts", "technique"],
            "CHARACTER": ["character", "characters", "person", "celebrity"],
            "STYLE": ["style", "styles", "art style", "artist"],
            "POSE": ["pose", "poses", "position", "posing"],
            "CLOTHING": ["clothing", "outfit", "clothes", "dress"],
            "OBJECT": ["object", "objects", "item", "tool"],
            "BACKGROUND": ["background", "scene", "location", "environment"],
            "ANIMAL": ["animal", "animals", "creature"],
            "VEHICLE": ["vehicle", "car", "airplane", "ship"],
        }

        # User-Agent for API requests
        self.user_agent = (
            "Civitai-DL/0.1.0 (+https://github.com/civitai-downloader/cli)"
        )

        # Rate limiting settings (requests per second)
        self.model_api_rate = 0.5
        self.image_api_rate = 2.0

        # Request timeout settings
        self.request_timeout = 30
        self.max_retries = 5

    @property
    def root_dir(self) -> Path:
        """Get the appropriate root directory."""
        return Path(self.test_root if self.is_test else self.production_root)

    @property
    def headers(self) -> Dict[str, str]:
        """Get HTTP headers for API requests."""
        headers = {
            "User-Agent": self.user_agent,
        }
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        return headers

    def validate(self) -> None:
        """Validate configuration."""
        if not self.api_key:
            raise ValueError(
                "Civitai API key is required. Set CIVITAI_API_KEY environment variable or pass --token option."
            )

        # Create root directory if it doesn't exist
        self.root_dir.mkdir(parents=True, exist_ok=True)
