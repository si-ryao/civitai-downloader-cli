#!/usr/bin/env python3
"""
Parallel models optimization test script.

This script tests different levels of model parallelism (1-5 concurrent models)
to find the optimal balance between performance and system stability.
"""

import argparse
import json
import sys
import time
import traceback
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, List

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from civitai_dl.config import DownloadConfig
from civitai_dl.services.parallel_download_service import ParallelDownloadService
from civitai_dl.core.model_parallelism_manager import ParallelismMode


class ParallelModelsOptimizationTester:
    """Parallel models optimization tester."""
    
    def __init__(self, test_user: str = "Fandingo"):
        self.test_user = test_user
        self.test_root = Path("./test_parallel_models")
        self.test_root.mkdir(exist_ok=True)
        
        # Test configurations
        self.test_modes = [
            (ParallelismMode.SEQUENTIAL, "1 model (baseline)"),
            (ParallelismMode.CONSERVATIVE, "2 models (conservative)"),
            (ParallelismMode.BALANCED, "3 models (balanced)"),
            (ParallelismMode.AGGRESSIVE, "4 models (aggressive)"),
            (ParallelismMode.MAXIMUM, "5 models (maximum)")
        ]
        
        # Results storage
        self.test_results = {
            "test_info": {
                "test_user": test_user,
                "test_timestamp": datetime.utcnow().isoformat(),
                "test_duration_total": 0.0
            },
            "mode_results": {},
            "performance_analysis": {},
            "recommendations": []
        }
        
    def create_test_config(self, mode_name: str) -> DownloadConfig:
        """テスト用設定作成."""
        test_dir = self.test_root / f"downloads_{mode_name}"
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
            max_user_images=10  # Limit for faster testing
        )
        
        return config
        
    def run_parallel_mode_test(self, mode: ParallelismMode, description: str, max_models: int = None) -> Dict[str, Any]:
        """特定並列モードでのテスト実行."""
        mode_name = mode.name.lower()
        print(f"\n🧪 Testing {description}")
        print(f"{'='*60}")
        
        config = self.create_test_config(mode_name)
        service = ParallelDownloadService(config)
        
        # 並列モードを強制設定
        service.set_max_parallel_models(mode.value)
        
        start_time = time.time()
        
        try:
            # Get models first to limit if needed
            all_models = service.api_client.get_all_user_models(self.test_user)
            if max_models and len(all_models) > max_models:
                print(f"📋 Limiting to first {max_models} models (of {len(all_models)} total)")
                # Create a temporary user models list for testing
                limited_models = all_models[:max_models]
                
                # Mock the API response for testing
                original_method = service.api_client.get_all_user_models
                def mock_get_models(username):
                    return limited_models
                service.api_client.get_all_user_models = mock_get_models
            
            # Execute download
            result = service.download_user_models(self.test_user)
            
            # Restore original method if mocked
            if max_models:
                service.api_client.get_all_user_models = original_method
            
            end_time = time.time()
            duration = end_time - start_time
            
            # Calculate metrics
            total_models = result.get("total_models", 0)
            successful_downloads = result.get("successful_downloads", 0)
            failed_downloads = result.get("failed_downloads", 0)
            
            success_rate = (successful_downloads / total_models * 100) if total_models > 0 else 0
            throughput = total_models / (duration / 60) if duration > 0 else 0
            
            # Get detailed performance stats
            performance_stats = result.get("performance_stats", {})
            parallelism_stats = performance_stats.get("parallelism_manager_stats", {})
            
            test_result = {
                "success": result.get("success", False),
                "mode": mode.name,
                "parallel_models": mode.value,
                "duration_minutes": duration / 60,
                "total_models": total_models,
                "successful_downloads": successful_downloads,
                "failed_downloads": failed_downloads,
                "success_rate_percent": success_rate,
                "throughput_models_per_minute": throughput,
                "performance_stats": performance_stats,
                "parallelism_stats": parallelism_stats,
                "error_message": result.get("message") if not result.get("success") else None
            }
            
            print(f"✅ {description} completed:")
            print(f"   Duration: {duration/60:.2f} minutes")
            print(f"   Models: {successful_downloads}/{total_models} successful")
            print(f"   Throughput: {throughput:.2f} models/min")
            print(f"   Success rate: {success_rate:.1f}%")
            
            if parallelism_stats:
                print(f"   System stats: Memory={parallelism_stats.get('latest_metrics', {}).get('memory_usage_mb', 0):.0f}MB, "
                      f"CPU={parallelism_stats.get('latest_metrics', {}).get('cpu_usage_percent', 0):.1f}%")
            
            return test_result
            
        except Exception as e:
            print(f"❌ {description} failed: {e}")
            traceback.print_exc()
            
            return {
                "success": False,
                "mode": mode.name,
                "parallel_models": mode.value,
                "error": str(e),
                "duration_minutes": (time.time() - start_time) / 60
            }
            
    def analyze_results(self) -> Dict[str, Any]:
        """結果分析."""
        print(f"\n📊 Analyzing parallel models optimization results...")
        
        successful_results = [result for result in self.test_results["mode_results"].values() if result.get("success")]
        
        if len(successful_results) < 2:
            return {
                "analysis_possible": False,
                "error": "Insufficient successful test results for analysis"
            }
            
        # Find best performing configurations
        best_throughput = max(successful_results, key=lambda x: x.get("throughput_models_per_minute", 0))
        best_success_rate = max(successful_results, key=lambda x: x.get("success_rate_percent", 0))
        most_stable = min(successful_results, key=lambda x: x.get("failed_downloads", float('inf')))
        
        # Calculate performance improvements
        baseline = next((r for r in successful_results if r["parallel_models"] == 1), None)
        if baseline:
            improvements = {}
            for result in successful_results:
                if result["parallel_models"] > 1:
                    baseline_throughput = baseline.get("throughput_models_per_minute", 0)
                    current_throughput = result.get("throughput_models_per_minute", 0)
                    
                    if baseline_throughput > 0:
                        improvement = ((current_throughput - baseline_throughput) / baseline_throughput) * 100
                        improvements[result["parallel_models"]] = {
                            "throughput_improvement_percent": improvement,
                            "speed_multiplier": current_throughput / baseline_throughput,
                            "mode": result["mode"],
                            "success_rate": result.get("success_rate_percent", 0),
                            "duration_minutes": result.get("duration_minutes", 0)
                        }
        
        # Resource efficiency analysis
        resource_analysis = {}
        for result in successful_results:
            parallelism_stats = result.get("parallelism_stats", {})
            latest_metrics = parallelism_stats.get("latest_metrics", {})
            
            resource_analysis[result["parallel_models"]] = {
                "throughput_per_parallel_model": result.get("throughput_models_per_minute", 0) / result["parallel_models"],
                "memory_usage_mb": latest_metrics.get("memory_usage_mb", 0),
                "cpu_usage_percent": latest_metrics.get("cpu_usage_percent", 0),
                "efficiency_score": self._calculate_efficiency_score(result)
            }
        
        analysis = {
            "analysis_possible": True,
            "best_configurations": {
                "highest_throughput": {
                    "mode": best_throughput["mode"],
                    "parallel_models": best_throughput["parallel_models"],
                    "throughput": best_throughput.get("throughput_models_per_minute", 0),
                    "success_rate": best_throughput.get("success_rate_percent", 0)
                },
                "highest_success_rate": {
                    "mode": best_success_rate["mode"],
                    "parallel_models": best_success_rate["parallel_models"],
                    "throughput": best_success_rate.get("throughput_models_per_minute", 0),
                    "success_rate": best_success_rate.get("success_rate_percent", 0)
                },
                "most_stable": {
                    "mode": most_stable["mode"],
                    "parallel_models": most_stable["parallel_models"],
                    "failed_downloads": most_stable.get("failed_downloads", 0),
                    "success_rate": most_stable.get("success_rate_percent", 0)
                }
            },
            "performance_improvements": improvements if baseline else {},
            "resource_efficiency": resource_analysis,
            "optimal_recommendation": self._determine_optimal_configuration(successful_results)
        }
        
        return analysis
        
    def _calculate_efficiency_score(self, result: Dict[str, Any]) -> float:
        """効率スコア計算."""
        throughput = result.get("throughput_models_per_minute", 0)
        success_rate = result.get("success_rate_percent", 0) / 100
        parallel_models = result.get("parallel_models", 1)
        
        parallelism_stats = result.get("parallelism_stats", {})
        latest_metrics = parallelism_stats.get("latest_metrics", {})
        memory_usage = latest_metrics.get("memory_usage_mb", 1000)
        cpu_usage = latest_metrics.get("cpu_usage_percent", 50)
        
        # Efficiency = (throughput * success_rate) / (resource_usage * parallel_models)
        resource_usage = (memory_usage / 1000) + (cpu_usage / 100)  # Normalized
        efficiency = (throughput * success_rate) / (resource_usage * parallel_models) if resource_usage > 0 else 0
        
        return efficiency
        
    def _determine_optimal_configuration(self, results: List[Dict[str, Any]]) -> Dict[str, Any]:
        """最適設定決定."""
        if not results:
            return {"error": "No results to analyze"}
            
        # Score each configuration
        scored_results = []
        for result in results:
            throughput = result.get("throughput_models_per_minute", 0)
            success_rate = result.get("success_rate_percent", 0) / 100
            efficiency = self._calculate_efficiency_score(result)
            
            # Composite score: throughput * success_rate + efficiency bonus
            score = (throughput * success_rate) + (efficiency * 0.1)
            
            scored_results.append({
                "result": result,
                "score": score,
                "efficiency": efficiency
            })
            
        # Sort by score
        scored_results.sort(key=lambda x: x["score"], reverse=True)
        
        best = scored_results[0]["result"]
        
        return {
            "recommended_mode": best["mode"],
            "recommended_parallel_models": best["parallel_models"],
            "expected_throughput": best.get("throughput_models_per_minute", 0),
            "expected_success_rate": best.get("success_rate_percent", 0),
            "efficiency_score": scored_results[0]["efficiency"],
            "composite_score": scored_results[0]["score"],
            "reasoning": f"Best balance of throughput ({best.get('throughput_models_per_minute', 0):.1f} models/min) and stability ({best.get('success_rate_percent', 0):.1f}%)"
        }
        
    def generate_recommendations(self, analysis: Dict[str, Any]) -> List[str]:
        """推奨事項生成."""
        recommendations = []
        
        if not analysis.get("analysis_possible"):
            recommendations.append("❌ Unable to analyze - insufficient test data")
            return recommendations
            
        optimal = analysis.get("optimal_recommendation", {})
        if optimal and not optimal.get("error"):
            recommendations.append(f"🎯 Optimal configuration: {optimal['recommended_mode']} ({optimal['recommended_parallel_models']} models)")
            recommendations.append(f"   Expected: {optimal['expected_throughput']:.1f} models/min at {optimal['expected_success_rate']:.1f}% success rate")
            
        # Performance analysis
        improvements = analysis.get("performance_improvements", {})
        if improvements:
            best_improvement = max(improvements.items(), key=lambda x: x[1]["throughput_improvement_percent"])
            parallel_models, improvement_data = best_improvement
            recommendations.append(f"🚀 Best performance: {parallel_models} models gives {improvement_data['throughput_improvement_percent']:+.1f}% improvement")
            
        # Stability recommendations
        best_configs = analysis.get("best_configurations", {})
        most_stable = best_configs.get("most_stable", {})
        if most_stable:
            recommendations.append(f"🛡️ Most stable: {most_stable['mode']} with {most_stable['success_rate']:.1f}% success rate")
            
        return recommendations
        
    def save_results(self) -> Path:
        """テスト結果保存."""
        timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
        results_file = self.test_root / f"parallel_models_optimization_{timestamp}.json"
        
        with open(results_file, 'w', encoding='utf-8') as f:
            json.dump(self.test_results, f, indent=2, ensure_ascii=False)
            
        print(f"\n💾 Optimization test results saved: {results_file}")
        return results_file
        
    def run_complete_optimization_test(self, max_models_per_test: int = None) -> Dict[str, Any]:
        """完全最適化テスト実行."""
        print(f"🧪 Starting parallel models optimization test for user: {self.test_user}")
        print(f"📁 Test results will be saved to: {self.test_root}")
        if max_models_per_test:
            print(f"⚡ Limited to {max_models_per_test} models per test for faster execution")
        
        total_start_time = time.time()
        
        # Run tests for each mode
        for mode, description in self.test_modes:
            mode_result = self.run_parallel_mode_test(mode, description, max_models_per_test)
            self.test_results["mode_results"][mode.name] = mode_result
            
        # Analyze results
        print(f"\n{'='*60}")
        print(f"OPTIMIZATION ANALYSIS")
        print(f"{'='*60}")
        
        analysis = self.analyze_results()
        self.test_results["performance_analysis"] = analysis
        
        # Generate recommendations
        recommendations = self.generate_recommendations(analysis)
        self.test_results["recommendations"] = recommendations
        
        # Update test info
        total_duration = time.time() - total_start_time
        self.test_results["test_info"]["test_duration_total"] = total_duration
        
        # Print summary
        print(f"\n{'='*60}")
        print(f"OPTIMIZATION SUMMARY")
        print(f"{'='*60}")
        print(f"Total test duration: {total_duration/60:.1f} minutes")
        
        if recommendations:
            print(f"\n💡 Recommendations:")
            for rec in recommendations:
                print(f"   {rec}")
                
        # Save results
        results_file = self.save_results()
        
        print(f"\n🎉 Parallel models optimization test completed!")
        
        return self.test_results


