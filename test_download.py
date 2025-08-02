"""Test script for download functionality."""

from pathlib import Path

from civitai_dl.config import DownloadConfig
from civitai_dl.services.download_service import DownloadService


def test_single_model_download():
    """Test downloading a single model."""
    # APIキーを読み取り
    api_key_file = Path("api_key.md")
    if not api_key_file.exists():
        print("❌ API key file not found")
        return

    api_key = api_key_file.read_text().strip().split("\n")[0]

    # 設定
    config = DownloadConfig(api_key=api_key, is_test=True)
    download_service = DownloadService(config)

    print("🧪 Testing download service...")

    try:
        # alericiviai のモデル一覧を取得（1つのみ）
        models = download_service.api_client.get_user_models("alericiviai", limit=1)

        if not models.get("items"):
            print("❌ No models found")
            return

        model = models["items"][0]
        print(f"📦 Testing with model: {model['name']}")
        print(f"🏷️  Tags: {model.get('tags', [])}")

        # タグ分析テスト
        tag_analysis = download_service.path_manager.analyze_tags(model)
        print(f"📊 Tag analysis result: {tag_analysis['final_category']}")

        # パス決定テスト
        if model.get("modelVersions"):
            version = model["modelVersions"][0]
            model_path = download_service.path_manager.determine_model_path(
                model, version
            )
            print(f"📁 Determined path: {model_path}")

            # ファイルパス生成テスト
            file_paths = download_service.path_manager.get_file_paths(
                model_path, model, version
            )
            print("📄 File paths:")
            for key, value in file_paths.items():
                if isinstance(value, list):
                    print(f"   {key}: {len(value)} files")
                    for i, path in enumerate(value[:2]):  # 最初の2つのみ表示
                        print(f"     {i+1}: {path}")
                else:
                    print(f"   {key}: {value}")

            # メタデータ生成テスト
            description = download_service.metadata_generator.generate_description_md(
                model, version
            )
            print("\n📝 Generated description preview:")
            print("=" * 50)
            print(description[:500] + "...")
            print("=" * 50)

            print("\n✅ All tests passed! Ready for actual download.")

            # 実際にダウンロードするか確認
            response = input("\n🤔 Proceed with actual download? (y/N): ")
            if response.lower() == "y":
                print("🚀 Starting actual download...")
                result = download_service.download_single_model(model)

                if result["success"]:
                    print("🎉 Download completed successfully!")
                    print(f"   📊 Result: {result}")
                else:
                    print(f"❌ Download failed: {result.get('error')}")
            else:
                print("⏭️  Skipping actual download.")

    except Exception as e:
        print(f"❌ Error during test: {e}")
        import traceback

        traceback.print_exc()


if __name__ == "__main__":
    test_single_model_download()
