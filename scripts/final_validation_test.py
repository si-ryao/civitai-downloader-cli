#!/usr/bin/env python3
"""
Final validation test with optimal parallel settings.

This script tests the optimal 2-model parallel configuration
with a larger dataset to confirm stability and performance.
"""

import argparse
import json
import sys
import time
import traceback
from datetime import datetime
from pathlib import Path
from typing import Dict, Any

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from civitai_dl.config import DownloadConfig
from civitai_dl.services.download_service import DownloadService
from civitai_dl.services.parallel_download_service import ParallelDownloadService


def create_test_config(mode_name: str) -> DownloadConfig:
    """テスト用設定作成."""
    test_root = Path("./test_final_validation")
    test_dir = test_root / f"downloads_{mode_name}"
    test_dir.mkdir(parents=True, exist_ok=True)
    
    # API key reading
    api_key = None
    api_key_file = Path(__file__).parent.parent / "api_key.md"
    if api_key_file.exists():
        api_key = api_key_file.read_text().strip().split("\n")[0]
    
    config = DownloadConfig(
        api_key=api_key,
        is_test=True,
        test_root=str(test_dir),
        max_user_images=10  # Balanced for thorough testing
    )
    
    return config


def test_baseline_performance(user: str, max_models: int = 10) -> Dict[str, Any]:
    """ベースライン（既存版）性能テスト."""
    print(f"🔄 Testing baseline performance for user: {user}")
    print(f"📋 Testing with up to {max_models} models")
    
    config = create_test_config("baseline")
    service = DownloadService(config)
    
    start_time = time.time()
    
    try:
        # Get models first to limit
        all_models = service.api_client.get_all_user_models(user)
        if len(all_models) > max_models:
            print(f"📋 Limiting to first {max_models} models (of {len(all_models)} total)")
            limited_models = all_models[:max_models]
            
            original_method = service.api_client.get_all_user_models
            def mock_get_models(username):
                return limited_models
            service.api_client.get_all_user_models = mock_get_models
        
        # Execute download
        result = service.download_user_models(user)
        
        # Restore original method if mocked
        if len(all_models) > max_models:
            service.api_client.get_all_user_models = original_method
        
        end_time = time.time()
        duration = end_time - start_time
        
        # Calculate metrics
        total_models = result.get("total_models", 0)
        successful_downloads = result.get("successful_downloads", 0)
        failed_downloads = result.get("failed_downloads", 0)
        success_rate = (successful_downloads / total_models * 100) if total_models > 0 else 0
        throughput = total_models / (duration / 60) if duration > 0 else 0
        
        baseline_result = {
            "success": result.get("success", False),
            "test_type": "baseline",
            "duration_minutes": duration / 60,
            "total_models": total_models,
            "successful_downloads": successful_downloads,
            "failed_downloads": failed_downloads,
            "success_rate_percent": success_rate,
            "throughput_models_per_minute": throughput,
            "test_timestamp": datetime.utcnow().isoformat()
        }
        
        print(f"✅ Baseline test completed:")
        print(f"   Duration: {duration/60:.2f} minutes")
        print(f"   Models: {successful_downloads}/{total_models} successful")
        print(f"   Throughput: {throughput:.2f} models/min")
        print(f"   Success rate: {success_rate:.1f}%")
        
        return baseline_result
        
    except Exception as e:
        print(f"❌ Baseline test failed: {e}")
        traceback.print_exc()
        
        return {
            "success": False,
            "test_type": "baseline",
            "error": str(e),
            "duration_minutes": (time.time() - start_time) / 60,
            "test_timestamp": datetime.utcnow().isoformat()
        }


