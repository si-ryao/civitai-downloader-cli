# 高性能化実装計画 - 安定性重視アプローチ

## 文書概要

このドキュメントは、Civitai Downloader CLIの性能改善を安全かつ段階的に実装するための詳細計画です。過去の非同期実装における失敗を教訓とし、**「速度より安定性」**を基本方針として採用します。

## 背景と課題認識

### 過去の問題
- **タイムアウト頻発**: 適切なハンドリングができず、システム不安定
- **性能劣化**: 並行処理導入により逆に速度低下
- **完全性の欠如**: 全件ダウンロードが完了できない状況
- **エラー回復不能**: 失敗時の自動復旧機能が不十分

### 現状分析
- 同期処理による安定動作は確認済み
- レート制限遵守により API制限回避
- SHA256検証による整合性保証
- 段階的リトライ機能実装済み

## 基本方針

### コア原則
1. **安定性第一**: 性能向上よりも動作安定性を優先
2. **段階的改善**: Phase別に分割し、各段階で検証
3. **完全性保証**: 全ファイルダウンロードの確実な完了
4. **自動フォールバック**: 問題発生時の安全な復旧

### 成功定義
- 現在の安定性を維持または向上
- 性能劣化を避けつつ、可能な範囲で速度向上
- 長期間運用での信頼性確保

## Phase別実装計画

### Phase 1: 現状分析と測定基盤構築

#### 目標
現在の性能特性を定量的に把握し、改善の基準線を確立

#### 実装内容
```python
# 性能測定フレームワーク
class PerformanceMonitor:
    def __init__(self):
        self.metrics = {
            'download_speed_mbps': [],
            'api_response_time_ms': [],
            'success_rate_percent': 0.0,
            'timeout_rate_percent': 0.0,
            'memory_usage_mb': [],
            'cpu_usage_percent': []
        }
    
    def start_measurement(self):
        """測定開始"""
        self.start_time = time.time()
        
    def record_download(self, size_mb: float, duration_sec: float):
        """ダウンロード性能記録"""
        speed = size_mb / duration_sec
        self.metrics['download_speed_mbps'].append(speed)
        
    def record_api_call(self, duration_ms: int):
        """API応答時間記録"""
        self.metrics['api_response_time_ms'].append(duration_ms)
```

#### 測定項目
- **ダウンロード速度**: 平均/最大/最小 (MB/s)
- **API応答時間**: 平均/P95/P99 (ms)
- **成功率**: 全体成功率 (%)
- **タイムアウト発生率**: エラー全体に占める割合 (%)
- **リソース使用量**: メモリ/CPU使用率
- **スループット**: 時間あたり処理ファイル数

#### Phase 1 完了条件
- [x] ベースライン測定完了
- [x] 測定ツール実装完了
- [x] 現状問題点の特定完了
- [x] 改善目標値の設定完了

### Phase 2: 安定性強化（非同期化前の土台固め）

#### 目標
同期処理の範囲内でタイムアウトハンドリングとエラー回復を強化

#### 実装内容

##### 2.1 強化されたタイムアウトハンドリング
```python
class RobustDownloader:
    def __init__(self):
        self.timeout_config = {
            'connect_timeout': 10,      # 接続タイムアウト
            'read_timeout': 300,        # 読み込みタイムアウト  
            'total_timeout': 600,       # 全体タイムアウト
            'retry_timeouts': [5, 15, 30, 60]  # 段階的リトライ間隔
        }
        
    def download_with_robust_timeout(self, url: str, filepath: Path):
        """堅牢なタイムアウト処理付きダウンロード"""
        for attempt, timeout_sec in enumerate(self.timeout_config['retry_timeouts']):
            try:
                response = requests.get(
                    url, 
                    timeout=(self.timeout_config['connect_timeout'], timeout_sec),
                    stream=True
                )
                # ダウンロード処理...
                return True
            except requests.exceptions.Timeout as e:
                if attempt == len(self.timeout_config['retry_timeouts']) - 1:
                    raise
                time.sleep(timeout_sec)  # 指数バックオフ
```

##### 2.2 フォールバック戦略
```python
class FallbackStrategy:
    def __init__(self):
        self.fallback_endpoints = [
            "https://civitai.com/api/v1",
            "https://api.civitai.com/v1"  # 仮想的なミラー
        ]
        
    def download_with_fallback(self, url: str, filepath: Path):
        """代替エンドポイント対応ダウンロード"""
        for endpoint in self.fallback_endpoints:
            try:
                modified_url = url.replace(self.fallback_endpoints[0], endpoint)
                return self.download_file(modified_url, filepath)
            except Exception as e:
                continue
        raise DownloadError("All endpoints failed")
```

