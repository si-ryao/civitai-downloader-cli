"""
Adaptive concurrency management for optimal performance with safety guarantees.

This module provides dynamic concurrency adjustment based on real-time performance
and safety metrics, ensuring maximum throughput while maintaining system stability.
"""

import time
from collections import deque
from dataclasses import dataclass
from typing import Dict, Optional, Callable, Any
from enum import Enum


class ConcurrencyMode(Enum):
    """Concurrency operation modes."""
    CONSERVATIVE = "conservative"  # 低並行度、高安全性
    BALANCED = "balanced"         # バランス重視
    AGGRESSIVE = "aggressive"     # 高並行度、性能重視
    SYNC_ONLY = "sync_only"      # 同期処理のみ（フォールバック）


@dataclass
class ConcurrencyConfig:
    """Concurrency configuration settings."""
    # API並行処理設定
    api_concurrent_min: int = 1
    api_concurrent_max: int = 5
    api_concurrent_default: int = 2
    
    # ギャラリー画像並行処理設定
    gallery_concurrent_min: int = 1
    gallery_concurrent_max: int = 4
    gallery_concurrent_default: int = 2
    
    # プレビュー画像並行処理設定  
    preview_concurrent_min: int = 1
    preview_concurrent_max: int = 3
    preview_concurrent_default: int = 2
    
    # モデルファイル並行処理設定（Phase 3で使用）
    model_concurrent_min: int = 1
    model_concurrent_max: int = 2
    model_concurrent_default: int = 1
    
    # 安全性閾値
    success_rate_excellent: float = 0.99   # 99%以上で並行度増加
    success_rate_good: float = 0.97        # 97%以上で現状維持
    success_rate_poor: float = 0.95        # 95%未満で並行度削減
    success_rate_critical: float = 0.90    # 90%未満で同期モード
    
    timeout_rate_excellent: float = 0.005  # 0.5%以下で並行度増加
    timeout_rate_acceptable: float = 0.02  # 2%以下で現状維持
    timeout_rate_poor: float = 0.05        # 5%以上で並行度削減
    timeout_rate_critical: float = 0.10    # 10%以上で同期モード
    
    # 調整間隔
    adjustment_interval_seconds: int = 30   # 30秒間隔で調整判定
    min_samples_for_adjustment: int = 10    # 最小サンプル数
    
    # フォールバック設定（緩和済み）
    consecutive_failures_for_fallback: int = 10  # 連続失敗でフォールバック（3→10に緩和）
    recovery_success_threshold: int = 3         # 復旧判定の成功数（10→3に緩和）


@dataclass
class PerformanceMetrics:
    """Performance metrics for concurrency decisions."""
    total_operations: int = 0
    successful_operations: int = 0
    failed_operations: int = 0
    timeout_operations: int = 0
    success_rate: float = 1.0
    timeout_rate: float = 0.0
    avg_duration_seconds: float = 0.0
    throughput_per_minute: float = 0.0


