"""
Real-time safety monitoring for parallel operations.

This module provides comprehensive safety monitoring to ensure system stability
during aggressive performance optimization, with automatic threat detection
and mitigation recommendations.
"""

import asyncio
import shutil
import time
import psutil
from collections import deque
from dataclasses import dataclass
from datetime import datetime, timedelta
from enum import Enum
from typing import Dict, List, Optional, Any, Callable
import aiohttp


class SafetyLevel(Enum):
    """System safety levels."""
    EXCELLENT = "excellent"    # 全て正常、積極的最適化可能
    GOOD = "good"             # 正常、通常の最適化可能
    WARNING = "warning"       # 注意が必要、保守的に動作
    CRITICAL = "critical"     # 危険、即座に安全モードへ
    EMERGENCY = "emergency"   # 緊急事態、全処理停止


@dataclass
class SystemHealth:
    """System health indicators."""
    # リソース使用量
    memory_usage_mb: float = 0.0
    memory_usage_percent: float = 0.0
    cpu_usage_percent: float = 0.0
    disk_free_gb: float = 0.0
    disk_usage_percent: float = 0.0
    
    # ネットワーク状態
    network_latency_ms: float = 0.0
    api_connectivity: bool = True
    
    # パフォーマンス指標
    success_rate: float = 1.0
    timeout_rate: float = 0.0
    error_rate: float = 0.0
    
    # システム安定性
    memory_growth_rate_mb_per_hour: float = 0.0
    error_trend: str = "stable"  # increasing, decreasing, stable
    
    # 総合安全性レベル
    overall_safety_level: SafetyLevel = SafetyLevel.GOOD
    safety_score: float = 100.0  # 0-100スコア


@dataclass
class SafetyAlert:
    """Safety alert information."""
    level: SafetyLevel
    component: str
    message: str
    current_value: float
    threshold_value: float
    timestamp: datetime
    recommended_action: str