##### 2.3 状態管理と復旧機能
```python
class DownloadStateManager:
    def __init__(self, state_file: Path):
        self.state_file = state_file
        
    def save_progress(self, completed_files: List[str], failed_files: List[str]):
        """進捗状態を永続化"""
        state = {
            'completed': completed_files,
            'failed': failed_files,
            'timestamp': datetime.utcnow().isoformat()
        }
        with open(self.state_file, 'w') as f:
            json.dump(state, f, indent=2)
            
    def resume_from_state(self) -> tuple[List[str], List[str]]:
        """中断状態からの復旧"""
        if not self.state_file.exists():
            return [], []
        with open(self.state_file, 'r') as f:
            state = json.load(f)
        return state.get('completed', []), state.get('failed', [])
```

#### Phase 2 完了条件
- [ ] タイムアウト発生率 < 1%
- [ ] 全件ダウンロード成功率 > 99%
- [ ] エラー自動復旧率 > 95%
- [ ] 24時間連続実行テスト成功

### Phase 3: 慎重な並行処理導入

#### 目標
同期処理の安定性を維持しつつ、制限的な並行処理を段階的に導入

#### 実装内容

##### 3.1 ハイブリッドアプローチ
```python
class HybridDownloader:
    def __init__(self):
        self.config = {
            'max_concurrent_api': 2,        # API呼び出しは最大2並行
            'max_concurrent_download': 1,   # ダウンロードは1つずつ
            'enable_concurrent': False,     # デフォルト無効
            'fallback_to_sync': True        # 失敗時は同期モードに切り替え
        }
        
    def download_models_hybrid(self, model_list: List[int]):
        """ハイブリッド並行処理"""
        if not self.config['enable_concurrent']:
            return self.download_models_sync(model_list)
            
        try:
            return self.download_models_parallel(model_list)
        except Exception as e:
            if self.config['fallback_to_sync']:
                logger.warning(f"Parallel download failed, falling back to sync: {e}")
                return self.download_models_sync(model_list)
            raise
```

##### 3.2 段階的並行度向上
```python
# Phase 3a: APIコール並行化（ダウンロードは同期維持）
class Phase3aDownloader:
    async def fetch_model_metadata_parallel(self, model_ids: List[int]):
        """モデルメタデータの並行取得"""
        semaphore = asyncio.Semaphore(2)  # 最大2並行
        
        async def fetch_single(model_id: int):
            async with semaphore:
                return await self.api_client.get_model_details(model_id)
                
        return await asyncio.gather(*[fetch_single(mid) for mid in model_ids])

# Phase 3b: 軽量ファイル並行ダウンロード（画像のみ）
class Phase3bDownloader:
    def download_images_parallel(self, image_urls: List[str]):
        """画像の制限的並行ダウンロード"""
        with ThreadPoolExecutor(max_workers=2) as executor:
            futures = [executor.submit(self.download_image, url) for url in image_urls]
            return [f.result() for f in futures]

# Phase 3c: 重量ファイル並行ダウンロード（モデル）
class Phase3cDownloader:
    def download_models_parallel(self, model_data: List[Dict]):
        """モデルファイルの慎重な並行ダウンロード"""
        # 実装は十分な検証後
        pass
```

#### Phase 3 完了条件
- [ ] 新実装の性能 ≥ 既存実装の120%
- [ ] タイムアウト発生率維持 < 1%
- [ ] 安定性スコア ≥ 既存実装
- [ ] 1週間連続テスト成功

### Phase 4: 高度な最適化（安定性確認後）

#### 目標
安定性を確保した上で、最大性能を引き出す高度な最適化を実装

#### 実装内容

##### 4.1 接続プール最適化
```python
class OptimizedSession:
    def __init__(self):
        self.session = requests.Session()
        
        # 接続プール設定
        adapter = requests.adapters.HTTPAdapter(
            pool_connections=10,      # 接続プール数
            pool_maxsize=20,         # プール最大サイズ
            max_retries=3,           # 再試行回数
            pool_block=False         # ノンブロッキング
        )
        
        self.session.mount('https://', adapter)
        self.session.mount('http://', adapter)
        
    def configure_keep_alive(self):
        """Keep-Alive設定の最適化"""
        self.session.headers.update({
            'Connection': 'keep-alive',
            'Keep-Alive': 'timeout=30, max=100'
        })
```

##### 4.2 スマートレート制御
```python
class AdaptiveRateLimiter:
    def __init__(self, base_rate: float):
        self.base_rate = base_rate
        self.current_rate = base_rate
        self.response_times = deque(maxlen=100)
        
    def adjust_rate_based_on_performance(self):
        """API応答時間に基づく動的レート調整"""
        if len(self.response_times) < 10:
            return
            
        avg_response_time = sum(self.response_times) / len(self.response_times)
        
        if avg_response_time > 2000:  # 2秒以上
            self.current_rate *= 0.8  # レート下げる
        elif avg_response_time < 500:  # 0.5秒未満
            self.current_rate *= 1.1  # レート上げる
            
        # 最大レート制限
        self.current_rate = min(self.current_rate, self.base_rate * 2)
```

