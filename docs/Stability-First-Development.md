# 安定性重視開発方針 - 失敗から学ぶ堅牢なシステム設計

## 文書概要

このドキュメントは、過去の非同期実装における失敗を詳細に分析し、同様の問題を回避するための具体的な開発方針を定義します。**「速度より安定性」**を基本原則とし、堅牢で信頼性の高いシステムを構築するためのガイドラインです。

## 過去の失敗分析

### 失敗パターン1: タイムアウト処理の不備

#### 症状
- 大ファイルダウンロード時に頻繁なタイムアウト
- タイムアウト後の適切な処理ができず、不完全なファイルが残る
- リトライ機構が機能せず、手動での再実行が必要

#### 根本原因
```python
# 問題のあった実装例（過去の失敗）
async def download_file_bad(url: str, filepath: Path):
    async with aiohttp.ClientSession(timeout=30) as session:  # 固定30秒
        async with session.get(url) as response:
            with open(filepath, 'wb') as f:
                async for chunk in response.content.iter_chunked(8192):
                    f.write(chunk)  # タイムアウト時の処理なし
```

#### 学んだ教訓
1. **固定タイムアウトの危険性**: ファイルサイズに応じた動的調整が必要
2. **部分ダウンロードの処理不足**: 中途半端なファイルの削除が必要
3. **エラー情報の不足**: 何が原因でタイムアウトしたかの情報が不十分

### 失敗パターン2: 並行処理による競合状態

#### 症状
- 同じファイルが複数回ダウンロードされる
- ファイル作成時の競合でIOError発生
- 並行数増加により逆に全体性能が低下

#### 根本原因
```python
# 問題のあった実装例（過去の失敗）
async def process_models_bad(model_list: List[int]):
    # 無制限並行処理
    tasks = []
    for model_id in model_list:
        task = asyncio.create_task(download_model(model_id))
        tasks.append(task)
    
    # エラーハンドリングなし
    await asyncio.gather(*tasks)  # 1つ失敗で全て停止
```

#### 学んだ教訓
1. **並行数制御の重要性**: セマフォによる制限が必須
2. **ファイル競合の考慮不足**: 排他制御メカニズムが必要
3. **部分失敗への対応不足**: 一部失敗でも他は継続すべき

### 失敗パターン3: リソースリークとメモリ不足

#### 症状
- 長時間実行でメモリ使用量が増加し続ける
- ファイルハンドルリークによりOSリソース枯渇
- プロセス強制終了が必要

#### 根本原因
```python
# 問題のあった実装例（過去の失敗）
class BadDownloader:
    def __init__(self):
        self.sessions = []  # セッションが蓄積される
        
    async def download(self, url: str):
        session = aiohttp.ClientSession()  # close()されない
        self.sessions.append(session)  # リークの原因
        
        response = await session.get(url)  # response.close()されない
        return await response.read()
```

#### 学んだ教訓
1. **リソース管理の徹底**: with文やfinally節での確実な解放
2. **セッション再利用**: 新規作成ではなく既存セッションの活用
3. **メモリ監視**: 長時間実行時のメモリ使用量追跡

### 失敗パターン4: エラー情報の不足

#### 症状
- エラー発生時に原因特定に時間がかかる
- 同じエラーが繰り返し発生する
- ユーザーが問題を報告できない

#### 根本原因
```python
# 問題のあった実装例（過去の失敗）
try:
    await download_model(model_id)
except Exception:
    print("Download failed")  # 詳細情報なし
    continue  # 問題の根本解決なし
```

#### 学んだ教訓
1. **詳細なログ記録**: エラー種別、時刻、コンテキスト情報
2. **構造化ログ**: 機械的な分析が可能な形式
3. **ユーザー向け情報**: 技術者でなくても理解できる説明

## 安定性重視の設計原則

### 原則1: Fail-Safe設計

#### 基本概念
システムが失敗した場合でも、**安全な状態を維持**し、**データの整合性を保証**する

