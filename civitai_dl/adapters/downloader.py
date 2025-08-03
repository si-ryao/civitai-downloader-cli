"""File downloader with progress tracking and integrity verification."""

import hashlib
import time
from pathlib import Path
from typing import Optional

import requests
from tqdm import tqdm

from ..config import DownloadConfig


class DownloadError(Exception):
    """ダウンロード関連のエラー."""

    pass


class FileDownloader:
    """ファイルダウンローダー with プログレスバー and SHA256検証."""

    def __init__(self, config: DownloadConfig, skip_existing: bool = False):
        self.config = config
        self.skip_existing = skip_existing
        self.session = requests.Session()
        self.session.headers.update(config.headers)

        # Rate limiting for downloads
        self._last_download_time = 0.0
        self._min_interval = 1.0 / config.image_api_rate  # seconds between downloads
        
        # Statistics
        self.skipped_count = 0
        self.downloaded_count = 0

    def _rate_limit(self) -> None:
        """Rate limiting for downloads."""
        current_time = time.time()
        time_since_last = current_time - self._last_download_time

        if time_since_last < self._min_interval:
            sleep_time = self._min_interval - time_since_last
            time.sleep(sleep_time)

        self._last_download_time = time.time()

    def download_file(
        self,
        url: str,
        filepath: Path,
        expected_sha256: Optional[str] = None,
        description: Optional[str] = None,
    ) -> bool:
        """ファイルをダウンロードし、オプションでSHA256検証を行う."""
        # 既存ファイルのチェック
        if filepath.exists():
            if expected_sha256:
                # SHA256がある場合は検証
                if self._verify_sha256(filepath, expected_sha256):
                    print(f"✓ File already exists and verified: {filepath.name}")
                    self.skipped_count += 1
                    return True
                else:
                    print(
                        f"⚠ File exists but SHA256 mismatch, re-downloading: {filepath.name}"
                    )
            elif self.skip_existing:
                # skip_existingが有効で、SHA256がない場合（主に画像）
                # ファイルサイズが1KB以上あれば有効とみなす
                if filepath.stat().st_size > 1024:
                    print(f"⏭️  Skipping existing file: {filepath.name}")
                    self.skipped_count += 1
                    return True
                else:
                    print(f"⚠ File exists but too small, re-downloading: {filepath.name}")

        # ディレクトリを作成
        filepath.parent.mkdir(parents=True, exist_ok=True)

        # Rate limiting
        self._rate_limit()

        try:
            # プログレス表示用の説明文
            desc = description or f"Downloading {filepath.name}"

            response = self.session.get(
                url, stream=True, timeout=self.config.request_timeout
            )
            response.raise_for_status()

            # Content-Lengthから総サイズを取得
            total_size = int(response.headers.get("content-length", 0))

            # プログレスバー付きダウンロード
            with open(filepath, "wb") as f:
                with tqdm(
                    total=total_size, unit="B", unit_scale=True, desc=desc
                ) as pbar:
                    for chunk in response.iter_content(chunk_size=8192):
                        if chunk:
                            f.write(chunk)
                            pbar.update(len(chunk))

            # SHA256検証
            if expected_sha256:
                if self._verify_sha256(filepath, expected_sha256):
                    print(f"✓ Download completed and verified: {filepath.name}")
                else:
                    filepath.unlink()  # 検証失敗時はファイルを削除
                    raise DownloadError(
                        f"SHA256 verification failed for {filepath.name}"
                    )
            else:
                print(f"✓ Download completed: {filepath.name}")

            self.downloaded_count += 1
            return True

        except requests.exceptions.RequestException as e:
            if filepath.exists():
                filepath.unlink()  # エラー時はファイルを削除
            raise DownloadError(f"Download failed for {url}: {e}")
        except Exception as e:
            if filepath.exists():
                filepath.unlink()  # エラー時はファイルを削除
            raise DownloadError(f"Unexpected error downloading {url}: {e}")

    def get_stats(self) -> dict:
        """ダウンロード統計を取得."""
        return {
            "downloaded": self.downloaded_count,
            "skipped": self.skipped_count,
            "total": self.downloaded_count + self.skipped_count
        }
        
    def reset_stats(self) -> None:
        """統計をリセット."""
        self.downloaded_count = 0
        self.skipped_count = 0

    def _verify_sha256(self, filepath: Path, expected_sha256: str) -> bool:
        """ファイルのSHA256ハッシュを検証."""
        if not filepath.exists():
            return False

        calculated_hash = hashlib.sha256()

        try:
            with open(filepath, "rb") as f:
                while True:
                    chunk = f.read(8192)
                    if not chunk:
                        break
                    calculated_hash.update(chunk)

            calculated = calculated_hash.hexdigest().upper()
            expected = expected_sha256.upper()

            return calculated == expected

        except Exception:
            return False

    def get_file_size_mb(self, filepath: Path) -> float:
        """ファイルサイズをMB単位で取得."""
        if not filepath.exists():
            return 0.0
        return filepath.stat().st_size / (1024 * 1024)