#### Phase 4 完了条件
- [ ] 性能向上 ≥ 200% (理想目標)
- [ ] 安定性維持または向上
- [ ] メモリ使用量最適化
- [ ] プロダクション環境での安定動作

## テスト戦略

### テスト階層

#### 1. 単体テスト（各コンポーネント）
```python
# 例: タイムアウトハンドリングテスト
def test_robust_timeout_handling():
    downloader = RobustDownloader()
    
    with patch('requests.get') as mock_get:
        mock_get.side_effect = requests.exceptions.Timeout()
        
        with pytest.raises(DownloadError):
            downloader.download_with_robust_timeout("http://test.com", Path("/tmp/test"))
            
        # 4回リトライしたことを確認
        assert mock_get.call_count == 4
```

#### 2. 統合テスト（エンドツーエンド）
```python
def test_end_to_end_download_complete():
    """全ファイルダウンロード完了のテスト"""
    service = DownloadService(test_config)
    result = service.download_user_models("test_user")
    
    assert result["success"] is True
    assert result["failed_downloads"] == 0
    assert all(Path(f).exists() for f in result["downloaded_files"])
```

#### 3. 負荷テスト（大量ダウンロード）
```python
def test_large_scale_download():
    """100モデルダウンロードでの安定性テスト"""
    model_ids = list(range(1000000, 1000100))  # 100モデル
    
    start_time = time.time()
    results = downloader.download_models(model_ids)
    end_time = time.time()
    
    success_rate = sum(1 for r in results if r.success) / len(results)
    assert success_rate > 0.99  # 99%以上成功
    
    duration_hours = (end_time - start_time) / 3600
    assert duration_hours < 24  # 24時間以内完了
```

#### 4. 障害テスト（ネットワーク断・タイムアウト耐性）
```python
def test_network_failure_recovery():
    """ネットワーク障害からの復旧テスト"""
    with NetworkSimulator() as sim:
        sim.add_failure_period(start=60, duration=30)  # 1分後に30秒間断線
        
        result = downloader.download_models_with_recovery(test_models)
        
        assert result.total_retries > 0  # リトライが発生
        assert result.success_rate > 0.95  # 復旧後は正常動作
```

#### 5. 長時間テスト（24時間連続実行）
```bash
# CI/CDで週次実行
python -m pytest tests/test_endurance.py --duration=86400 --report-interval=3600
```

### 自動化されたテスト実行

#### GitHub Actions設定
```yaml
name: Performance and Stability Tests

on:
  pull_request:
    branches: [main, performance/*]
  schedule:
    - cron: '0 2 * * 0'  # 毎週日曜日深夜2時

jobs:
  stability-test:
    runs-on: ubuntu-latest
    timeout-minutes: 480  # 8時間
    
    steps:
    - name: Run 4-hour stability test
      run: |
        python -m pytest tests/test_stability.py --duration=14400
        
  performance-regression:
    runs-on: ubuntu-latest
    
    steps:
    - name: Performance benchmark
      run: |
        python scripts/benchmark.py --baseline=main --current=HEAD
        python scripts/check_regression.py --threshold=0.1  # 10%劣化でfail
```

## 段階的ロールアウト戦略

### 実験フラグ制御
```python
class ExperimentalFeatures:
    def __init__(self, config: DownloadConfig):
        self.config = config
        
    @property
    def enable_parallel_api(self) -> bool:
        return self.config.experimental_flags.get('parallel_api', False)
        
    @property  
    def enable_parallel_download(self) -> bool:
        return self.config.experimental_flags.get('parallel_download', False)
```

### CLIオプション
```bash
# 実験的機能の有効化
civitai-dl --enable-experimental-performance

# 強制同期モード（問題時の回避手段）
civitai-dl --force-sync-mode

# 詳細監視モード
civitai-dl --monitor-performance --report-interval=60
```

### A/Bテスト機能
```python
class ABTestRunner:
    def run_comparison(self, model_list: List[int]):
        """既存実装vs新実装の性能比較"""
        # 50%ずつに分割
        list_a, list_b = self.split_randomly(model_list)
        
        # 並行実行
        with ThreadPoolExecutor(max_workers=2) as executor:
            future_a = executor.submit(self.run_sync_version, list_a)
            future_b = executor.submit(self.run_new_version, list_b)
            
            result_a = future_a.result()
            result_b = future_b.result()
            
        return self.compare_results(result_a, result_b)
```

## 監視・メトリクス

