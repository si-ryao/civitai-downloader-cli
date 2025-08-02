"""Tests for Civitai API client."""

import json
from pathlib import Path

import pytest

from civitai_dl.adapters.api_client import CivitaiApiClient, CivitaiApiError
from civitai_dl.config import DownloadConfig


class TestCivitaiApiClient:
    """Test suite for CivitaiApiClient."""

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
    def client(self, config):
        """Create API client for testing."""
        return CivitaiApiClient(config)

    def test_api_client_initialization(self, client):
        """Test API client initialization."""
        assert client.base_url == "https://civitai.com/api/v1"
        assert client.config.api_key is not None
        assert "Authorization" in client.session.headers

    def test_get_user_models_alericiviai(self, client):
        """Test getting models for alericiviai user."""
        try:
            response = client.get_user_models("alericiviai", limit=5)

            # レスポンス構造の確認
            assert "items" in response
            assert "metadata" in response

            models = response["items"]
            if models:  # モデルが存在する場合
                model = models[0]
                print(f"First model: {json.dumps(model, indent=2)}")

                # 必要なフィールドの存在確認
                assert "id" in model
                assert "name" in model
                assert "type" in model
                assert "creator" in model
                assert "username" in model["creator"]

                # タグ情報の確認
                if "tags" in model:
                    print(f"Tags: {model['tags']}")

                # バージョン情報の確認
                if "modelVersions" in model:
                    version = model["modelVersions"][0]
                    print(f"First version: {json.dumps(version, indent=2)}")

                    assert "id" in version
                    assert "name" in version

                    if "baseModel" in version:
                        print(f"Base model: {version['baseModel']}")

            print(f"Found {len(models)} models for alericiviai")

        except CivitaiApiError as e:
            pytest.fail(f"API error: {e}")

    def test_get_all_user_models_alericiviai(self, client):
        """Test getting all models for alericiviai user."""
        try:
            all_models = client.get_all_user_models("alericiviai")

            print(f"Total models found for alericiviai: {len(all_models)}")

            if all_models:
                # 各モデルの基本情報を出力
                for i, model in enumerate(all_models[:3]):  # 最初の3つだけ
                    print(f"Model {i+1}: {model['name']} (ID: {model['id']})")
                    if "tags" in model:
                        print(f"  Tags: {model['tags']}")
                    if "modelVersions" in model and model["modelVersions"]:
                        version = model["modelVersions"][0]
                        print(f"  Base model: {version.get('baseModel', 'Unknown')}")

        except CivitaiApiError as e:
            pytest.fail(f"API error: {e}")

    def test_get_model_details(self, client):
        """Test getting model details."""
        try:
            # まずalericiviai のモデル一覧を取得
            models = client.get_user_models("alericiviai", limit=1)

            if models["items"]:
                model_id = models["items"][0]["id"]

                # モデル詳細を取得
                details = client.get_model_details(model_id)

                print(f"Model details: {json.dumps(details, indent=2)}")

                assert "id" in details
                assert "name" in details
                assert "modelVersions" in details

                # バージョン詳細の確認
                if details["modelVersions"]:
                    version = details["modelVersions"][0]
                    assert "files" in version
                    assert "images" in version

                    if version["files"]:
                        file_info = version["files"][0]
                        print(f"File info: {json.dumps(file_info, indent=2)}")
                        assert "name" in file_info
                        assert "downloadUrl" in file_info

        except CivitaiApiError as e:
            pytest.fail(f"API error: {e}")


if __name__ == "__main__":
    # 直接実行した場合のテスト
    config = DownloadConfig(is_test=True)

    # APIキーをapi_key.mdから読み取り
    api_key_file = Path(__file__).parent.parent / "api_key.md"
    if api_key_file.exists():
        config.api_key = api_key_file.read_text().strip().split("\n")[0]

    client = CivitaiApiClient(config)

    print("Testing API client with alericiviai user...")

    try:
        # ユーザーモデル取得テスト
        response = client.get_user_models("alericiviai", limit=3)
        print(f"API Response: {json.dumps(response, indent=2)}")

    except Exception as e:
        print(f"Error: {e}")