#### 具体的実装
```python
class FailSafeDownloader:
    def __init__(self, config: DownloadConfig):
        self.config = config
        self.temp_dir = Path(config.output_dir) / ".temp"
        self.temp_dir.mkdir(exist_ok=True)
        
    def download_file_safely(self, url: str, final_path: Path) -> bool:
        """失敗時の安全性を保証するダウンロード"""
        # 一時ファイルに保存
        temp_path = self.temp_dir / f"{uuid.uuid4()}.tmp"
        
        try:
            # ダウンロード実行
            success = self._download_to_temp(url, temp_path)
            
            if success and self._verify_integrity(temp_path):
                # 検証成功時のみ最終位置に移動
                shutil.move(temp_path, final_path)
                return True
            else:
                # 失敗時は一時ファイル削除
                temp_path.unlink(missing_ok=True)
                return False
                
        except Exception as e:
            # 例外発生時も一時ファイル削除
            temp_path.unlink(missing_ok=True)
            logger.error(f"Download failed safely: {e}")
            return False
        
    def _verify_integrity(self, filepath: Path) -> bool:
        """ファイル整合性検証"""
        if not filepath.exists():
            return False
            
        # ファイルサイズチェック（最低限）
        if filepath.stat().st_size < 1024:  # 1KB未満は不正
            return False
            
        # ファイル形式チェック（拡張子に応じて）
        if not self._verify_file_format(filepath):
            return False
            
        return True
```

### 原則2: 段階的劣化（Graceful Degradation）

#### 基本概念
システムの一部が失敗しても、**残りの機能は正常に動作**し続ける

#### 具体的実装
```python
class GracefulDownloadService:
    def __init__(self, config: DownloadConfig):
        self.config = config
        self.feature_flags = {
            'parallel_download': True,
            'gallery_images': True,
            'preview_images': True,
            'metadata_generation': True
        }
        
    def download_model_with_degradation(self, model_data: Dict) -> DownloadResult:
        """段階的劣化対応ダウンロード"""
        result = DownloadResult(model_id=model_data['id'])
        
        try:
            # 1. メインファイルダウンロード（最優先）
            success = self._download_main_file(model_data)
            result.main_file_success = success
            
            if not success:
                # メインファイル失敗時はリトライ
                success = self._download_main_file_with_retry(model_data)
                result.main_file_success = success
                
        except Exception as e:
            logger.error(f"Main file download failed: {e}")
            result.main_file_success = False
            
        # 2. 付随ファイル（失敗しても継続）
        if self.feature_flags['preview_images']:
            try:
                result.preview_count = self._download_preview_images(model_data)
            except Exception as e:
                logger.warning(f"Preview download failed, continuing: {e}")
                self.feature_flags['preview_images'] = False  # 一時無効化
                
        if self.feature_flags['gallery_images']:
            try:
                result.gallery_count = self._download_gallery_images(model_data)
            except Exception as e:
                logger.warning(f"Gallery download failed, continuing: {e}")
                self.feature_flags['gallery_images'] = False  # 一時無効化
                
        if self.feature_flags['metadata_generation']:
            try:
                self._generate_metadata(model_data)
                result.metadata_generated = True
            except Exception as e:
                logger.warning(f"Metadata generation failed, continuing: {e}")
                
        return result
```

### 原則3: 観測可能性（Observability）

#### 基本概念
システムの内部状態を**外部から観測可能**にし、問題の早期発見と迅速な対応を可能にする

#### 具体的実装
```python
import structlog
from datetime import datetime
from typing import Dict, Any

class ObservableDownloader:
    def __init__(self):
        self.logger = structlog.get_logger()
        self.metrics = MetricsCollector()
        
    def download_with_observability(self, url: str, filepath: Path) -> bool:
        """観測可能なダウンロード"""
        operation_id = str(uuid.uuid4())
        
        # 開始ログ
        self.logger.info(
            "download_started",
            operation_id=operation_id,
            url=url,
            filepath=str(filepath),
            timestamp=datetime.utcnow().isoformat()
        )
        
        start_time = time.time()
        
        try:
            # メトリクス記録開始
            with self.metrics.time_operation("download_duration"):
                success = self._perform_download(url, filepath)
                
            # 成功時のログとメトリクス
            duration = time.time() - start_time
            file_size_mb = filepath.stat().st_size / (1024 * 1024) if success else 0
            
            self.logger.info(
                "download_completed",
                operation_id=operation_id,
                success=success,
                duration_seconds=duration,
                file_size_mb=file_size_mb,
                throughput_mbps=file_size_mb / duration if duration > 0 else 0
            )
            
            # メトリクス更新
            self.metrics.increment("downloads_total")
            if success:
                self.metrics.increment("downloads_successful")
                self.metrics.histogram("download_size_mb", file_size_mb)
            else:
                self.metrics.increment("downloads_failed")
                
            return success
            
        except Exception as e:
            # エラー時の詳細ログ
            self.logger.error(
                "download_error",
                operation_id=operation_id,
                error_type=type(e).__name__,
                error_message=str(e),
                duration_seconds=time.time() - start_time,
                url=url,
                filepath=str(filepath)
            )
            
            # エラーメトリクス
            self.metrics.increment("downloads_total")
            self.metrics.increment("downloads_failed")
            self.metrics.increment(f"download_errors.{type(e).__name__}")
            
            return False
```

