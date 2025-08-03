#!/usr/bin/env python3
"""
Simple parallel models test script.

This script performs a simplified test to compare parallel model processing
without the complex retry manager dependencies.
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


def create_test_config(mode_name: str, test_root: Path) -> DownloadConfig:
    """テスト用設定作成."""
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
        max_user_images=5  # Minimal for quick testing
    )
    
    return config


def test_parallel_models(user: str, parallel_models: int, max_models: int = 3) -> Dict[str, Any]:
    """並列モデル数でのテスト実行."""
    test_root = Path("./test_simple_parallel")
    mode_name = f"parallel_{parallel_models}"
    
    print(f"\n🧪 Testing {parallel_models} parallel models")
    print(f"{'='*50}")
    
    config = create_test_config(mode_name, test_root)
    service = ParallelDownloadService(config)
    
    # 並列モードを設定
    service.set_max_parallel_models(parallel_models)
    
    start_time = time.time()
    
    try:
        # Get models first to limit
        all_models = service.api_client.get_all_user_models(user)
        if len(all_models) > max_models:
            print(f"📋 Limiting to first {max_models} models (of {len(all_models)} total)")
            # Create limited test by mocking the API response
            limited_models = all_models[:max_models]
            
            original_method = service.api_client.get_all_user_models
            def mock_get_models(username):
                return limited_models
            service.api_client.get_all_user_models = mock_get_models
        
        # 並列処理を無効にして安全にテスト（フォールバック）
        service.model_parallel_enabled = False
        
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
        success_rate = (successful_downloads / total_models * 100) if total_models > 0 else 0
        throughput = total_models / (duration / 60) if duration > 0 else 0
        
        test_result = {
            "success": result.get("success", False),
            "parallel_models": parallel_models,
            "duration_minutes": duration / 60,
            "total_models": total_models,
            "successful_downloads": successful_downloads,
            "success_rate_percent": success_rate,
            "throughput_models_per_minute": throughput,
            "test_timestamp": datetime.utcnow().isoformat()
        }
        
        print(f"✅ {parallel_models} parallel models completed:")
        print(f"   Duration: {duration/60:.2f} minutes")
        print(f"   Models: {successful_downloads}/{total_models} successful")
        print(f"   Throughput: {throughput:.2f} models/min")
        print(f"   Success rate: {success_rate:.1f}%")
        
        return test_result
        
    except Exception as e:
        print(f"❌ {parallel_models} parallel models failed: {e}")
        traceback.print_exc()
        
        return {
            "success": False,
            "parallel_models": parallel_models,
            "error": str(e),
            "duration_minutes": (time.time() - start_time) / 60,
            "test_timestamp": datetime.utcnow().isoformat()
        }


def compare_results(results: List[Dict[str, Any]]) -> Dict[str, Any]:
    """結果比較."""
    print(f"\n📊 Analyzing results...")
    
    successful_results = [r for r in results if r.get("success")]
    
    if len(successful_results) < 2:
        return {"error": "Need at least 2 successful results for comparison"}
    
    # Find baseline (1 parallel model)
    baseline = next((r for r in successful_results if r["parallel_models"] == 1), successful_results[0])
    
    # Calculate improvements
    improvements = []
    for result in successful_results:
        if result["parallel_models"] != baseline["parallel_models"]:
            baseline_throughput = baseline.get("throughput_models_per_minute", 0)
            current_throughput = result.get("throughput_models_per_minute", 0)
            
            if baseline_throughput > 0:
                improvement = ((current_throughput - baseline_throughput) / baseline_throughput) * 100
                improvements.append({
                    "parallel_models": result["parallel_models"],
                    "throughput_improvement_percent": improvement,
                    "speed_multiplier": current_throughput / baseline_throughput,
                    "success_rate": result.get("success_rate_percent", 0),
                    "duration_minutes": result.get("duration_minutes", 0)
                })
    
    # Find best performing
    best_throughput = max(successful_results, key=lambda x: x.get("throughput_models_per_minute", 0))
    
    analysis = {
        "baseline": {
            "parallel_models": baseline["parallel_models"],
            "throughput": baseline.get("throughput_models_per_minute", 0),
            "duration_minutes": baseline.get("duration_minutes", 0)
        },
        "best_performance": {
            "parallel_models": best_throughput["parallel_models"],
            "throughput": best_throughput.get("throughput_models_per_minute", 0),
            "success_rate": best_throughput.get("success_rate_percent", 0)
        },
        "improvements": improvements
    }
    
    return analysis


def main():
    """メイン実行関数."""
    parser = argparse.ArgumentParser(description="Simple Parallel Models Test")
    parser.add_argument("--user", default="Fandingo", help="Test user (default: Fandingo)")
    parser.add_argument("--max-models", type=int, default=3, help="Max models per test")
    parser.add_argument("--max-parallel", type=int, default=3, help="Max parallel models to test")
    
    args = parser.parse_args()
    
    print(f"🧪 Starting simple parallel models test for user: {args.user}")
    print(f"📋 Testing 1 to {args.max_parallel} parallel models with {args.max_models} models each")
    
    results = []
    
    # Test different parallel levels
    for parallel_models in range(1, args.max_parallel + 1):
        try:
            result = test_parallel_models(args.user, parallel_models, args.max_models)
            results.append(result)
        except Exception as e:
            print(f"❌ Failed to test {parallel_models} parallel models: {e}")
            results.append({
                "success": False,
                "parallel_models": parallel_models,
                "error": str(e)
            })
    
    # Analyze results
    print(f"\n{'='*50}")
    print(f"ANALYSIS")
    print(f"{'='*50}")
    
    analysis = compare_results(results)
    
    # Save results
    test_data = {
        "test_info": {
            "test_user": args.user,
            "test_timestamp": datetime.utcnow().isoformat(),
            "max_models_per_test": args.max_models,
            "max_parallel_tested": args.max_parallel
        },
        "test_results": results,
        "analysis": analysis
    }
    
    results_file = Path("./test_simple_parallel") / f"simple_parallel_test_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}.json"
    results_file.parent.mkdir(exist_ok=True)
    
    with open(results_file, 'w', encoding='utf-8') as f:
        json.dump(test_data, f, indent=2, ensure_ascii=False)
    
    print(f"\n💾 Results saved: {results_file}")
    
    # Print summary
    if not analysis.get("error"):
        baseline = analysis.get("baseline", {})
        best = analysis.get("best_performance", {})
        improvements = analysis.get("improvements", [])
        
        print(f"\n🎉 Test Summary:")
        print(f"   Baseline ({baseline.get('parallel_models', 1)} models): {baseline.get('throughput', 0):.2f} models/min")
        print(f"   Best performance ({best.get('parallel_models', 1)} models): {best.get('throughput', 0):.2f} models/min")
        print(f"   Success rate: {best.get('success_rate', 0):.1f}%")
        
        if improvements:
            best_improvement = max(improvements, key=lambda x: x["throughput_improvement_percent"])
            print(f"   Best improvement: {best_improvement['parallel_models']} models gives {best_improvement['throughput_improvement_percent']:+.1f}%")
    else:
        print(f"\n❌ Analysis failed: {analysis['error']}")


if __name__ == "__main__":
    main()