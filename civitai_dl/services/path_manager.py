"""Path management service for organizing downloads."""

from pathlib import Path
from typing import Any, Dict, List

from ..config import DownloadConfig
from ..utils.fs import sanitize_filename


class PathManager:
    """ダウンロードファイルのパス管理とタグベース分類."""

    def __init__(self, config: DownloadConfig):
        self.config = config
        self.tag_mappings = config.tag_mappings

    def determine_model_path(
        self, model_data: Dict[str, Any], version_data: Dict[str, Any]
    ) -> Path:
        """タグベース分類でモデルの保存先パスを決定."""
        # 1. ルートディレクトリ（本番/テスト切り替え）
        root = self.config.root_dir

        # 2. models/images分類
        model_type = model_data.get("type", "").upper()
        type_dir = "models" if model_type in ["CHECKPOINT", "LORA"] else "images"

        # 3. ベースモデル分類
        base_model = version_data.get("baseModel", "Unknown")
        base_model = sanitize_filename(base_model)

        # 4. タグ分類（完全一致優先）
        tag_category = self._classify_by_tags(model_data.get("tags", []))

        # 5. フォルダ名: {user}_{model}_{version}
        folder_name = self._create_folder_name(model_data, version_data)

        return root / type_dir / base_model / tag_category / folder_name

    def _classify_by_tags(self, model_tags: List[str]) -> str:
        """タグに基づいてカテゴリを決定（完全一致優先）."""
        if not model_tags:
            return "MISC"

        # タグを正規化（小文字、スペース除去）
        normalized_tags = [tag.lower().strip() for tag in model_tags]

        # 完全一致を優先
        for category, keywords in self.tag_mappings.items():
            # カテゴリ名そのものがタグに含まれているかチェック
            if category.lower() in normalized_tags:
                return category

        # 部分一致でフォールバック
        for category, keywords in self.tag_mappings.items():
            for keyword in keywords:
                keyword_lower = keyword.lower()
                if any(
                    keyword_lower in tag or keyword_lower == tag
                    for tag in normalized_tags
                ):
                    return category

        return "MISC"  # 分類不能な場合

    def _create_folder_name(
        self, model_data: Dict[str, Any], version_data: Dict[str, Any]
    ) -> str:
        """ユーザー名_モデル名_バージョン名 形式のフォルダ名を生成."""
        # ユーザー名取得
        creator = model_data.get("creator", {})
        username = creator.get("username", "Unknown")

        # モデル名取得
        model_name = model_data.get("name", "Unknown")

        # バージョン名取得
        version_name = version_data.get("name", "Unknown")

        # サニタイズして結合
        clean_username = sanitize_filename(username)
        clean_model = sanitize_filename(model_name)
        clean_version = sanitize_filename(version_name)

        return f"{clean_username}_{clean_model}_{clean_version}"

    def get_file_paths(
        self, model_dir: Path, model_data: Dict[str, Any], version_data: Dict[str, Any]
    ) -> Dict[str, Path]:
        """モデルディレクトリ内のファイルパスを決定."""
        # メインファイル名を取得
        files = version_data.get("files", [])
        if not files:
            raise ValueError("No files found in version data")

        main_file = files[0]  # primary fileを使用
        filename = main_file.get("name", "model.safetensors")
        base_name = Path(filename).stem

        # 基本パス構造
        paths = {
            "model_file": model_dir / filename,
            "civitai_info": model_dir / f"{base_name}.civitai.info",
            "description": model_dir / "description.md",
            "gallery_dir": model_dir / "gallery",
        }

        # プレビュー画像のパス
        images = version_data.get("images", [])
        preview_paths = []
        for idx, image_info in enumerate(images):
            url = image_info.get("url", "")
            if not url:
                continue

            # URL から拡張子を推定
            # URL にクエリパラメータがある場合があるので、最後の / 以降を取得
            url_filename = url.split("/")[-1].split("?")[0]
            ext = Path(url_filename).suffix or ".jpeg"

            # プレビュー画像の命名規則
            if idx == 0:
                preview_name = f"{base_name}.preview{ext}"
            else:
                preview_name = f"{base_name}.preview.{idx + 1}{ext}"

            preview_paths.append(model_dir / preview_name)

        paths["previews"] = preview_paths

        # ギャラリー画像パス生成（Galleryフォルダ内）
        model_id = model_data.get("id")
        if model_id:
            gallery_dir = model_dir / "Gallery"
            paths["gallery_dir"] = gallery_dir
            # 最大50枚のギャラリー画像（実際のパスはダウンロード時に生成）
            paths["gallery_max_count"] = 50

        return paths

    def analyze_tags(self, model_data: Dict[str, Any]) -> Dict[str, Any]:
        """タグ分析結果を返す（デバッグ用）."""
        tags = model_data.get("tags", [])
        normalized_tags = [tag.lower().strip() for tag in tags]

        # 各カテゴリとのマッチング結果
        matches = {}
        for category, keywords in self.tag_mappings.items():
            category_matches = []

            # 完全一致チェック
            if category.lower() in normalized_tags:
                category_matches.append(f"EXACT: {category}")

            # 部分一致チェック
            for keyword in keywords:
                keyword_lower = keyword.lower()
                matching_tags = [
                    tag
                    for tag in normalized_tags
                    if keyword_lower in tag or keyword_lower == tag
                ]
                if matching_tags:
                    category_matches.extend(
                        [f"PARTIAL: {keyword} -> {tag}" for tag in matching_tags]
                    )

            if category_matches:
                matches[category] = category_matches

        result_category = self._classify_by_tags(tags)

        return {
            "original_tags": tags,
            "normalized_tags": normalized_tags,
            "category_matches": matches,
            "final_category": result_category,
        }

    def determine_user_images_path(self, username: str) -> Path:
        """ユーザー投稿画像のベースパスを決定."""
        images_root = Path(self.config.root_dir) / "images"
        return images_root / username

    def get_user_image_paths(
        self, username: str, images_data: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """ユーザー投稿画像用のファイルパスを生成."""
        user_images_dir = self.determine_user_images_path(username)

        paths = {
            "images_dir": user_images_dir,
            "metadata_file": user_images_dir / "images_metadata.json",
            "image_files": [],
        }

        # 各画像のファイルパスを生成
        for image_info in images_data:
            image_id = image_info.get("id")
            image_url = image_info.get("url", "")

            if not image_id:
                continue

            # URLから拡張子を判定
            if ".jpeg" in image_url.lower():
                ext = ".jpeg"
            elif ".jpg" in image_url.lower():
                ext = ".jpg"
            elif ".png" in image_url.lower():
                ext = ".png"
            else:
                ext = ".jpeg"  # デフォルト

            image_path = user_images_dir / f"{image_id}{ext}"
            paths["image_files"].append(
                {
                    "path": image_path,
                    "id": image_id,
                    "url": image_url,
                    "info": image_info,
                }
            )

        return paths