## 堅牢なタイムアウト戦略

### 動的タイムアウト調整

```python
class AdaptiveTimeoutManager:
    def __init__(self):
        self.base_timeout = 30  # 基本タイムアウト（秒）
        self.timeout_history = deque(maxlen=100)  # 過去のタイムアウト履歴
        self.size_based_factor = 2.0  # ファイルサイズ係数（MB当たり秒数）
        
    def calculate_timeout(self, file_size_mb: float, connection_speed_mbps: float = None) -> int:
        """ファイルサイズと接続速度に基づくタイムアウト計算"""
        # ベースタイムアウト
        timeout = self.base_timeout
        
        # ファイルサイズベースの調整
        if file_size_mb > 0:
            size_timeout = file_size_mb * self.size_based_factor
            timeout = max(timeout, size_timeout)
            
        # 接続速度ベースの調整
        if connection_speed_mbps and connection_speed_mbps > 0:
            estimated_time = file_size_mb / connection_speed_mbps
            timeout = max(timeout, estimated_time * 2.0)  # 余裕を持たせる
            
        # 過去の失敗率に基づく調整
        recent_failure_rate = self._calculate_recent_failure_rate()
        if recent_failure_rate > 0.1:  # 10%以上の失敗率
            timeout *= (1 + recent_failure_rate)  # タイムアウトを延長
            
        return int(timeout)
    
    def record_timeout_result(self, timeout_used: int, success: bool, actual_duration: float):
        """タイムアウト結果の記録"""
        self.timeout_history.append({
            'timeout_used': timeout_used,
            'success': success,
            'actual_duration': actual_duration,
            'timestamp': time.time()
        })
    
    def _calculate_recent_failure_rate(self) -> float:
        """直近のタイムアウト失敗率計算"""
        if not self.timeout_history:
            return 0.0
            
        recent_results = [r for r in self.timeout_history if time.time() - r['timestamp'] < 3600]  # 1時間以内
        if not recent_results:
            return 0.0
            
        failures = sum(1 for r in recent_results if not r['success'])
        return failures / len(recent_results)
```

### 段階的リトライ戦略

```python
class RobustRetryManager:
    def __init__(self):
        self.retry_strategies = {
            'network_error': [2, 5, 10, 30],      # ネットワークエラー
            'timeout': [5, 15, 30, 60],           # タイムアウト
            'server_error': [1, 3, 5, 10],        # サーバーエラー
            'rate_limit': [60, 120, 300, 600]     # レート制限
        }
        
    async def retry_with_strategy(self, operation, error_classifier, max_attempts: int = 4):
        """エラー種別に応じた段階的リトライ"""
        last_exception = None
        
        for attempt in range(max_attempts):
            try:
                return await operation()
                
            except Exception as e:
                last_exception = e
                error_type = error_classifier(e)
                
                if attempt == max_attempts - 1:
                    # 最後の試行
                    break
                    
                # リトライ間隔決定
                retry_delays = self.retry_strategies.get(error_type, [1, 2, 4, 8])
                delay = retry_delays[min(attempt, len(retry_delays) - 1)]
                
                logger.warning(
                    f"Operation failed (attempt {attempt + 1}/{max_attempts}), "
                    f"retrying in {delay}s: {e}"
                )
                
                await asyncio.sleep(delay)
                
        raise last_exception
    
    def classify_error(self, error: Exception) -> str:
        """エラー分類"""
        if isinstance(error, (aiohttp.ClientConnectionError, aiohttp.ClientConnectorError)):
            return 'network_error'
        elif isinstance(error, asyncio.TimeoutError):
            return 'timeout'
        elif isinstance(error, aiohttp.ClientResponseError):
            if error.status == 429:
                return 'rate_limit'
            elif 500 <= error.status < 600:
                return 'server_error'
        
        return 'unknown'
```

## エラー回復戦略

### 自動回復メカニズム

