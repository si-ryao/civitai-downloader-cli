"""
Intelligent retry management with adaptive strategies.

This module provides sophisticated retry mechanisms that adapt to different
error types and network conditions, maximizing success rates while minimizing
resource waste and unnecessary delays.
"""

import asyncio
import random
import time
from collections import defaultdict, deque
from dataclasses import dataclass
from enum import Enum
from typing import Dict, List, Optional, Callable, Any, TypeVar, Awaitable
import aiohttp
import requests


T = TypeVar('T')


class ErrorCategory(Enum):
    """Error category classification."""
    NETWORK_TIMEOUT = "network_timeout"           # ネットワークタイムアウト
    NETWORK_CONNECTION = "network_connection"     # 接続エラー
    SERVER_ERROR = "server_error"                 # サーバーエラー (5xx)
    RATE_LIMIT = "rate_limit"                     # レート制限 (429)
    CLIENT_ERROR = "client_error"                 # クライアントエラー (4xx)
    FILE_CORRUPTION = "file_corruption"           # ファイル破損
    DISK_FULL = "disk_full"                       # ディスク容量不足
    UNKNOWN = "unknown"                           # 分類不能


@dataclass
class RetryStrategy:
    """Retry strategy configuration."""
    max_attempts: int = 3
    base_delay_seconds: float = 1.0
    max_delay_seconds: float = 60.0
    backoff_multiplier: float = 2.0
    jitter_ratio: float = 0.1  # ランダム要素の比率
    timeout_multiplier: float = 1.5  # タイムアウト値の増加率


@dataclass
class RetryAttempt:
    """Individual retry attempt record."""
    attempt_number: int
    error_category: ErrorCategory
    delay_seconds: float
    timeout_seconds: float
    success: bool
    timestamp: float
    error_message: str


