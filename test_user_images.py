"""Test user images download functionality."""

from pathlib import Path

from civitai_dl.config import DownloadConfig
from civitai_dl.services.download_service import DownloadService


def test_user_images_download():
    """Test downloading user images."""
    # APIキーを読み取り
    api_key_file = Path("api_key.md")
    if not api_key_file.exists():
        print("❌ API key file not found")
        return

    api_key = api_key_file.read_text().strip().split("\n")[0]

    # 設定
    config = DownloadConfig(api_key=api_key, is_test=True)
    download_service = DownloadService(config)

    print("🧪 Testing user images download...")

    try:
        # alericiviai のユーザー画像をダウンロード
        result = download_service.download_user_images("alericiviai")

        if result["success"]:
            print("🎉 User images download test successful!")
            print(f"   👤 User: {result['username']}")
            print(
                f"   📸 Downloaded: {result['downloaded_images']}/{result['total_images']}"
            )
            print(f"   📁 Directory: {result['images_dir']}")

            # ダウンロードされたファイルを確認
            images_dir = Path(result["images_dir"])
            if images_dir.exists():
                files = list(images_dir.glob("*"))
                print(f"   📄 Files in directory: {len(files)}")
                for file in files[:5]:  # 最初の5つのみ表示
                    if file.is_file():
                        size_mb = file.stat().st_size / (1024 * 1024)
                        print(f"     - {file.name} ({size_mb:.2f} MB)")

        else:
            print(f"❌ User images download failed: {result.get('message')}")

    except Exception as e:
        print(f"❌ Error during test: {e}")
        import traceback

        traceback.print_exc()


if __name__ == "__main__":
    test_user_images_download()
