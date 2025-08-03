"""
Graduated fallback management for system stability.

This module provides intelligent fallback strategies that gradually reduce
system load and concurrency levels in response to detected issues, ensuring
graceful degradation rather than abrupt failures.
"""

import time
from collections import deque
from dataclasses import dataclass
from enum import Enum
from typing import Dict, List, Optional, Any, Callable
from datetime import datetime, timedelta


class FallbackLevel(Enum):
    """Graduated fallback levels."""
    NORMAL = 0          # 通常動作
    REDUCED = 1         # 並行度削減
    CONSERVATIVE = 2    # 保守的モード
    SYNC_ONLY = 3       # 同期処理のみ
    EMERGENCY_STOP = 4  # 緊急停止


class TriggerReason(Enum):
    """Fallback trigger reasons."""
    HIGH_ERROR_RATE = "high_error_rate"
    MEMORY_PRESSURE = "memory_pressure"
    DISK_SPACE_LOW = "disk_space_low"
    NETWORK_ISSUES = "network_issues"
    CONSECUTIVE_FAILURES = "consecutive_failures"
    CPU_OVERLOAD = "cpu_overload"
    SAFETY_ALERT = "safety_alert"
    USER_REQUEST = "user_request"


@dataclass
class FallbackEvent:
    """Fallback event record."""
    timestamp: datetime
    from_level: FallbackLevel
    to_level: FallbackLevel
    trigger_reason: TriggerReason
    trigger_details: Dict[str, Any]
    auto_recovery_enabled: bool = True


@dataclass
class RecoveryConditions:
    """Recovery condition thresholds."""
    min_stable_duration_minutes: int = 10
    required_success_rate: float = 0.98
    max_error_rate: float = 0.02
    max_memory_usage_mb: float = 2048
    min_disk_free_gb: float = 5.0
    max_cpu_usage_percent: float = 80.0