class IntelligentRetryManager:
    """
    Intelligent retry management system.
    
    Provides adaptive retry strategies based on error classification,
    historical success rates, and current system conditions.
    """
    
    def __init__(self):
        # エラー種別別のリトライ戦略
        self.strategies = {
            ErrorCategory.NETWORK_TIMEOUT: RetryStrategy(
                max_attempts=4,
                base_delay_seconds=2.0,
                max_delay_seconds=30.0,
                backoff_multiplier=1.5,
                timeout_multiplier=2.0
            ),
            ErrorCategory.NETWORK_CONNECTION: RetryStrategy(
                max_attempts=3,
                base_delay_seconds=1.0,
                max_delay_seconds=15.0,
                backoff_multiplier=2.0,
                timeout_multiplier=1.2
            ),
            ErrorCategory.SERVER_ERROR: RetryStrategy(
                max_attempts=3,
                base_delay_seconds=5.0,
                max_delay_seconds=60.0,
                backoff_multiplier=2.0,
                timeout_multiplier=1.0
            ),
            ErrorCategory.RATE_LIMIT: RetryStrategy(
                max_attempts=5,
                base_delay_seconds=60.0,
                max_delay_seconds=300.0,
                backoff_multiplier=1.5,
                timeout_multiplier=1.0
            ),
            ErrorCategory.CLIENT_ERROR: RetryStrategy(
                max_attempts=1,  # 4xxエラーは通常リトライしない
                base_delay_seconds=0.0,
                timeout_multiplier=1.0
            ),
            ErrorCategory.FILE_CORRUPTION: RetryStrategy(
                max_attempts=2,
                base_delay_seconds=1.0,
                max_delay_seconds=5.0,
                backoff_multiplier=1.0,
                timeout_multiplier=1.5
            ),
            ErrorCategory.DISK_FULL: RetryStrategy(
                max_attempts=1,  # ディスク不足は通常即座に失敗
                base_delay_seconds=0.0,
                timeout_multiplier=1.0
            ),
            ErrorCategory.UNKNOWN: RetryStrategy(
                max_attempts=2,
                base_delay_seconds=2.0,
                max_delay_seconds=10.0,
                backoff_multiplier=2.0,
                timeout_multiplier=1.2
            )
        }
        
        # リトライ履歴（学習用）
        self.retry_history: Dict[ErrorCategory, deque] = defaultdict(lambda: deque(maxlen=100))
        
        # 成功率統計
        self.success_rates: Dict[ErrorCategory, float] = defaultdict(float)
        
        # 動的調整用データ
        self.recent_network_performance = deque(maxlen=50)
        
    def classify_error(self, error: Exception) -> ErrorCategory:
        """エラー分類."""
        error_type = type(error)
        error_message = str(error).lower()
        
        # タイムアウト系エラー
        if isinstance(error, (asyncio.TimeoutError, requests.exceptions.Timeout)):
            return ErrorCategory.NETWORK_TIMEOUT
            
        # 接続系エラー
        if isinstance(error, (
            aiohttp.ClientConnectionError,
            aiohttp.ClientConnectorError,
            requests.exceptions.ConnectionError,
            ConnectionError
        )):
            return ErrorCategory.NETWORK_CONNECTION
            
        # HTTPエラー
        if isinstance(error, (aiohttp.ClientResponseError, requests.exceptions.HTTPError)):
            status_code = getattr(error, 'status', None) or getattr(error, 'response', {}).get('status_code', 0)
            
            if status_code == 429:
                return ErrorCategory.RATE_LIMIT
            elif 500 <= status_code < 600:
                return ErrorCategory.SERVER_ERROR
            elif 400 <= status_code < 500:
                return ErrorCategory.CLIENT_ERROR
                
        # ファイル系エラー
        if isinstance(error, (IOError, OSError)):
            if "no space left" in error_message or "disk full" in error_message:
                return ErrorCategory.DISK_FULL
            elif "corruption" in error_message or "checksum" in error_message:
                return ErrorCategory.FILE_CORRUPTION
                
        # SHA256検証エラー
        if "sha256" in error_message or "hash" in error_message or "checksum" in error_message:
            return ErrorCategory.FILE_CORRUPTION
            
        return ErrorCategory.UNKNOWN
        
    async def retry_async(
        self,
        operation: Callable[..., Awaitable[T]],
        *args,
        error_context: Optional[Dict[str, Any]] = None,
        **kwargs
    ) -> T:
        """非同期操作のリトライ実行."""
        last_exception = None
        
        for attempt in range(1, 6):  # 最大5回試行
            try:
                return await operation(*args, **kwargs)
                
            except Exception as e:
                last_exception = e
                error_category = self.classify_error(e)
                
                # リトライ戦略取得
                strategy = self.strategies[error_category]
                
                if attempt >= strategy.max_attempts:
                    break
                    
                # 遅延時間計算
                delay = self._calculate_delay(error_category, attempt, strategy)
                
                # タイムアウト調整
                if 'timeout' in kwargs:
                    kwargs['timeout'] = kwargs['timeout'] * strategy.timeout_multiplier
                    
                # リトライ記録
                retry_attempt = RetryAttempt(
                    attempt_number=attempt,
                    error_category=error_category,
                    delay_seconds=delay,
                    timeout_seconds=kwargs.get('timeout', 0),
                    success=False,
                    timestamp=time.time(),
                    error_message=str(e)
                )
                
                self.retry_history[error_category].append(retry_attempt)
                
                print(f"🔄 Retry {attempt}/{strategy.max_attempts} after {delay:.1f}s "
                      f"({error_category.value}): {str(e)[:100]}")
                
                if delay > 0:
                    await asyncio.sleep(delay)
                    
        # 最終的に失敗
        if last_exception:
            error_category = self.classify_error(last_exception)
            self._update_success_rate(error_category, False)
            raise last_exception
            
        raise RuntimeError("Unexpected retry loop exit")
        
    def retry_sync(
        self,
        operation: Callable[..., T],
        *args,
        error_context: Optional[Dict[str, Any]] = None,
        **kwargs
    ) -> T:
        """同期操作のリトライ実行."""
        last_exception = None
        
        for attempt in range(1, 6):  # 最大5回試行
            try:
                result = operation(*args, **kwargs)
                
                # 成功時の統計更新
                if last_exception:
                    error_category = self.classify_error(last_exception)
                    self._update_success_rate(error_category, True)
                    
                return result
                
            except Exception as e:
                last_exception = e
                error_category = self.classify_error(e)
                
                # リトライ戦略取得
                strategy = self.strategies[error_category]
                
                if attempt >= strategy.max_attempts:
                    break
                    
                # 遅延時間計算
                delay = self._calculate_delay(error_category, attempt, strategy)
                
                # タイムアウト調整
                if 'timeout' in kwargs:
                    kwargs['timeout'] = kwargs['timeout'] * strategy.timeout_multiplier
                    
                # リトライ記録
                retry_attempt = RetryAttempt(
                    attempt_number=attempt,
                    error_category=error_category,
                    delay_seconds=delay,
                    timeout_seconds=kwargs.get('timeout', 0),
                    success=False,
                    timestamp=time.time(),
                    error_message=str(e)
                )
                
                self.retry_history[error_category].append(retry_attempt)
                
                print(f"🔄 Retry {attempt}/{strategy.max_attempts} after {delay:.1f}s "
                      f"({error_category.value}): {str(e)[:100]}")
                
                if delay > 0:
                    time.sleep(delay)
                    
        # 最終的に失敗
        if last_exception:
            error_category = self.classify_error(last_exception)
            self._update_success_rate(error_category, False)
            raise last_exception
            
        raise RuntimeError("Unexpected retry loop exit")
        
    def _calculate_delay(
        self, 
        error_category: ErrorCategory, 
        attempt: int, 
        strategy: RetryStrategy
    ) -> float:
        """リトライ遅延時間計算."""
        # 基本遅延時間（指数バックオフ）
        delay = strategy.base_delay_seconds * (strategy.backoff_multiplier ** (attempt - 1))
        
        # 最大遅延時間でクリップ
        delay = min(delay, strategy.max_delay_seconds)
        
        # ジッター追加（thundering herd回避）
        if strategy.jitter_ratio > 0:
            jitter = delay * strategy.jitter_ratio * random.random()
            delay += jitter
            
        # ネットワーク状況による動的調整
        delay = self._adjust_delay_for_network_conditions(delay, error_category)
        
        return delay
        
    def _adjust_delay_for_network_conditions(
        self, 
        base_delay: float, 
        error_category: ErrorCategory
    ) -> float:
        """ネットワーク状況に応じた遅延調整."""
        if error_category not in [ErrorCategory.NETWORK_TIMEOUT, ErrorCategory.NETWORK_CONNECTION]:
            return base_delay
            
        # 最近のネットワーク性能が悪い場合は遅延を増加
        if len(self.recent_network_performance) >= 5:
            recent_avg = sum(self.recent_network_performance) / len(self.recent_network_performance)
            if recent_avg > 5000:  # 5秒以上の平均レスポンス時間
                return base_delay * 1.5
            elif recent_avg > 2000:  # 2秒以上
                return base_delay * 1.2
                
        return base_delay
        
    def _update_success_rate(self, error_category: ErrorCategory, success: bool) -> None:
        """成功率統計更新."""
        history = self.retry_history[error_category]
        if not history:
            return
            
        # 最近の試行における成功率を計算
        recent_attempts = list(history)[-20:]  # 最近20回
        if success:
            # 成功した場合、最後の失敗を成功に更新
            if recent_attempts:
                recent_attempts[-1].success = True
                
        total_attempts = len(recent_attempts)
        successful_retries = sum(1 for attempt in recent_attempts if attempt.success)
        
        self.success_rates[error_category] = successful_retries / total_attempts if total_attempts > 0 else 0.0
        
    def get_strategy_effectiveness(self) -> Dict[str, Dict[str, Any]]:
        """リトライ戦略の効果分析."""
        effectiveness = {}
        
        for category, history in self.retry_history.items():
            if not history:
                continue
                
            attempts = list(history)
            total_retries = len(attempts)
            successful_retries = sum(1 for attempt in attempts if attempt.success)
            
            # 平均試行回数
            avg_attempts = sum(attempt.attempt_number for attempt in attempts) / total_retries
            
            # 平均遅延時間
            avg_delay = sum(attempt.delay_seconds for attempt in attempts) / total_retries
            
            effectiveness[category.value] = {
                "total_retries": total_retries,
                "success_rate": successful_retries / total_retries if total_retries > 0 else 0.0,
                "average_attempts": avg_attempts,
                "average_delay_seconds": avg_delay,
                "current_strategy": {
                    "max_attempts": self.strategies[category].max_attempts,
                    "base_delay": self.strategies[category].base_delay_seconds,
                    "max_delay": self.strategies[category].max_delay_seconds
                }
            }
            
        return effectiveness
        
    def optimize_strategies(self) -> None:
        """履歴に基づくリトライ戦略の最適化."""
        for category, history in self.retry_history.items():
            if len(history) < 20:  # 十分なデータがない場合はスキップ
                continue
                
            attempts = list(history)
            success_rate = self.success_rates[category]
            
            # 成功率が低い場合は最大試行回数を増加
            if success_rate < 0.3 and self.strategies[category].max_attempts < 5:
                self.strategies[category].max_attempts += 1
                print(f"🔧 Increased max attempts for {category.value} to {self.strategies[category].max_attempts}")
                
            # 成功率が高い場合は遅延時間を短縮
            elif success_rate > 0.8:
                current_delay = self.strategies[category].base_delay_seconds
                if current_delay > 0.5:
                    self.strategies[category].base_delay_seconds *= 0.9
                    print(f"🔧 Reduced base delay for {category.value} to {self.strategies[category].base_delay_seconds:.1f}s")
                    
    def record_network_performance(self, response_time_ms: float) -> None:
        """ネットワーク性能記録."""
        self.recent_network_performance.append(response_time_ms)
        
    def get_recommended_timeout(self, base_timeout: float, error_category: ErrorCategory) -> float:
        """推奨タイムアウト値計算."""
        strategy = self.strategies[error_category]
        return base_timeout * strategy.timeout_multiplier
        
    def should_retry_immediately(self, error: Exception) -> bool:
        """即座リトライが推奨されるかどうか判定."""
        category = self.classify_error(error)
        
        # ファイル破損は即座リトライが有効
        if category == ErrorCategory.FILE_CORRUPTION:
            return True
            
        # レート制限やディスク不足は遅延が必要
        if category in [ErrorCategory.RATE_LIMIT, ErrorCategory.DISK_FULL]:
            return False
            
        # 成功率が高いエラー種別は即座リトライを試みる
        success_rate = self.success_rates.get(category, 0.5)
        return success_rate > 0.7
        
    def get_status_report(self) -> Dict[str, Any]:
        """現在の状態レポート生成."""
        total_retries = sum(len(history) for history in self.retry_history.values())
        
        category_stats = {}
        for category, history in self.retry_history.items():
            if history:
                category_stats[category.value] = {
                    "total_attempts": len(history),
                    "success_rate": self.success_rates.get(category, 0.0),
                    "avg_delay": sum(a.delay_seconds for a in history) / len(history)
                }
                
        return {
            "total_retry_attempts": total_retries,
            "category_statistics": category_stats,
            "network_performance_samples": len(self.recent_network_performance),
            "average_network_latency_ms": (
                sum(self.recent_network_performance) / len(self.recent_network_performance)
                if self.recent_network_performance else 0
            )
        }