#!/usr/bin/env python3
"""
Phase 2 performance testing script for Fandingo user.

This script runs comparative tests between the baseline DownloadService 
and the new ParallelDownloadService, measuring performance improvements
and stability metrics.
"""

import argparse
import asyncio
import json
import sys
import time
import traceback
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, Optional, List

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from civitai_dl.config import DownloadConfig
from civitai_dl.services.download_service import DownloadService
from civitai_dl.services.parallel_download_service import ParallelDownloadService


class Phase2PerformanceTester:
    """Phase 2 performance testing framework."""
    
    def __init__(self, test_user: str = "Fandingo"):
        self.test_user = test_user
        self.test_root = Path("./test_phase2_results")
        self.test_root.mkdir(exist_ok=True)
        
        # Test results storage
        self.results = {
            "test_info": {
                "test_user": test_user,
                "test_timestamp": datetime.utcnow().isoformat(),
                "test_duration_total": 0.0
            },
            "baseline_results": {},
            "parallel_results": {},
            "comparison": {},
            "recommendations": []
        }
        
    def create_test_config(self, test_mode_suffix: str) -> DownloadConfig:
        """テスト用設定作成."""
        test_dir = self.test_root / f"downloads_{test_mode_suffix}"
        test_dir.mkdir(exist_ok=True)
        
        # API key reading
        api_key = None
        api_key_file = Path(__file__).parent.parent / "api_key.md"
        if api_key_file.exists():
            api_key = api_key_file.read_text().strip().split("\n")[0]
        
        config = DownloadConfig(
            api_key=api_key,
            is_test=True,
            test_root=str(test_dir),
            max_user_images=20  # Limit for testing
        )
        
        return config
        
    def run_baseline_test(self) -> Dict[str, Any]:
        """ベースライン（既存版）テスト実行."""
        print(f"🔄 Running baseline test for user: {self.test_user}")
        
        config = self.create_test_config("baseline")
        service = DownloadService(config)
        
        start_time = time.time()
        
        try:
            # Execute download
            result = service.download_user_models(self.test_user)
            
            end_time = time.time()
            duration = end_time - start_time
            
            # Calculate metrics
            total_models = result.get("total_models", 0)
            successful_downloads = result.get("successful_downloads", 0)
            failed_downloads = result.get("failed_downloads", 0)
            
            success_rate = (successful_downloads / total_models * 100) if total_models > 0 else 0
            throughput = total_models / (duration / 60) if duration > 0 else 0  # models per minute
            
            baseline_results = {
                "success": result.get("success", False),
                "duration_minutes": duration / 60,
                "total_models": total_models,
                "successful_downloads": successful_downloads,
                "failed_downloads": failed_downloads,
                "success_rate_percent": success_rate,
                "throughput_models_per_minute": throughput,
                "error_message": result.get("message") if not result.get("success") else None
            }
            
            print(f"✅ Baseline test completed:")
            print(f"   Duration: {duration/60:.2f} minutes")
            print(f"   Models: {successful_downloads}/{total_models} successful")
            print(f"   Throughput: {throughput:.2f} models/min")
            print(f"   Success rate: {success_rate:.1f}%")
            
            return baseline_results
            
        except Exception as e:
            print(f"❌ Baseline test failed: {e}")
            traceback.print_exc()
            
            return {
                "success": False,
                "error": str(e),
                "duration_minutes": (time.time() - start_time) / 60
            }
            
    def run_parallel_test(self) -> Dict[str, Any]:
        """並行処理版テスト実行."""
        print(f"🚀 Running parallel test for user: {self.test_user}")
        
        config = self.create_test_config("parallel")
        service = ParallelDownloadService(config)
        
        start_time = time.time()
        
        try:
            # Execute download with parallel processing
            result = service.download_user_models(self.test_user)
            
            end_time = time.time()
            duration = end_time - start_time
            
            # Calculate metrics
            total_models = result.get("total_models", 0)
            successful_downloads = result.get("successful_downloads", 0)
            failed_downloads = result.get("failed_downloads", 0)
            
            success_rate = (successful_downloads / total_models * 100) if total_models > 0 else 0
            throughput = total_models / (duration / 60) if duration > 0 else 0
            
            # Get performance stats from the service
            performance_stats = result.get("performance_stats", {})
            concurrency_stats = performance_stats.get("concurrency_stats", {})
            safety_stats = performance_stats.get("safety_stats", {})
            
            parallel_results = {
                "success": result.get("success", False),
                "duration_minutes": duration / 60,
                "total_models": total_models,
                "successful_downloads": successful_downloads,
                "failed_downloads": failed_downloads,
                "success_rate_percent": success_rate,
                "throughput_models_per_minute": throughput,
                "concurrency_mode": concurrency_stats.get("current_mode", "unknown"),
                "fallback_activated": concurrency_stats.get("fallback_active", False),
                "safety_level": safety_stats.get("safety_level", "unknown"),
                "safety_score": safety_stats.get("safety_score", 0),
                "memory_usage_mb": safety_stats.get("memory_usage_mb", 0),
                "performance_report": service.get_performance_report(),
                "error_message": result.get("message") if not result.get("success") else None
            }
            
            print(f"✅ Parallel test completed:")
            print(f"   Duration: {duration/60:.2f} minutes")
            print(f"   Models: {successful_downloads}/{total_models} successful")
            print(f"   Throughput: {throughput:.2f} models/min")
            print(f"   Success rate: {success_rate:.1f}%")
            print(f"   Concurrency mode: {parallel_results['concurrency_mode']}")
            print(f"   Safety level: {parallel_results['safety_level']}")
            
            return parallel_results
            
        except Exception as e:
            print(f"❌ Parallel test failed: {e}")
            traceback.print_exc()
            
            return {
                "success": False,
                "error": str(e),
                "duration_minutes": (time.time() - start_time) / 60,
                "fallback_to_baseline": True
            }
            
    def compare_results(self, baseline: Dict[str, Any], parallel: Dict[str, Any]) -> Dict[str, Any]:
        """結果比較分析."""
        print(f"\n📊 Analyzing performance comparison...")
        
        if not baseline.get("success") or not parallel.get("success"):
            return {
                "comparison_possible": False,
                "baseline_success": baseline.get("success", False),
                "parallel_success": parallel.get("success", False),
                "error": "One or both tests failed"
            }
            
        # Performance calculations
        baseline_duration = baseline.get("duration_minutes", 0)
        parallel_duration = parallel.get("duration_minutes", 0)
        
        baseline_throughput = baseline.get("throughput_models_per_minute", 0)
        parallel_throughput = parallel.get("throughput_models_per_minute", 0)
        
        # Calculate improvements
        duration_improvement = 0.0
        throughput_improvement = 0.0
        
        if baseline_duration > 0:
            duration_improvement = ((baseline_duration - parallel_duration) / baseline_duration) * 100
            
        if baseline_throughput > 0:
            throughput_improvement = ((parallel_throughput - baseline_throughput) / baseline_throughput) * 100
            
        comparison = {
            "comparison_possible": True,
            "performance_improvements": {
                "duration_improvement_percent": duration_improvement,
                "throughput_improvement_percent": throughput_improvement,
                "speed_multiplier": parallel_throughput / baseline_throughput if baseline_throughput > 0 else 0
            },
            "reliability_comparison": {
                "baseline_success_rate": baseline.get("success_rate_percent", 0),
                "parallel_success_rate": parallel.get("success_rate_percent", 0),
                "success_rate_change": parallel.get("success_rate_percent", 0) - baseline.get("success_rate_percent", 0)
            },
            "resource_usage": {
                "memory_usage_mb": parallel.get("memory_usage_mb", 0),
                "safety_score": parallel.get("safety_score", 0),
                "concurrency_mode_used": parallel.get("concurrency_mode", "unknown")
            },
            "goal_achievement": {
                "target_improvement_percent": 150,  # 150-200% target
                "achieved_improvement_percent": throughput_improvement,
                "target_met": throughput_improvement >= 50  # 150% = 50% improvement
            }
        }
        
        print(f"📈 Performance Analysis:")
        print(f"   Duration improvement: {duration_improvement:+.1f}%")
        print(f"   Throughput improvement: {throughput_improvement:+.1f}%")
        print(f"   Speed multiplier: {comparison['performance_improvements']['speed_multiplier']:.2f}x")
        print(f"   Target achievement: {'✅ MET' if comparison['goal_achievement']['target_met'] else '❌ NOT MET'}")
        
        return comparison
        
    def generate_recommendations(self, comparison: Dict[str, Any]) -> List[str]:
        """推奨事項生成."""
        recommendations = []
        
        if not comparison.get("comparison_possible"):
            recommendations.append("Fix test failures before assessing performance")
            return recommendations
            
        perf = comparison.get("performance_improvements", {})
        goal = comparison.get("goal_achievement", {})
        
        throughput_improvement = perf.get("throughput_improvement_percent", 0)
        
        if goal.get("target_met", False):
            recommendations.append(f"✅ Phase 2 successfully achieved performance target ({throughput_improvement:.1f}% improvement)")
            
            if throughput_improvement > 100:
                recommendations.append("🚀 Exceptional performance - consider proceeding to Phase 3")
            else:
                recommendations.append("📊 Good performance - monitor stability before Phase 3")
                
        else:
            recommendations.append(f"⚠️ Phase 2 below target ({throughput_improvement:.1f}% vs 50%+ target)")
            
            if throughput_improvement > 0:
                recommendations.append("🔧 Performance improved but investigate bottlenecks")
            else:
                recommendations.append("❌ Performance regression - review parallel implementation")
                
        # Safety and reliability recommendations
        reliability = comparison.get("reliability_comparison", {})
        success_rate_change = reliability.get("success_rate_change", 0)
        
        if success_rate_change < -5:
            recommendations.append("⚠️ Success rate decreased - review error handling")
        elif success_rate_change > 5:
            recommendations.append("✅ Success rate improved - parallel processing is stable")
            
        return recommendations
        
    def save_results(self) -> Path:
        """テスト結果保存."""
        timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
        results_file = self.test_root / f"phase2_test_results_{timestamp}.json"
        
        with open(results_file, 'w', encoding='utf-8') as f:
            json.dump(self.results, f, indent=2, ensure_ascii=False)
            
        print(f"\n💾 Test results saved: {results_file}")
        return results_file
        
    def run_complete_test(self) -> Dict[str, Any]:
        """完全テスト実行."""
        print(f"🧪 Starting Phase 2 performance test for user: {self.test_user}")
        print(f"📁 Test results will be saved to: {self.test_root}")
        
        total_start_time = time.time()
        
        # Run baseline test
        print(f"\n{'='*50}")
        print(f"BASELINE TEST (Existing DownloadService)")
        print(f"{'='*50}")
        
        baseline_results = self.run_baseline_test()
        self.results["baseline_results"] = baseline_results
        
        # Run parallel test
        print(f"\n{'='*50}")
        print(f"PARALLEL TEST (New ParallelDownloadService)")
        print(f"{'='*50}")
        
        parallel_results = self.run_parallel_test()
        self.results["parallel_results"] = parallel_results
        
        # Compare results
        print(f"\n{'='*50}")
        print(f"PERFORMANCE COMPARISON")
        print(f"{'='*50}")
        
        comparison = self.compare_results(baseline_results, parallel_results)
        self.results["comparison"] = comparison
        
        # Generate recommendations
        recommendations = self.generate_recommendations(comparison)
        self.results["recommendations"] = recommendations
        
        # Update test info
        total_duration = time.time() - total_start_time
        self.results["test_info"]["test_duration_total"] = total_duration
        
        # Print summary
        print(f"\n{'='*50}")
        print(f"TEST SUMMARY")
        print(f"{'='*50}")
        print(f"Total test duration: {total_duration/60:.1f} minutes")
        
        if recommendations:
            print(f"\n💡 Recommendations:")
            for rec in recommendations:
                print(f"   {rec}")
                
        # Save results
        results_file = self.save_results()
        
        print(f"\n🎉 Phase 2 performance test completed!")
        
        return self.results


def main():
    """メイン実行関数."""
    parser = argparse.ArgumentParser(description="Phase 2 Performance Test")
    parser.add_argument("--user", default="Fandingo", help="Test user (default: Fandingo)")
    parser.add_argument("--baseline-only", action="store_true", help="Run baseline test only")
    parser.add_argument("--parallel-only", action="store_true", help="Run parallel test only")
    
    args = parser.parse_args()
    
    tester = Phase2PerformanceTester(test_user=args.user)
    
    try:
        if args.baseline_only:
            print("Running baseline test only...")
            result = tester.run_baseline_test()
            print(json.dumps(result, indent=2))
        elif args.parallel_only:
            print("Running parallel test only...")
            result = tester.run_parallel_test()
            print(json.dumps(result, indent=2))
        else:
            # Run complete test
            tester.run_complete_test()
            
    except KeyboardInterrupt:
        print(f"\n⏹️ Test interrupted by user")
    except Exception as e:
        print(f"\n❌ Test failed with error: {e}")
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()