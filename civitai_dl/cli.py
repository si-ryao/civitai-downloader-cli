"""CLI interface for Civitai Downloader."""

import sys
from pathlib import Path
from typing import Optional

import click

from .config import DownloadConfig


@click.command()
@click.option("--user", "-u", help="Civitai username to download models from")
@click.option("--model", "-m", type=int, help="Specific model ID to download")
@click.option(
    "--token", "-t", help="Civitai API token (or set CIVITAI_API_KEY env var)"
)
@click.option(
    "--output",
    "-o",
    type=click.Path(path_type=Path),
    help="Output directory (default: H:\\Civitai\\civitai-models)",
)
@click.option(
    "--test-mode", is_flag=True, help="Run in test mode (save to ./test_downloads/)"
)
@click.option("--verbose", "-v", is_flag=True, help="Enable verbose logging")
@click.option(
    "--max-images",
    type=int,
    default=50,
    help="Maximum number of user images to download (default: 50)",
)
def main(
    user: Optional[str] = None,
    model: Optional[int] = None,
    token: Optional[str] = None,
    output: Optional[Path] = None,
    test_mode: bool = False,
    verbose: bool = False,
    max_images: int = 50,
) -> None:
    """Civitai model and image downloader with tag-based organization."""

    try:
        # APIキーを確認（api_key.mdから読み取り可能）
        if not token:
            api_key_file = Path(__file__).parent.parent / "api_key.md"
            if api_key_file.exists():
                token = api_key_file.read_text().strip().split("\n")[0]

        # 設定初期化
        config = DownloadConfig(
            api_key=token, is_test=test_mode, max_user_images=max_images
        )

        if output:
            if test_mode:
                config.test_root = str(output)
            else:
                config.production_root = str(output)

        # 設定検証
        config.validate()

        if verbose:
            click.echo(f"Using API key: {config.api_key[:8]}...")
            click.echo(f"Output directory: {config.root_dir}")
            click.echo(f"Test mode: {config.is_test}")

        # 引数検証
        if not user and not model:
            click.echo("Error: Must specify either --user or --model", err=True)
            sys.exit(1)

        if user and model:
            click.echo("Error: Cannot specify both --user and --model", err=True)
            sys.exit(1)

        # ダウンローダー実行
        from .services.download_service import DownloadService

        download_service = DownloadService(config)

        if user:
            click.echo(f"📥 Starting download for user: {user}")

            # モデルダウンロード
            model_result = download_service.download_user_models(user)

            if model_result["success"]:
                click.echo("✅ Models download completed!")
                click.echo(
                    f"   📊 Models: {model_result['successful_downloads']}/{model_result['total_models']} downloaded"
                )
            else:
                click.echo(
                    f"❌ Models download failed: {model_result.get('message', 'Unknown error')}"
                )
                sys.exit(1)

            # ユーザー画像ダウンロード
            click.echo("🖼️  Starting user images download...")
            image_result = download_service.download_user_images(user)

            if image_result["success"]:
                click.echo("✅ User images download completed!")
                click.echo(
                    f"   📸 Images: {image_result['downloaded_images']}/{image_result['total_images']} downloaded"
                )
                click.echo(f"   📁 Saved to: {image_result['images_dir']}")
            else:
                click.echo(
                    f"⚠️  User images download failed: {image_result.get('message', 'Unknown error')}"
                )
                # 画像ダウンロード失敗は全体の失敗にはしない

        elif model:
            click.echo(f"📥 Downloading model ID: {model}")
            result = download_service.download_model_by_id(model)

            if result["success"]:
                click.echo("✅ Download completed successfully!")
                click.echo(f"   📊 Model: {result['model_name']}")
                click.echo(f"   🏷️  Category: {result['category']}")
                click.echo(f"   📁 Versions: {len(result['versions'])}")
            else:
                click.echo(
                    f"❌ Download failed: {result.get('message', 'Unknown error')}"
                )
                sys.exit(1)

    except Exception as e:
        click.echo(f"Error: {e}", err=True)
        sys.exit(1)


if __name__ == "__main__":
    main()