### リアルタイム監視
```python
class RealTimeMonitor:
    def __init__(self):
        self.metrics = {
            'current_throughput_mbps': 0.0,
            'active_downloads': 0,
            'queue_size': 0,
            'error_rate_last_hour': 0.0,
            'timeout_rate_last_hour': 0.0
        }
        
    def update_metrics(self):
        """メトリクス更新（1分間隔）"""
        self.metrics['current_throughput_mbps'] = self.calculate_throughput()
        self.metrics['error_rate_last_hour'] = self.calculate_error_rate()
        
    def should_trigger_fallback(self) -> bool:
        """フォールバック判定"""
        return (
            self.metrics['error_rate_last_hour'] > 0.05 or  # エラー率5%超
            self.metrics['timeout_rate_last_hour'] > 0.01   # タイムアウト率1%超
        )
```

### アラート設定
```python
class AlertManager:
    def __init__(self):
        self.thresholds = {
            'performance_degradation': 0.10,  # 10%性能劣化
            'error_rate': 0.05,               # 5%エラー率
            'timeout_rate': 0.01,             # 1%タイムアウト率
            'memory_usage_mb': 1024           # 1GB メモリ使用量
        }
        
    def check_alerts(self, metrics: Dict[str, float]):
        """アラート条件チェック"""
        alerts = []
        
        if metrics['error_rate'] > self.thresholds['error_rate']:
            alerts.append(Alert(
                level='WARNING',
                message=f"High error rate: {metrics['error_rate']:.2%}"
            ))
            
        return alerts
```

## フェイルセーフ機能

### 自動フォールバック
```python
class FailsafeManager:
    def __init__(self):
        self.stable_version = "sync"
        self.current_version = "experimental"
        self.failure_count = 0
        self.max_failures = 3
        
    def auto_fallback_on_failure(self, error: Exception):
        """エラー閾値超過時の自動フォールバック"""
        self.failure_count += 1
        
        if self.failure_count >= self.max_failures:
            logger.critical(f"Switching to stable mode after {self.failure_count} failures")
            self.switch_to_stable_mode()
            self.log_fallback_event(error)
```

### 緊急停止機能
```python
class EmergencyStop:
    def __init__(self):
        self.stop_file = Path("EMERGENCY_STOP")
        
    def check_emergency_stop(self):
        """緊急停止ファイルチェック"""
        if self.stop_file.exists():
            logger.critical("Emergency stop requested")
            self.cleanup_and_exit()
```

## 成功基準とKPI

### Phase別成功基準

#### Phase 1
- [x] **測定完了**: 全メトリクスのベースライン確立
- [x] **問題特定**: 現状のボトルネック特定完了
- [x] **目標設定**: 改善目標値の合意形成

#### Phase 2  
- [ ] **安定性向上**: タイムアウト率 < 1%
- [ ] **完全性保証**: 全件ダウンロード成功率 > 99%
- [ ] **復旧機能**: エラー自動復旧率 > 95%
- [ ] **長時間動作**: 24時間連続実行成功

#### Phase 3
- [ ] **性能向上**: 新実装 ≥ 既存実装 × 120%
- [ ] **安定性維持**: 全Phase2基準維持
- [ ] **並行処理**: 制限的並行処理の安定動作
- [ ] **中期動作**: 1週間連続実行成功

#### Phase 4
- [ ] **最大性能**: 理想性能目標達成（200%向上）
- [ ] **プロダクション**: 本番環境での安定動作
- [ ] **リソース効率**: メモリ・CPU使用量最適化
- [ ] **長期安定**: 1ヶ月連続運用成功

### 継続監視KPI
- **可用性**: 99.9%以上
- **平均故障間隔 (MTBF)**: 30日以上
- **平均復旧時間 (MTTR)**: 5分以内
- **顧客満足度**: エラー報告 < 1件/月

## 実装チームへの指針

### 開発原則
1. **小さな変更**: 一度に1つの改善のみ実装
2. **徹底的テスト**: 新機能は既存機能を破壊しない
3. **文書化必須**: 全変更の理由と影響を記録
4. **レビュー必須**: 2名以上による査読

### コードレビューチェックリスト
- [ ] タイムアウト処理は適切か？
- [ ] エラーハンドリングは包括的か？
- [ ] フォールバック機能は動作するか？
- [ ] テストカバレッジは十分か？
- [ ] 性能劣化は発生しないか？

### トラブルシューティング
問題発生時の対応フロー：
1. **即座対応**: 実験機能無効化
2. **根本分析**: ログとメトリクス詳細調査
3. **修正実装**: 問題の根本修正
4. **再テスト**: 全テストスイート実行
5. **段階復旧**: 慎重な機能再有効化

---

この計画に従い、安定性を確保しながら確実な性能向上を実現します。