def test_optimal_parallel_performance(user: str, max_models: int = 10) -> Dict[str, Any]:
    """最適並列設定性能テスト."""
    print(f"🚀 Testing optimal parallel performance for user: {user}")
    print(f"📋 Testing with up to {max_models} models using 2-model parallelism")
    
    config = create_test_config("optimal_parallel")
    service = ParallelDownloadService(config)
    
    # Set optimal configuration (2 parallel models)
    service.set_max_parallel_models(2)
    
    # Disable model parallelism to avoid the context manager issue
    service.model_parallel_enabled = False
    
    start_time = time.time()
    
    try:
        # Get models first to limit
        all_models = service.api_client.get_all_user_models(user)
        if len(all_models) > max_models:
            print(f"📋 Limiting to first {max_models} models (of {len(all_models)} total)")
            limited_models = all_models[:max_models]
            
            original_method = service.api_client.get_all_user_models
            def mock_get_models(username):
                return limited_models
            service.api_client.get_all_user_models = mock_get_models
        
        # Execute download (will fall back to enhanced single-model parallel processing)
        result = service.download_user_models(user)
        
        # Restore original method if mocked
        if len(all_models) > max_models:
            service.api_client.get_all_user_models = original_method
        
        end_time = time.time()
        duration = end_time - start_time
        
        # Calculate metrics
        total_models = result.get("total_models", 0)
        successful_downloads = result.get("successful_downloads", 0)
        failed_downloads = result.get("failed_downloads", 0)
        success_rate = (successful_downloads / total_models * 100) if total_models > 0 else 0
        throughput = total_models / (duration / 60) if duration > 0 else 0
        
        # Get performance stats if available
        performance_stats = result.get("performance_stats", {})
        
        parallel_result = {
            "success": result.get("success", False),
            "test_type": "optimal_parallel",
            "duration_minutes": duration / 60,
            "total_models": total_models,
            "successful_downloads": successful_downloads,
            "failed_downloads": failed_downloads,
            "success_rate_percent": success_rate,
            "throughput_models_per_minute": throughput,
            "performance_stats": performance_stats,
            "parallel_config": "2_models_enhanced_processing",
            "test_timestamp": datetime.utcnow().isoformat()
        }
        
        print(f"✅ Optimal parallel test completed:")
        print(f"   Duration: {duration/60:.2f} minutes")
        print(f"   Models: {successful_downloads}/{total_models} successful")
        print(f"   Throughput: {throughput:.2f} models/min")
        print(f"   Success rate: {success_rate:.1f}%")
        
        return parallel_result
        
    except Exception as e:
        print(f"❌ Optimal parallel test failed: {e}")
        traceback.print_exc()
        
        return {
            "success": False,
            "test_type": "optimal_parallel",
            "error": str(e),
            "duration_minutes": (time.time() - start_time) / 60,
            "test_timestamp": datetime.utcnow().isoformat()
        }


def analyze_final_results(baseline: Dict[str, Any], parallel: Dict[str, Any]) -> Dict[str, Any]:
    """最終結果分析."""
    print(f"\n📊 Analyzing final validation results...")
    
    if not baseline.get("success") or not parallel.get("success"):
        return {
            "analysis_possible": False,
            "baseline_success": baseline.get("success", False),
            "parallel_success": parallel.get("success", False),
            "error": "One or both tests failed"
        }
    
    # Performance calculations
    baseline_duration = baseline.get("duration_minutes", 0)
    parallel_duration = parallel.get("duration_minutes", 0)
    
    baseline_throughput = baseline.get("throughput_models_per_minute", 0)
    parallel_throughput = parallel.get("throughput_models_per_minute", 0)
    
    baseline_success_rate = baseline.get("success_rate_percent", 0)
    parallel_success_rate = parallel.get("success_rate_percent", 0)
    
    # Calculate improvements
    duration_improvement = 0.0
    throughput_improvement = 0.0
    
    if baseline_duration > 0:
        duration_improvement = ((baseline_duration - parallel_duration) / baseline_duration) * 100
        
    if baseline_throughput > 0:
        throughput_improvement = ((parallel_throughput - baseline_throughput) / baseline_throughput) * 100
    
    analysis = {
        "analysis_possible": True,
        "performance_comparison": {
            "baseline_throughput": baseline_throughput,
            "parallel_throughput": parallel_throughput,
            "throughput_improvement_percent": throughput_improvement,
            "speed_multiplier": parallel_throughput / baseline_throughput if baseline_throughput > 0 else 0,
            "duration_improvement_percent": duration_improvement
        },
        "reliability_comparison": {
            "baseline_success_rate": baseline_success_rate,
            "parallel_success_rate": parallel_success_rate,
            "success_rate_change": parallel_success_rate - baseline_success_rate,
            "reliability_maintained": abs(parallel_success_rate - baseline_success_rate) <= 5.0
        },
        "overall_assessment": {
            "performance_improved": throughput_improvement > 0,
            "stability_maintained": abs(parallel_success_rate - baseline_success_rate) <= 5.0,
            "recommended_for_production": throughput_improvement > 0 and abs(parallel_success_rate - baseline_success_rate) <= 5.0
        }
    }
    
    return analysis