```python
class AutoRecoveryManager:
    def __init__(self, config: DownloadConfig):
        self.config = config
        self.recovery_strategies = {
            'download_corruption': self._recover_corrupted_download,
            'network_partition': self._recover_network_issues,
            'storage_full': self._recover_storage_issues,
            'rate_limit_exceeded': self._recover_rate_limit
        }
        
    async def attempt_recovery(self, error: Exception, context: Dict[str, Any]) -> bool:
        """エラーからの自動回復試行"""
        error_type = self._classify_error_for_recovery(error)
        
        if error_type not in self.recovery_strategies:
            return False
            
        try:
            recovery_func = self.recovery_strategies[error_type]
            return await recovery_func(error, context)
        except Exception as recovery_error:
            logger.error(f"Recovery attempt failed: {recovery_error}")
            return False
    
    async def _recover_corrupted_download(self, error: Exception, context: Dict[str, Any]) -> bool:
        """破損ダウンロードからの回復"""
        filepath = context.get('filepath')
        if not filepath or not isinstance(filepath, Path):
            return False
            
        # 破損ファイル削除
        filepath.unlink(missing_ok=True)
        
        # 一時ファイルも削除
        temp_files = filepath.parent.glob(f"{filepath.stem}.tmp*")
        for temp_file in temp_files:
            temp_file.unlink(missing_ok=True)
            
        logger.info(f"Cleaned up corrupted download: {filepath}")
        return True
    
    async def _recover_network_issues(self, error: Exception, context: Dict[str, Any]) -> bool:
        """ネットワーク問題からの回復"""
        # DNS キャッシュクリア
        await self._clear_dns_cache()
        
        # 接続プールリセット
        await self._reset_connection_pool()
        
        # 短時間待機（ネットワーク復旧待ち）
        await asyncio.sleep(10)
        
        return True
    
    async def _recover_storage_issues(self, error: Exception, context: Dict[str, Any]) -> bool:
        """ストレージ問題からの回復"""
        output_dir = Path(self.config.output_dir)
        
        # 古い一時ファイル削除
        temp_files_deleted = await self._cleanup_temp_files(output_dir)
        
        # ディスク容量チェック
        free_space_gb = shutil.disk_usage(output_dir).free / (1024 ** 3)
        
        if free_space_gb < 1.0:  # 1GB未満
            logger.error(f"Insufficient disk space: {free_space_gb:.2f}GB")
            return False
            
        logger.info(f"Cleaned up {temp_files_deleted} temp files, {free_space_gb:.2f}GB free")
        return True
    
    async def _recover_rate_limit(self, error: Exception, context: Dict[str, Any]) -> bool:
        """レート制限からの回復"""
        # レート制限情報を取得
        retry_after = getattr(error, 'retry_after', 60)
        
        logger.info(f"Rate limited, backing off for {retry_after} seconds")
        await asyncio.sleep(retry_after)
        
        # API クライアントのレート制限設定を更新
        if hasattr(self.config, 'api_rate'):
            self.config.api_rate *= 0.8  # レートを20%下げる
            
        return True
```

### 状態復旧機能

```python
class StateRecoveryManager:
    def __init__(self, state_file: Path):
        self.state_file = state_file
        self.backup_file = state_file.with_suffix('.bak')
        
    def save_checkpoint(self, state: Dict[str, Any]):
        """チェックポイント保存"""
        # バックアップ作成
        if self.state_file.exists():
            shutil.copy(self.state_file, self.backup_file)
            
        # 新しい状態保存  
        with open(self.state_file, 'w') as f:
            json.dump(state, f, indent=2, default=str)
            
    def load_checkpoint(self) -> Dict[str, Any]:
        """チェックポイント読み込み"""
        # メインファイル試行
        if self.state_file.exists():
            try:
                with open(self.state_file, 'r') as f:
                    return json.load(f)
            except json.JSONDecodeError:
                logger.warning("State file corrupted, trying backup")
                
        # バックアップファイル試行
        if self.backup_file.exists():
            try:
                with open(self.backup_file, 'r') as f:
                    state = json.load(f)
                # バックアップから復旧
                self.save_checkpoint(state)
                return state
            except json.JSONDecodeError:
                logger.error("Backup file also corrupted")
                
        return {}
    
    def recover_partial_downloads(self, output_dir: Path) -> List[Path]:
        """部分ダウンロードファイルの検出と回復"""
        partial_files = []
        
        # .tmp ファイルを検索
        for tmp_file in output_dir.rglob('*.tmp'):
            # ファイルサイズチェック
            if tmp_file.stat().st_size > 0:
                # 対応する完成ファイル名を推定
                target_file = tmp_file.with_suffix('')
                
                if not target_file.exists():
                    # Range Request で続きをダウンロード可能
                    partial_files.append(tmp_file)
                else:
                    # 重複ファイル、削除
                    tmp_file.unlink()
                    
        return partial_files
```

