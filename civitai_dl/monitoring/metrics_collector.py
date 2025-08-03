"""Metrics collection and aggregation system."""

import json
import time
from collections import defaultdict, deque
from dataclasses import dataclass, asdict
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional, Any, Union
import threading


@dataclass
class SystemMetrics:
    """System-wide metrics snapshot."""
    timestamp: str
    total_downloads: int
    successful_downloads: int
    failed_downloads: int
    timeout_count: int
    error_rate: float
    timeout_rate: float
    average_download_speed_mbps: float
    average_api_response_time_ms: float
    memory_usage_mb: float
    cpu_usage_percent: float
    active_operations: int
    queue_size: int
    memory_growth_rate_mb_per_hour: float


class MetricsCollector:
    """
    Thread-safe metrics collection and aggregation system.
    
    Provides counters, histograms, and gauges for comprehensive
    performance monitoring and analysis.
    """
    
    def __init__(self, output_dir: Path):
        self.output_dir = output_dir
        self.metrics_dir = output_dir / "metrics"
        self.metrics_dir.mkdir(exist_ok=True)
        
        # Thread safety
        self._lock = threading.Lock()
        
        # カウンター（累積値）
        self._counters: Dict[str, int] = defaultdict(int)
        
        # ゲージ（現在値）
        self._gauges: Dict[str, float] = {}
        
        # ヒストグラム（値の分布）
        self._histograms: Dict[str, deque] = defaultdict(lambda: deque(maxlen=1000))
        
        # タイマー（処理時間測定）
        self._active_timers: Dict[str, float] = {}
        
        # メトリクス履歴
        self._metrics_history: deque = deque(maxlen=1440)  # 24時間分（1分間隔）
        
        # 開始時刻
        self._start_time = time.time()
        
        # 自動保存設定
        self._auto_save_interval = 300  # 5分
        self._last_save_time = time.time()
        
    def increment(self, name: str, value: int = 1) -> None:
        """カウンター増加."""
        with self._lock:
            self._counters[name] += value
            
    def decrement(self, name: str, value: int = 1) -> None:
        """カウンター減少."""
        with self._lock:
            self._counters[name] -= value
            
    def set_gauge(self, name: str, value: float) -> None:
        """ゲージ値設定."""
        with self._lock:
            self._gauges[name] = value
            
    def histogram(self, name: str, value: float) -> None:
        """ヒストグラム値追加."""
        with self._lock:
            self._histograms[name].append(value)
            
    def time_operation(self, name: str):
        """処理時間測定用コンテキストマネージャー."""
        return TimingContext(self, name)
        
    def start_timer(self, name: str) -> None:
        """タイマー開始."""
        with self._lock:
            self._active_timers[name] = time.time()
            
    def end_timer(self, name: str) -> Optional[float]:
        """タイマー終了して処理時間を記録."""
        with self._lock:
            if name in self._active_timers:
                duration = time.time() - self._active_timers[name]
                del self._active_timers[name]
                self.histogram(f"{name}_duration", duration)
                return duration
        return None
        
    def get_counter(self, name: str) -> int:
        """カウンター値取得."""
        with self._lock:
            return self._counters.get(name, 0)
            
    def get_gauge(self, name: str) -> Optional[float]:
        """ゲージ値取得."""
        with self._lock:
            return self._gauges.get(name)
            
    def get_histogram_stats(self, name: str) -> Dict[str, float]:
        """ヒストグラム統計取得."""
        with self._lock:
            values = list(self._histograms.get(name, []))
            
        if not values:
            return {
                "count": 0,
                "min": 0.0,
                "max": 0.0,
                "avg": 0.0,
                "p50": 0.0,
                "p95": 0.0,
                "p99": 0.0
            }
            
        sorted_values = sorted(values)
        count = len(sorted_values)
        
        return {
            "count": count,
            "min": sorted_values[0],
            "max": sorted_values[-1],
            "avg": sum(sorted_values) / count,
            "p50": sorted_values[int(count * 0.5)],
            "p95": sorted_values[int(count * 0.95)],
            "p99": sorted_values[int(count * 0.99)]
        }
        
    def collect_system_metrics(self) -> SystemMetrics:
        """システム全体のメトリクス収集."""
        with self._lock:
            total_downloads = self._counters.get("downloads_total", 0)
            successful_downloads = self._counters.get("downloads_successful", 0)
            failed_downloads = self._counters.get("downloads_failed", 0)
            timeout_count = self._counters.get("timeouts_total", 0)
            
            # 成功率・タイムアウト率計算
            error_rate = (failed_downloads / total_downloads) if total_downloads > 0 else 0.0
            timeout_rate = (timeout_count / total_downloads) if total_downloads > 0 else 0.0
            
            # ダウンロード速度統計
            speed_stats = self.get_histogram_stats("download_speed_mbps")
            
            # API応答時間統計
            api_stats = self.get_histogram_stats("api_response_time_ms")
            
            # 現在のリソース使用量
            memory_usage = self._gauges.get("memory_usage_mb", 0.0)
            cpu_usage = self._gauges.get("cpu_usage_percent", 0.0)
            active_operations = self._gauges.get("active_operations", 0.0)
            queue_size = self._gauges.get("queue_size", 0.0)
            
            # メモリ増加率計算
            memory_growth_rate = self._calculate_memory_growth_rate()
            
        return SystemMetrics(
            timestamp=datetime.utcnow().isoformat(),
            total_downloads=total_downloads,
            successful_downloads=successful_downloads,
            failed_downloads=failed_downloads,
            timeout_count=timeout_count,
            error_rate=error_rate,
            timeout_rate=timeout_rate,
            average_download_speed_mbps=speed_stats["avg"],
            average_api_response_time_ms=api_stats["avg"],
            memory_usage_mb=memory_usage,
            cpu_usage_percent=cpu_usage,
            active_operations=int(active_operations),
            queue_size=int(queue_size),
            memory_growth_rate_mb_per_hour=memory_growth_rate
        )
        
    def _calculate_memory_growth_rate(self) -> float:
        """メモリ増加率計算（MB/時間）."""
        if len(self._metrics_history) < 2:
            return 0.0
            
        # 最初と最後の記録を比較
        first_record = self._metrics_history[0]
        last_record = self._metrics_history[-1]
        
        time_diff_hours = (
            datetime.fromisoformat(last_record.timestamp) - 
            datetime.fromisoformat(first_record.timestamp)
        ).total_seconds() / 3600
        
        if time_diff_hours <= 0:
            return 0.0
            
        memory_diff = last_record.memory_usage_mb - first_record.memory_usage_mb
        return memory_diff / time_diff_hours
        
    def record_metrics_snapshot(self) -> SystemMetrics:
        """メトリクススナップショット記録."""
        metrics = self.collect_system_metrics()
        
        with self._lock:
            self._metrics_history.append(metrics)
            
        # 自動保存チェック
        if time.time() - self._last_save_time > self._auto_save_interval:
            self.save_metrics_to_file()
            
        return metrics
        
    def save_metrics_to_file(self, filename: Optional[str] = None) -> Path:
        """メトリクスファイル保存."""
        if filename is None:
            timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
            filename = f"metrics_{timestamp}.json"
            
        filepath = self.metrics_dir / filename
        
        # 現在のメトリクス状態をまとめて保存
        metrics_data = {
            "metadata": {
                "collection_start_time": datetime.fromtimestamp(self._start_time).isoformat(),
                "collection_duration_hours": (time.time() - self._start_time) / 3600,
                "total_snapshots": len(self._metrics_history)
            },
            "current_metrics": asdict(self.collect_system_metrics()),
            "counters": dict(self._counters),
            "gauges": dict(self._gauges),
            "histogram_stats": {
                name: self.get_histogram_stats(name) 
                for name in self._histograms.keys()
            },
            "metrics_history": [asdict(m) for m in list(self._metrics_history)]
        }
        
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(metrics_data, f, indent=2, ensure_ascii=False)
            
        self._last_save_time = time.time()
        return filepath
        
    def load_metrics_from_file(self, filepath: Path) -> bool:
        """メトリクスファイル読み込み."""
        if not filepath.exists():
            return False
            
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                data = json.load(f)
                
            with self._lock:
                # カウンターとゲージを復元
                self._counters.update(data.get("counters", {}))
                self._gauges.update(data.get("gauges", {}))
                
                # 履歴を復元
                history_data = data.get("metrics_history", [])
                for record_data in history_data:
                    self._metrics_history.append(SystemMetrics(**record_data))
                    
            return True
        except (json.JSONDecodeError, KeyError, TypeError) as e:
            print(f"Failed to load metrics: {e}")
            return False
            
    def reset_metrics(self) -> None:
        """メトリクスリセット."""
        with self._lock:
            self._counters.clear()
            self._gauges.clear()
            self._histograms.clear()
            self._active_timers.clear()
            self._metrics_history.clear()
            self._start_time = time.time()
            
    def generate_performance_summary(self) -> Dict[str, Any]:
        """パフォーマンス要約生成."""
        current_metrics = self.collect_system_metrics()
        
        # 各種統計の取得
        download_stats = self.get_histogram_stats("download_speed_mbps")
        api_stats = self.get_histogram_stats("api_response_time_ms")
        duration_stats = self.get_histogram_stats("download_duration")
        
        summary = {
            "overview": {
                "collection_duration_hours": (time.time() - self._start_time) / 3600,
                "total_operations": current_metrics.total_downloads,
                "success_rate": (1 - current_metrics.error_rate) * 100,
                "timeout_rate": current_metrics.timeout_rate * 100
            },
            "performance": {
                "download_speed": {
                    "average_mbps": download_stats["avg"],
                    "max_mbps": download_stats["max"],
                    "p95_mbps": download_stats["p95"]
                },
                "api_response": {
                    "average_ms": api_stats["avg"],
                    "max_ms": api_stats["max"],
                    "p95_ms": api_stats["p95"]
                },
                "operation_duration": {
                    "average_seconds": duration_stats["avg"],
                    "max_seconds": duration_stats["max"],
                    "p95_seconds": duration_stats["p95"]
                }
            },
            "resource_usage": {
                "current_memory_mb": current_metrics.memory_usage_mb,
                "memory_growth_rate_mb_per_hour": current_metrics.memory_growth_rate_mb_per_hour,
                "current_cpu_percent": current_metrics.cpu_usage_percent
            },
            "reliability": {
                "error_rate_percent": current_metrics.error_rate * 100,
                "timeout_rate_percent": current_metrics.timeout_rate * 100,
                "total_errors": current_metrics.failed_downloads,
                "total_timeouts": current_metrics.timeout_count
            }
        }
        
        return summary
        
    def compare_with_baseline(self, baseline_file: Path) -> Optional[Dict[str, Any]]:
        """ベースラインとの比較分析."""
        if not baseline_file.exists():
            return None
            
        try:
            with open(baseline_file, 'r', encoding='utf-8') as f:
                baseline_data = json.load(f)
                
            baseline_metrics = baseline_data.get("current_metrics", {})
            current_metrics = asdict(self.collect_system_metrics())
            
            def calculate_change(current_val, baseline_val):
                if baseline_val == 0:
                    return 0.0
                return ((current_val - baseline_val) / baseline_val) * 100
                
            comparison = {
                "performance_changes": {
                    "download_speed_change_percent": calculate_change(
                        current_metrics["average_download_speed_mbps"],
                        baseline_metrics.get("average_download_speed_mbps", 0)
                    ),
                    "api_response_time_change_percent": calculate_change(
                        current_metrics["average_api_response_time_ms"],
                        baseline_metrics.get("average_api_response_time_ms", 0)
                    ),
                    "memory_usage_change_percent": calculate_change(
                        current_metrics["memory_usage_mb"],
                        baseline_metrics.get("memory_usage_mb", 0)
                    )
                },
                "reliability_changes": {
                    "error_rate_change_percent": calculate_change(
                        current_metrics["error_rate"],
                        baseline_metrics.get("error_rate", 0)
                    ),
                    "timeout_rate_change_percent": calculate_change(
                        current_metrics["timeout_rate"],
                        baseline_metrics.get("timeout_rate", 0)
                    )
                },
                "current_metrics": current_metrics,
                "baseline_metrics": baseline_metrics,
                "comparison_timestamp": datetime.utcnow().isoformat()
            }
            
            return comparison
            
        except (json.JSONDecodeError, KeyError) as e:
            print(f"Failed to compare with baseline: {e}")
            return None


class TimingContext:
    """処理時間測定用コンテキストマネージャー."""
    
    def __init__(self, collector: MetricsCollector, name: str):
        self.collector = collector
        self.name = name
        self.start_time = None
        
    def __enter__(self):
        self.start_time = time.time()
        return self
        
    def __exit__(self, exc_type, exc_val, exc_tb):
        if self.start_time is not None:
            duration = time.time() - self.start_time
            self.collector.histogram(f"{self.name}_duration", duration)