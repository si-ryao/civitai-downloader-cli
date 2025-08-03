#!/usr/bin/env python3
"""
Performance benchmark script for measuring current system baseline.

This script provides comprehensive performance measurement and baseline
establishment for the Civitai downloader system.
"""

import argparse
import asyncio
import json
import sys
import time
import uuid
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Any, Optional

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from civitai_dl.config import DownloadConfig
from civitai_dl.services.download_service import DownloadService
from civitai_dl.monitoring.performance_monitor import PerformanceMonitor
from civitai_dl.monitoring.health_monitor import HealthMonitor
from civitai_dl.monitoring.metrics_collector import MetricsCollector


class BenchmarkRunner:
    """Performance benchmark execution and analysis."""
    
    def __init__(self, config: DownloadConfig):
        self.config = config
        self.output_dir = Path(config.output_dir) 
        self.benchmark_dir = self.output_dir / "benchmarks"
        self.benchmark_dir.mkdir(exist_ok=True)
        
        # 監視システム初期化
        self.performance_monitor = PerformanceMonitor(self.output_dir)
        self.health_monitor = HealthMonitor(config, self.output_dir)
        self.metrics_collector = MetricsCollector(self.output_dir)
        
        # ダウンロードサービス
        self.download_service = DownloadService(config)
        
    def run_baseline_benchmark(
        self, 
        test_users: List[str],
        duration_minutes: Optional[int] = None,
        max_models: Optional[int] = None
    ) -> Dict[str, Any]:
        """ベースライン性能測定実行."""
        print("🚀 Starting baseline performance benchmark")
        print(f"   Test users: {len(test_users)}")
        if duration_minutes:
            print(f"   Duration limit: {duration_minutes} minutes")
        if max_models:
            print(f"   Model limit: {max_models} models")
            
        start_time = time.time()
        benchmark_id = str(uuid.uuid4())
        
        # 健全性チェック開始
        health_task = None
        if duration_minutes:
            health_task = asyncio.create_task(
                self.health_monitor.continuous_monitoring(duration_minutes / 60)
            )
        
        results = {
            "benchmark_id": benchmark_id,
            "start_time": datetime.utcnow().isoformat(),
            "configuration": {
                "test_users": test_users,
                "duration_minutes": duration_minutes,
                "max_models": max_models,
                "output_dir": str(self.output_dir),
                "production_mode": not self.config.is_test
            },
            "user_results": [],
            "overall_performance": {},
            "health_status": {},
            "recommendations": []
        }
        
        try:
            total_models_processed = 0
            
            for i, username in enumerate(test_users, 1):
                print(f"\n📦 Processing user {i}/{len(test_users)}: {username}")
                
                # 時間制限チェック
                if duration_minutes:
                    elapsed_minutes = (time.time() - start_time) / 60
                    if elapsed_minutes >= duration_minutes:
                        print(f"⏰ Time limit reached: {elapsed_minutes:.1f} minutes")
                        break
                
                # モデル数制限チェック
                if max_models and total_models_processed >= max_models:
                    print(f"📊 Model limit reached: {total_models_processed} models")
                    break
                    
                user_start_time = time.time()
                
                try:
                    # ユーザーのモデルダウンロード実行
                    user_result = self.download_service.download_user_models(username)
                    
                    # パフォーマンス記録
                    user_duration = time.time() - user_start_time
                    models_processed = user_result.get("total_models", 0)
                    total_models_processed += models_processed
                    
                    user_benchmark = {
                        "username": username,
                        "success": user_result.get("success", False),
                        "duration_minutes": user_duration / 60,
                        "total_models": models_processed,
                        "successful_downloads": user_result.get("successful_downloads", 0),
                        "failed_downloads": user_result.get("failed_downloads", 0),
                        "models_per_minute": models_processed / (user_duration / 60) if user_duration > 0 else 0
                    }
                    
                    results["user_results"].append(user_benchmark)
                    
                    print(f"   ✅ Completed: {models_processed} models in {user_duration/60:.1f}min")
                    
                except Exception as e:
                    print(f"   ❌ Failed: {e}")
                    results["user_results"].append({
                        "username": username,
                        "success": False,
                        "error": str(e),
                        "duration_minutes": (time.time() - user_start_time) / 60
                    })
                    
                # 中間メトリクス記録
                self.metrics_collector.record_metrics_snapshot()
                
            # 最終性能サマリー生成
            end_time = time.time()
            total_duration = end_time - start_time
            
            results["end_time"] = datetime.utcnow().isoformat()
            results["total_duration_minutes"] = total_duration / 60
            results["total_models_processed"] = total_models_processed
            
            # パフォーマンス統計
            results["overall_performance"] = self._calculate_performance_stats(results["user_results"])
            
            # メトリクス要約
            results["metrics_summary"] = self.metrics_collector.generate_performance_summary()
            
            # 健全性レポート
            results["health_status"] = self.health_monitor.generate_health_report()
            
            # 推奨事項生成
            results["recommendations"] = self._generate_benchmark_recommendations(results)
            
            print(f"\n🎉 Benchmark completed!")
            print(f"   Duration: {total_duration/60:.1f} minutes")
            print(f"   Models processed: {total_models_processed}")
            print(f"   Average speed: {total_models_processed/(total_duration/60):.1f} models/min")
            
        except KeyboardInterrupt:
            print("\n⏹️  Benchmark interrupted by user")
            results["interrupted"] = True
            results["end_time"] = datetime.utcnow().isoformat()
            
        except Exception as e:
            print(f"\n❌ Benchmark failed: {e}")
            results["error"] = str(e)
            results["end_time"] = datetime.utcnow().isoformat()
            
        finally:
            # 健全性監視停止
            if health_task and not health_task.done():
                health_task.cancel()
                try:
                    await health_task
                except asyncio.CancelledError:
                    pass
                    
        # ベンチマーク結果保存
        self._save_benchmark_results(results)
        
        return results
        
    def _calculate_performance_stats(self, user_results: List[Dict[str, Any]]) -> Dict[str, Any]:
        """パフォーマンス統計計算."""
        successful_users = [r for r in user_results if r.get("success", False)]
        
        if not successful_users:
            return {
                "total_users": len(user_results),
                "successful_users": 0,
                "success_rate": 0.0,
                "average_models_per_user": 0.0,
                "average_duration_per_user_minutes": 0.0,
                "total_throughput_models_per_minute": 0.0
            }
            
        total_models = sum(r.get("total_models", 0) for r in successful_users)
        total_duration_minutes = sum(r.get("duration_minutes", 0) for r in successful_users)
        
        return {
            "total_users": len(user_results),
            "successful_users": len(successful_users),
            "success_rate": len(successful_users) / len(user_results) * 100,
            "total_models": total_models,
            "average_models_per_user": total_models / len(successful_users),
            "average_duration_per_user_minutes": total_duration_minutes / len(successful_users),
            "total_throughput_models_per_minute": total_models / total_duration_minutes if total_duration_minutes > 0 else 0
        }
        
    def _generate_benchmark_recommendations(self, results: Dict[str, Any]) -> List[str]:
        """ベンチマーク結果に基づく推奨事項生成."""
        recommendations = []
        
        overall_perf = results.get("overall_performance", {})
        metrics_summary = results.get("metrics_summary", {})
        
        # 成功率チェック
        success_rate = overall_perf.get("success_rate", 0)
        if success_rate < 95:
            recommendations.append(
                f"Low success rate ({success_rate:.1f}%). "
                "Consider implementing additional error handling and retry logic."
            )
            
        # スループットチェック
        throughput = overall_perf.get("total_throughput_models_per_minute", 0)
        if throughput < 5:  # 5モデル/分未満
            recommendations.append(
                f"Low throughput ({throughput:.1f} models/min). "
                "Consider optimizing download speed or implementing limited concurrency."
            )
            
        # エラー率チェック
        reliability = metrics_summary.get("reliability", {})
        error_rate = reliability.get("error_rate_percent", 0)
        if error_rate > 5:
            recommendations.append(
                f"High error rate ({error_rate:.1f}%). "
                "Review error logs and implement more robust error handling."
            )
            
        # タイムアウト率チェック
        timeout_rate = reliability.get("timeout_rate_percent", 0)
        if timeout_rate > 1:
            recommendations.append(
                f"High timeout rate ({timeout_rate:.1f}%). "
                "Consider implementing adaptive timeout handling."
            )
            
        # メモリ使用量チェック
        resource_usage = metrics_summary.get("resource_usage", {})
        memory_growth = resource_usage.get("memory_growth_rate_mb_per_hour", 0)
        if memory_growth > 50:  # 50MB/時間以上の増加
            recommendations.append(
                f"Memory growth detected ({memory_growth:.1f} MB/hour). "
                "Investigate potential memory leaks."
            )
            
        if not recommendations:
            recommendations.append("System performance is within acceptable ranges.")
            
        return recommendations
        
    def _save_benchmark_results(self, results: Dict[str, Any]) -> Path:
        """ベンチマーク結果保存."""
        timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
        filename = f"baseline_benchmark_{timestamp}.json"
        filepath = self.benchmark_dir / filename
        
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(results, f, indent=2, ensure_ascii=False)
            
        print(f"📊 Benchmark results saved: {filepath}")
        
        # ベースラインファイルとしてもコピー
        baseline_file = self.benchmark_dir / "baseline.json"
        with open(baseline_file, 'w', encoding='utf-8') as f:
            json.dump(results, f, indent=2, ensure_ascii=False)
            
        return filepath
        
    def compare_benchmarks(self, baseline_file: Path, current_results: Dict[str, Any]) -> Dict[str, Any]:
        """ベンチマーク比較分析."""
        if not baseline_file.exists():
            return {"error": "Baseline file not found"}
            
        try:
            with open(baseline_file, 'r', encoding='utf-8') as f:
                baseline_results = json.load(f)
                
        except (json.JSONDecodeError, IOError) as e:
            return {"error": f"Failed to load baseline: {e}"}
            
        baseline_perf = baseline_results.get("overall_performance", {})
        current_perf = current_results.get("overall_performance", {})
        
        def calculate_change(current_val, baseline_val):
            if baseline_val == 0:
                return 0.0
            return ((current_val - baseline_val) / baseline_val) * 100
            
        comparison = {
            "baseline_date": baseline_results.get("start_time"),
            "current_date": current_results.get("start_time"),
            "performance_changes": {
                "success_rate_change": calculate_change(
                    current_perf.get("success_rate", 0),
                    baseline_perf.get("success_rate", 0)
                ),
                "throughput_change": calculate_change(
                    current_perf.get("total_throughput_models_per_minute", 0),
                    baseline_perf.get("total_throughput_models_per_minute", 0)
                ),
                "duration_change": calculate_change(
                    current_perf.get("average_duration_per_user_minutes", 0),
                    baseline_perf.get("average_duration_per_user_minutes", 0)
                )
            },
            "interpretation": self._interpret_comparison_results(
                current_perf, baseline_perf
            )
        }
        
        return comparison
        
    def _interpret_comparison_results(
        self, 
        current_perf: Dict[str, Any], 
        baseline_perf: Dict[str, Any]
    ) -> List[str]:
        """比較結果の解釈."""
        interpretations = []
        
        current_throughput = current_perf.get("total_throughput_models_per_minute", 0)
        baseline_throughput = baseline_perf.get("total_throughput_models_per_minute", 0)
        
        if baseline_throughput > 0:
            throughput_change = (current_throughput - baseline_throughput) / baseline_throughput * 100
            
            if throughput_change > 10:
                interpretations.append(
                    f"✅ Significant performance improvement: {throughput_change:.1f}% faster"
                )
            elif throughput_change > 5:
                interpretations.append(
                    f"✅ Moderate performance improvement: {throughput_change:.1f}% faster"
                )
            elif throughput_change > -5:
                interpretations.append(
                    "➡️ Performance is stable (within 5% of baseline)"
                )
            elif throughput_change > -10:
                interpretations.append(
                    f"⚠️ Minor performance regression: {abs(throughput_change):.1f}% slower"
                )
            else:
                interpretations.append(
                    f"❌ Significant performance regression: {abs(throughput_change):.1f}% slower"
                )
                
        return interpretations


