#!/usr/bin/env python3
"""複数ユーザー/モデルの一括ダウンロードスクリプト."""

import sys
from pathlib import Path
from typing import List, Optional, Dict, Any

from civitai_dl.config import DownloadConfig
from civitai_dl.services.download_service import DownloadService


class BatchDownloader:
    """一括ダウンロード管理クラス."""
    
    def __init__(self, max_user_images: int = 100):
        self.output_dir = r"H:\Civitai\civitai-models"  # ハードコード
        self.max_user_images = max_user_images
        self.stats = {
            "total_users": 0,
            "total_models": 0,
            "processed_models": 0,
            "successful_models": 0,
            "failed_models": 0,
            "total_galleries": 0,
            "successful_galleries": 0,
            "total_user_images": 0,
            "models_by_user": {}
        }
        
        # APIキー読み取り
        api_key_file = Path("api_key.md")
        if not api_key_file.exists():
            raise FileNotFoundError(
                "❌ api_key.md が見つかりません\n"
                "💡 ヒント: api_key.md ファイルを作成してCivitai APIキーを記載してください"
            )
        
        api_key = api_key_file.read_text().strip().split('\n')[0]
        
        # 設定初期化
        self.config = DownloadConfig(
            api_key=api_key,
            is_test=False,
            production_root=self.output_dir,
            max_user_images=max_user_images
        )
        
        self.download_service = DownloadService(self.config)
    
    def extract_username_from_url(self, url: str) -> Optional[str]:
        """URLからユーザー名を抽出."""
        url = url.strip()
        if "civitai.com/user/" in url:
            parts = url.split("civitai.com/user/")
            if len(parts) > 1:
                username = parts[1].split("/")[0].split("?")[0]
                return username
        return None
    
    def read_user_urls(self, filepath: Path = Path("user.txt")) -> List[str]:
        """user.txt からユーザーURLリストを読み込み."""
        if not filepath.exists():
            print(f"❌ ファイルが見つかりません: {filepath}")
            return []
        
        urls = []
        with open(filepath, 'r', encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith('#'):
                    urls.append(line)
        
        return urls
    
    def extract_model_id_from_url(self, url: str) -> Optional[int]:
        """URLからモデルIDを抽出."""
        url = url.strip()
        if "civitai.com/models/" in url:
            parts = url.split("civitai.com/models/")
            if len(parts) > 1:
                # ID部分を抽出（/や?で区切られる前まで）
                id_part = parts[1].split("/")[0].split("?")[0]
                try:
                    return int(id_part)
                except ValueError:
                    pass
        return None
    
    def read_model_urls(self, filepath: Path = Path("models.txt")) -> List[int]:
        """models.txt からモデルURLリストを読み込み、IDに変換."""
        if not filepath.exists():
            print(f"❌ ファイルが見つかりません: {filepath}")
            return []
        
        model_ids = []
        with open(filepath, 'r', encoding='utf-8') as f:
            for line_num, line in enumerate(f, 1):
                line = line.strip()
                if line and not line.startswith('#'):
                    # URLからモデルIDを抽出
                    model_id = self.extract_model_id_from_url(line)
                    if model_id:
                        model_ids.append(model_id)
                    else:
                        # 数値の直接入力もフォールバックとして対応
                        try:
                            model_id = int(line)
                            model_ids.append(model_id)
                            print(f"💡 行{line_num}: モデルID {model_id} を直接指定として処理")
                        except ValueError:
                            print(f"⚠️  行{line_num}: 無効なURL/ID: {line}")
        
        return model_ids
    
    def process_user(self, username: str, user_index: int, total_users: int) -> Dict[str, Any]:
        """単一ユーザーを処理."""
        print(f"\n{'='*70}")
        print(f"📥 ユーザー [{user_index}/{total_users}]: {username}")
        print(f"{'='*70}")
        
        user_stats = {
            "username": username,
            "models_found": 0,
            "models_success": 0,
            "models_failed": 0,
            "galleries_downloaded": 0,
            "user_images_downloaded": 0
        }
        
        try:
            # モデルダウンロード
            print(f"\n📦 モデルを取得中...")
            model_result = self.download_service.download_user_models(username)
            
            if model_result["success"]:
                user_stats["models_found"] = model_result["total_models"]
                user_stats["models_success"] = model_result["successful_downloads"]
                user_stats["models_failed"] = model_result["failed_downloads"]
                
                # ギャラリー画像のカウント
                for model in model_result.get("models", []):
                    for version in model.get("versions", []):
                        gallery_files = [f for f in version.get("downloaded_files", []) 
                                       if f.startswith("Gallery/")]
                        user_stats["galleries_downloaded"] += len(gallery_files)
                
                # 統計更新
                self.stats["total_models"] += user_stats["models_found"]
                self.stats["successful_models"] += user_stats["models_success"]
                self.stats["failed_models"] += user_stats["models_failed"]
                self.stats["successful_galleries"] += user_stats["galleries_downloaded"]
                
                # 残りモデル数を表示
                remaining = self.stats["total_models"] - self.stats["processed_models"]
                print(f"\n📊 進捗状況:")
                print(f"   処理済み: {self.stats['processed_models']}/{self.stats['total_models']} モデル")
                print(f"   残り: {remaining} モデル")
                
                self.stats["processed_models"] += user_stats["models_found"]
            
            # ユーザー画像ダウンロード
            print(f"\n🖼️  ユーザー画像をダウンロード中...")
            image_result = self.download_service.download_user_images(username)
            
            if image_result["success"]:
                user_stats["user_images_downloaded"] = image_result["downloaded_images"]
                self.stats["total_user_images"] += user_stats["user_images_downloaded"]
            
            # ユーザー統計を保存
            self.stats["models_by_user"][username] = user_stats
            
            # ユーザーサマリー
            print(f"\n✅ ユーザー {username} の処理完了:")
            print(f"   モデル: {user_stats['models_success']}/{user_stats['models_found']} 成功")
            print(f"   ギャラリー画像: {user_stats['galleries_downloaded']} 枚")
            print(f"   ユーザー画像: {user_stats['user_images_downloaded']} 枚")
            
        except Exception as e:
            print(f"❌ エラー: {e}")
            
        return user_stats
    
    def process_model(self, model_id: int, model_index: int, total_models: int) -> Dict[str, Any]:
        """単一モデルを処理."""
        print(f"\n{'='*70}")
        print(f"📥 モデル [{model_index}/{total_models}]: ID {model_id}")
        print(f"{'='*70}")
        
        model_stats = {
            "model_id": model_id,
            "success": False,
            "versions": 0,
            "galleries_downloaded": 0
        }
        
        try:
            result = self.download_service.download_model_by_id(model_id)
            
            if result["success"]:
                model_stats["success"] = True
                model_stats["versions"] = len(result.get("versions", []))
                
                # ギャラリー画像のカウント
                for version in result.get("versions", []):
                    gallery_files = [f for f in version.get("downloaded_files", []) 
                                   if f.startswith("Gallery/")]
                    model_stats["galleries_downloaded"] += len(gallery_files)
                
                self.stats["successful_models"] += 1
                self.stats["successful_galleries"] += model_stats["galleries_downloaded"]
            else:
                self.stats["failed_models"] += 1
            
            self.stats["processed_models"] += 1
            
            # 進捗表示
            remaining = total_models - model_index
            print(f"\n📊 進捗状況:")
            print(f"   処理済み: {model_index}/{total_models} モデル")
            print(f"   残り: {remaining} モデル")
            
        except Exception as e:
            print(f"❌ エラー: {e}")
            self.stats["failed_models"] += 1
            
        return model_stats
    
    def run_user_batch(self):
        """user.txt から一括処理."""
        urls = self.read_user_urls()
        if not urls:
            print("❌ 処理するユーザーURLが見つかりません")
            return
        
        self.stats["total_users"] = len(urls)
        print(f"📋 {len(urls)} 件のユーザーを処理します")
        print(f"📁 保存先: {self.output_dir}")
        print(f"🖼️  ユーザー画像の最大ダウンロード数: {self.max_user_images}")
        
        for i, url in enumerate(urls, 1):
            username = self.extract_username_from_url(url)
            if not username:
                print(f"\n❌ 無効なURL: {url}")
                continue
            
            self.process_user(username, i, len(urls))
        
        self.print_final_stats()
    
    def run_model_batch(self):
        """models.txt から一括処理."""
        model_ids = self.read_model_urls()
        if not model_ids:
            print("❌ 処理するモデルURL/IDが見つかりません")
            return
        
        self.stats["total_models"] = len(model_ids)
        print(f"📋 {len(model_ids)} 件のモデルを処理します")
        print(f"📁 保存先: {self.output_dir}")
        
        for i, model_id in enumerate(model_ids, 1):
            self.process_model(model_id, i, len(model_ids))
        
        self.print_final_stats()
    
    def print_final_stats(self):
        """最終統計を表示."""
        print(f"\n{'='*70}")
        print(f"🎉 一括ダウンロード完了!")
        print(f"{'='*70}")
        print(f"📊 最終統計:")
        print(f"   保存先: {self.output_dir}")
        
        if self.stats["total_users"] > 0:
            print(f"\n👥 ユーザー統計:")
            print(f"   処理ユーザー数: {self.stats['total_users']}")
            
            for username, user_stats in self.stats["models_by_user"].items():
                print(f"\n   {username}:")
                print(f"     - モデル: {user_stats['models_success']}/{user_stats['models_found']} 成功")
                print(f"     - ギャラリー画像: {user_stats['galleries_downloaded']} 枚")
                print(f"     - ユーザー画像: {user_stats['user_images_downloaded']} 枚")
        
        print(f"\n📦 モデル統計:")
        print(f"   総モデル数: {self.stats['total_models']}")
        print(f"   成功: {self.stats['successful_models']}")
        print(f"   失敗: {self.stats['failed_models']}")
        print(f"   成功率: {self.stats['successful_models']/max(1, self.stats['total_models'])*100:.1f}%")
        
        print(f"\n🖼️  画像統計:")
        print(f"   ギャラリー画像: {self.stats['successful_galleries']} 枚")
        print(f"   ユーザー画像: {self.stats['total_user_images']} 枚")
        print(f"   合計: {self.stats['successful_galleries'] + self.stats['total_user_images']} 枚")


def main():
    """メイン処理."""
    import argparse
    
    parser = argparse.ArgumentParser(description="Civitai一括ダウンロードツール")
    parser.add_argument("--models", action="store_true", 
                       help="models.txt からモデルURLを読み込んでダウンロード")
    parser.add_argument("--max-images", type=int, default=100,
                       help="ユーザー画像の最大ダウンロード数 (default: 100)")
    
    args = parser.parse_args()
    
    try:
        downloader = BatchDownloader(max_user_images=args.max_images)
        
        if args.models:
            # models.txt からモデルURLを読み込んでダウンロード
            downloader.run_model_batch()
        else:
            # user.txt からユーザーURLを読み込んでダウンロード（デフォルト）
            downloader.run_user_batch()
            
    except FileNotFoundError as e:
        print(str(e))
        sys.exit(1)
    except Exception as e:
        print(f"❌ エラーが発生しました: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()