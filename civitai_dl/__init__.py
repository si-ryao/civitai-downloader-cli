"""Civitai Downloader CLI - AI Model Downloader with Tag-based Organization."""

__version__ = "0.1.0"
__author__ = "Civitai Downloader CLI Team"
__description__ = (
    "CLI tool for downloading Civitai models and images with tag-based organization"
)

from .cli import main

__all__ = ["main"]
