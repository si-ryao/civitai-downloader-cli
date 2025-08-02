"""Metadata generator for creating description.md and .civitai.info files."""

import json
from datetime import datetime
from pathlib import Path
from typing import Any, Dict


class MetadataGenerator:
    """メタデータファイル生成器."""

    def generate_description_md(
        self, model_data: Dict[str, Any], version_data: Dict[str, Any]
    ) -> str:
        """APIレスポンスからdescription.mdを生成."""

        # 基本情報
        model_name = model_data.get("name", "Unknown Model")
        creator = model_data.get("creator", {})
        username = creator.get("username", "Unknown")
        model_type = model_data.get("type", "Unknown")

        # バージョン情報
        version_name = version_data.get("name", "Unknown")
        base_model = version_data.get("baseModel", "Unknown")
        trained_words = version_data.get("trainedWords", [])

        # ファイル情報
        files = version_data.get("files", [])
        main_file = files[0] if files else {}
        file_size_kb = main_file.get("sizeKB", 0)
        file_size_mb = file_size_kb / 1024 if file_size_kb else 0

        # ハッシュ情報
        hashes = main_file.get("hashes", {})
        model_hash = hashes.get("AutoV2", hashes.get("SHA256", "Unknown"))
        sha256 = hashes.get("SHA256", "Unknown")

        # 統計情報
        stats = version_data.get("stats", {})
        download_count = stats.get("downloadCount", 0)
        rating = stats.get("rating", 0)
        thumbs_up = stats.get("thumbsUpCount", 0)

        # NSFW情報
        nsfw_level = model_data.get("nsfwLevel", 0)

        # 説明文
        description = model_data.get("description", "")
        # HTMLタグを簡単に除去
        if description:
            import re

            description = re.sub(r"<[^>]+>", "", description)
            description = description.strip()

        if not description:
            description = "No description available"

        # ダウンロード情報
        download_url = version_data.get("downloadUrl", "Unknown")
        model_id = model_data.get("id", 0)
        version_id = version_data.get("id", 0)
        web_url = f"https://civitai.com/models/{model_id}?modelVersionId={version_id}"

        # Markdown生成
        md_content = f"""# {model_name}

**作者**: {username}
**タイプ**: {model_type}
**ベースモデル**: {base_model}

## Detail

- **トリガーワード**:
  - {', '.join(trained_words) if trained_words else 'なし'}
- **モデルハッシュ**: {model_hash}
- **バージョン**: {version_name}
- **ファイルサイズ**: {file_size_mb:.2f} MB
- **ダウンロード数**: {download_count:,}
- **評価**: ⭐{rating}
- **👍**: {thumbs_up}
- **NSFW レベル**: {nsfw_level}

## 説明

{description}

## ダウンロード情報

- **ダウンロード日時**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
- **ダウンロードURL**: {download_url}
- **Civitai WebページURL**: {web_url}
- **SHA256**: {sha256}
"""

        return md_content

    def save_civitai_info(self, model_data: Dict[str, Any], filepath: Path) -> None:
        """APIレスポンスを.civitai.info形式で保存."""
        filepath.parent.mkdir(parents=True, exist_ok=True)

        try:
            with open(filepath, "w", encoding="utf-8") as f:
                json.dump(model_data, f, ensure_ascii=False, indent=4)
            print(f"✓ Saved metadata: {filepath.name}")
        except Exception as e:
            raise IOError(f"Failed to save civitai.info: {e}")

    def save_description_md(self, content: str, filepath: Path) -> None:
        """description.mdファイルを保存."""
        filepath.parent.mkdir(parents=True, exist_ok=True)

        try:
            with open(filepath, "w", encoding="utf-8") as f:
                f.write(content)
            print(f"✓ Saved description: {filepath.name}")
        except Exception as e:
            raise IOError(f"Failed to save description.md: {e}")

    def format_file_size(self, size_kb: float) -> str:
        """ファイルサイズを人間が読みやすい形式に変換."""
        if size_kb < 1024:
            return f"{size_kb:.2f} KB"
        elif size_kb < 1024 * 1024:
            return f"{size_kb / 1024:.2f} MB"
        else:
            return f"{size_kb / (1024 * 1024):.2f} GB"
