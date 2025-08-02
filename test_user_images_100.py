#!/usr/bin/env python3
"""Test user images download with 100 image limit."""

from pathlib import Path

from civitai_dl.config import DownloadConfig
from civitai_dl.services.download_service import DownloadService


def main():
    print("🧪 Testing user images download with 100 image limit...")

    # APIキーを取得
    api_key_file = Path(__file__).parent / "api_key.md"
    if not api_key_file.exists():
        print("❌ api_key.md not found")
        return

    api_key = api_key_file.read_text().strip().split("\n")[0]

    # 設定（100枚制限）
    config = DownloadConfig(api_key=api_key, is_test=True, max_user_images=100)

    # ダウンロードサービス初期化
    download_service = DownloadService(config)

    # ユーザー画像ダウンロード
    username = "alericiviai"
    result = download_service.download_user_images(username)

    if result["success"]:
        print("🎉 User images download test successful!")
        print(f"   👤 User: {result['username']}")
        print(
            f"   📸 Downloaded: {result['downloaded_images']}/{result['total_images']}"
        )
        print(f"   📁 Directory: {result['images_dir']}")

        # ディレクトリの実際のファイル数を確認
        images_dir = Path(result["images_dir"])
        if images_dir.exists():
            files = list(images_dir.glob("*.jpeg"))
            metadata_files = list(images_dir.glob("*.json"))
            print(f"   📄 Files in directory: {len(files) + len(metadata_files)}")
            for file in sorted(files)[:5]:  # 最初の5ファイルのみ表示
                size_mb = file.stat().st_size / (1024 * 1024)
                print(f"     - {file.name} ({size_mb:.2f} MB)")
            if len(files) > 5:
                print(f"     ... and {len(files) - 5} more image files")
    else:
        print("❌ User images download test failed!")
        print(f"   Error: {result.get('message', 'Unknown error')}")


if __name__ == "__main__":
    main()
