"""Performance monitoring and measurement framework."""

import json
import time
from collections import deque
from dataclasses import dataclass, asdict
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional, Any
import psutil


@dataclass
class PerformanceMetrics:
    """Performance metrics data structure."""
    timestamp: str
    download_speed_mbps: float
    api_response_time_ms: int
    memory_usage_mb: float
    cpu_usage_percent: float
    success_rate_percent: float
    timeout_rate_percent: float
    active_downloads: int
    queue_size: int
    total_downloads: int
    successful_downloads: int
    failed_downloads: int


@dataclass
class DownloadOperation:
    """Individual download operation tracking."""
    operation_id: str
    url: str
    filepath: str
    start_time: float
    end_time: Optional[float] = None
    file_size_mb: float = 0.0
    success: bool = False
    error_type: Optional[str] = None
    timeout_occurred: bool = False


class PerformanceMonitor:
    """
    Comprehensive performance monitoring system.
    
    Tracks download speeds, API response times, resource usage,
    and provides baseline measurements for optimization.
    """
    
    def __init__(self, output_dir: Path):
        self.output_dir = output_dir
        self.metrics_dir = output_dir / "metrics"
        self.metrics_dir.mkdir(exist_ok=True)
        
        # メトリクス履歴（メモリ内）
        self.download_speeds: deque = deque(maxlen=1000)
        self.api_response_times: deque = deque(maxlen=1000)
        self.memory_usage: deque = deque(maxlen=100)
        self.cpu_usage: deque = deque(maxlen=100)
        
        # 進行中の操作追跡
        self.active_operations: Dict[str, DownloadOperation] = {}
        
        # 統計情報
        self.total_downloads = 0
        self.successful_downloads = 0
        self.failed_downloads = 0
        self.timeout_count = 0
        
        # 監視開始時刻
        self.monitoring_start_time = time.time()
        
        # プロセス情報
        self.process = psutil.Process()
        
    def start_download_operation(self, operation_id: str, url: str, filepath: Path) -> None:
        """ダウンロード操作開始記録."""
        operation = DownloadOperation(
            operation_id=operation_id,
            url=url,
            filepath=str(filepath),
            start_time=time.time()
        )
        self.active_operations[operation_id] = operation
        
    def complete_download_operation(
        self, 
        operation_id: str, 
        success: bool, 
        file_size_mb: float = 0.0,
        error_type: Optional[str] = None,
        timeout_occurred: bool = False
    ) -> None:
        """ダウンロード操作完了記録."""
        if operation_id not in self.active_operations:
            return
            
        operation = self.active_operations[operation_id]
        operation.end_time = time.time()
        operation.success = success
        operation.file_size_mb = file_size_mb
        operation.error_type = error_type
        operation.timeout_occurred = timeout_occurred
        
        # 統計更新
        self.total_downloads += 1
        if success:
            self.successful_downloads += 1
            
            # ダウンロード速度記録
            duration = operation.end_time - operation.start_time
            if duration > 0 and file_size_mb > 0:
                speed_mbps = file_size_mb / duration
                self.download_speeds.append(speed_mbps)
        else:
            self.failed_downloads += 1
            
        if timeout_occurred:
            self.timeout_count += 1
            
        # 完了した操作を履歴に保存
        self._save_operation_log(operation)
        del self.active_operations[operation_id]
        
    def record_api_response_time(self, response_time_ms: int) -> None:
        """API応答時間記録."""
        self.api_response_times.append(response_time_ms)
        
    def collect_system_metrics(self) -> None:
        """システムメトリクス収集."""
        try:
            # メモリ使用量
            memory_info = self.process.memory_info()
            memory_mb = memory_info.rss / (1024 * 1024)
            self.memory_usage.append(memory_mb)
            
            # CPU使用率
            cpu_percent = self.process.cpu_percent()
            self.cpu_usage.append(cpu_percent)
            
        except psutil.NoSuchProcess:
            # プロセスが終了している場合
            pass
            
    def get_current_metrics(self) -> PerformanceMetrics:
        """現在のパフォーマンスメトリクス取得."""
        self.collect_system_metrics()
        
        # 平均値計算
        avg_download_speed = (
            sum(self.download_speeds) / len(self.download_speeds) 
            if self.download_speeds else 0.0
        )
        
        avg_api_response_time = (
            sum(self.api_response_times) / len(self.api_response_times)
            if self.api_response_times else 0
        )
        
        current_memory = (
            self.memory_usage[-1] if self.memory_usage else 0.0
        )
        
        current_cpu = (
            self.cpu_usage[-1] if self.cpu_usage else 0.0
        )
        
        # 成功率・タイムアウト率計算
        success_rate = (
            (self.successful_downloads / self.total_downloads * 100)
            if self.total_downloads > 0 else 100.0
        )
        
        timeout_rate = (
            (self.timeout_count / self.total_downloads * 100)
            if self.total_downloads > 0 else 0.0
        )
        
        return PerformanceMetrics(
            timestamp=datetime.utcnow().isoformat(),
            download_speed_mbps=avg_download_speed,
            api_response_time_ms=int(avg_api_response_time),
            memory_usage_mb=current_memory,
            cpu_usage_percent=current_cpu,
            success_rate_percent=success_rate,
            timeout_rate_percent=timeout_rate,
            active_downloads=len(self.active_operations),
            queue_size=0,  # キューサイズは別途実装
            total_downloads=self.total_downloads,
            successful_downloads=self.successful_downloads,
            failed_downloads=self.failed_downloads
        )
        
    def save_metrics_snapshot(self, filename: Optional[str] = None) -> Path:
        """メトリクススナップショット保存."""
        if filename is None:
            timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
            filename = f"metrics_snapshot_{timestamp}.json"
            
        filepath = self.metrics_dir / filename
        metrics = self.get_current_metrics()
        
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(asdict(metrics), f, indent=2, ensure_ascii=False)
            
        return filepath
        
    def generate_performance_report(self) -> Dict[str, Any]:
        """パフォーマンスレポート生成."""
        current_metrics = self.get_current_metrics()
        
        # 統計値計算
        download_speeds_list = list(self.download_speeds)
        api_times_list = list(self.api_response_times)
        
        report = {
            "summary": {
                "monitoring_duration_hours": (
                    time.time() - self.monitoring_start_time
                ) / 3600,
                "total_operations": self.total_downloads,
                "success_rate": current_metrics.success_rate_percent,
                "timeout_rate": current_metrics.timeout_rate_percent
            },
            "download_performance": {
                "average_speed_mbps": current_metrics.download_speed_mbps,
                "max_speed_mbps": max(download_speeds_list) if download_speeds_list else 0,
                "min_speed_mbps": min(download_speeds_list) if download_speeds_list else 0,
                "speed_samples": len(download_speeds_list)
            },
            "api_performance": {
                "average_response_time_ms": current_metrics.api_response_time_ms,
                "max_response_time_ms": max(api_times_list) if api_times_list else 0,
                "min_response_time_ms": min(api_times_list) if api_times_list else 0,
                "response_samples": len(api_times_list)
            },
            "resource_usage": {
                "current_memory_mb": current_metrics.memory_usage_mb,
                "peak_memory_mb": max(self.memory_usage) if self.memory_usage else 0,
                "average_cpu_percent": (
                    sum(self.cpu_usage) / len(self.cpu_usage)
                    if self.cpu_usage else 0
                )
            },
            "error_analysis": {
                "total_failures": self.failed_downloads,
                "timeout_failures": self.timeout_count,
                "other_failures": self.failed_downloads - self.timeout_count
            }
        }
        
        return report
        
    def save_performance_report(self, filename: Optional[str] = None) -> Path:
        """パフォーマンスレポート保存."""
        if filename is None:
            timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
            filename = f"performance_report_{timestamp}.json"
            
        filepath = self.metrics_dir / filename
        report = self.generate_performance_report()
        
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(report, f, indent=2, ensure_ascii=False)
            
        return filepath
        
    def _save_operation_log(self, operation: DownloadOperation) -> None:
        """個別操作ログ保存."""
        log_file = self.metrics_dir / "operations.jsonl"
        
        log_entry = {
            "timestamp": datetime.utcnow().isoformat(),
            "operation_id": operation.operation_id,
            "url": operation.url,
            "filepath": operation.filepath,
            "duration_seconds": (
                operation.end_time - operation.start_time 
                if operation.end_time else 0
            ),
            "file_size_mb": operation.file_size_mb,
            "success": operation.success,
            "error_type": operation.error_type,
            "timeout_occurred": operation.timeout_occurred,
            "speed_mbps": (
                operation.file_size_mb / (operation.end_time - operation.start_time)
                if operation.end_time and operation.end_time > operation.start_time and operation.file_size_mb > 0
                else 0
            )
        }
        
        with open(log_file, 'a', encoding='utf-8') as f:
            f.write(json.dumps(log_entry, ensure_ascii=False) + '\n')
            
    def load_baseline_metrics(self, baseline_file: Path) -> Optional[PerformanceMetrics]:
        """ベースラインメトリクス読み込み."""
        if not baseline_file.exists():
            return None
            
        try:
            with open(baseline_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
                return PerformanceMetrics(**data)
        except (json.JSONDecodeError, TypeError) as e:
            print(f"Failed to load baseline metrics: {e}")
            return None
            
    def compare_with_baseline(self, baseline: PerformanceMetrics) -> Dict[str, Any]:
        """ベースラインとの比較."""
        current = self.get_current_metrics()
        
        def calculate_change(current_val, baseline_val):
            if baseline_val == 0:
                return 0.0
            return ((current_val - baseline_val) / baseline_val) * 100
            
        comparison = {
            "download_speed_change_percent": calculate_change(
                current.download_speed_mbps, baseline.download_speed_mbps
            ),
            "api_response_time_change_percent": calculate_change(
                current.api_response_time_ms, baseline.api_response_time_ms
            ),
            "memory_usage_change_percent": calculate_change(
                current.memory_usage_mb, baseline.memory_usage_mb
            ),
            "success_rate_change_percent": calculate_change(
                current.success_rate_percent, baseline.success_rate_percent
            ),
            "timeout_rate_change_percent": calculate_change(
                current.timeout_rate_percent, baseline.timeout_rate_percent
            ),
            "current_metrics": asdict(current),
            "baseline_metrics": asdict(baseline)
        }
        
        return comparison