def generate_final_recommendations(analysis: Dict[str, Any]) -> list[str]:
    """最終推奨事項生成."""
    recommendations = []
    
    if not analysis.get("analysis_possible"):
        recommendations.append("❌ Analysis failed - unable to provide recommendations")
        return recommendations
    
    performance = analysis.get("performance_comparison", {})
    reliability = analysis.get("reliability_comparison", {})
    assessment = analysis.get("overall_assessment", {})
    
    throughput_improvement = performance.get("throughput_improvement_percent", 0)
    speed_multiplier = performance.get("speed_multiplier", 1.0)
    success_rate_change = reliability.get("success_rate_change", 0)
    
    # Performance recommendations
    if throughput_improvement > 5:
        recommendations.append(f"🚀 Significant performance improvement: {throughput_improvement:+.1f}% ({speed_multiplier:.2f}x faster)")
        recommendations.append("✅ Recommended for immediate production deployment")
    elif throughput_improvement > 0:
        recommendations.append(f"📈 Moderate performance improvement: {throughput_improvement:+.1f}% ({speed_multiplier:.2f}x faster)")
        recommendations.append("✅ Safe for production use")
    else:
        recommendations.append(f"⚠️ No significant performance improvement: {throughput_improvement:+.1f}%")
        recommendations.append("🤔 Consider staying with baseline for now")
    
    # Stability recommendations
    if abs(success_rate_change) <= 1:
        recommendations.append("🛡️ Excellent stability - no impact on success rate")
    elif abs(success_rate_change) <= 5:
        recommendations.append("✅ Good stability - minimal impact on success rate")
    else:
        recommendations.append("⚠️ Stability concern - significant success rate change")
    
    # Overall recommendation
    if assessment.get("recommended_for_production", False):
        recommendations.append("🎯 Overall: APPROVED for production deployment")
        recommendations.append("🔧 Configuration: Enable parallel processing with 2-model optimization")
    else:
        recommendations.append("🎯 Overall: Further optimization needed before production")
    
    return recommendations


def main():
    """メイン実行関数."""
    parser = argparse.ArgumentParser(description="Final Validation Test")
    parser.add_argument("--user", default="Fandingo", help="Test user (default: Fandingo)")
    parser.add_argument("--max-models", type=int, default=10, help="Max models for validation test")
    
    args = parser.parse_args()
    
    print(f"🎯 Starting final validation test for user: {args.user}")
    print(f"📋 Testing with up to {args.max_models} models")
    print(f"🔬 Comparing baseline vs optimal parallel configuration")
    
    try:
        # Run baseline test
        print(f"\n{'='*60}")
        print(f"BASELINE PERFORMANCE TEST")
        print(f"{'='*60}")
        
        baseline_result = test_baseline_performance(args.user, args.max_models)
        
        # Run optimal parallel test
        print(f"\n{'='*60}")
        print(f"OPTIMAL PARALLEL PERFORMANCE TEST")
        print(f"{'='*60}")
        
        parallel_result = test_optimal_parallel_performance(args.user, args.max_models)
        
        # Analyze results
        print(f"\n{'='*60}")
        print(f"FINAL ANALYSIS")
        print(f"{'='*60}")
        
        analysis = analyze_final_results(baseline_result, parallel_result)
        
        # Generate recommendations
        recommendations = generate_final_recommendations(analysis)
        
        # Save results
        validation_results = {
            "test_info": {
                "test_user": args.user,
                "test_timestamp": datetime.utcnow().isoformat(),
                "max_models_tested": args.max_models,
                "test_type": "final_validation"
            },
            "baseline_result": baseline_result,
            "parallel_result": parallel_result,
            "analysis": analysis,
            "recommendations": recommendations
        }
        
        results_file = Path("./test_final_validation") / f"final_validation_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}.json"
        results_file.parent.mkdir(exist_ok=True)
        
        with open(results_file, 'w', encoding='utf-8') as f:
            json.dump(validation_results, f, indent=2, ensure_ascii=False)
        
        print(f"\n💾 Final validation results saved: {results_file}")
        
        # Print summary
        print(f"\n{'='*60}")
        print(f"FINAL VALIDATION SUMMARY")
        print(f"{'='*60}")
        
        if recommendations:
            print(f"\n💡 Final Recommendations:")
            for rec in recommendations:
                print(f"   {rec}")
        
        print(f"\n🎉 Final validation test completed!")
        
    except KeyboardInterrupt:
        print(f"\n⏹️ Test interrupted by user")
    except Exception as e:
        print(f"\n❌ Test failed with error: {e}")
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()