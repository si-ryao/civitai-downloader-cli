"""File system utilities for Civitai Downloader CLI."""

import re
from pathlib import Path
from typing import Dict, List


def sanitize_filename(name: str) -> str:
    """ファイル名から危険な文字を除去."""
    if not name:
        return "unnamed"

    # Windows/Unix両対応の禁止文字
    forbidden_chars = r'<>:"/\\|?*'
    for char in forbidden_chars:
        name = name.replace(char, "_")

    # 制御文字を除去
    name = re.sub(r"[\x00-\x1f\x7f-\x9f]", "_", name)

    # 先頭/末尾のドット、スペースを除去
    name = name.strip(". ")

    # 空文字になった場合のフォールバック
    if not name:
        return "unnamed"

    # ファイル名長さ制限（拡張子を考慮して200文字）
    return name[:200]


def organize_model_files(
    model_dir: Path, filename: str, images: List[dict]
) -> Dict[str, Path]:
    """モデルファイルの保存先パスを決定."""
    if not filename:
        raise ValueError("Filename cannot be empty")

    base_name = Path(filename).stem
    paths = {
        "model": model_dir / filename,
        "civitai_info": model_dir / f"{base_name}.civitai.info",
        "description": model_dir / "description.md",
        "gallery_dir": model_dir / "gallery",
        "previews": [],
    }

    # プレビュー画像のパス決定
    for idx, image_info in enumerate(images):
        if not image_info.get("url"):
            continue

        # URLから拡張子を推定
        url_path = Path(image_info["url"])
        ext = url_path.suffix

        # 拡張子がない場合のフォールバック
        if not ext:
            ext = ".jpeg"

        # プレビュー画像の命名規則
        if idx == 0:
            preview_name = f"{base_name}.preview{ext}"
        else:
            preview_name = f"{base_name}.preview.{idx + 1}{ext}"

        paths["previews"].append(model_dir / preview_name)

    return paths


def ensure_directory(path: Path) -> None:
    """ディレクトリが存在することを保証."""
    try:
        path.mkdir(parents=True, exist_ok=True)
    except Exception as e:
        raise OSError(f"Failed to create directory {path}: {e}")


def get_file_size_mb(path: Path) -> float:
    """ファイルサイズをMB単位で取得."""
    if not path.exists():
        return 0.0
    return path.stat().st_size / (1024 * 1024)