async def main():
    """メイン実行関数."""
    parser = argparse.ArgumentParser(description="Civitai Downloader Performance Benchmark")
    parser.add_argument("--users", nargs="+", default=["alericiviai"], help="Test usernames")
    parser.add_argument("--duration", type=int, help="Duration limit in minutes")
    parser.add_argument("--max-models", type=int, help="Maximum models to process")
    parser.add_argument("--output-dir", type=str, default="./benchmarks", help="Output directory")
    parser.add_argument("--compare-with", type=str, help="Baseline file to compare with")
    parser.add_argument("--is-test", action="store_true", help="Run in test mode")
    
    args = parser.parse_args()
    
    # 設定作成
    config = DownloadConfig(
        is_test=args.is_test,
        production_root=args.output_dir if not args.is_test else "./test_benchmarks"
    )
    
    # ベンチマーク実行
    runner = BenchmarkRunner(config)
    
    print(f"🔧 Configuration:")
    print(f"   Test mode: {config.is_test}")
    print(f"   Output directory: {config.output_dir}")
    print(f"   Users: {args.users}")
    
    results = await runner.run_baseline_benchmark(
        test_users=args.users,
        duration_minutes=args.duration,
        max_models=args.max_models
    )
    
    # 比較分析（指定されている場合）
    if args.compare_with:
        baseline_file = Path(args.compare_with)
        comparison = runner.compare_benchmarks(baseline_file, results)
        
        print("\n📊 Comparison Results:")
        if "error" in comparison:
            print(f"   ❌ {comparison['error']}")
        else:
            changes = comparison["performance_changes"]
            print(f"   Success rate change: {changes['success_rate_change']:+.1f}%")
            print(f"   Throughput change: {changes['throughput_change']:+.1f}%")
            print(f"   Duration change: {changes['duration_change']:+.1f}%")
            
            for interpretation in comparison["interpretation"]:
                print(f"   {interpretation}")
    
    # 推奨事項表示
    recommendations = results.get("recommendations", [])
    if recommendations:
        print("\n💡 Recommendations:")
        for rec in recommendations:
            print(f"   • {rec}")
    
    print(f"\n📁 Results saved to: {runner.benchmark_dir}")
    

if __name__ == "__main__":
    asyncio.run(main())