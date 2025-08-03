"""
Model parallelism management with dynamic adjustment.

This module provides intelligent management of model-level parallelism,
automatically adjusting the number of concurrent model downloads based
on system performance and resource availability.
"""

import psutil
import time
from collections import deque
from dataclasses import dataclass
from enum import Enum
from typing import Dict, List, Optional, Any, Tuple
from datetime import datetime, timedelta


class ParallelismMode(Enum):
    """Model parallelism modes."""
    SEQUENTIAL = 1      # 順次処理（1モデル）
    CONSERVATIVE = 2    # 保守的（2モデル）
    BALANCED = 3        # バランス（3モデル）
    AGGRESSIVE = 4      # 積極的（4モデル）
    MAXIMUM = 5         # 最大（5モデル）


@dataclass
class PerformanceMetrics:
    """Performance metrics for parallelism adjustment."""
    timestamp: datetime
    parallel_models: int
    throughput_models_per_minute: float
    success_rate: float
    memory_usage_mb: float
    cpu_usage_percent: float
    disk_io_mb_per_sec: float
    network_io_mb_per_sec: float
    avg_response_time_ms: float


@dataclass
class SystemThresholds:
    """System resource thresholds for parallelism control."""
    max_memory_usage_mb: float = 4096      # 4GB
    max_cpu_usage_percent: float = 80      # 80%
    max_disk_io_mb_per_sec: float = 100    # 100MB/s
    min_success_rate: float = 0.95         # 95%
    max_avg_response_time_ms: float = 5000 # 5秒