## 包括的監視システム

### リアルタイム健全性監視

```python
class HealthMonitoring:
    def __init__(self, config: DownloadConfig):
        self.config = config
        self.health_checks = {
            'api_connectivity': self._check_api_connectivity,
            'disk_space': self._check_disk_space,
            'memory_usage': self._check_memory_usage,
            'network_latency': self._check_network_latency,
            'error_rates': self._check_error_rates
        }
        
    async def run_health_checks(self) -> Dict[str, bool]:
        """全健全性チェック実行"""
        results = {}
        
        for check_name, check_func in self.health_checks.items():
            try:
                results[check_name] = await check_func()
            except Exception as e:
                logger.error(f"Health check {check_name} failed: {e}")
                results[check_name] = False
                
        return results
    
    async def _check_api_connectivity(self) -> bool:
        """API接続性チェック"""
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(
                    "https://civitai.com/api/v1/models",
                    params={'limit': 1},
                    timeout=aiohttp.ClientTimeout(total=10)
                ) as response:
                    return response.status == 200
        except Exception:
            return False
    
    async def _check_disk_space(self) -> bool:
        """ディスク容量チェック"""
        try:
            free_space_gb = shutil.disk_usage(self.config.output_dir).free / (1024 ** 3)
            return free_space_gb > 5.0  # 5GB以上
        except Exception:
            return False
    
    async def _check_memory_usage(self) -> bool:
        """メモリ使用量チェック"""
        try:
            import psutil
            memory_percent = psutil.virtual_memory().percent
            return memory_percent < 90  # 90%未満
        except Exception:
            return True  # psutil未インストール時は通過
    
    async def _check_network_latency(self) -> bool:
        """ネットワーク遅延チェック"""
        try:
            start_time = time.time()
            async with aiohttp.ClientSession() as session:
                async with session.get("https://civitai.com") as response:
                    latency_ms = (time.time() - start_time) * 1000
                    return latency_ms < 5000  # 5秒未満
        except Exception:
            return False
    
    async def _check_error_rates(self) -> bool:
        """エラー率チェック"""
        # メトリクスからエラー率を計算
        recent_errors = self._get_recent_error_count()
        recent_total = self._get_recent_total_count()
        
        if recent_total == 0:
            return True
            
        error_rate = recent_errors / recent_total
        return error_rate < 0.05  # 5%未満
```

### プロアクティブアラート

```python
class ProactiveAlertSystem:
    def __init__(self):
        self.alert_rules = [
            AlertRule(
                name="high_error_rate",
                condition=lambda m: m.error_rate > 0.05,
                severity=AlertSeverity.WARNING,
                cooldown_minutes=15
            ),
            AlertRule(
                name="critical_error_rate", 
                condition=lambda m: m.error_rate > 0.20,
                severity=AlertSeverity.CRITICAL,
                cooldown_minutes=5
            ),
            AlertRule(
                name="memory_leak_detected",
                condition=lambda m: m.memory_growth_rate > 100,  # MB/hour
                severity=AlertSeverity.WARNING,
                cooldown_minutes=30
            ),
            AlertRule(
                name="disk_space_low",
                condition=lambda m: m.free_disk_gb < 5.0,
                severity=AlertSeverity.CRITICAL,
                cooldown_minutes=60
            )
        ]
        
    def evaluate_alerts(self, metrics: SystemMetrics) -> List[Alert]:
        """アラート条件評価"""
        triggered_alerts = []
        
        for rule in self.alert_rules:
            if rule.should_evaluate() and rule.condition(metrics):
                alert = Alert(
                    rule=rule,
                    metrics=metrics,
                    timestamp=datetime.utcnow()
                )
                triggered_alerts.append(alert)
                rule.record_trigger()
                
        return triggered_alerts
    
    def send_alerts(self, alerts: List[Alert]):
        """アラート送信"""
        for alert in alerts:
            if alert.rule.severity == AlertSeverity.CRITICAL:
                self._send_immediate_notification(alert)
            else:
                self._queue_batch_notification(alert)
```

## テスト駆動の安定性保証

### 安定性テストスイート

