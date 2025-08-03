"""System health monitoring and alerting."""

import asyncio
import json
import shutil
import time
from dataclasses import dataclass
from datetime import datetime, timedelta
from enum import Enum
from pathlib import Path
from typing import Dict, List, Optional, Any
import aiohttp
import psutil


class AlertLevel(Enum):
    """Alert severity levels."""
    INFO = "info"
    WARNING = "warning"
    CRITICAL = "critical"


@dataclass
class Alert:
    """System alert data structure."""
    level: AlertLevel
    message: str
    metric: str
    value: float
    threshold: float
    timestamp: str
    
    
@dataclass
class HealthStatus:
    """System health status."""
    api_connectivity: bool
    disk_space_ok: bool
    memory_usage_ok: bool
    network_latency_ok: bool
    error_rate_ok: bool
    overall_healthy: bool
    alerts: List[Alert]
    timestamp: str


class HealthMonitor:
    """
    Comprehensive system health monitoring.
    
    Monitors API connectivity, resource usage, error rates,
    and generates alerts when thresholds are exceeded.
    """
    
    def __init__(self, config, output_dir: Path):
        self.config = config
        self.output_dir = output_dir
        self.health_dir = output_dir / "health"
        self.health_dir.mkdir(exist_ok=True)
        
        # 健全性チェック閾値
        self.thresholds = {
            'error_rate_warning': 0.05,    # 5%
            'error_rate_critical': 0.20,   # 20%
            'timeout_rate_warning': 0.01,  # 1%
            'timeout_rate_critical': 0.05, # 5%
            'memory_usage_warning': 2048,  # 2GB
            'memory_usage_critical': 4096, # 4GB
            'disk_space_warning': 5.0,     # 5GB
            'disk_space_critical': 1.0,    # 1GB
            'network_latency_warning': 5000,  # 5秒
            'network_latency_critical': 10000 # 10秒
        }
        
        # アラート履歴（重複回避用）
        self.alert_history: List[Alert] = []
        self.last_alert_times: Dict[str, datetime] = {}
        
        # 健全性チェック間隔（秒）
        self.check_interval = 60
        
        # プロセス情報
        self.process = psutil.Process()
        
    async def run_health_checks(self) -> HealthStatus:
        """全健全性チェック実行."""
        checks = {
            'api_connectivity': self._check_api_connectivity(),
            'disk_space': self._check_disk_space(),
            'memory_usage': self._check_memory_usage(),
            'network_latency': self._check_network_latency(),
            'error_rates': self._check_error_rates()
        }
        
        results = {}
        for check_name, check_coro in checks.items():
            try:
                results[check_name] = await check_coro
            except Exception as e:
                print(f"Health check {check_name} failed: {e}")
                results[check_name] = False
                
        # アラート生成
        alerts = self._generate_alerts(results)
        
        # 全体的な健全性判定
        overall_healthy = all(results.values()) and not any(
            alert.level == AlertLevel.CRITICAL for alert in alerts
        )
        
        status = HealthStatus(
            api_connectivity=results.get('api_connectivity', False),
            disk_space_ok=results.get('disk_space', False),
            memory_usage_ok=results.get('memory_usage', False),
            network_latency_ok=results.get('network_latency', False),
            error_rate_ok=results.get('error_rates', False),
            overall_healthy=overall_healthy,
            alerts=alerts,
            timestamp=datetime.utcnow().isoformat()
        )
        
        # 健全性ログ保存
        self._save_health_log(status)
        
        return status
    
    async def _check_api_connectivity(self) -> bool:
        """API接続性チェック."""
        try:
            timeout = aiohttp.ClientTimeout(total=10)
            async with aiohttp.ClientSession(timeout=timeout) as session:
                # ヘルスチェック用の軽量リクエスト
                async with session.get(
                    "https://civitai.com/api/v1/models",
                    params={'limit': 1}
                ) as response:
                    return response.status == 200
        except Exception:
            return False
    
    async def _check_disk_space(self) -> bool:
        """ディスク容量チェック."""
        try:
            usage = shutil.disk_usage(self.output_dir)
            free_space_gb = usage.free / (1024 ** 3)
            
            if free_space_gb < self.thresholds['disk_space_critical']:
                self._add_alert(
                    AlertLevel.CRITICAL,
                    f"Critical disk space: {free_space_gb:.2f}GB remaining",
                    "disk_space_gb",
                    free_space_gb,
                    self.thresholds['disk_space_critical']
                )
                return False
            elif free_space_gb < self.thresholds['disk_space_warning']:
                self._add_alert(
                    AlertLevel.WARNING,
                    f"Low disk space: {free_space_gb:.2f}GB remaining",
                    "disk_space_gb",
                    free_space_gb,
                    self.thresholds['disk_space_warning']
                )
                
            return free_space_gb > self.thresholds['disk_space_critical']
        except Exception:
            return False
    
    async def _check_memory_usage(self) -> bool:
        """メモリ使用量チェック."""
        try:
            memory_info = self.process.memory_info()
            memory_mb = memory_info.rss / (1024 * 1024)
            
            if memory_mb > self.thresholds['memory_usage_critical']:
                self._add_alert(
                    AlertLevel.CRITICAL,
                    f"Critical memory usage: {memory_mb:.2f}MB",
                    "memory_usage_mb",
                    memory_mb,
                    self.thresholds['memory_usage_critical']
                )
                return False
            elif memory_mb > self.thresholds['memory_usage_warning']:
                self._add_alert(
                    AlertLevel.WARNING,
                    f"High memory usage: {memory_mb:.2f}MB",
                    "memory_usage_mb",
                    memory_mb,
                    self.thresholds['memory_usage_warning']
                )
                
            return memory_mb < self.thresholds['memory_usage_critical']
        except Exception:
            return True  # メモリチェック失敗時は通過
    
    async def _check_network_latency(self) -> bool:
        """ネットワーク遅延チェック."""
        try:
            start_time = time.time()
            timeout = aiohttp.ClientTimeout(total=15)
            
            async with aiohttp.ClientSession(timeout=timeout) as session:
                async with session.get("https://civitai.com") as response:
                    latency_ms = (time.time() - start_time) * 1000
                    
                    if latency_ms > self.thresholds['network_latency_critical']:
                        self._add_alert(
                            AlertLevel.CRITICAL,
                            f"Critical network latency: {latency_ms:.0f}ms",
                            "network_latency_ms",
                            latency_ms,
                            self.thresholds['network_latency_critical']
                        )
                        return False
                    elif latency_ms > self.thresholds['network_latency_warning']:
                        self._add_alert(
                            AlertLevel.WARNING,
                            f"High network latency: {latency_ms:.0f}ms",
                            "network_latency_ms",
                            latency_ms,
                            self.thresholds['network_latency_warning']
                        )
                        
                    return latency_ms < self.thresholds['network_latency_critical']
        except Exception:
            return False
    
    async def _check_error_rates(self) -> bool:
        """エラー率チェック."""
        # メトリクスファイルから最近のエラー率を取得
        error_rate = self._get_recent_error_rate()
        timeout_rate = self._get_recent_timeout_rate()
        
        error_rate_ok = True
        timeout_rate_ok = True
        
        # エラー率チェック
        if error_rate > self.thresholds['error_rate_critical']:
            self._add_alert(
                AlertLevel.CRITICAL,
                f"Critical error rate: {error_rate:.2%}",
                "error_rate",
                error_rate,
                self.thresholds['error_rate_critical']
            )
            error_rate_ok = False
        elif error_rate > self.thresholds['error_rate_warning']:
            self._add_alert(
                AlertLevel.WARNING,
                f"High error rate: {error_rate:.2%}",
                "error_rate",
                error_rate,
                self.thresholds['error_rate_warning']
            )
            
        # タイムアウト率チェック
        if timeout_rate > self.thresholds['timeout_rate_critical']:
            self._add_alert(
                AlertLevel.CRITICAL,
                f"Critical timeout rate: {timeout_rate:.2%}",
                "timeout_rate",
                timeout_rate,
                self.thresholds['timeout_rate_critical']
            )
            timeout_rate_ok = False
        elif timeout_rate > self.thresholds['timeout_rate_warning']:
            self._add_alert(
                AlertLevel.WARNING,
                f"High timeout rate: {timeout_rate:.2%}",
                "timeout_rate",
                timeout_rate,
                self.thresholds['timeout_rate_warning']
            )
            
        return error_rate_ok and timeout_rate_ok
    
    def _get_recent_error_rate(self) -> float:
        """最近1時間のエラー率取得."""
        operations_file = self.output_dir / "metrics" / "operations.jsonl"
        if not operations_file.exists():
            return 0.0
            
        try:
            cutoff_time = datetime.utcnow() - timedelta(hours=1)
            total_operations = 0
            failed_operations = 0
            
            with open(operations_file, 'r', encoding='utf-8') as f:
                for line in f:
                    try:
                        operation = json.loads(line.strip())
                        op_time = datetime.fromisoformat(operation['timestamp'].replace('Z', '+00:00'))
                        
                        if op_time > cutoff_time:
                            total_operations += 1
                            if not operation.get('success', True):
                                failed_operations += 1
                    except (json.JSONDecodeError, KeyError, ValueError):
                        continue
                        
            return failed_operations / total_operations if total_operations > 0 else 0.0
        except Exception:
            return 0.0
    
    def _get_recent_timeout_rate(self) -> float:
        """最近1時間のタイムアウト率取得."""
        operations_file = self.output_dir / "metrics" / "operations.jsonl"
        if not operations_file.exists():
            return 0.0
            
        try:
            cutoff_time = datetime.utcnow() - timedelta(hours=1)
            total_operations = 0
            timeout_operations = 0
            
            with open(operations_file, 'r', encoding='utf-8') as f:
                for line in f:
                    try:
                        operation = json.loads(line.strip())
                        op_time = datetime.fromisoformat(operation['timestamp'].replace('Z', '+00:00'))
                        
                        if op_time > cutoff_time:
                            total_operations += 1
                            if operation.get('timeout_occurred', False):
                                timeout_operations += 1
                    except (json.JSONDecodeError, KeyError, ValueError):
                        continue
                        
            return timeout_operations / total_operations if total_operations > 0 else 0.0
        except Exception:
            return 0.0
    
    def _add_alert(self, level: AlertLevel, message: str, metric: str, value: float, threshold: float):
        """アラート追加（重複回避付き）."""
        alert_key = f"{metric}_{level.value}"
        now = datetime.utcnow()
        
        # クールダウンチェック（同じアラートを短時間で重複送信回避）
        if alert_key in self.last_alert_times:
            last_time = self.last_alert_times[alert_key]
            cooldown_minutes = 15 if level == AlertLevel.WARNING else 5
            
            if now - last_time < timedelta(minutes=cooldown_minutes):
                return  # クールダウン中
                
        alert = Alert(
            level=level,
            message=message,
            metric=metric,
            value=value,
            threshold=threshold,
            timestamp=now.isoformat()
        )
        
        self.alert_history.append(alert)
        self.last_alert_times[alert_key] = now
        
        # アラート履歴の制限（最新100件まで）
        if len(self.alert_history) > 100:
            self.alert_history = self.alert_history[-100:]
    
    def _generate_alerts(self, check_results: Dict[str, bool]) -> List[Alert]:
        """現在のアラート生成."""
        current_alerts = []
        
        # 最近のアラートから現在も有効なもの抽出
        recent_cutoff = datetime.utcnow() - timedelta(minutes=30)
        
        for alert in self.alert_history:
            alert_time = datetime.fromisoformat(alert.timestamp)
            if alert_time > recent_cutoff:
                current_alerts.append(alert)
                
        return current_alerts
    
    def _save_health_log(self, status: HealthStatus):
        """健全性ログ保存."""
        log_file = self.health_dir / "health.jsonl"
        
        log_entry = {
            "timestamp": status.timestamp,
            "api_connectivity": status.api_connectivity,
            "disk_space_ok": status.disk_space_ok,
            "memory_usage_ok": status.memory_usage_ok,
            "network_latency_ok": status.network_latency_ok,
            "error_rate_ok": status.error_rate_ok,
            "overall_healthy": status.overall_healthy,
            "active_alerts": len(status.alerts),
            "critical_alerts": len([a for a in status.alerts if a.level == AlertLevel.CRITICAL])
        }
        
        with open(log_file, 'a', encoding='utf-8') as f:
            f.write(json.dumps(log_entry, ensure_ascii=False) + '\n')
    
    async def continuous_monitoring(self, duration_hours: Optional[float] = None):
        """継続的な健全性監視."""
        start_time = time.time()
        
        print(f"🔍 Starting continuous health monitoring (interval: {self.check_interval}s)")
        
        try:
            while True:
                # 健全性チェック実行
                status = await self.run_health_checks()
                
                # ステータス表示
                health_indicator = "✅" if status.overall_healthy else "❌"
                print(f"{health_indicator} Health check: {status.timestamp}")
                
                # クリティカルアラートがあれば詳細表示
                critical_alerts = [a for a in status.alerts if a.level == AlertLevel.CRITICAL]
                if critical_alerts:
                    print("🚨 CRITICAL ALERTS:")
                    for alert in critical_alerts:
                        print(f"   - {alert.message}")
                
                # 実行時間制限チェック
                if duration_hours:
                    elapsed_hours = (time.time() - start_time) / 3600
                    if elapsed_hours >= duration_hours:
                        print(f"⏰ Monitoring duration completed: {elapsed_hours:.2f}h")
                        break
                
                # 次のチェックまで待機
                await asyncio.sleep(self.check_interval)
                
        except KeyboardInterrupt:
            print("\n⏹️  Health monitoring stopped by user")
        except Exception as e:
            print(f"❌ Health monitoring error: {e}")
    
    def generate_health_report(self) -> Dict[str, Any]:
        """健全性レポート生成."""
        # 最近24時間のログ分析
        log_file = self.health_dir / "health.jsonl"
        if not log_file.exists():
            return {"error": "No health log data available"}
            
        cutoff_time = datetime.utcnow() - timedelta(hours=24)
        health_records = []
        
        try:
            with open(log_file, 'r', encoding='utf-8') as f:
                for line in f:
                    try:
                        record = json.loads(line.strip())
                        record_time = datetime.fromisoformat(record['timestamp'])
                        if record_time > cutoff_time:
                            health_records.append(record)
                    except (json.JSONDecodeError, KeyError, ValueError):
                        continue
        except Exception:
            return {"error": "Failed to read health log"}
            
        if not health_records:
            return {"error": "No recent health data available"}
            
        # 統計計算
        total_checks = len(health_records)
        healthy_checks = sum(1 for r in health_records if r['overall_healthy'])
        
        report = {
            "period": "Last 24 hours",
            "total_health_checks": total_checks,
            "healthy_percentage": (healthy_checks / total_checks * 100) if total_checks > 0 else 0,
            "component_availability": {
                "api_connectivity": sum(1 for r in health_records if r['api_connectivity']) / total_checks * 100,
                "disk_space": sum(1 for r in health_records if r['disk_space_ok']) / total_checks * 100,
                "memory_usage": sum(1 for r in health_records if r['memory_usage_ok']) / total_checks * 100,
                "network_latency": sum(1 for r in health_records if r['network_latency_ok']) / total_checks * 100,
                "error_rates": sum(1 for r in health_records if r['error_rate_ok']) / total_checks * 100
            },
            "alert_summary": {
                "total_alerts": sum(r['active_alerts'] for r in health_records),
                "critical_alerts": sum(r['critical_alerts'] for r in health_records),
                "avg_alerts_per_check": sum(r['active_alerts'] for r in health_records) / total_checks
            },
            "recommendations": self._generate_recommendations(health_records)
        }
        
        return report
    
    def _generate_recommendations(self, health_records: List[Dict]) -> List[str]:
        """健全性改善推奨事項生成."""
        recommendations = []
        
        # 各コンポーネントの可用性チェック
        total_checks = len(health_records)
        
        api_availability = sum(1 for r in health_records if r['api_connectivity']) / total_checks
        if api_availability < 0.95:
            recommendations.append(
                f"API connectivity is low ({api_availability:.1%}). "
                "Consider implementing retry logic or checking network configuration."
            )
            
        disk_availability = sum(1 for r in health_records if r['disk_space_ok']) / total_checks
        if disk_availability < 0.90:
            recommendations.append(
                f"Disk space issues detected ({disk_availability:.1%}). "
                "Consider cleanup routines or increasing storage capacity."
            )
            
        memory_availability = sum(1 for r in health_records if r['memory_usage_ok']) / total_checks
        if memory_availability < 0.90:
            recommendations.append(
                f"Memory usage concerns ({memory_availability:.1%}). "
                "Consider implementing memory optimization or increasing available RAM."
            )
            
        error_rate_ok = sum(1 for r in health_records if r['error_rate_ok']) / total_checks
        if error_rate_ok < 0.90:
            recommendations.append(
                f"High error rates detected ({error_rate_ok:.1%}). "
                "Review error logs and implement additional error handling."
            )
            
        return recommendations