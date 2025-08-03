"""Civitai API client for fetching model and image data."""

import time
from typing import Any, Dict, List, Optional

import requests

from ..config import DownloadConfig


class CivitaiApiError(Exception):
    """Civitai API関連のエラー."""

    def __init__(self, message: str, status_code: Optional[int] = None):
        super().__init__(message)
        self.status_code = status_code


class CivitaiApiClient:
    """Civitai API クライアント."""

    def __init__(self, config: DownloadConfig):
        self.config = config
        self.session = requests.Session()
        
        # Ensure UTF-8 encoding for HTTP responses (fixes cp932 environment issues)
        self.session.headers.update(config.headers)
        self.session.headers.update({
            'Accept-Charset': 'utf-8',
        })
        
        self.base_url = "https://civitai.com/api/v1"

        # Rate limiting
        self._last_request_time = 0.0
        self._min_interval = 1.0 / config.model_api_rate  # seconds between requests

    def _rate_limit(self) -> None:
        """Rate limiting for API requests."""
        current_time = time.time()
        time_since_last = current_time - self._last_request_time

        if time_since_last < self._min_interval:
            sleep_time = self._min_interval - time_since_last
            time.sleep(sleep_time)

        self._last_request_time = time.time()

    def _request(
        self, method: str, endpoint: str, params: Optional[Dict] = None
    ) -> Dict[str, Any]:
        """Make HTTP request with error handling and rate limiting."""
        self._rate_limit()

        url = f"{self.base_url}/{endpoint.lstrip('/')}"

        try:
            response = self.session.request(
                method=method,
                url=url,
                params=params,
                timeout=self.config.request_timeout,
            )

            # Check for rate limiting
            if response.status_code == 429:
                retry_after = int(response.headers.get("Retry-After", 60))
                raise CivitaiApiError(
                    f"Rate limited. Retry after {retry_after} seconds", status_code=429
                )

            # Check for other HTTP errors
            if response.status_code >= 400:
                raise CivitaiApiError(
                    f"HTTP {response.status_code}: {response.text}",
                    status_code=response.status_code,
                )

            # Ensure UTF-8 encoding for JSON response (fixes cp932 environment issues)
            response.encoding = 'utf-8'
            return response.json()

        except requests.exceptions.RequestException as e:
            raise CivitaiApiError(f"Request failed: {e}")

    def get_user_models(
        self, username: str, limit: int = 20, page: int = 1
    ) -> Dict[str, Any]:
        """指定ユーザーのモデル一覧を取得."""
        params = {
            "username": username,
            "limit": limit,
            "page": page,
            "nsfw": "true",  # NSFWコンテンツも含める
        }

        return self._request("GET", "/models", params)

    def get_all_user_models(self, username: str) -> List[Dict[str, Any]]:
        """指定ユーザーの全モデルを取得（ページネーション対応）."""
        all_models = []
        page = 1

        while True:
            response = self.get_user_models(username, limit=100, page=page)
            models = response.get("items", [])

            if not models:
                break

            all_models.extend(models)

            # Check if there are more pages
            metadata = response.get("metadata", {})
            current_page = metadata.get("currentPage", page)
            total_pages = metadata.get("totalPages", current_page)

            if current_page >= total_pages:
                break

            page += 1

        return all_models

    def get_model_details(self, model_id: int) -> Dict[str, Any]:
        """指定モデルの詳細情報を取得."""
        return self._request("GET", f"/models/{model_id}")

    def get_model_version_details(self, version_id: int) -> Dict[str, Any]:
        """指定バージョンの詳細情報を取得."""
        return self._request("GET", f"/model-versions/{version_id}")

    def get_images_for_model(
        self, model_id: int, limit: int = 20, page: int = 1
    ) -> Dict[str, Any]:
        """指定モデルの画像一覧を取得."""
        params = {"modelId": model_id, "limit": limit, "page": page, "nsfw": "true"}

        return self._request("GET", "/images", params)

    def get_all_images_for_model(self, model_id: int) -> List[Dict[str, Any]]:
        """指定モデルの全画像を取得（ページネーション対応）."""
        all_images = []
        page = 1

        while True:
            response = self.get_images_for_model(model_id, limit=100, page=page)
            images = response.get("items", [])

            if not images:
                break

            all_images.extend(images)

            # Check if there are more pages
            metadata = response.get("metadata", {})
            current_page = metadata.get("currentPage", page)
            total_pages = metadata.get("totalPages", current_page)

            if current_page >= total_pages:
                break

            page += 1

        return all_images

    def get_user_images(
        self, username: str, limit: int = 20, page: int = 1
    ) -> Dict[str, Any]:
        """指定ユーザーの投稿画像一覧を取得."""
        params = {"username": username, "limit": limit, "page": page, "nsfw": "true"}

        return self._request("GET", "/images", params)

    def get_all_user_images(self, username: str) -> List[Dict[str, Any]]:
        """指定ユーザーの全投稿画像を取得（ページネーション対応）."""
        all_images = []
        page = 1

        while True:
            response = self.get_user_images(username, limit=100, page=page)
            images = response.get("items", [])

            if not images:
                break

            all_images.extend(images)

            # Check if there are more pages
            metadata = response.get("metadata", {})
            current_page = metadata.get("currentPage", page)
            total_pages = metadata.get("totalPages", current_page)

            if current_page >= total_pages:
                break

            page += 1

        return all_images
