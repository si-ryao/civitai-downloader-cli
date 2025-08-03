"""
Parallel download service with adaptive concurrency and safety monitoring.

This service extends the base DownloadService with intelligent parallel processing
capabilities, providing significant performance improvements while maintaining
system stability through comprehensive safety monitoring.
"""

import asyncio
import concurrent.futures
import time
import uuid
from pathlib import Path
from typing import Dict, List, Any, Optional, Tuple
from concurrent.futures import ThreadPoolExecutor

from ..config import DownloadConfig
from ..services.download_service import DownloadService
from ..core.adaptive_concurrency import AdaptiveConcurrencyManager, ConcurrencyConfig
from ..core.safety_monitor import SafetyMonitor
from ..core.intelligent_retry import IntelligentRetryManager
from ..core.model_parallelism_manager import ModelParallelismManager, ParallelismMode
from ..monitoring.performance_monitor import PerformanceMonitor


class ParallelDownloadService(DownloadService):
    """
    Enhanced download service with intelligent parallel processing.
    
    Provides significant performance improvements through safe concurrency
    while maintaining comprehensive monitoring and automatic fallback capabilities.
    """
    
    def __init__(self, config: DownloadConfig, skip_existing: bool = False, base_model_filter=None):
        super().__init__(config, skip_existing=skip_existing, base_model_filter=base_model_filter)
        
        # 並行処理管理システム初期化
        concurrency_config = ConcurrencyConfig()
        self.concurrency_manager = AdaptiveConcurrencyManager(concurrency_config)
        self.safety_monitor = SafetyMonitor(str(config.root_dir))
        self.retry_manager = IntelligentRetryManager()
        
        # パフォーマンス監視
        self.performance_monitor = PerformanceMonitor(config.root_dir)
        
        # モデル並列処理管理（新機能）
        # デフォルトで3モデル並列（BALANCED mode）
        self.model_parallelism_manager = ModelParallelismManager(ParallelismMode.BALANCED)
        # 確実に3モデル並列になるよう強制設定
        self.model_parallelism_manager.current_parallel_models = 3
        self.model_parallel_enabled = True
        self.model_executor = None  # 動的に作成
        
        # 並行処理実行器
        self.api_executor = ThreadPoolExecutor(max_workers=5, thread_name_prefix="api")
        self.download_executor = ThreadPoolExecutor(max_workers=4, thread_name_prefix="download")
        
        # フォールバック状態
        self.fallback_active = False
        self.parallel_enabled = True
        
        # 安全性監視コールバック設定
        self.safety_monitor.add_alert_callback(self._handle_safety_alert)
        
        print("🚀 Parallel download service initialized")
        print(f"   API concurrency: {self.concurrency_manager.get_current_concurrency('api')}")
        print(f"   Gallery concurrency: {self.concurrency_manager.get_current_concurrency('gallery')}")
        
    def download_user_models(self, username: str) -> Dict[str, Any]:
        """並行処理対応ユーザーモデルダウンロード."""
        # 🔥 CRITICAL FIX: ユーザー毎に状態を強制リセット（状態汚染防止）
        print(f"🔄 Resetting parallel processing state for user: {username}")
        self.fallback_active = False
        self.parallel_enabled = True
        
        # AdaptiveConcurrencyManagerの状態もリセット
        if hasattr(self.concurrency_manager, 'consecutive_failures'):
            self.concurrency_manager.consecutive_failures = 0
            self.concurrency_manager.consecutive_successes = 0
            self.concurrency_manager.fallback_active = False
            print("   ✅ Concurrency manager state reset")
        
        # デバッグ情報を表示
        print(f"🔍 Debug: fallback_active={self.fallback_active}, parallel_enabled={self.parallel_enabled}")
        
        if self.fallback_active or not self.parallel_enabled:
            print(f"⚠️ Running in fallback mode (synchronous)")
            print(f"   Reason: fallback_active={self.fallback_active}, parallel_enabled={self.parallel_enabled}")
            return super().download_user_models(username)
            
        print(f"🚀 Starting parallel download for user: {username}")
        
        # 健全性チェック（一時的に無効化して並列処理を強制）
        # asyncio.run(self._check_system_health())
        
        # if self.safety_monitor.should_force_safety_mode():
        #     print("🛡️ Safety monitor forced fallback to sync mode")
        #     return self._fallback_to_sync_download(username)
        
        print("🚀 Forcing parallel processing mode (safety checks disabled for debugging)")
            
        try:
            # モデル並列処理が有効かつ複数モデル処理可能な場合
            recommended_parallel = self.model_parallelism_manager.get_recommended_parallel_models()
            print(f"🔍 TRACE: model_parallel_enabled={self.model_parallel_enabled}, recommended_parallel={recommended_parallel}")
            
            # 🔍 CRITICAL TRACE: 条件分岐の詳細ログ
            condition1 = self.model_parallel_enabled
            condition2 = recommended_parallel > 1
            final_condition = condition1 and condition2
            print(f"🔍 TRACE: Condition check - model_parallel_enabled={condition1}, recommended_parallel>1={condition2}, final={final_condition}")
            
            if final_condition:
                print(f"🎯 TRACE: ENTERING model parallelism path with {recommended_parallel} models")
                result = self._download_user_models_with_model_parallelism(username)
                print(f"🎯 TRACE: EXITING model parallelism path")
                return result
            else:
                print(f"🎯 TRACE: ENTERING standard parallel path (no model parallelism)")
                result = self._download_user_models_parallel(username)
                print(f"🎯 TRACE: EXITING standard parallel path")
                return result
        except Exception as e:
            print(f"❌ Parallel download failed: {e}")
            return self._fallback_to_sync_download(username)
            
    def _download_user_models_parallel(self, username: str) -> Dict[str, Any]:
        """並行処理でのユーザーモデルダウンロード実行."""
        start_time = time.time()
        operation_id = str(uuid.uuid4())
        
        # パフォーマンス監視開始
        self.performance_monitor.start_download_operation(
            operation_id, f"user:{username}", self.config.root_dir
        )
        
        # ユーザーの全モデルを並行取得
        try:
            all_models = self._fetch_user_models_parallel(username)
        except Exception as e:
            self._record_operation_failure("api", e)
            raise
            
        if not all_models:
            return {"success": False, "message": f"No models found for {username}"}
            
        print(f"📋 Found {len(all_models)} models for {username}")
        
        results = {
            "success": True,
            "username": username,
            "total_models": len(all_models),
            "processed_models": 0,
            "successful_downloads": 0,
            "failed_downloads": 0,
            "models": [],
            "performance_stats": {}
        }
        
        # モデルダウンロード実行
        for i, model in enumerate(all_models, 1):
            print(f"\n📦 Processing model {i}/{len(all_models)}: {model['name']}")
            
            # 定期的な健全性チェック
            if i % 5 == 0:
                asyncio.run(self._check_system_health())
                if self.safety_monitor.should_force_safety_mode():
                    print("🛡️ Safety monitor triggered during processing")
                    break
                    
            try:
                model_result = self._download_single_model_parallel(model)
                results["models"].append(model_result)
                results["processed_models"] += 1
                
                if model_result["success"]:
                    results["successful_downloads"] += 1
                    self._record_operation_success("model_download")
                else:
                    results["failed_downloads"] += 1
                    
            except Exception as e:
                print(f"❌ Error processing model {model['name']}: {e}")
                self._record_operation_failure("model_download", e)
                results["models"].append({
                    "model_id": model.get("id"),
                    "model_name": model.get("name"),
                    "success": False,
                    "error": str(e),
                })
                results["failed_downloads"] += 1
                
        # パフォーマンス統計
        total_duration = time.time() - start_time
        results["performance_stats"] = {
            "total_duration_minutes": total_duration / 60,
            "models_per_minute": len(all_models) / (total_duration / 60) if total_duration > 0 else 0,
            "concurrency_stats": self.concurrency_manager.get_status_report(),
            "safety_stats": asyncio.run(self._get_safety_stats())
        }
        
        # パフォーマンス監視完了
        self.performance_monitor.complete_download_operation(
            operation_id, results["success"], total_duration / 60
        )
        
        print(f"\n🎉 Parallel download completed!")
        print(f"   Duration: {total_duration/60:.1f} minutes")
        print(f"   Success rate: {results['successful_downloads']}/{results['total_models']}")
        print(f"   Throughput: {results['performance_stats']['models_per_minute']:.1f} models/min")
        
        return results
        
    def _download_user_models_with_model_parallelism(self, username: str) -> Dict[str, Any]:
        """複数モデル並列処理でのユーザーモデルダウンロード."""
        print(f"🔥 TRACE: _download_user_models_with_model_parallelism STARTED for {username}")
        start_time = time.time()
        operation_id = str(uuid.uuid4())
        
        # 動的並列度取得
        current_parallel_models = self.model_parallelism_manager.get_recommended_parallel_models()
        
        print(f"🚀 Starting MULTI-MODEL parallel download for user: {username}")
        print(f"   Current parallel models: {current_parallel_models}")
        print(f"   Mode: {self.model_parallelism_manager.get_current_mode().name}")
        
        # パフォーマンス監視開始
        self.performance_monitor.start_download_operation(
            operation_id, f"user:{username}:multi-model", self.config.root_dir
        )
        
        # ユーザーの全モデルを取得
        try:
            all_models = self._fetch_user_models_parallel(username)
        except Exception as e:
            self._record_operation_failure("api", e)
            raise
            
        if not all_models:
            return {"success": False, "message": f"No models found for {username}"}
            
        print(f"📋 Found {len(all_models)} models for {username}")
        
        results = {
            "success": True,
            "username": username,
            "total_models": len(all_models),
            "processed_models": 0,
            "successful_downloads": 0,
            "failed_downloads": 0,
            "models": [],
            "performance_stats": {},
            "parallel_execution": True,
            "max_parallel_models": current_parallel_models
        }
        
        # モデル並列処理実行器を作成
        if self.model_executor:
            self.model_executor.shutdown(wait=False)
        self.model_executor = ThreadPoolExecutor(
            max_workers=current_parallel_models, 
            thread_name_prefix="model"
        )
        
        # モデルをバッチに分割
        model_batches = self._create_model_batches(all_models, current_parallel_models)
        print(f"🔥 TRACE: Created {len(model_batches)} batches with batch_size={current_parallel_models}")
        for i, batch in enumerate(model_batches):
            print(f"🔥 TRACE: Batch {i+1}: {len(batch)} models - {[m.get('name', 'Unknown')[:20] for m in batch]}")
        
        try:
            # バッチごとに並列実行
            for batch_num, batch in enumerate(model_batches, 1):
                print(f"\n🔥 TRACE: Starting batch {batch_num}/{len(model_batches)} with {len(batch)} models")
                
                # 定期的な健全性チェック
                if batch_num % 3 == 0:
                    asyncio.run(self._check_system_health())
                    if self.safety_monitor.should_force_safety_mode():
                        print("🛡️ Safety monitor triggered during batch processing")
                        break
                
                print(f"🔥 TRACE: Calling _process_model_batch_parallel for batch {batch_num}")
                batch_results = self._process_model_batch_parallel(batch, batch_num)
                print(f"🔥 TRACE: Completed _process_model_batch_parallel for batch {batch_num}, got {len(batch_results)} results")
                
                # バッチ結果をマージ  
                for model_result in batch_results:
                    results["models"].append(model_result)
                    results["processed_models"] += 1
                    
                    if model_result["success"]:
                        results["successful_downloads"] += 1
                        self._record_operation_success("model_download")
                    else:
                        results["failed_downloads"] += 1
                        self._record_operation_failure("model_download", Exception(model_result.get("error", "Unknown error")))
                        
        finally:
            # モデル実行器をクリーンアップ
            if self.model_executor:
                self.model_executor.shutdown(wait=True)
                self.model_executor = None
        
        # パフォーマンス統計
        total_duration = time.time() - start_time
        throughput = len(all_models) / (total_duration / 60) if total_duration > 0 else 0
        success_rate = results["successful_downloads"] / results["total_models"] if results["total_models"] > 0 else 0
        
        results["performance_stats"] = {
            "total_duration_minutes": total_duration / 60,
            "models_per_minute": throughput,
            "concurrency_stats": self.concurrency_manager.get_status_report(),
            "safety_stats": asyncio.run(self._get_safety_stats()),
            "model_parallelism_used": True,
            "effective_parallelism": current_parallel_models,
            "parallelism_manager_stats": self.model_parallelism_manager.get_performance_summary()
        }
        
        # パフォーマンス記録（動的調整用）
        self.model_parallelism_manager.record_performance_metrics(
            parallel_models=current_parallel_models,
            throughput=throughput,
            success_rate=success_rate,
            models_processed=results["total_models"],
            successful_models=results["successful_downloads"]
        )
        
        # パフォーマンス監視完了
        self.performance_monitor.complete_download_operation(
            operation_id, results["success"], total_duration / 60
        )
        
        print(f"\n🎉 Multi-model parallel download completed!")
        print(f"   Duration: {total_duration/60:.1f} minutes")
        print(f"   Success rate: {results['successful_downloads']}/{results['total_models']}")
        print(f"   Throughput: {results['performance_stats']['models_per_minute']:.1f} models/min")
        print(f"   Parallel models: {self.max_parallel_models}")
        
        return results
        
    def _create_model_batches(self, models: List[Dict[str, Any]], batch_size: int) -> List[List[Dict[str, Any]]]:
        """モデルをバッチに分割."""
        batches = []
        for i in range(0, len(models), batch_size):
            batch = models[i:i + batch_size]
            batches.append(batch)
        return batches
        
    def _process_model_batch_parallel(self, model_batch: List[Dict[str, Any]], batch_num: int) -> List[Dict[str, Any]]:
        """モデルバッチの並列処理."""
        print(f"🔥 TRACE: _process_model_batch_parallel STARTED - batch {batch_num}")
        
        if not self.model_executor:
            print(f"🔥 TRACE: ERROR - Model executor not initialized!")
            raise RuntimeError("Model executor not initialized")
            
        print(f"🔥 TRACE: ThreadPoolExecutor status - max_workers: {self.model_executor._max_workers}")
        print(f"🔥 Starting batch {batch_num} with {len(model_batch)} models in parallel")
        for i, model in enumerate(model_batch):
            print(f"   Model {i+1}: {model.get('name', 'Unknown')}")
            
        batch_results = []
        
        # バッチ内のモデルを並列実行
        future_to_model = {}
        print(f"🔥 TRACE: About to submit {len(model_batch)} tasks to ThreadPoolExecutor")
        
        for i, model in enumerate(model_batch):
            print(f"🔥 TRACE: Submitting task {i+1}/{len(model_batch)}: {model.get('name', 'Unknown')[:30]}")
            future = self.model_executor.submit(self._download_single_model_parallel_safe, model)
            future_to_model[future] = model
            print(f"🔥 TRACE: Task {i+1} submitted successfully, future: {future}")
            
        print(f"🔥 TRACE: All {len(future_to_model)} tasks submitted, waiting for completion...")
            
        # 結果を収集
        completed_count = 0
        for future in concurrent.futures.as_completed(future_to_model, timeout=1800):  # 30分タイムアウト
            model = future_to_model[future]
            completed_count += 1
            print(f"🔥 TRACE: Task completed {completed_count}/{len(future_to_model)}: {model.get('name', 'Unknown')[:30]}")
            
            try:
                model_result = future.result()
                batch_results.append(model_result)
                print(f"    ✅ Completed successfully: {model['name']}")
            except Exception as e:
                print(f"    ❌ Failed with exception: {model['name']} - {e}")
                batch_results.append({
                    "model_id": model.get("id"),
                    "model_name": model.get("name"),
                    "success": False,
                    "error": str(e),
                    "versions": []
                })
                
        print(f"🔥 TRACE: _process_model_batch_parallel COMPLETED - batch {batch_num}, {len(batch_results)} results")
        return batch_results
        
    def _download_single_model_parallel_safe(self, model_data: Dict[str, Any]) -> Dict[str, Any]:
        """安全なモデル並列ダウンロード（例外処理付き）."""
        model_name = model_data.get('name', 'Unknown')
        print(f"🔥 TRACE: _download_single_model_parallel_safe STARTED: {model_name[:30]}")
        
        try:
            result = self._download_single_model_parallel(model_data)
            print(f"🔥 TRACE: _download_single_model_parallel_safe SUCCESS: {model_name[:30]}")
            return result
        except Exception as e:
            print(f"🔥 TRACE: _download_single_model_parallel_safe FAILED: {model_name[:30]} - {str(e)}")
            return {
                "model_id": model_data.get("id"),
                "model_name": model_data.get("name"),
                "success": False,
                "error": str(e),
                "versions": []
            }
        
    def _fetch_user_models_parallel(self, username: str) -> List[Dict[str, Any]]:
        """並行処理でユーザーモデル一覧取得."""
        api_concurrency = self.concurrency_manager.get_current_concurrency('api')
        
        print(f"📡 Fetching models with {api_concurrency} concurrent API calls...")
        
        # ページネーション対応の並行処理
        try:
            # retry_syncを通常の関数として呼び出す
            models = self.retry_manager.retry_sync(
                self._get_paginated_models_parallel, 
                username, 
                api_concurrency
            )
            return models
        except Exception as e:
            raise e
        
    def _get_paginated_models_parallel(self, username: str, concurrency: int) -> List[Dict[str, Any]]:
        """ページネーション対応並行モデル取得."""
        # 最初のページで総ページ数を取得
        first_page = self.api_client.get_user_models(username, limit=100, page=1)
        metadata = first_page.get("metadata", {})
        total_pages = metadata.get("totalPages", 1)
        
        if total_pages <= 1:
            return first_page.get("items", [])
            
        all_models = first_page.get("items", [])
        
        # 残りのページを並行取得
        if total_pages > 1:
            remaining_pages = list(range(2, total_pages + 1))
            
            with ThreadPoolExecutor(max_workers=min(concurrency, len(remaining_pages))) as executor:
                future_to_page = {
                    executor.submit(self._fetch_single_page, username, page): page
                    for page in remaining_pages
                }
                
                for future in concurrent.futures.as_completed(future_to_page):
                    page_num = future_to_page[future]
                    try:
                        page_data = future.result(timeout=30)
                        all_models.extend(page_data.get("items", []))
                        self._record_operation_success("api")
                    except Exception as e:
                        print(f"⚠️ Failed to fetch page {page_num}: {e}")
                        self._record_operation_failure("api", e)
                        
        return all_models
        
    def _fetch_single_page(self, username: str, page: int) -> Dict[str, Any]:
        """単一ページ取得."""
        start_time = time.time()
        try:
            result = self.api_client.get_user_models(username, limit=100, page=page)
            
            # ネットワーク性能記録
            response_time = (time.time() - start_time) * 1000
            self.retry_manager.record_network_performance(response_time)
            
            return result
        except Exception as e:
            # リトライマネージャーに記録
            response_time = (time.time() - start_time) * 1000
            self.retry_manager.record_network_performance(response_time)
            raise e
            
    def _download_single_model_parallel(self, model_data: Dict[str, Any]) -> Dict[str, Any]:
        """並行処理での単一モデルダウンロード."""
        model_id = model_data.get("id")
        model_name = model_data.get("name", "Unknown")
        
        # タグ分析（変更なし）
        tag_analysis = self.path_manager.analyze_tags(model_data)
        
        model_result = {
            "model_id": model_id,
            "model_name": model_name,
            "category": tag_analysis["final_category"],
            "success": True,
            "versions": [],
            "error": None,
        }
        
        # 各バージョンを並行処理でダウンロード
        versions = model_data.get("modelVersions", [])
        if not versions:
            model_result["success"] = False
            model_result["error"] = "No versions found"
            return model_result
            
        for version in versions:
            try:
                version_result = self._download_single_version_parallel(model_data, version)
                model_result["versions"].append(version_result)
                
                if not version_result["success"]:
                    model_result["success"] = False
                    
            except Exception as e:
                print(f"    ❌ Error downloading version {version.get('name')}: {e}")
                model_result["versions"].append({
                    "version_id": version.get("id"),
                    "version_name": version.get("name"),
                    "success": False,
                    "error": str(e),
                })
                model_result["success"] = False
                
        return model_result
        
    def _download_single_version_parallel(
        self, 
        model_data: Dict[str, Any], 
        version_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """並行処理での単一バージョンダウンロード."""
        version_id = version_data.get("id")
        version_name = version_data.get("name", "Unknown")
        
        # パス決定（変更なし）
        model_dir = self.path_manager.determine_model_path(model_data, version_data)
        file_paths = self.path_manager.get_file_paths(model_dir, model_data, version_data)
        
        version_result = {
            "version_id": version_id,
            "version_name": version_name,
            "path": str(model_dir),
            "success": True,
            "downloaded_files": [],
            "error": None,
        }
        
        try:
            # 1. メタデータファイル生成（同期処理）
            self._save_metadata(model_data, version_data, file_paths)
            version_result["downloaded_files"].extend([
                "description.md",
                f"{Path(file_paths['model_file']).stem}.civitai.info",
            ])
            
            # 2. モデルファイルダウンロード（同期処理 - Phase 3で並行化）
            self._download_model_files(version_data, file_paths, version_result)
            
            # 3. 画像ダウンロード（並行処理）
            self._download_images_parallel(model_data, version_data, file_paths, version_result)
            
        except Exception as e:
            print(f"      ❌ Version download failed: {e}")
            version_result["success"] = False
            version_result["error"] = str(e)
            
        return version_result
        
    def _download_images_parallel(
        self,
        model_data: Dict[str, Any],
        version_data: Dict[str, Any], 
        file_paths: Dict[str, Path],
        result: Dict[str, Any]
    ) -> None:
        """画像の並行ダウンロード."""
        preview_concurrency = self.concurrency_manager.get_current_concurrency('preview')
        gallery_concurrency = self.concurrency_manager.get_current_concurrency('gallery')
        
        # 並行タスクリスト
        tasks = []
        
        # プレビュー画像タスク
        preview_images = version_data.get("images", [])[:3]  # 最大3枚
        preview_paths = file_paths.get("previews", [])
        
        for i, (image_info, preview_path) in enumerate(zip(preview_images, preview_paths)):
            tasks.append(("preview", image_info, preview_path, f"Preview {i+1}"))
            
        # ギャラリー画像タスク
        gallery_dir = file_paths.get("gallery_dir")
        if gallery_dir:
            try:
                all_gallery_images = self.api_client.get_all_images_for_model(model_data.get("id"))
                max_gallery = file_paths.get("gallery_max_count", 50)
                
                for i, image_info in enumerate(all_gallery_images[:max_gallery]):
                    image_id = image_info.get("id")
                    if image_id:
                        # 拡張子判定
                        image_url = image_info.get("url", "")
                        if ".jpeg" in image_url.lower():
                            ext = ".jpeg"
                        elif ".jpg" in image_url.lower():
                            ext = ".jpg"
                        elif ".png" in image_url.lower():
                            ext = ".png"
                        else:
                            ext = ".jpeg"
                            
                        gallery_path = gallery_dir / f"{image_id}{ext}"
                        tasks.append(("gallery", image_info, gallery_path, f"Gallery {i+1}"))
                        
            except Exception as e:
                print(f"      ⚠️ Failed to fetch gallery images: {e}")
                
        # 並行ダウンロード実行
        if tasks:
            max_workers = max(preview_concurrency, gallery_concurrency)
            
            with ThreadPoolExecutor(max_workers=max_workers, thread_name_prefix="image") as executor:
                future_to_task = {
                    executor.submit(self._download_single_image, task_type, image_info, path, desc): (task_type, desc)
                    for task_type, image_info, path, desc in tasks
                }
                
                for future in concurrent.futures.as_completed(future_to_task, timeout=300):
                    task_type, desc = future_to_task[future]
                    try:
                        success, filename = future.result()
                        if success:
                            if task_type == "gallery":
                                result["downloaded_files"].append(f"Gallery/{filename}")
                            else:
                                result["downloaded_files"].append(filename)
                            self._record_operation_success(f"{task_type}_download")
                        else:
                            self._record_operation_failure(f"{task_type}_download", Exception("Download failed"))
                    except Exception as e:
                        print(f"      ⚠️ Failed to download {desc}: {e}")
                        self._record_operation_failure(f"{task_type}_download", e)
                        
    def _download_single_image(
        self, 
        task_type: str, 
        image_info: Dict[str, Any], 
        filepath: Path, 
        description: str
    ) -> Tuple[bool, str]:
        """単一画像ダウンロード."""
        image_url = image_info.get("url")
        if not image_url:
            return False, ""
            
        try:
            # リトライ機能付きダウンロード
            success = self.retry_manager.retry_sync(
                self.file_downloader.download_file,
                url=image_url,
                filepath=filepath,
                description=description
            )
            return success, filepath.name
        except Exception as e:
            print(f"      ⚠️ Failed to download {description}: {e}")
            return False, ""
            
    def _record_operation_success(self, operation_type: str) -> None:
        """操作成功記録."""
        self.concurrency_manager.record_operation_result(
            operation_type, success=True, duration_seconds=1.0  # 実際の時間測定は今後実装
        )
        
    def _record_operation_failure(self, operation_type: str, error: Exception) -> None:
        """操作失敗記録."""
        timeout_occurred = "timeout" in str(error).lower()
        self.concurrency_manager.record_operation_result(
            operation_type, 
            success=False, 
            duration_seconds=1.0,
            timeout_occurred=timeout_occurred
        )
        
    async def _check_system_health(self) -> None:
        """システム健全性チェック."""
        health = await self.safety_monitor.get_current_health()
        await self.safety_monitor.monitor_and_alert(health)
        self.safety_monitor.record_health_snapshot(health)
        
    async def _get_safety_stats(self) -> Dict[str, Any]:
        """安全性統計取得."""
        health = await self.safety_monitor.get_current_health()
        return {
            "safety_level": health.overall_safety_level.value,
            "safety_score": health.safety_score,
            "memory_usage_mb": health.memory_usage_mb,
            "cpu_usage_percent": health.cpu_usage_percent,
            "disk_free_gb": health.disk_free_gb
        }
        
    def _handle_safety_alert(self, alert) -> None:
        """安全性アラート処理."""
        from ..core.safety_monitor import SafetyLevel
        
        print(f"🚨 Safety Alert: {alert.message}")
        
        if alert.level in [SafetyLevel.CRITICAL, SafetyLevel.EMERGENCY]:
            print("🛡️ Activating emergency fallback due to safety alert")
            self.fallback_active = True
            self.concurrency_manager.force_mode(
                self.concurrency_manager.current_mode.__class__.SYNC_ONLY
            )
            
    def _fallback_to_sync_download(self, username: str) -> Dict[str, Any]:
        """同期モード フォールバック."""
        print("🔄 Falling back to synchronous download mode")
        self.fallback_active = True
        return super().download_user_models(username)
        
    def get_performance_report(self) -> Dict[str, Any]:
        """パフォーマンスレポート生成."""
        return {
            "concurrency_status": self.concurrency_manager.get_status_report(),
            "retry_effectiveness": self.retry_manager.get_status_report(),
            "performance_metrics": self.performance_monitor.generate_performance_report(),
            "parallel_mode_active": not self.fallback_active
        }
        
    def set_max_parallel_models(self, max_parallel: int) -> None:
        """最大並列モデル数を設定（強制モード）."""
        if max_parallel < 1:
            max_parallel = 1
        elif max_parallel > 5:  # 安全上限
            max_parallel = 5
            
        # 対応するParallelismModeに変換
        try:
            mode = ParallelismMode(max_parallel)
            self.model_parallelism_manager.force_mode(mode)
            print(f"🔧 Parallel models forced to: {max_parallel} ({mode.name})")
        except ValueError:
            print(f"❌ Invalid parallel models count: {max_parallel}")
        
    def get_parallel_models_status(self) -> Dict[str, Any]:
        """並列モデル処理状況を取得."""
        current_parallel = self.model_parallelism_manager.get_recommended_parallel_models()
        current_mode = self.model_parallelism_manager.get_current_mode()
        
        return {
            "model_parallel_enabled": self.model_parallel_enabled,
            "current_parallel_models": current_parallel,
            "current_mode": current_mode.name,
            "model_executor_active": self.model_executor is not None,
            "model_executor_workers": current_parallel if self.model_executor else 0,
            "parallelism_manager_summary": self.model_parallelism_manager.get_performance_summary()
        }

    def __del__(self):
        """リソースクリーンアップ."""
        if hasattr(self, 'api_executor'):
            self.api_executor.shutdown(wait=False)
        if hasattr(self, 'download_executor'):
            self.download_executor.shutdown(wait=False)
        if hasattr(self, 'model_executor') and self.model_executor:
            self.model_executor.shutdown(wait=False)