class SafetyMonitor:
    """
    Real-time system safety monitoring.
    
    Continuously monitors system health indicators and provides
    safety assessments for concurrency decisions.
    """
    
    def __init__(self, output_dir_path: str):
        self.output_dir_path = output_dir_path
        
        # 監視閾値設定
        self.thresholds = {
            # メモリ関連
            'memory_usage_warning_mb': 2048,    # 2GB
            'memory_usage_critical_mb': 4096,   # 4GB
            'memory_growth_warning_mb_per_hour': 100,  # 100MB/時間
            'memory_growth_critical_mb_per_hour': 500, # 500MB/時間
            
            # CPU関連
            'cpu_usage_warning_percent': 80,     # 80%
            'cpu_usage_critical_percent': 95,    # 95%
            
            # ディスク関連
            'disk_free_warning_gb': 5.0,         # 5GB
            'disk_free_critical_gb': 1.0,        # 1GB
            
            # ネットワーク関連
            'network_latency_warning_ms': 3000,  # 3秒
            'network_latency_critical_ms': 10000, # 10秒
            
            # パフォーマンス関連
            'success_rate_warning': 0.95,        # 95%
            'success_rate_critical': 0.90,       # 90%
            'timeout_rate_warning': 0.02,        # 2%
            'timeout_rate_critical': 0.05,       # 5%
            'error_rate_warning': 0.05,          # 5%
            'error_rate_critical': 0.10,         # 10%
        }
        
        # 監視履歴
        self.health_history: deque = deque(maxlen=720)  # 12時間分（1分間隔）
        self.alert_history: deque = deque(maxlen=100)
        
        # システム情報
        self.process = psutil.Process()
        self.monitoring_start_time = time.time()
        
        # アラートコールバック
        self.alert_callbacks: List[Callable[[SafetyAlert], None]] = []
        
    def add_alert_callback(self, callback: Callable[[SafetyAlert], None]) -> None:
        """アラートコールバック追加."""
        self.alert_callbacks.append(callback)
        
    async def get_current_health(self) -> SystemHealth:
        """現在のシステム健全性取得."""
        health = SystemHealth()
        
        try:
            # メモリ使用量
            memory_info = self.process.memory_info()
            health.memory_usage_mb = memory_info.rss / (1024 * 1024)
            
            system_memory = psutil.virtual_memory()
            health.memory_usage_percent = system_memory.percent
            
            # CPU使用率
            health.cpu_usage_percent = self.process.cpu_percent()
            
            # ディスク使用量
            disk_usage = shutil.disk_usage(self.output_dir_path)
            health.disk_free_gb = disk_usage.free / (1024 ** 3)
            health.disk_usage_percent = (
                (disk_usage.total - disk_usage.free) / disk_usage.total * 100
            )
            
            # ネットワーク遅延
            health.network_latency_ms = await self._measure_network_latency()
            health.api_connectivity = await self._check_api_connectivity()
            
            # メモリ増加率計算
            health.memory_growth_rate_mb_per_hour = self._calculate_memory_growth_rate()
            
            # エラー傾向分析
            health.error_trend = self._analyze_error_trend()
            
            # 総合安全性評価
            health.overall_safety_level, health.safety_score = self._assess_overall_safety(health)
            
        except Exception as e:
            print(f"⚠️ Error collecting health metrics: {e}")
            health.overall_safety_level = SafetyLevel.WARNING
            health.safety_score = 50.0
            
        return health
        
    async def _measure_network_latency(self) -> float:
        """ネットワーク遅延測定."""
        try:
            start_time = time.time()
            timeout = aiohttp.ClientTimeout(total=10)
            
            async with aiohttp.ClientSession(timeout=timeout) as session:
                async with session.get("https://civitai.com") as response:
                    return (time.time() - start_time) * 1000
        except Exception:
            return 10000.0  # タイムアウト時は10秒として扱う
            
    async def _check_api_connectivity(self) -> bool:
        """API接続性確認."""
        try:
            timeout = aiohttp.ClientTimeout(total=5)
            async with aiohttp.ClientSession(timeout=timeout) as session:
                async with session.get(
                    "https://civitai.com/api/v1/models",
                    params={'limit': 1}
                ) as response:
                    return response.status == 200
        except Exception:
            return False
            
    def _calculate_memory_growth_rate(self) -> float:
        """メモリ増加率計算."""
        if len(self.health_history) < 2:
            return 0.0
            
        # 最初と最後の記録を比較
        first_record = self.health_history[0]
        last_record = self.health_history[-1]
        
        # 記録が1時間以上離れている場合のみ計算
        time_diff_hours = (last_record['timestamp'] - first_record['timestamp']) / 3600
        if time_diff_hours < 1.0:
            return 0.0
            
        memory_diff = last_record['memory_usage_mb'] - first_record['memory_usage_mb']
        return memory_diff / time_diff_hours
        
    def _analyze_error_trend(self) -> str:
        """エラー傾向分析."""
        if len(self.health_history) < 5:
            return "stable"
            
        # 最近5つの記録でエラー率の傾向を分析
        recent_records = list(self.health_history)[-5:]
        error_rates = [r['error_rate'] for r in recent_records]
        
        # 線形回帰で傾向を判定
        n = len(error_rates)
        x_avg = (n - 1) / 2
        y_avg = sum(error_rates) / n
        
        slope = sum((i - x_avg) * (error_rates[i] - y_avg) for i in range(n))
        slope /= sum((i - x_avg) ** 2 for i in range(n))
        
        if slope > 0.01:  # 1%以上の増加傾向
            return "increasing"
        elif slope < -0.01:  # 1%以上の減少傾向
            return "decreasing"
        else:
            return "stable"
            
    def _assess_overall_safety(self, health: SystemHealth) -> tuple[SafetyLevel, float]:
        """総合安全性評価."""
        score = 100.0
        level = SafetyLevel.EXCELLENT
        
        # メモリ使用量評価
        if health.memory_usage_mb > self.thresholds['memory_usage_critical_mb']:
            score -= 30
            level = max(level, SafetyLevel.CRITICAL, key=lambda x: x.value)
        elif health.memory_usage_mb > self.thresholds['memory_usage_warning_mb']:
            score -= 15
            level = max(level, SafetyLevel.WARNING, key=lambda x: x.value)
            
        # CPU使用率評価
        if health.cpu_usage_percent > self.thresholds['cpu_usage_critical_percent']:
            score -= 25
            level = max(level, SafetyLevel.CRITICAL, key=lambda x: x.value)
        elif health.cpu_usage_percent > self.thresholds['cpu_usage_warning_percent']:
            score -= 10
            level = max(level, SafetyLevel.WARNING, key=lambda x: x.value)
            
        # ディスク容量評価
        if health.disk_free_gb < self.thresholds['disk_free_critical_gb']:
            score -= 35
            level = SafetyLevel.EMERGENCY  # ディスク不足は緊急事態
        elif health.disk_free_gb < self.thresholds['disk_free_warning_gb']:
            score -= 20
            level = max(level, SafetyLevel.WARNING, key=lambda x: x.value)
            
        # ネットワーク遅延評価
        if health.network_latency_ms > self.thresholds['network_latency_critical_ms']:
            score -= 20
            level = max(level, SafetyLevel.CRITICAL, key=lambda x: x.value)
        elif health.network_latency_ms > self.thresholds['network_latency_warning_ms']:
            score -= 10
            level = max(level, SafetyLevel.WARNING, key=lambda x: x.value)
            
        # パフォーマンス指標評価
        if health.success_rate < self.thresholds['success_rate_critical']:
            score -= 25
            level = max(level, SafetyLevel.CRITICAL, key=lambda x: x.value)
        elif health.success_rate < self.thresholds['success_rate_warning']:
            score -= 10
            level = max(level, SafetyLevel.WARNING, key=lambda x: x.value)
            
        # メモリ増加率評価
        if health.memory_growth_rate_mb_per_hour > self.thresholds['memory_growth_critical_mb_per_hour']:
            score -= 30
            level = max(level, SafetyLevel.CRITICAL, key=lambda x: x.value)
        elif health.memory_growth_rate_mb_per_hour > self.thresholds['memory_growth_warning_mb_per_hour']:
            score -= 15
            level = max(level, SafetyLevel.WARNING, key=lambda x: x.value)
            
        # API接続性評価
        if not health.api_connectivity:
            score -= 40
            level = max(level, SafetyLevel.CRITICAL, key=lambda x: x.value)
            
        # スコアの下限設定
        score = max(score, 0.0)
        
        # レベルとスコアの整合性確保
        if score >= 90:
            level = SafetyLevel.EXCELLENT
        elif score >= 70:
            level = max(level, SafetyLevel.GOOD, key=lambda x: x.value)
        elif score >= 50:
            level = max(level, SafetyLevel.WARNING, key=lambda x: x.value)
        elif score >= 20:
            level = max(level, SafetyLevel.CRITICAL, key=lambda x: x.value)
        else:
            level = SafetyLevel.EMERGENCY
            
        return level, score
        
    async def monitor_and_alert(self, health: SystemHealth) -> List[SafetyAlert]:
        """監視とアラート生成."""
        alerts = []
        
        # メモリ使用量チェック
        if health.memory_usage_mb > self.thresholds['memory_usage_critical_mb']:
            alert = SafetyAlert(
                level=SafetyLevel.CRITICAL,
                component="memory",
                message=f"Critical memory usage: {health.memory_usage_mb:.0f}MB",
                current_value=health.memory_usage_mb,
                threshold_value=self.thresholds['memory_usage_critical_mb'],
                timestamp=datetime.utcnow(),
                recommended_action="Reduce concurrency to minimum and check for memory leaks"
            )
            alerts.append(alert)
            
        elif health.memory_usage_mb > self.thresholds['memory_usage_warning_mb']:
            alert = SafetyAlert(
                level=SafetyLevel.WARNING,
                component="memory",
                message=f"High memory usage: {health.memory_usage_mb:.0f}MB",
                current_value=health.memory_usage_mb,
                threshold_value=self.thresholds['memory_usage_warning_mb'],
                timestamp=datetime.utcnow(),
                recommended_action="Consider reducing concurrency levels"
            )
            alerts.append(alert)
            
        # ディスク容量チェック
        if health.disk_free_gb < self.thresholds['disk_free_critical_gb']:
            alert = SafetyAlert(
                level=SafetyLevel.EMERGENCY,
                component="disk",
                message=f"Critical disk space: {health.disk_free_gb:.1f}GB remaining",
                current_value=health.disk_free_gb,
                threshold_value=self.thresholds['disk_free_critical_gb'],
                timestamp=datetime.utcnow(),
                recommended_action="STOP all downloads immediately and free disk space"
            )
            alerts.append(alert)
            
        # CPU使用率チェック
        if health.cpu_usage_percent > self.thresholds['cpu_usage_critical_percent']:
            alert = SafetyAlert(
                level=SafetyLevel.CRITICAL,
                component="cpu",
                message=f"Critical CPU usage: {health.cpu_usage_percent:.1f}%",
                current_value=health.cpu_usage_percent,
                threshold_value=self.thresholds['cpu_usage_critical_percent'],
                timestamp=datetime.utcnow(),
                recommended_action="Reduce concurrency and check system load"
            )
            alerts.append(alert)
            
        # ネットワーク遅延チェック
        if health.network_latency_ms > self.thresholds['network_latency_critical_ms']:
            alert = SafetyAlert(
                level=SafetyLevel.CRITICAL,
                component="network",
                message=f"Critical network latency: {health.network_latency_ms:.0f}ms",
                current_value=health.network_latency_ms,
                threshold_value=self.thresholds['network_latency_critical_ms'],
                timestamp=datetime.utcnow(),
                recommended_action="Switch to conservative mode and check network connection"
            )
            alerts.append(alert)
            
        # メモリリークチェック
        if health.memory_growth_rate_mb_per_hour > self.thresholds['memory_growth_critical_mb_per_hour']:
            alert = SafetyAlert(
                level=SafetyLevel.CRITICAL,
                component="memory_leak",
                message=f"Potential memory leak: {health.memory_growth_rate_mb_per_hour:.1f}MB/hour growth",
                current_value=health.memory_growth_rate_mb_per_hour,
                threshold_value=self.thresholds['memory_growth_critical_mb_per_hour'],
                timestamp=datetime.utcnow(),
                recommended_action="Investigate memory leak and restart if necessary"
            )
            alerts.append(alert)
            
        # アラート処理
        for alert in alerts:
            self.alert_history.append(alert)
            
            # コールバック実行
            for callback in self.alert_callbacks:
                try:
                    callback(alert)
                except Exception as e:
                    print(f"⚠️ Alert callback error: {e}")
                    
        return alerts
        
    def record_health_snapshot(self, health: SystemHealth) -> None:
        """健全性スナップショット記録."""
        snapshot = {
            'timestamp': time.time(),
            'memory_usage_mb': health.memory_usage_mb,
            'cpu_usage_percent': health.cpu_usage_percent,
            'disk_free_gb': health.disk_free_gb,
            'network_latency_ms': health.network_latency_ms,
            'success_rate': health.success_rate,
            'timeout_rate': health.timeout_rate,
            'error_rate': health.error_rate,
            'safety_level': health.overall_safety_level.value,
            'safety_score': health.safety_score
        }
        
        self.health_history.append(snapshot)
        
    def is_safe_for_concurrency_increase(self) -> bool:
        """並行度増加が安全かどうか判定."""
        if not self.health_history:
            return True  # 履歴がない場合は許可
            
        latest_health = self.health_history[-1]
        safety_level = SafetyLevel(latest_health['safety_level'])
        
        return safety_level in [SafetyLevel.EXCELLENT, SafetyLevel.GOOD]
        
    def should_force_safety_mode(self) -> bool:
        """安全モード強制が必要かどうか判定."""
        if not self.health_history:
            return False
            
        latest_health = self.health_history[-1]
        safety_level = SafetyLevel(latest_health['safety_level'])
        
        return safety_level in [SafetyLevel.CRITICAL, SafetyLevel.EMERGENCY]
        
    def get_safety_recommendations(self, health: SystemHealth) -> List[str]:
        """安全性向上の推奨事項生成."""
        recommendations = []
        
        if health.memory_usage_mb > self.thresholds['memory_usage_warning_mb']:
            recommendations.append("Consider reducing concurrent operations to lower memory usage")
            
        if health.disk_free_gb < self.thresholds['disk_free_warning_gb']:
            recommendations.append("Clean up temporary files and consider increasing disk space")
            
        if health.network_latency_ms > self.thresholds['network_latency_warning_ms']:
            recommendations.append("Check network connection stability")
            
        if health.success_rate < self.thresholds['success_rate_warning']:
            recommendations.append("Review error logs and implement additional error handling")
            
        if health.memory_growth_rate_mb_per_hour > self.thresholds['memory_growth_warning_mb_per_hour']:
            recommendations.append("Monitor for potential memory leaks")
            
        if not recommendations:
            recommendations.append("System health is within acceptable parameters")
            
        return recommendations