def main():
    """メイン実行関数."""
    parser = argparse.ArgumentParser(description="Parallel Models Optimization Test")
    parser.add_argument("--user", default="Fandingo", help="Test user (default: Fandingo)")
    parser.add_argument("--max-models", type=int, help="Max models per test (for faster execution)")
    parser.add_argument("--mode", choices=["sequential", "conservative", "balanced", "aggressive", "maximum"], help="Test specific mode only")
    
    args = parser.parse_args()
    
    tester = ParallelModelsOptimizationTester(test_user=args.user)
    
    try:
        if args.mode:
            # Test single mode
            mode_map = {
                "sequential": ParallelismMode.SEQUENTIAL,
                "conservative": ParallelismMode.CONSERVATIVE,
                "balanced": ParallelismMode.BALANCED,
                "aggressive": ParallelismMode.AGGRESSIVE,
                "maximum": ParallelismMode.MAXIMUM
            }
            mode = mode_map[args.mode]
            description = f"{mode.value} models ({args.mode})"
            result = tester.run_parallel_mode_test(mode, description, args.max_models)
            print(json.dumps(result, indent=2))
        else:
            # Run complete optimization test
            tester.run_complete_optimization_test(args.max_models)
            
    except KeyboardInterrupt:
        print(f"\n⏹️ Test interrupted by user")
    except Exception as e:
        print(f"\n❌ Test failed with error: {e}")
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()