```python
# tests/stability/test_long_running.py
import pytest
import asyncio
from datetime import datetime, timedelta

class TestLongRunningStability:
    @pytest.mark.slow
    @pytest.mark.asyncio
    async def test_24_hour_continuous_operation(self):
        """24時間連続実行テスト"""
        start_time = datetime.utcnow()
        end_time = start_time + timedelta(hours=24)
        
        downloader = StabilityTestDownloader()
        errors = []
        completed_count = 0
        
        while datetime.utcnow() < end_time:
            try:
                result = await downloader.download_test_file()
                if result.success:
                    completed_count += 1
                else:
                    errors.append(result.error)
                    
            except Exception as e:
                errors.append(e)
                
            # 1分間隔
            await asyncio.sleep(60)
            
        # 成功率チェック
        total_attempts = completed_count + len(errors)
        success_rate = completed_count / total_attempts if total_attempts > 0 else 0
        
        assert success_rate > 0.99, f"Success rate too low: {success_rate:.2%}"
        assert len(errors) < total_attempts * 0.01, f"Too many errors: {len(errors)}"
    
    @pytest.mark.asyncio
    async def test_memory_leak_detection(self):
        """メモリリーク検出テスト"""
        import psutil
        
        process = psutil.Process()
        initial_memory = process.memory_info().rss
        
        downloader = MemoryTestDownloader()
        
        # 1000回実行
        for i in range(1000):
            await downloader.download_small_file()
            
            # 100回ごとにメモリチェック
            if i % 100 == 0:
                current_memory = process.memory_info().rss
                memory_growth = current_memory - initial_memory
                memory_growth_mb = memory_growth / (1024 * 1024)
                
                # 100MB以上の増加は異常
                assert memory_growth_mb < 100, f"Memory leak detected: {memory_growth_mb:.2f}MB"
    
    @pytest.mark.asyncio
    async def test_error_recovery_effectiveness(self):
        """エラー回復機能の効果測定"""
        recovery_manager = AutoRecoveryManager(test_config)
        
        # 各種エラーシナリオでテスト
        error_scenarios = [
            NetworkTimeoutError(),
            CorruptedDownloadError(),
            DiskFullError(),
            RateLimitError()
        ]
        
        recovery_success_count = 0
        
        for error in error_scenarios:
            context = {'filepath': Path('/tmp/test'), 'url': 'http://test.com'}
            
            # 回復試行
            success = await recovery_manager.attempt_recovery(error, context)
            if success:
                recovery_success_count += 1
                
        # 80%以上の回復成功を期待
        recovery_rate = recovery_success_count / len(error_scenarios)
        assert recovery_rate > 0.8, f"Recovery rate too low: {recovery_rate:.2%}"
```

## 実装チェックリスト

### 開発時チェック項目

#### 基本安全性
- [ ] すべての外部リソース（ファイル、ネットワーク）は try-finally で管理
- [ ] 一時ファイルは例外時にも確実に削除
- [ ] タイムアウトは動的に調整可能
- [ ] エラーログには十分なコンテキスト情報を含む

#### 並行処理安全性
- [ ] 共有リソースへのアクセスは適切に同期化
- [ ] デッドロック回避のためのタイムアウト設定
- [ ] 並行数は設定可能で制限値あり
- [ ] 部分失敗でも他の処理は継続

#### 観測可能性
- [ ] 重要な操作は構造化ログで記録
- [ ] メトリクスは時系列で収集・保存
- [ ] エラー分類と統計情報の提供
- [ ] 健全性チェック機能の実装

#### 回復機能
- [ ] 中断からの再開機能
- [ ] 破損ファイルの自動検出・削除
- [ ] ネットワーク問題からの自動回復
- [ ] 設定の動的調整機能

### コードレビュー時チェック項目

#### エラーハンドリング
- [ ] 例外の種類に応じた適切な処理
- [ ] ユーザーが理解できるエラーメッセージ
- [ ] エラー情報の機械的な分析が可能
- [ ] 再試行可能エラーの適切な判定

#### リソース管理
- [ ] メモリリークの可能性がない
- [ ] ファイルハンドルリークの可能性がない
- [ ] ネットワーク接続の適切な管理
- [ ] 一時リソースの確実な解放

#### 性能と安定性
- [ ] 大量データ処理時の安定性
- [ ] 長時間実行時の安定性
- [ ] 異常系での適切な動作
- [ ] 設定変更への適切な対応

---

この安定性重視開発方針により、過去の失敗を繰り返すことなく、堅牢で信頼性の高いシステムを構築します。