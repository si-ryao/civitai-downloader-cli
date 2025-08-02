"""失敗したダウンロードの再試行スクリプト."""

from pathlib import Path

from civitai_dl.config import DownloadConfig
from civitai_dl.services.download_service import DownloadService


def retry_failed_downloads():
    """失敗したモデルの再ダウンロード."""
    # APIキー読み取り
    api_key_file = Path("api_key.md")
    if not api_key_file.exists():
        print("❌ API key file not found")
        return

    api_key = api_key_file.read_text().strip().split("\n")[0]

    # 設定
    config = DownloadConfig(api_key=api_key, is_test=True)
    download_service = DownloadService(config)

    # 失敗したモデルのバージョンID
    failed_versions = [
        {
            "model_id": 1591074,
            "version_id": 1800478,
            "name": "Extreme Size difference V1",
        },
        {"model_id": 1674467, "version_id": 1895217, "name": "Anal gape V1"},
        {
            "model_id": 1805768,
            "version_id": 2043531,
            "name": "Anal self fisting illustrious V1",
        },
        {
            "model_id": 1164832,
            "version_id": 1641053,
            "name": "Selfie poses big ass v1.0 illustrious",
        },
        {
            "model_id": 1164832,
            "version_id": 2043613,
            "name": "Selfie poses big ass v1.5 illus",
        },
        {"model_id": 1276306, "version_id": 1439816, "name": "duo Anal fisting V1"},
    ]

    print(f"🔄 Retrying {len(failed_versions)} failed downloads...")

    success_count = 0

    for i, failed in enumerate(failed_versions, 1):
        print(f"\n📥 [{i}/{len(failed_versions)}] Retrying: {failed['name']}")

        try:
            # モデル詳細を取得
            model_data = download_service.api_client.get_model_details(
                failed["model_id"]
            )

            # 該当バージョンを見つける
            target_version = None
            for version in model_data.get("modelVersions", []):
                if version.get("id") == failed["version_id"]:
                    target_version = version
                    break

            if not target_version:
                print(f"  ❌ Version not found: {failed['version_id']}")
                continue

            # 再ダウンロード実行
            result = download_service.download_single_version(
                model_data, target_version
            )

            if result["success"]:
                print(f"  ✅ Success: {failed['name']}")
                success_count += 1
            else:
                print(f"  ❌ Failed: {result.get('error', 'Unknown error')}")

        except Exception as e:
            print(f"  ❌ Error: {e}")

    print(f"\n🎉 Retry completed: {success_count}/{len(failed_versions)} successful")

    return success_count == len(failed_versions)


if __name__ == "__main__":
    retry_failed_downloads()