class ModelParallelismManager:
    """
    Model parallelism manager with dynamic adjustment.
    
    Automatically adjusts the number of concurrent model downloads based on
    system performance, resource usage, and success rates.
    """
    
    def __init__(self, initial_mode: ParallelismMode = ParallelismMode.SEQUENTIAL):
        # Current state
        self.current_mode = initial_mode
        self.current_parallel_models = initial_mode.value
        
        # Performance tracking
        self.performance_history: deque = deque(maxlen=50)
        self.recent_metrics: deque = deque(maxlen=10)
        
        # System thresholds
        self.thresholds = SystemThresholds()
        
        # Adjustment settings
        self.min_samples_for_adjustment = 5
        self.adjustment_cooldown_minutes = 5
        self.last_adjustment_time = datetime.utcnow()
        
        # Performance tracking
        self.session_start_time = time.time()
        self.total_models_processed = 0
        self.total_successful_models = 0
        
        print(f"🎛️ Model parallelism manager initialized")
        print(f"   Initial mode: {initial_mode.name} ({initial_mode.value} models)")
        
    def record_performance_metrics(
        self, 
        parallel_models: int,
        throughput: float,
        success_rate: float,
        models_processed: int = 0,
        successful_models: int = 0
    ) -> None:
        """Record performance metrics for adjustment decisions."""
        
        # Update session counters
        self.total_models_processed += models_processed
        self.total_successful_models += successful_models
        
        # Get system metrics
        system_metrics = self._get_system_metrics()
        
        # Create performance record
        metrics = PerformanceMetrics(
            timestamp=datetime.utcnow(),
            parallel_models=parallel_models,
            throughput_models_per_minute=throughput,
            success_rate=success_rate,
            memory_usage_mb=system_metrics['memory_usage_mb'],
            cpu_usage_percent=system_metrics['cpu_usage_percent'],
            disk_io_mb_per_sec=system_metrics['disk_io_mb_per_sec'],
            network_io_mb_per_sec=system_metrics['network_io_mb_per_sec'],
            avg_response_time_ms=system_metrics['avg_response_time_ms']
        )
        
        self.performance_history.append(metrics)
        self.recent_metrics.append(metrics)
        
        # Check if adjustment is needed
        self._check_adjustment_needed()
        
    def _get_system_metrics(self) -> Dict[str, float]:
        """Get current system resource metrics."""
        try:
            # Memory usage
            memory = psutil.virtual_memory()
            memory_usage_mb = (memory.total - memory.available) / 1024 / 1024
            
            # CPU usage
            cpu_usage_percent = psutil.cpu_percent(interval=0.1)
            
            # Disk I/O (approximation)
            disk_io = psutil.disk_io_counters()
            disk_io_mb_per_sec = 0
            if hasattr(self, '_last_disk_io'):
                time_diff = time.time() - self._last_disk_io_time
                if time_diff > 0:
                    read_diff = disk_io.read_bytes - self._last_disk_io.read_bytes
                    write_diff = disk_io.write_bytes - self._last_disk_io.write_bytes
                    disk_io_mb_per_sec = (read_diff + write_diff) / time_diff / 1024 / 1024
            
            self._last_disk_io = disk_io
            self._last_disk_io_time = time.time()
            
            # Network I/O (approximation)
            network_io = psutil.net_io_counters()
            network_io_mb_per_sec = 0
            if hasattr(self, '_last_network_io'):
                time_diff = time.time() - self._last_network_io_time
                if time_diff > 0:
                    sent_diff = network_io.bytes_sent - self._last_network_io.bytes_sent
                    recv_diff = network_io.bytes_recv - self._last_network_io.bytes_recv
                    network_io_mb_per_sec = (sent_diff + recv_diff) / time_diff / 1024 / 1024
            
            self._last_network_io = network_io
            self._last_network_io_time = time.time()
            
            return {
                'memory_usage_mb': memory_usage_mb,
                'cpu_usage_percent': cpu_usage_percent,
                'disk_io_mb_per_sec': disk_io_mb_per_sec,
                'network_io_mb_per_sec': network_io_mb_per_sec,
                'avg_response_time_ms': 1000  # Placeholder
            }
            
        except Exception as e:
            print(f"⚠️ Error getting system metrics: {e}")
            return {
                'memory_usage_mb': 0,
                'cpu_usage_percent': 0,
                'disk_io_mb_per_sec': 0,
                'network_io_mb_per_sec': 0,
                'avg_response_time_ms': 1000
            }
            
    def _check_adjustment_needed(self) -> None:
        """Check if parallelism adjustment is needed."""
        # Need minimum samples
        if len(self.recent_metrics) < self.min_samples_for_adjustment:
            return
            
        # Check cooldown period
        time_since_adjustment = datetime.utcnow() - self.last_adjustment_time
        if time_since_adjustment < timedelta(minutes=self.adjustment_cooldown_minutes):
            return
            
        # Analyze recent performance
        avg_metrics = self._calculate_average_metrics()
        adjustment_decision = self._make_adjustment_decision(avg_metrics)
        
        if adjustment_decision != self.current_mode:
            self._apply_adjustment(adjustment_decision, avg_metrics)
            
    def _calculate_average_metrics(self) -> Dict[str, float]:
        """Calculate average metrics from recent samples."""
        if not self.recent_metrics:
            return {}
            
        metrics_sum = {
            'throughput': 0,
            'success_rate': 0,
            'memory_usage_mb': 0,
            'cpu_usage_percent': 0,
            'disk_io_mb_per_sec': 0,
            'network_io_mb_per_sec': 0,
            'avg_response_time_ms': 0
        }
        
        for metric in self.recent_metrics:
            metrics_sum['throughput'] += metric.throughput_models_per_minute
            metrics_sum['success_rate'] += metric.success_rate
            metrics_sum['memory_usage_mb'] += metric.memory_usage_mb
            metrics_sum['cpu_usage_percent'] += metric.cpu_usage_percent
            metrics_sum['disk_io_mb_per_sec'] += metric.disk_io_mb_per_sec
            metrics_sum['network_io_mb_per_sec'] += metric.network_io_mb_per_sec
            metrics_sum['avg_response_time_ms'] += metric.avg_response_time_ms
            
        count = len(self.recent_metrics)
        return {key: value / count for key, value in metrics_sum.items()}
        
    def _make_adjustment_decision(self, avg_metrics: Dict[str, float]) -> ParallelismMode:
        """Make adjustment decision based on metrics."""
        # Check for resource pressure (scale down)
        if (avg_metrics['memory_usage_mb'] > self.thresholds.max_memory_usage_mb or
            avg_metrics['cpu_usage_percent'] > self.thresholds.max_cpu_usage_percent or
            avg_metrics['success_rate'] < self.thresholds.min_success_rate or
            avg_metrics['avg_response_time_ms'] > self.thresholds.max_avg_response_time_ms):
            
            # Scale down
            if self.current_mode.value > ParallelismMode.SEQUENTIAL.value:
                return ParallelismMode(self.current_mode.value - 1)
                
        # Check for scale up opportunity
        elif (avg_metrics['memory_usage_mb'] < self.thresholds.max_memory_usage_mb * 0.7 and
              avg_metrics['cpu_usage_percent'] < self.thresholds.max_cpu_usage_percent * 0.7 and
              avg_metrics['success_rate'] > 0.98 and
              avg_metrics['avg_response_time_ms'] < self.thresholds.max_avg_response_time_ms * 0.5):
            
            # Scale up
            if self.current_mode.value < ParallelismMode.MAXIMUM.value:
                return ParallelismMode(self.current_mode.value + 1)
                
        return self.current_mode
        
    def _apply_adjustment(self, new_mode: ParallelismMode, avg_metrics: Dict[str, float]) -> None:
        """Apply parallelism adjustment."""
        old_mode = self.current_mode
        self.current_mode = new_mode
        self.current_parallel_models = new_mode.value
        self.last_adjustment_time = datetime.utcnow()
        
        direction = "🔺" if new_mode.value > old_mode.value else "🔻"
        print(f"{direction} Parallelism adjusted: {old_mode.name} → {new_mode.name}")
        print(f"   Models: {old_mode.value} → {new_mode.value}")
        print(f"   Reason: Memory={avg_metrics['memory_usage_mb']:.0f}MB, "
              f"CPU={avg_metrics['cpu_usage_percent']:.1f}%, "
              f"Success={avg_metrics['success_rate']:.1%}")
              
    def get_recommended_parallel_models(self) -> int:
        """Get current recommended number of parallel models."""
        return self.current_parallel_models
        
    def get_current_mode(self) -> ParallelismMode:
        """Get current parallelism mode."""
        return self.current_mode
        
    def force_mode(self, mode: ParallelismMode) -> None:
        """Force specific parallelism mode."""
        old_mode = self.current_mode
        self.current_mode = mode
        self.current_parallel_models = mode.value
        self.last_adjustment_time = datetime.utcnow()
        
        print(f"🔧 Parallelism forced: {old_mode.name} → {mode.name}")
        print(f"   Models: {old_mode.value} → {mode.value}")
        
    def get_performance_summary(self) -> Dict[str, Any]:
        """Get performance summary."""
        if not self.performance_history:
            return {"no_data": True}
            
        # Calculate session statistics
        session_duration = time.time() - self.session_start_time
        overall_throughput = (self.total_models_processed / (session_duration / 60)) if session_duration > 0 else 0
        overall_success_rate = (self.total_successful_models / self.total_models_processed) if self.total_models_processed > 0 else 0
        
        # Get latest metrics
        latest = self.performance_history[-1] if self.performance_history else None
        
        return {
            "current_mode": self.current_mode.name,
            "current_parallel_models": self.current_parallel_models,
            "session_duration_minutes": session_duration / 60,
            "total_models_processed": self.total_models_processed,
            "total_successful_models": self.total_successful_models,
            "overall_throughput_models_per_minute": overall_throughput,
            "overall_success_rate": overall_success_rate,
            "latest_metrics": {
                "memory_usage_mb": latest.memory_usage_mb if latest else 0,
                "cpu_usage_percent": latest.cpu_usage_percent if latest else 0,
                "throughput": latest.throughput_models_per_minute if latest else 0,
                "success_rate": latest.success_rate if latest else 0
            } if latest else {},
            "performance_samples": len(self.performance_history),
            "adjustments_made": len([m for m in self.performance_history if m.parallel_models != self.performance_history[0].parallel_models]) if len(self.performance_history) > 1 else 0
        }
        
    def get_performance_history(self) -> List[Dict[str, Any]]:
        """Get performance history for analysis."""
        return [
            {
                "timestamp": metric.timestamp.isoformat(),
                "parallel_models": metric.parallel_models,
                "throughput": metric.throughput_models_per_minute,
                "success_rate": metric.success_rate,
                "memory_usage_mb": metric.memory_usage_mb,
                "cpu_usage_percent": metric.cpu_usage_percent,
                "disk_io_mb_per_sec": metric.disk_io_mb_per_sec,
                "network_io_mb_per_sec": metric.network_io_mb_per_sec,
                "avg_response_time_ms": metric.avg_response_time_ms
            }
            for metric in self.performance_history
        ]