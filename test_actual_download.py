"""Test actual download functionality."""

from pathlib import Path

from civitai_dl.config import DownloadConfig
from civitai_dl.services.download_service import DownloadService


def test_actual_download():
    """Test actual download of one model."""
    # APIキーを読み取り
    api_key_file = Path("api_key.md")
    if not api_key_file.exists():
        print("❌ API key file not found")
        return

    api_key = api_key_file.read_text().strip().split("\n")[0]

    # 設定
    config = DownloadConfig(api_key=api_key, is_test=True)
    download_service = DownloadService(config)

    print("🚀 Starting actual download test...")

    try:
        # alericiviai のモデル一覧を取得（1つのみ）
        models = download_service.api_client.get_user_models("alericiviai", limit=1)

        if not models.get("items"):
            print("❌ No models found")
            return

        model = models["items"][0]
        print(f"📦 Downloading model: {model['name']}")

        # 実際のダウンロード実行
        result = download_service.download_single_model(model)

        if result["success"]:
            print("🎉 Download completed successfully!")
            print(f"   📊 Model: {result['model_name']}")
            print(f"   🏷️  Category: {result['category']}")
            print(f"   📁 Versions: {len(result['versions'])}")

            # ダウンロードされたファイルの確認
            for version in result["versions"]:
                print(f"   📥 Version: {version['version_name']}")
                print(f"      ✅ Success: {version['success']}")
                print(f"      📄 Files: {version['downloaded_files']}")

                # 実際のファイル存在確認
                if version["success"]:
                    version_path = Path(version["path"])
                    print(f"      📁 Path: {version_path}")

                    if version_path.exists():
                        files = list(version_path.rglob("*"))
                        files = [f for f in files if f.is_file()]
                        print(f"      📄 Found {len(files)} files:")
                        for file in files:
                            size_mb = file.stat().st_size / (1024 * 1024)
                            print(f"         - {file.name} ({size_mb:.2f} MB)")
                    else:
                        print(f"      ⚠️  Path does not exist: {version_path}")
        else:
            print(f"❌ Download failed: {result.get('error')}")

    except Exception as e:
        print(f"❌ Error during download: {e}")
        import traceback

        traceback.print_exc()


if __name__ == "__main__":
    test_actual_download()
