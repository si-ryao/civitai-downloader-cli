"""CLI interface for Civitai Downloader."""

import sys
from pathlib import Path
from typing import List, Optional

import click

from .config import DownloadConfig


def parse_user_list(file_path: Path) -> List[str]:
    """Parse user list file and extract usernames.
    
    Args:
        file_path: Path to the user list file
        
    Returns:
        List of usernames to download
    """
    users = []
    with open(file_path, 'r', encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            # Skip empty lines and comments
            if not line or line.startswith('#'):
                continue
            
            # Extract username from URL format
            if line.startswith('https://civitai.com/user/'):
                username = line.replace('https://civitai.com/user/', '')
            else:
                username = line
            
            if username:
                users.append(username)
    
    return users


def parse_base_model_filter(file_path: Path) -> List[str]:
    """Parse base model filter file and extract allowed base models.
    
    Args:
        file_path: Path to the base model filter file
        
    Returns:
        List of allowed base model names (case-insensitive)
    """
    base_models = []
    with open(file_path, 'r', encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            # Skip empty lines and comments
            if not line or line.startswith('#'):
                continue
            
            # Add base model name (normalize case)
            base_model = line.strip()
            if base_model:
                base_models.append(base_model)
    
    return base_models


@click.command()
@click.option("--user", "-u", help="Civitai username to download models from")
@click.option("--model", "-m", type=int, help="Specific model ID to download")
@click.option(
    "--user-list",
    type=click.Path(exists=True, path_type=Path),
    help="File containing list of users to download (one per line)",
)
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
    default=1000,
    help="Maximum number of user images to download (default: 1000)",
)
@click.option(
    "--parallel-mode",
    is_flag=True,
    help="Enable parallel processing mode (Phase 2 features)",
)
@click.option(
    "--skip-existing",
    is_flag=True,
    help="Skip downloading files that already exist (images only, models always verify SHA256)",
)
@click.option(
    "--base-model-filter",
    type=click.Path(exists=True, path_type=Path),
    help="Filter models by base model using whitelist file (one base model per line, e.g., 'Illustrious', 'Pony')",
)
def main(
    user: Optional[str] = None,
    model: Optional[int] = None,
    user_list: Optional[Path] = None,
    token: Optional[str] = None,
    output: Optional[Path] = None,
    test_mode: bool = False,
    verbose: bool = False,
    max_images: int = 1000,
    parallel_mode: bool = False,
    skip_existing: bool = False,
    base_model_filter: Optional[Path] = None,
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
        if not user and not model and not user_list:
            click.echo("Error: Must specify either --user, --model, or --user-list", err=True)
            sys.exit(1)

        # 複数のオプションが指定されている場合はエラー
        options_count = sum(bool(opt) for opt in [user, model, user_list])
        if options_count > 1:
            click.echo("Error: Cannot specify multiple options (--user, --model, --user-list) at the same time", err=True)
            sys.exit(1)

        # ベースモデルフィルター読み込み
        allowed_base_models = None
        if base_model_filter:
            try:
                allowed_base_models = parse_base_model_filter(base_model_filter)
                click.echo(f"🔍 Base model filter loaded: {len(allowed_base_models)} models allowed")
                if verbose:
                    click.echo(f"   Allowed base models: {', '.join(allowed_base_models)}")
            except Exception as e:
                click.echo(f"Error: Failed to load base model filter: {e}", err=True)
                sys.exit(1)

        # ダウンローダー実行
        if parallel_mode:
            from .services.parallel_download_service import ParallelDownloadService
            download_service = ParallelDownloadService(config, skip_existing=skip_existing, base_model_filter=allowed_base_models)
            if verbose:
                click.echo("🚀 Using parallel processing mode (Phase 2)")
                if skip_existing:
                    click.echo("⏭️  Skip existing files enabled")
                if allowed_base_models:
                    click.echo(f"🔍 Base model filter active: {len(allowed_base_models)} models allowed")
        else:
            from .services.download_service import DownloadService
            download_service = DownloadService(config, skip_existing=skip_existing, base_model_filter=allowed_base_models)
            if verbose:
                click.echo("🔄 Using standard processing mode")
                if skip_existing:
                    click.echo("⏭️  Skip existing files enabled")
                if allowed_base_models:
                    click.echo(f"🔍 Base model filter active: {len(allowed_base_models)} models allowed")

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

        elif user_list:
            # ユーザーリストからユーザー名を取得
            users = parse_user_list(user_list)
            
            if not users:
                click.echo("⚠️  No valid users found in the user list file", err=True)
                sys.exit(1)
            
            click.echo(f"📋 Found {len(users)} users to download")
            click.echo(f"👥 Users: {', '.join(users[:5])}{'...' if len(users) > 5 else ''}")
            click.echo("="*50)
            
            # 各ユーザーのダウンロード結果を記録
            successful_users = []
            failed_users = []
            
            for idx, username in enumerate(users, 1):
                click.echo(f"\n[{idx}/{len(users)}] 📥 Processing user: {username}")
                click.echo("-"*40)
                
                try:
                    # モデルダウンロード
                    model_result = download_service.download_user_models(username)
                    
                    if model_result["success"]:
                        click.echo(f"✅ Models: {model_result['successful_downloads']}/{model_result['total_models']} downloaded")
                        
                        # ユーザー画像ダウンロード
                        click.echo("🖼️  Downloading user images...")
                        image_result = download_service.download_user_images(username)
                        
                        if image_result["success"]:
                            click.echo(f"✅ Images: {image_result['downloaded_images']}/{image_result['total_images']} downloaded")
                            successful_users.append(username)
                        else:
                            click.echo(f"⚠️  Images failed: {image_result.get('message', 'Unknown error')}")
                            # 画像失敗でもユーザーは成功扱い（モデルがダウンロードできているため）
                            successful_users.append(username)
                    else:
                        click.echo(f"❌ Failed: {model_result.get('message', 'Unknown error')}")
                        failed_users.append((username, model_result.get('message', 'Unknown error')))
                        
                except Exception as e:
                    click.echo(f"❌ Error processing user: {str(e)}")
                    failed_users.append((username, str(e)))
            
            # 最終結果のサマリー
            click.echo("\n" + "="*50)
            click.echo("📊 BATCH DOWNLOAD SUMMARY")
            click.echo("="*50)
            click.echo(f"✅ Successful: {len(successful_users)}/{len(users)} users")
            if successful_users:
                click.echo(f"   Users: {', '.join(successful_users[:10])}{'...' if len(successful_users) > 10 else ''}")
            
            if failed_users:
                click.echo(f"\n❌ Failed: {len(failed_users)} users")
                for username, error in failed_users[:5]:  # 最初の5件のみ表示
                    click.echo(f"   - {username}: {error}")
                if len(failed_users) > 5:
                    click.echo(f"   ... and {len(failed_users) - 5} more")
            
            # 一部でも成功していれば正常終了
            if successful_users:
                click.echo("\n✅ Batch download completed!")
            else:
                click.echo("\n❌ All downloads failed!")
                sys.exit(1)

    except Exception as e:
        click.echo(f"Error: {e}", err=True)
        sys.exit(1)


if __name__ == "__main__":
    main()
