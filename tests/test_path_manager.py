"""Tests for PathManager and tag-based classification."""

import json
from pathlib import Path

import pytest

from civitai_dl.adapters.api_client import CivitaiApiClient
from civitai_dl.config import DownloadConfig
from civitai_dl.services.path_manager import PathManager


class TestPathManager:
    """Test suite for PathManager."""

    @pytest.fixture
    def config(self):
        """Create config for testing."""
        # APIキーをapi_key.mdから読み取り
        api_key_file = Path(__file__).parent.parent / "api_key.md"
        api_key = None
        if api_key_file.exists():
            api_key = api_key_file.read_text().strip().split("\n")[0]

        return DownloadConfig(api_key=api_key, is_test=True)

    @pytest.fixture
    def path_manager(self, config):
        """Create PathManager for testing."""
        return PathManager(config)

    def test_tag_classification_concept(self, path_manager):
        """Test tag classification for concept models."""
        model_data = {
            "id": 1202733,
            "name": "Size difference",
            "type": "LORA",
            "creator": {"username": "alericiviai"},
            "tags": ["concept", "big dom", "small sub"],
        }

        analysis = path_manager.analyze_tags(model_data)
        print(f"Tag analysis: {json.dumps(analysis, indent=2)}")

        # "concept" タグがあるのでCONCEPTカテゴリになるはず
        assert analysis["final_category"] == "CONCEPT"
        assert "CONCEPT" in analysis["category_matches"]

    def test_tag_classification_pose(self, path_manager):
        """Test tag classification for pose models."""
        model_data = {
            "id": 1164832,
            "name": "Selfie poses big ass",
            "type": "LORA",
            "creator": {"username": "alericiviai"},
            "tags": ["butt", "poses", "big ass", "nsfw"],
        }

        analysis = path_manager.analyze_tags(model_data)
        print(f"Tag analysis: {json.dumps(analysis, indent=2)}")

        # "poses" タグがあるのでPOSEカテゴリになるはず
        assert analysis["final_category"] == "POSE"
        assert "POSE" in analysis["category_matches"]

    def test_folder_name_generation(self, path_manager):
        """Test folder name generation."""
        model_data = {"name": "Size difference", "creator": {"username": "alericiviai"}}
        version_data = {"name": "v1.5"}

        folder_name = path_manager._create_folder_name(model_data, version_data)
        expected = "alericiviai_Size difference_v1.5"

        print(f"Generated folder name: {folder_name}")
        assert folder_name == expected

    def test_path_determination(self, path_manager):
        """Test complete path determination."""
        model_data = {
            "id": 1202733,
            "name": "Size difference",
            "type": "LORA",
            "creator": {"username": "alericiviai"},
            "tags": ["concept", "big dom", "small sub"],
        }
        version_data = {"name": "v1.5", "baseModel": "Illustrious"}

        path = path_manager.determine_model_path(model_data, version_data)
        print(f"Determined path: {path}")

        # パス構造の確認
        path_parts = path.parts

        # テストモードなので ./test_downloads で始まるはず
        assert "test_downloads" in path_parts

        # models ディレクトリがあるはず
        assert "models" in path_parts

        # ベースモデル Illustrious があるはず
        assert "Illustrious" in path_parts

        # CONCEPT カテゴリがあるはず
        assert "CONCEPT" in path_parts

        # フォルダ名があるはず
        assert "alericiviai_Size difference_v1.5" in path_parts

    def test_file_paths_generation(self, path_manager):
        """Test file paths generation."""
        model_dir = Path(
            "test_downloads/models/Illustrious/CONCEPT/alericiviai_Size difference_v1.5"
        )

        model_data = {"name": "Size difference"}
        version_data = {
            "files": [{"name": "Height_difference.safetensors", "primary": True}],
            "images": [
                {
                    "url": "https://image.civitai.com/xG1nkqKTMzGDvpLrqFT7WA/5aeb55a9-282c-436b-bfa7-29acc2aa60b4/width=832/89306689.jpeg"
                },
                {
                    "url": "https://image.civitai.com/xG1nkqKTMzGDvpLrqFT7WA/9000e21a-0727-4eb9-9505-2cb336aeca6a/width=832/89306688.jpeg"
                },
            ],
        }

        paths = path_manager.get_file_paths(model_dir, model_data, version_data)
        print(
            f"File paths: {json.dumps({k: str(v) for k, v in paths.items()}, indent=2)}"
        )

        # ファイルパスの確認
        assert paths["model_file"].name == "Height_difference.safetensors"
        assert paths["civitai_info"].name == "Height_difference.civitai.info"
        assert paths["description"].name == "description.md"
        assert len(paths["previews"]) == 2
        assert paths["previews"][0].name == "Height_difference.preview.jpeg"
        assert paths["previews"][1].name == "Height_difference.preview.2.jpeg"

    def test_with_real_api_data(self, path_manager):
        """Test with real API data from alericiviai."""
        # APIキーをapi_key.mdから読み取り
        api_key_file = Path(__file__).parent.parent / "api_key.md"
        if not api_key_file.exists():
            pytest.skip("API key file not found")

        api_key = api_key_file.read_text().strip().split("\n")[0]
        config = DownloadConfig(api_key=api_key, is_test=True)
        client = CivitaiApiClient(config)

        try:
            # 実際のデータを取得
            response = client.get_user_models("alericiviai", limit=2)
            models = response.get("items", [])

            if not models:
                pytest.skip("No models found for alericiviai")

            for model in models:
                print(f"\n=== Processing model: {model['name']} ===")

                if "modelVersions" not in model or not model["modelVersions"]:
                    continue

                version = model["modelVersions"][0]  # 最新バージョン

                # タグ分析
                analysis = path_manager.analyze_tags(model)
                print(f"Tag analysis: {json.dumps(analysis, indent=2)}")

                # パス決定
                path = path_manager.determine_model_path(model, version)
                print(f"Determined path: {path}")

                # ファイルパス生成
                if version.get("files"):
                    file_paths = path_manager.get_file_paths(path, model, version)
                    print("File paths:")
                    for key, value in file_paths.items():
                        if isinstance(value, list):
                            print(f"  {key}: {[str(p) for p in value]}")
                        else:
                            print(f"  {key}: {value}")

                # 分類が適切かチェック
                category = analysis["final_category"]
                assert category in [
                    "CONCEPT",
                    "POSE",
                    "MISC",
                ], f"Unexpected category: {category}"

                print(f"✓ Model classified as: {category}")

        except Exception as e:
            pytest.fail(f"Real API test failed: {e}")


if __name__ == "__main__":
    # 直接実行した場合のテスト
    api_key_file = Path(__file__).parent.parent / "api_key.md"
    if api_key_file.exists():
        api_key = api_key_file.read_text().strip().split("\n")[0]
        config = DownloadConfig(api_key=api_key, is_test=True)
        path_manager = PathManager(config)

        print("Testing PathManager with real alericiviai data...")

        # 実際のAPIデータでテスト
        client = CivitaiApiClient(config)
        response = client.get_user_models("alericiviai", limit=3)

        for model in response.get("items", []):
            print(f"\n=== {model['name']} ===")
            print(f"Tags: {model.get('tags', [])}")

            analysis = path_manager.analyze_tags(model)
            print(f"Category: {analysis['final_category']}")

            if model.get("modelVersions"):
                version = model["modelVersions"][0]
                path = path_manager.determine_model_path(model, version)
                print(f"Path: {path}")
    else:
        print("API key file not found. Skipping real API test.")