class AdaptiveConcurrencyManager:
    """
    Dynamic concurrency management system.
    
    Automatically adjusts concurrency levels based on real-time performance
    metrics while maintaining strict safety guarantees.
    """
    
    def __init__(self, config: ConcurrencyConfig):
        self.config = config
        
        # 現在の並行度設定
        self.current_concurrency = {
            'api': config.api_concurrent_default,
            'gallery': config.gallery_concurrent_default,
            'preview': config.preview_concurrent_default,
            'model': config.model_concurrent_default
        }
        
        # 現在の動作モード
        self.current_mode = ConcurrencyMode.BALANCED
        
        # パフォーマンス追跡
        self.metrics_window = deque(maxlen=100)  # 最新100操作
        self.last_adjustment_time = time.time()
        
        # 安全性監視
        self.consecutive_failures = 0
        self.consecutive_successes = 0
        self.fallback_active = False
        
        # 調整履歴（デバッグ用）
        self.adjustment_history: deque = deque(maxlen=50)
        
    def record_operation_result(
        self, 
        operation_type: str,
        success: bool, 
        duration_seconds: float,
        timeout_occurred: bool = False
    ) -> None:
        """操作結果を記録."""
        timestamp = time.time()
        
        result = {
            'timestamp': timestamp,
            'operation_type': operation_type,
            'success': success,
            'duration_seconds': duration_seconds,
            'timeout_occurred': timeout_occurred
        }
        
        self.metrics_window.append(result)
        
        # 連続成功/失敗カウント更新
        if success:
            self.consecutive_successes += 1
            self.consecutive_failures = 0
        else:
            self.consecutive_failures += 1
            self.consecutive_successes = 0
            
        # 緊急フォールバック判定
        if self.consecutive_failures >= self.config.consecutive_failures_for_fallback:
            self._trigger_emergency_fallback()
            
        # 復旧判定
        elif self.fallback_active and self.consecutive_successes >= self.config.recovery_success_threshold:
            self._attempt_recovery()
            
        # 定期的な並行度調整判定
        if self._should_adjust_concurrency():
            self._adjust_concurrency()
            
    def get_current_concurrency(self, operation_type: str) -> int:
        """現在の並行度取得."""
        if self.fallback_active:
            return 1  # フォールバック時は同期処理
            
        return self.current_concurrency.get(operation_type, 1)
        
    def get_current_metrics(self) -> PerformanceMetrics:
        """現在のパフォーマンスメトリクス取得."""
        if not self.metrics_window:
            return PerformanceMetrics()
            
        total_ops = len(self.metrics_window)
        successful_ops = sum(1 for r in self.metrics_window if r['success'])
        failed_ops = total_ops - successful_ops
        timeout_ops = sum(1 for r in self.metrics_window if r.get('timeout_occurred', False))
        
        success_rate = successful_ops / total_ops if total_ops > 0 else 1.0
        timeout_rate = timeout_ops / total_ops if total_ops > 0 else 0.0
        
        durations = [r['duration_seconds'] for r in self.metrics_window]
        avg_duration = sum(durations) / len(durations) if durations else 0.0
        
        # 直近1分間のスループット計算
        recent_cutoff = time.time() - 60
        recent_ops = [r for r in self.metrics_window if r['timestamp'] > recent_cutoff]
        throughput = len(recent_ops)  # operations per minute
        
        return PerformanceMetrics(
            total_operations=total_ops,
            successful_operations=successful_ops,
            failed_operations=failed_ops,
            timeout_operations=timeout_ops,
            success_rate=success_rate,
            timeout_rate=timeout_rate,
            avg_duration_seconds=avg_duration,
            throughput_per_minute=throughput
        )
        
    def _should_adjust_concurrency(self) -> bool:
        """並行度調整が必要かどうか判定."""
        if self.fallback_active:
            return False  # フォールバック中は調整しない
            
        # 最低サンプル数チェック
        if len(self.metrics_window) < self.config.min_samples_for_adjustment:
            return False
            
        # 調整間隔チェック
        time_since_last_adjustment = time.time() - self.last_adjustment_time
        return time_since_last_adjustment >= self.config.adjustment_interval_seconds
        
    def _adjust_concurrency(self) -> None:
        """並行度調整実行."""
        metrics = self.get_current_metrics()
        previous_concurrency = self.current_concurrency.copy()
        previous_mode = self.current_mode
        
        # 新しいモード決定
        new_mode = self._determine_optimal_mode(metrics)
        
        # モードに応じて並行度調整
        if new_mode != self.current_mode:
            self._apply_concurrency_mode(new_mode)
            self.current_mode = new_mode
            
        # 調整履歴記録
        adjustment = {
            'timestamp': time.time(),
            'previous_mode': previous_mode.value,
            'new_mode': self.current_mode.value,
            'previous_concurrency': previous_concurrency,
            'new_concurrency': self.current_concurrency.copy(),
            'metrics': {
                'success_rate': metrics.success_rate,
                'timeout_rate': metrics.timeout_rate,
                'throughput': metrics.throughput_per_minute
            }
        }
        
        self.adjustment_history.append(adjustment)
        self.last_adjustment_time = time.time()
        
        print(f"🔧 Concurrency adjusted: {previous_mode.value} → {self.current_mode.value}")
        print(f"   Success rate: {metrics.success_rate:.1%}, Timeout rate: {metrics.timeout_rate:.1%}")
        
    def _determine_optimal_mode(self, metrics: PerformanceMetrics) -> ConcurrencyMode:
        """最適な並行度モード決定."""
        success_rate = metrics.success_rate
        timeout_rate = metrics.timeout_rate
        
        # クリティカル状況：同期モードに強制移行
        if (success_rate < self.config.success_rate_critical or 
            timeout_rate > self.config.timeout_rate_critical):
            return ConcurrencyMode.SYNC_ONLY
            
        # 性能優秀：積極的モード
        elif (success_rate >= self.config.success_rate_excellent and 
              timeout_rate <= self.config.timeout_rate_excellent):
            return ConcurrencyMode.AGGRESSIVE
            
        # 性能良好：バランスモード
        elif (success_rate >= self.config.success_rate_good and 
              timeout_rate <= self.config.timeout_rate_acceptable):
            return ConcurrencyMode.BALANCED
            
        # 性能不良：保守的モード
        else:
            return ConcurrencyMode.CONSERVATIVE
            
    def _apply_concurrency_mode(self, mode: ConcurrencyMode) -> None:
        """並行度モード適用."""
        if mode == ConcurrencyMode.SYNC_ONLY:
            # 同期モード：すべて1並行
            self.current_concurrency = {
                'api': 1,
                'gallery': 1,
                'preview': 1,
                'model': 1
            }
        elif mode == ConcurrencyMode.CONSERVATIVE:
            # 保守的モード：最小並行度
            self.current_concurrency = {
                'api': self.config.api_concurrent_min,
                'gallery': self.config.gallery_concurrent_min,
                'preview': self.config.preview_concurrent_min,
                'model': self.config.model_concurrent_min
            }
        elif mode == ConcurrencyMode.BALANCED:
            # バランスモード：デフォルト並行度
            self.current_concurrency = {
                'api': self.config.api_concurrent_default,
                'gallery': self.config.gallery_concurrent_default,
                'preview': self.config.preview_concurrent_default,
                'model': self.config.model_concurrent_default
            }
        elif mode == ConcurrencyMode.AGGRESSIVE:
            # 積極的モード：最大並行度
            self.current_concurrency = {
                'api': self.config.api_concurrent_max,
                'gallery': self.config.gallery_concurrent_max,
                'preview': self.config.preview_concurrent_max,
                'model': self.config.model_concurrent_max
            }
            
    def _trigger_emergency_fallback(self) -> None:
        """緊急フォールバック実行."""
        if not self.fallback_active:
            self.fallback_active = True
            print("🚨 Emergency fallback activated: switching to sync mode")
            print(f"   Reason: {self.consecutive_failures} consecutive failures")
            
    def _attempt_recovery(self) -> None:
        """復旧試行."""
        if self.fallback_active:
            self.fallback_active = False
            self.current_mode = ConcurrencyMode.CONSERVATIVE  # 保守的モードで復旧
            self._apply_concurrency_mode(self.current_mode)
            print("✅ Recovery from fallback: switching to conservative mode")
            print(f"   Reason: {self.consecutive_successes} consecutive successes")
            
    def get_status_report(self) -> Dict[str, Any]:
        """現在の状態レポート生成."""
        metrics = self.get_current_metrics()
        
        return {
            "current_mode": self.current_mode.value,
            "fallback_active": self.fallback_active,
            "current_concurrency": self.current_concurrency.copy(),
            "performance_metrics": {
                "success_rate": f"{metrics.success_rate:.1%}",
                "timeout_rate": f"{metrics.timeout_rate:.1%}",
                "throughput_per_minute": metrics.throughput_per_minute,
                "avg_duration_seconds": f"{metrics.avg_duration_seconds:.2f}"
            },
            "safety_indicators": {
                "consecutive_failures": self.consecutive_failures,
                "consecutive_successes": self.consecutive_successes,
                "total_samples": len(self.metrics_window)
            },
            "recent_adjustments": len(self.adjustment_history)
        }
        
    def force_mode(self, mode: ConcurrencyMode) -> None:
        """強制的にモード変更（テスト・デバッグ用）."""
        print(f"🔧 Forcing concurrency mode: {self.current_mode.value} → {mode.value}")
        self.current_mode = mode
        self._apply_concurrency_mode(mode)
        
        if mode == ConcurrencyMode.SYNC_ONLY:
            self.fallback_active = True
        else:
            self.fallback_active = False