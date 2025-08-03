#!/usr/bin/env python3
"""
Minimal Phase 2 test for ultra-fast validation.

This script performs a minimal test with 1 model only to quickly
validate Phase 2 functionality and measure performance improvements.
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


def create_minimal_config(test_mode_suffix: str) -> DownloadConfig:
    """最小限テスト用設定作成."""
    test_root = Path("./test_phase2_minimal")
    test_dir = test_root / f"downloads_{test_mode_suffix}"
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
        max_user_images=5  # Limit user images to 5 for quick test
    )
    
    return config


def test_single_model_baseline(user: str) -> Dict[str, Any]:
    """ベースライン版単一モデルテスト."""
    print(f"🔄 Minimal baseline test for user: {user}")
    
    config = create_minimal_config("baseline")
    service = DownloadService(config)
    
    start_time = time.time()
    
    try:
        # Get first model only
        all_models = service.api_client.get_all_user_models(user)
        if not all_models:
            return {"success": False, "message": f"No models found for {user}"}
            
        test_model = all_models[0]  # Test with first model only
        print(f"📋 Testing with 1 model: {test_model['name']}")
        
        # Download single model
        model_result = service.download_single_model(test_model)
        
        end_time = time.time()
        duration = end_time - start_time
        
        baseline_results = {
            "success": model_result["success"],
            "duration_minutes": duration / 60,
            "model_name": test_model["name"],
            "model_id": test_model["id"],
            "throughput_models_per_minute": 1 / (duration / 60) if duration > 0 else 0,
        }
        
        print(f"✅ Baseline test completed:")
        print(f"   Duration: {duration/60:.2f} minutes")
        print(f"   Model: {test_model['name']}")
        print(f"   Success: {model_result['success']}")
        print(f"   Throughput: {baseline_results['throughput_models_per_minute']:.2f} models/min")
        
        return baseline_results
        
    except Exception as e:
        print(f"❌ Baseline test failed: {e}")
        traceback.print_exc()
        
        return {
            "success": False,
            "error": str(e),
            "duration_minutes": (time.time() - start_time) / 60
        }


def test_single_model_parallel(user: str) -> Dict[str, Any]:
    """並行処理版単一モデルテスト."""
    print(f"🚀 Minimal parallel test for user: {user}")
    
    config = create_minimal_config("parallel")
    service = ParallelDownloadService(config)
    
    start_time = time.time()
    
    try:
        # Get first model only
        all_models = service.api_client.get_all_user_models(user)
        if not all_models:
            return {"success": False, "message": f"No models found for {user}"}
            
        test_model = all_models[0]  # Test with first model only
        print(f"📋 Testing with 1 model: {test_model['name']}")
        
        # Download single model with parallel processing
        model_result = service._download_single_model_parallel(test_model)
        
        end_time = time.time()
        duration = end_time - start_time
        
        # Get performance report
        performance_report = service.get_performance_report()
        concurrency_stats = performance_report.get("concurrency_status", {})
        
        parallel_results = {
            "success": model_result["success"],
            "duration_minutes": duration / 60,
            "model_name": test_model["name"],
            "model_id": test_model["id"],
            "throughput_models_per_minute": 1 / (duration / 60) if duration > 0 else 0,
            "concurrency_mode": concurrency_stats.get("current_mode", "unknown"),
            "fallback_activated": concurrency_stats.get("fallback_active", False),
            "performance_report": performance_report,
        }
        
        print(f"✅ Parallel test completed:")
        print(f"   Duration: {duration/60:.2f} minutes")
        print(f"   Model: {test_model['name']}")  
        print(f"   Success: {model_result['success']}")
        print(f"   Throughput: {parallel_results['throughput_models_per_minute']:.2f} models/min")
        print(f"   Concurrency mode: {parallel_results['concurrency_mode']}")
        
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


def compare_minimal_results(baseline: Dict[str, Any], parallel: Dict[str, Any]) -> Dict[str, Any]:
    """最小限結果比較分析."""
    print(f"\n📊 Analyzing minimal performance comparison...")
    
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
        "concurrency_info": {
            "concurrency_mode_used": parallel.get("concurrency_mode", "unknown"),
            "fallback_activated": parallel.get("fallback_activated", False)
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


def main():
    """メイン実行関数."""
    parser = argparse.ArgumentParser(description="Minimal Phase 2 Performance Test")
    parser.add_argument("--user", default="Fandingo", help="Test user (default: Fandingo)")
    
    args = parser.parse_args()
    
    print(f"🧪 Starting MINIMAL Phase 2 performance test for user: {args.user}")
    print(f"📋 Testing with first model only for ultra-fast validation")
    
    try:
        # Run baseline test
        print(f"\n{'='*40}")
        print(f"BASELINE TEST (Single Model)")
        print(f"{'='*40}")
        
        baseline_results = test_single_model_baseline(args.user)
        
        # Run parallel test
        print(f"\n{'='*40}")
        print(f"PARALLEL TEST (Single Model)")
        print(f"{'='*40}")
        
        parallel_results = test_single_model_parallel(args.user)
        
        # Compare results
        print(f"\n{'='*40}")
        print(f"PERFORMANCE COMPARISON")
        print(f"{'='*40}")
        
        comparison = compare_minimal_results(baseline_results, parallel_results)
        
        # Save results
        results = {
            "test_info": {
                "test_user": args.user,
                "test_type": "minimal_test",
                "test_timestamp": datetime.utcnow().isoformat(),
                "limited_scope": "1 model only, 5 user images"
            },
            "baseline_results": baseline_results,
            "parallel_results": parallel_results,
            "comparison": comparison
        }
        
        results_file = Path("./test_phase2_minimal") / f"minimal_test_results_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}.json"
        results_file.parent.mkdir(exist_ok=True)
        
        with open(results_file, 'w', encoding='utf-8') as f:
            json.dump(results, f, indent=2, ensure_ascii=False)
            
        print(f"\n💾 Minimal test results saved: {results_file}")
        
        # Summary
        if comparison.get("comparison_possible", False):
            improvement = comparison["performance_improvements"]["throughput_improvement_percent"]
            target_met = comparison["goal_achievement"]["target_met"]
            
            print(f"\n🎉 Minimal Test Summary:")
            print(f"   Throughput improvement: {improvement:+.1f}%")
            print(f"   Target (50%+): {'✅ ACHIEVED' if target_met else '❌ NOT ACHIEVED'}")
            
            if target_met:
                print(f"   🚀 Phase 2 shows promising results!")
            else:
                print(f"   ⚠️  Phase 2 needs optimization")
        else:
            print(f"\n❌ Test failed - check error details above")
            
    except KeyboardInterrupt:
        print(f"\n⏹️ Test interrupted by user")
    except Exception as e:
        print(f"\n❌ Test failed with error: {e}")
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()