class GraduatedFallbackManager:
    """
    Graduated fallback management system.
    
    Provides intelligent fallback strategies that progressively reduce system
    load in response to various failure conditions, with automatic recovery
    when conditions improve.
    """
    
    def __init__(self):
        # Current state
        self.current_level = FallbackLevel.NORMAL
        self.fallback_start_time: Optional[datetime] = None
        
        # History and monitoring
        self.fallback_history: deque = deque(maxlen=50)
        self.recent_errors: deque = deque(maxlen=100)
        self.system_metrics: deque = deque(maxlen=60)  # 1 hour at 1-minute intervals
        
        # Recovery conditions
        self.recovery_conditions = RecoveryConditions()
        
        # Callbacks for level changes
        self.level_change_callbacks: List[Callable[[FallbackLevel], None]] = []
        
        # Auto-recovery settings
        self.auto_recovery_enabled = True
        self.recovery_check_interval = 60  # seconds
        self.last_recovery_check = time.time()
        
        # Escalation thresholds
        self.escalation_thresholds = {
            FallbackLevel.NORMAL: {
                'error_rate_threshold': 0.05,      # 5%
                'consecutive_failures': 3,
                'memory_threshold_mb': 3072,       # 3GB
                'cpu_threshold_percent': 85,
                'disk_threshold_gb': 3.0
            },
            FallbackLevel.REDUCED: {
                'error_rate_threshold': 0.10,      # 10%
                'consecutive_failures': 5,
                'memory_threshold_mb': 4096,       # 4GB
                'cpu_threshold_percent': 90,
                'disk_threshold_gb': 2.0
            },
            FallbackLevel.CONSERVATIVE: {
                'error_rate_threshold': 0.20,      # 20%
                'consecutive_failures': 8,
                'memory_threshold_mb': 5120,       # 5GB
                'cpu_threshold_percent': 95,
                'disk_threshold_gb': 1.0
            },
            FallbackLevel.SYNC_ONLY: {
                'error_rate_threshold': 0.50,      # 50%
                'consecutive_failures': 10,
                'memory_threshold_mb': 6144,       # 6GB
                'cpu_threshold_percent': 98,
                'disk_threshold_gb': 0.5
            }
        }
        
    def add_level_change_callback(self, callback: Callable[[FallbackLevel], None]) -> None:
        """レベル変更コールバック追加."""
        self.level_change_callbacks.append(callback)
        
    def record_operation_result(self, success: bool, error_details: Optional[Dict[str, Any]] = None) -> None:
        """操作結果記録."""
        result = {
            'timestamp': time.time(),
            'success': success,
            'error_details': error_details or {}
        }
        
        self.recent_errors.append(result)
        
        # Auto-escalation check
        if not success:
            self._check_escalation_needed()
            
        # Auto-recovery check (if not in emergency mode)
        if (self.current_level != FallbackLevel.EMERGENCY_STOP and 
            self.auto_recovery_enabled and
            time.time() - self.last_recovery_check >= self.recovery_check_interval):
            self._check_recovery_conditions()
            
    def record_system_metrics(self, metrics: Dict[str, Any]) -> None:
        """システムメトリクス記録."""
        metric_record = {
            'timestamp': time.time(),
            'memory_usage_mb': metrics.get('memory_usage_mb', 0),
            'cpu_usage_percent': metrics.get('cpu_usage_percent', 0),
            'disk_free_gb': metrics.get('disk_free_gb', 0),
            'error_rate': metrics.get('error_rate', 0),
            'success_rate': metrics.get('success_rate', 1.0)
        }
        
        self.system_metrics.append(metric_record)
        
        # Check if escalation needed based on system metrics
        self._check_system_based_escalation(metric_record)
        
    def trigger_fallback(
        self, 
        reason: TriggerReason, 
        details: Optional[Dict[str, Any]] = None,
        target_level: Optional[FallbackLevel] = None
    ) -> bool:
        """手動フォールバック実行."""
        if target_level is None:
            target_level = self._calculate_next_fallback_level(reason)
            
        return self._execute_fallback(target_level, reason, details or {})
        
    def force_level(self, level: FallbackLevel, reason: str = "manual_override") -> bool:
        """強制レベル変更."""
        return self._execute_fallback(
            level, 
            TriggerReason.USER_REQUEST, 
            {"reason": reason}
        )
        
    def attempt_recovery(self) -> bool:
        """手動復旧試行."""
        if self.current_level == FallbackLevel.NORMAL:
            return True  # Already at normal level
            
        if self._check_recovery_conditions():
            target_level = self._calculate_recovery_level()
            return self._execute_recovery(target_level)
            
        return False
        
    def _check_escalation_needed(self) -> None:
        """エスカレーション必要性チェック."""
        if self.current_level == FallbackLevel.EMERGENCY_STOP:
            return  # Already at maximum level
            
        # Recent error analysis
        recent_window = [r for r in self.recent_errors if time.time() - r['timestamp'] < 300]  # 5 minutes
        
        if len(recent_window) < 10:
            return  # Insufficient data
            
        # Calculate error rate
        error_count = sum(1 for r in recent_window if not r['success'])
        error_rate = error_count / len(recent_window)
        
        # Calculate consecutive failures
        consecutive_failures = 0
        for result in reversed(list(self.recent_errors)):
            if not result['success']:
                consecutive_failures += 1
            else:
                break
                
        # Check thresholds
        thresholds = self.escalation_thresholds.get(self.current_level, {})
        
        escalation_needed = False
        reason = None
        details = {}
        
        if error_rate > thresholds.get('error_rate_threshold', 1.0):
            escalation_needed = True
            reason = TriggerReason.HIGH_ERROR_RATE
            details = {'error_rate': error_rate, 'threshold': thresholds['error_rate_threshold']}
            
        elif consecutive_failures >= thresholds.get('consecutive_failures', 100):
            escalation_needed = True
            reason = TriggerReason.CONSECUTIVE_FAILURES
            details = {'consecutive_failures': consecutive_failures}
            
        if escalation_needed:
            next_level = FallbackLevel(min(self.current_level.value + 1, FallbackLevel.EMERGENCY_STOP.value))
            self._execute_fallback(next_level, reason, details)
            
    def _check_system_based_escalation(self, current_metrics: Dict[str, Any]) -> None:
        """システムメトリクスベースのエスカレーションチェック."""
        if self.current_level == FallbackLevel.EMERGENCY_STOP:
            return
            
        thresholds = self.escalation_thresholds.get(self.current_level, {})
        
        # Memory pressure check
        if current_metrics['memory_usage_mb'] > thresholds.get('memory_threshold_mb', float('inf')):
            self._execute_fallback(
                FallbackLevel(min(self.current_level.value + 1, FallbackLevel.EMERGENCY_STOP.value)),
                TriggerReason.MEMORY_PRESSURE,
                {'memory_usage_mb': current_metrics['memory_usage_mb']}
            )
            return
            
        # CPU overload check
        if current_metrics['cpu_usage_percent'] > thresholds.get('cpu_threshold_percent', 100):
            self._execute_fallback(
                FallbackLevel(min(self.current_level.value + 1, FallbackLevel.EMERGENCY_STOP.value)),
                TriggerReason.CPU_OVERLOAD,
                {'cpu_usage_percent': current_metrics['cpu_usage_percent']}
            )
            return
            
        # Disk space check
        if current_metrics['disk_free_gb'] < thresholds.get('disk_threshold_gb', 0):
            # Disk space is critical - jump to emergency stop
            self._execute_fallback(
                FallbackLevel.EMERGENCY_STOP,
                TriggerReason.DISK_SPACE_LOW,
                {'disk_free_gb': current_metrics['disk_free_gb']}
            )
            
    def _check_recovery_conditions(self) -> bool:
        """復旧条件チェック."""
        self.last_recovery_check = time.time()
        
        if self.current_level == FallbackLevel.NORMAL:
            return True
            
        if not self.fallback_start_time:
            return False
            
        # Check minimum stable duration
        time_in_fallback = datetime.utcnow() - self.fallback_start_time
        if time_in_fallback < timedelta(minutes=self.recovery_conditions.min_stable_duration_minutes):
            return False
            
        # Check recent performance
        recent_window = [r for r in self.recent_errors if time.time() - r['timestamp'] < 600]  # 10 minutes
        
        if len(recent_window) < 5:
            return False  # Insufficient recent data
            
        success_count = sum(1 for r in recent_window if r['success'])
        success_rate = success_count / len(recent_window)
        
        if success_rate < self.recovery_conditions.required_success_rate:
            return False
            
        # Check system metrics
        if self.system_metrics:
            latest_metrics = self.system_metrics[-1]
            
            if (latest_metrics['memory_usage_mb'] > self.recovery_conditions.max_memory_usage_mb or
                latest_metrics['cpu_usage_percent'] > self.recovery_conditions.max_cpu_usage_percent or
                latest_metrics['disk_free_gb'] < self.recovery_conditions.min_disk_free_gb):
                return False
                
        return True
        
    def _calculate_next_fallback_level(self, reason: TriggerReason) -> FallbackLevel:
        """次のフォールバックレベル計算."""
        if reason == TriggerReason.DISK_SPACE_LOW:
            return FallbackLevel.EMERGENCY_STOP  # Disk issues are critical
            
        # Normal progression
        next_value = min(self.current_level.value + 1, FallbackLevel.EMERGENCY_STOP.value)
        return FallbackLevel(next_value)
        
    def _calculate_recovery_level(self) -> FallbackLevel:
        """復旧目標レベル計算."""
        # Gradual recovery - move up one level at a time
        if self.current_level.value > 0:
            return FallbackLevel(self.current_level.value - 1)
        return FallbackLevel.NORMAL
        
    def _execute_fallback(
        self, 
        target_level: FallbackLevel, 
        reason: TriggerReason, 
        details: Dict[str, Any]
    ) -> bool:
        """フォールバック実行."""
        if target_level == self.current_level:
            return True
            
        previous_level = self.current_level
        
        # Record fallback event
        event = FallbackEvent(
            timestamp=datetime.utcnow(),
            from_level=previous_level,
            to_level=target_level,
            trigger_reason=reason,
            trigger_details=details
        )
        
        self.fallback_history.append(event)
        self.current_level = target_level
        
        if previous_level == FallbackLevel.NORMAL:
            self.fallback_start_time = datetime.utcnow()
            
        # Notify callbacks
        for callback in self.level_change_callbacks:
            try:
                callback(target_level)
            except Exception as e:
                print(f"⚠️ Fallback callback error: {e}")
                
        print(f"⬇️ Fallback: {previous_level.name} → {target_level.name}")
        print(f"   Reason: {reason.value}")
        print(f"   Details: {details}")
        
        return True
        
    def _execute_recovery(self, target_level: FallbackLevel) -> bool:
        """復旧実行."""
        previous_level = self.current_level
        
        # Record recovery event
        event = FallbackEvent(
            timestamp=datetime.utcnow(),
            from_level=previous_level,
            to_level=target_level,
            trigger_reason=TriggerReason.USER_REQUEST,  # Recovery is always manual
            trigger_details={"type": "recovery", "conditions_met": True}
        )
        
        self.fallback_history.append(event)
        self.current_level = target_level
        
        if target_level == FallbackLevel.NORMAL:
            self.fallback_start_time = None
            
        # Notify callbacks
        for callback in self.level_change_callbacks:
            try:
                callback(target_level)
            except Exception as e:
                print(f"⚠️ Recovery callback error: {e}")
                
        print(f"⬆️ Recovery: {previous_level.name} → {target_level.name}")
        
        return True
        
    def get_current_restrictions(self) -> Dict[str, Any]:
        """現在の制限事項取得."""
        restrictions = {
            "level": self.current_level.name,
            "level_value": self.current_level.value,
            "fallback_active": self.current_level != FallbackLevel.NORMAL
        }
        
        if self.current_level == FallbackLevel.NORMAL:
            restrictions.update({
                "max_api_concurrency": 5,
                "max_download_concurrency": 4,
                "max_parallel_models": 2,
                "allow_experimental_features": True
            })
        elif self.current_level == FallbackLevel.REDUCED:
            restrictions.update({
                "max_api_concurrency": 3,
                "max_download_concurrency": 2,
                "max_parallel_models": 1,
                "allow_experimental_features": True
            })
        elif self.current_level == FallbackLevel.CONSERVATIVE:
            restrictions.update({
                "max_api_concurrency": 2,
                "max_download_concurrency": 1,
                "max_parallel_models": 1,
                "allow_experimental_features": False
            })
        elif self.current_level == FallbackLevel.SYNC_ONLY:
            restrictions.update({
                "max_api_concurrency": 1,
                "max_download_concurrency": 1,
                "max_parallel_models": 1,
                "allow_experimental_features": False
            })
        else:  # EMERGENCY_STOP
            restrictions.update({
                "max_api_concurrency": 0,
                "max_download_concurrency": 0,
                "max_parallel_models": 0,
                "allow_experimental_features": False,
                "emergency_stop": True
            })
            
        return restrictions
        
    def get_status_report(self) -> Dict[str, Any]:
        """状態レポート生成."""
        recent_failures = sum(1 for r in self.recent_errors if not r['success'])
        
        return {
            "current_level": self.current_level.name,
            "fallback_active": self.current_level != FallbackLevel.NORMAL,
            "time_in_current_level_minutes": (
                (datetime.utcnow() - self.fallback_start_time).total_seconds() / 60
                if self.fallback_start_time else 0
            ),
            "auto_recovery_enabled": self.auto_recovery_enabled,
            "recent_error_count": recent_failures,
            "total_fallback_events": len(self.fallback_history),
            "restrictions": self.get_current_restrictions(),
            "recovery_conditions_met": self._check_recovery_conditions() if self.current_level != FallbackLevel.NORMAL else True
        }
        
    def get_fallback_history(self, limit: int = 10) -> List[Dict[str, Any]]:
        """フォールバック履歴取得."""
        recent_events = list(self.fallback_history)[-limit:]
        
        history = []
        for event in recent_events:
            history.append({
                "timestamp": event.timestamp.isoformat(),
                "from_level": event.from_level.name,
                "to_level": event.to_level.name,
                "reason": event.trigger_reason.value,
                "details": event.trigger_details
            })
            
        return history