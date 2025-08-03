"""Integrated download service for models and images."""

from pathlib import Path
from typing import Any, Dict, List, Optional

from ..adapters.api_client import CivitaiApiClient
from ..adapters.downloader import FileDownloader
from ..config import DownloadConfig
from ..services.metadata_generator import MetadataGenerator
from ..services.path_manager import PathManager


class DownloadService:
    """統合ダウンロードサービス."""

    def __init__(self, config: DownloadConfig, skip_existing: bool = False, base_model_filter: Optional[List[str]] = None):
        self.config = config
        self.api_client = CivitaiApiClient(config)
        self.file_downloader = FileDownloader(config, skip_existing=skip_existing)
        self.path_manager = PathManager(config)
        self.metadata_generator = MetadataGenerator()
        self.base_model_filter = base_model_filter
        
        # フィルター統計
        self.filter_stats = {
            "total_checked": 0,
            "filtered_out": 0,
            "passed_filter": 0
        }

    def download_user_models(self, username: str) -> Dict[str, Any]:
        """指定ユーザーの全モデルをダウンロード."""
        print(f"🚀 Starting download for user: {username}")

        # ユーザーの全モデルを取得
        print(f"📡 Fetching models for {username}...")
        all_models = self.api_client.get_all_user_models(username)

        if not all_models:
            print(f"❌ No models found for user: {username}")
            return {"success": False, "message": f"No models found for {username}"}

        print(f"📋 Found {len(all_models)} models for {username}")

        results = {
            "success": True,
            "username": username,
            "total_models": len(all_models),
            "processed_models": 0,
            "successful_downloads": 0,
            "failed_downloads": 0,
            "models": [],
        }

        for i, model in enumerate(all_models, 1):
            print(f"\n📦 Processing model {i}/{len(all_models)}: {model['name']}")

            # ベースモデルフィルターチェック
            if not self._should_download_model(model):
                print(f"  🔍 Skipped: Base model not in whitelist")
                continue

            try:
                model_result = self.download_single_model(model)
                results["models"].append(model_result)
                results["processed_models"] += 1

                if model_result["success"]:
                    results["successful_downloads"] += 1
                else:
                    results["failed_downloads"] += 1

            except Exception as e:
                print(f"❌ Error processing model {model['name']}: {e}")
                results["models"].append(
                    {
                        "model_id": model.get("id"),
                        "model_name": model.get("name"),
                        "success": False,
                        "error": str(e),
                    }
                )
                results["failed_downloads"] += 1

        print("\n🎉 Download completed!")
        print(f"   Total: {results['total_models']}")
        print(f"   Success: {results['successful_downloads']}")
        print(f"   Failed: {results['failed_downloads']}")
        
        # フィルター統計表示
        if self.base_model_filter:
            print(f"   🔍 Filter stats: {self.filter_stats['passed_filter']}/{self.filter_stats['total_checked']} models passed filter ({self.filter_stats['filtered_out']} filtered out)")
            results["filter_stats"] = self.filter_stats.copy()

        return results

    def download_single_model(self, model_data: Dict[str, Any]) -> Dict[str, Any]:
        """単一モデルをダウンロード（全バージョン）."""
        model_id = model_data.get("id")
        model_name = model_data.get("name", "Unknown")

        print(f"  📊 Analyzing tags for: {model_name}")
        tag_analysis = self.path_manager.analyze_tags(model_data)
        print(f"  🏷️  Category: {tag_analysis['final_category']}")

        model_result = {
            "model_id": model_id,
            "model_name": model_name,
            "category": tag_analysis["final_category"],
            "success": True,
            "versions": [],
            "error": None,
        }

        # 各バージョンをダウンロード
        versions = model_data.get("modelVersions", [])
        if not versions:
            print(f"  ⚠️  No versions found for model: {model_name}")
            model_result["success"] = False
            model_result["error"] = "No versions found"
            return model_result

        for version in versions:
            print(f"    📥 Downloading version: {version.get('name', 'Unknown')}")
            # 各バージョンごとに統計をリセット
            self.file_downloader.reset_stats()

            try:
                version_result = self.download_single_version(model_data, version)
                model_result["versions"].append(version_result)

                if not version_result["success"]:
                    model_result["success"] = False

            except Exception as e:
                print(f"    ❌ Error downloading version {version.get('name')}: {e}")
                model_result["versions"].append(
                    {
                        "version_id": version.get("id"),
                        "version_name": version.get("name"),
                        "success": False,
                        "error": str(e),
                    }
                )
                model_result["success"] = False

        return model_result

    def download_single_version(
        self, model_data: Dict[str, Any], version_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """単一バージョンをダウンロード."""
        version_id = version_data.get("id")
        version_name = version_data.get("name", "Unknown")

        # パス決定
        model_dir = self.path_manager.determine_model_path(model_data, version_data)
        file_paths = self.path_manager.get_file_paths(
            model_dir, model_data, version_data
        )

        print(f"      📁 Saving to: {model_dir}")

        version_result = {
            "version_id": version_id,
            "version_name": version_name,
            "path": str(model_dir),
            "success": True,
            "downloaded_files": [],
            "error": None,
        }

        try:
            # 1. メタデータファイル生成
            self._save_metadata(model_data, version_data, file_paths)
            version_result["downloaded_files"].extend(
                [
                    "description.md",
                    f"{Path(file_paths['model_file']).stem}.civitai.info",
                ]
            )

            # 2. モデルファイルダウンロード
            self._download_model_files(version_data, file_paths, version_result)

            # 3. プレビュー画像ダウンロード
            self._download_preview_images(version_data, file_paths, version_result)

            # 4. ギャラリー画像ダウンロード
            self._download_gallery_images(model_data, file_paths, version_result)

            # ダウンロード統計を表示
            stats = self.file_downloader.get_stats()
            if stats["skipped"] > 0:
                print(f"      ✅ Version download completed: {version_name}")
                print(f"         📊 Downloaded: {stats['downloaded']}, Skipped: {stats['skipped']}")
            else:
                print(f"      ✅ Version download completed: {version_name}")

        except Exception as e:
            print(f"      ❌ Version download failed: {e}")
            version_result["success"] = False
            version_result["error"] = str(e)

        return version_result

    def _save_metadata(
        self,
        model_data: Dict[str, Any],
        version_data: Dict[str, Any],
        file_paths: Dict[str, Path],
    ) -> None:
        """メタデータファイルを保存."""
        # description.md生成
        description_content = self.metadata_generator.generate_description_md(
            model_data, version_data
        )
        self.metadata_generator.save_description_md(
            description_content, file_paths["description"]
        )

        # civitai.info保存
        self.metadata_generator.save_civitai_info(
            model_data, file_paths["civitai_info"]
        )

    def _download_model_files(
        self,
        version_data: Dict[str, Any],
        file_paths: Dict[str, Path],
        result: Dict[str, Any],
    ) -> None:
        """モデルファイルをダウンロード."""
        files = version_data.get("files", [])
        if not files:
            raise ValueError("No files found in version data")

        main_file = files[0]  # Primary file
        download_url = main_file.get("downloadUrl")
        if not download_url:
            raise ValueError("No download URL found")

        # SHA256ハッシュ取得
        expected_sha256 = main_file.get("hashes", {}).get("SHA256")

        # ダウンロード実行
        success = self.file_downloader.download_file(
            url=download_url,
            filepath=file_paths["model_file"],
            expected_sha256=expected_sha256,
            description=f"Model: {file_paths['model_file'].name}",
        )

        if success:
            result["downloaded_files"].append(file_paths["model_file"].name)

    def _download_preview_images(
        self,
        version_data: Dict[str, Any],
        file_paths: Dict[str, Path],
        result: Dict[str, Any],
    ) -> None:
        """プレビュー画像をダウンロード."""
        preview_paths = file_paths.get("previews", [])
        images = version_data.get("images", [])

        if not images or not preview_paths:
            print("      ℹ️  No preview images to download")
            return

        # 最大3枚のプレビュー画像をダウンロード
        for i, (image_info, preview_path) in enumerate(zip(images, preview_paths)):
            if i >= 3:  # 最大3枚まで
                break

            image_url = image_info.get("url")
            if not image_url:
                continue

            try:
                success = self.file_downloader.download_file(
                    url=image_url,
                    filepath=preview_path,
                    description=f"Preview {i+1}: {preview_path.name}",
                )

                if success:
                    result["downloaded_files"].append(preview_path.name)

            except Exception as e:
                print(f"      ⚠️  Failed to download preview {i+1}: {e}")
                # プレビュー画像の失敗は全体の失敗にはしない

    def _download_gallery_images(
        self,
        model_data: Dict[str, Any],
        file_paths: Dict[str, Path],
        result: Dict[str, Any],
    ) -> None:
        """ギャラリー画像をGalleryフォルダにダウンロード."""
        gallery_dir = file_paths.get("gallery_dir")
        max_count = file_paths.get("gallery_max_count", 50)
        model_id = model_data.get("id")

        if not model_id or not gallery_dir:
            print("      ℹ️  No gallery images to download")
            return

        try:
            # モデルのギャラリー画像を取得
            all_images = self.api_client.get_all_images_for_model(model_id)

            if not all_images:
                print("      ℹ️  No gallery images found")
                return

            print(f"      🖼️  Found {len(all_images)} gallery images")

            # Galleryフォルダを作成
            gallery_dir.mkdir(exist_ok=True)

            # 最大50枚のギャラリー画像をダウンロード
            downloaded_count = 0
            for i, image_info in enumerate(all_images):
                if downloaded_count >= max_count:  # 最大50枚まで
                    break

                image_url = image_info.get("url")
                image_id = image_info.get("id")

                if not image_url or not image_id:
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

                # 画像IDをファイル名に使用
                gallery_path = gallery_dir / f"{image_id}{ext}"

                try:
                    success = self.file_downloader.download_file(
                        url=image_url,
                        filepath=gallery_path,
                        description=f"Gallery {downloaded_count+1}: {gallery_path.name}",
                    )

                    if success:
                        result["downloaded_files"].append(
                            f"Gallery/{gallery_path.name}"
                        )
                        downloaded_count += 1

                except Exception as e:
                    print(
                        f"      ⚠️  Failed to download gallery {downloaded_count+1}: {e}"
                    )
                    # ギャラリー画像の失敗は全体の失敗にはしない

            if downloaded_count > 0:
                print(
                    f"      ✅ Downloaded {downloaded_count} gallery images to Gallery folder"
                )

        except Exception as e:
            print(f"      ⚠️  Failed to fetch gallery images: {e}")
            # ギャラリー画像の失敗は全体の失敗にはしない

    def download_model_by_id(self, model_id: int) -> Dict[str, Any]:
        """モデルIDを指定して単一モデルをダウンロード."""
        print(f"🔍 Fetching model details for ID: {model_id}")

        try:
            # モデル詳細を取得
            model_data = self.api_client.get_model_details(model_id)

            if not model_data:
                return {"success": False, "message": f"Model not found: {model_id}"}

            print(f"📦 Found model: {model_data.get('name', 'Unknown')}")

            # 既存の単一モデルダウンロード機能を使用
            return self.download_single_model(model_data)

        except Exception as e:
            print(f"❌ Error downloading model {model_id}: {e}")
            return {
                "success": False,
                "message": f"Error downloading model {model_id}: {e}",
            }

    def download_user_images(self, username: str) -> Dict[str, Any]:
        """指定ユーザーの投稿画像をダウンロード."""
        print(f"🖼️  Starting user images download for: {username}")
        # 統計をリセット
        self.file_downloader.reset_stats()

        try:
            # ユーザーの投稿画像を取得
            all_images = self.api_client.get_all_user_images(username)

            if not all_images:
                return {
                    "success": False,
                    "message": f"No images found for user: {username}",
                }

            print(f"📸 Found {len(all_images)} user images for {username}")

            # パス生成
            image_paths = self.path_manager.get_user_image_paths(username, all_images)
            images_dir = image_paths["images_dir"]
            metadata_file = image_paths["metadata_file"]
            image_files = image_paths["image_files"]

            # ディレクトリ作成
            images_dir.mkdir(parents=True, exist_ok=True)

            result = {
                "success": True,
                "username": username,
                "images_dir": str(images_dir),
                "total_images": len(all_images),
                "downloaded_images": 0,
                "failed_images": 0,
                "image_files": [],
            }

            # メタデータ保存
            import json

            with open(metadata_file, "w", encoding="utf-8") as f:
                json.dump(
                    {
                        "username": username,
                        "total_images": len(all_images),
                        "download_date": str(Path().cwd()),  # 簡易日時
                        "images": all_images,
                    },
                    f,
                    indent=2,
                    ensure_ascii=False,
                )

            print(f"✓ Saved metadata: {metadata_file.name}")

            # 画像ダウンロード（設定可能な制限）
            max_download = min(self.config.max_user_images, len(image_files))
            print(
                f"📥 Downloading {max_download} images (limited from {len(image_files)})"
            )

            for i, image_file in enumerate(image_files[:max_download]):
                image_path = image_file["path"]
                image_url = image_file["url"]
                image_id = image_file["id"]

                try:
                    success = self.file_downloader.download_file(
                        url=image_url,
                        filepath=image_path,
                        description=f"User Image {i+1}: {image_path.name}",
                    )

                    if success:
                        result["downloaded_images"] += 1
                        result["image_files"].append(str(image_path.name))
                    else:
                        result["failed_images"] += 1

                except Exception as e:
                    print(f"      ⚠️  Failed to download image {image_id}: {e}")
                    result["failed_images"] += 1

            # 最終統計を表示
            stats = self.file_downloader.get_stats()
            print("🎉 User images download completed!")
            if stats["skipped"] > 0:
                print(
                    f"   📊 Downloaded: {stats['downloaded']}, Skipped: {stats['skipped']} (Total: {result['total_images']})"
                )
            else:
                print(
                    f"   📊 Downloaded: {result['downloaded_images']}/{result['total_images']}"
                )
            print(f"   📁 Saved to: {images_dir}")

            return result

        except Exception as e:
            print(f"❌ Error downloading user images for {username}: {e}")
            return {"success": False, "message": f"Error downloading user images: {e}"}

    def _should_download_model(self, model_data: Dict[str, Any]) -> bool:
        """ベースモデルフィルターに基づいてモデルをダウンロードすべきかチェック."""
        self.filter_stats["total_checked"] += 1
        
        # フィルターが設定されていない場合は全てダウンロード
        if not self.base_model_filter:
            self.filter_stats["passed_filter"] += 1
            return True
        
        # モデルのバージョンからベースモデル情報を取得
        versions = model_data.get("modelVersions", [])
        if not versions:
            # バージョンが無い場合は保守的にスキップ
            self.filter_stats["filtered_out"] += 1
            return False
        
        # 最新バージョン（通常は最初）のベースモデルを確認
        latest_version = versions[0]
        base_model = latest_version.get("baseModel", "").strip()
        
        if not base_model:
            # ベースモデル情報がない場合は保守的にスキップ
            self.filter_stats["filtered_out"] += 1
            return False
        
        # 大文字小文字を無視してマッチング
        base_model_lower = base_model.lower()
        for allowed_model in self.base_model_filter:
            if allowed_model.lower() in base_model_lower or base_model_lower in allowed_model.lower():
                self.filter_stats["passed_filter"] += 1
                return True
        
        # フィルターに一致しない場合はスキップ
        self.filter_stats["filtered_out"] += 1
        return False
