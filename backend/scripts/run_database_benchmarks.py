#!/usr/bin/env python3
"""
Database Benchmarking Script

Run comprehensive database benchmarks to measure performance
and validate optimization improvements.
"""

import asyncio
import sys
import json
from pathlib import Path

# Add backend to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.database.core import AsyncDatabase
from backend.app.utils.database_performance_profiler import DatabasePerformanceProfiler
from backend.app.utils.database_micro_optimizations import DatabaseMicroOptimizer
from app.config import settings
from backend.app.services.logger import get_service_logger
from backend.app.enums import LoggerName

logger = get_service_logger(LoggerName.TEST)


async def main():
    """Run comprehensive database benchmarks."""
    print("=" * 80)
    print("DATABASE BENCHMARKING SUITE")
    print("=" * 80)

    # Initialize database
    db = AsyncDatabase()
    try:
        await db.initialize()
        print("✅ Database connection established")

        # Initialize optimization tools
        profiler = DatabasePerformanceProfiler(db)
        optimizer = DatabaseMicroOptimizer(db)
        print("✅ Optimization tools initialized")

        # Run performance profiling
        print("\n🔍 Running performance profiling...")
        performance_results = await profiler.run_comprehensive_profile()

        # Extract common queries for micro-optimization analysis
        common_operations = [
            (
                "get_cameras",
                "SELECT c.*, t.status as timelapse_status FROM cameras c LEFT JOIN timelapses t ON c.id = t.camera_id",
                50,
            ),
            ("get_active_cameras", "SELECT * FROM cameras WHERE enabled = true", 20),
            (
                "get_images_paginated",
                "SELECT * FROM images ORDER BY captured_at DESC LIMIT 50 OFFSET 0",
                50,
            ),
            ("get_all_settings", "SELECT key, value FROM settings ORDER BY key", 100),
            ("get_camera_by_id", "SELECT * FROM cameras WHERE id = %s", 1),
        ]

        print("\n🔧 Running micro-optimization analysis...")
        optimization_report = await optimizer.generate_optimization_report(
            common_operations
        )

        # Generate implementation plan
        implementation_plan = optimizer.generate_implementation_plan(
            optimization_report
        )

        # Display comprehensive results
        print("\n" + "=" * 80)
        print("BENCHMARK RESULTS SUMMARY")
        print("=" * 80)

        # Performance summary
        print(f"\n📊 Performance Summary:")
        camera_ops = performance_results.get("camera_operations", {})
        total_camera_time = sum(
            op_data.get("metrics", {}).get("execution_time_ms", 0)
            for op_data in camera_ops.values()
        )
        print(f"   Total Camera Operations Time: {total_camera_time:.2f}ms")

        pool_perf = performance_results.get("connection_pool", {}).get(
            "connection_performance", {}
        )
        avg_conn_time = pool_perf.get("average_time_ms", 0)
        print(f"   Average Connection Time: {avg_conn_time}ms")

        # Optimization opportunities
        print(f"\n🎯 Optimization Opportunities:")
        high_priority_ops = optimization_report["summary"]["high_priority_operations"]
        quick_wins = optimization_report["summary"]["quick_wins"]
        index_recommendations = optimization_report["summary"]["index_recommendations"]

        print(f"   High Priority Operations: {len(high_priority_ops)}")
        for op in high_priority_ops:
            print(f"     • {op}")

        print(f"   Quick Wins Available: {len(quick_wins)}")
        for win in quick_wins[:3]:  # Show first 3
            print(f"     • {win['operation']}: {win['fix']}")

        print(f"   Index Recommendations: {len(index_recommendations)}")
        unique_indexes = set()
        for idx in index_recommendations[:5]:  # Show first 5
            key = f"{idx['table']}.{idx['column']}"
            if key not in unique_indexes:
                unique_indexes.add(key)
                print(f"     • {idx['suggestion']}")

        # Implementation plan
        print(f"\n📋 Implementation Plan ({len(implementation_plan)} tasks):")
        for i, task in enumerate(implementation_plan[:5], 1):  # Show first 5
            print(f"   {i}. [{task['type'].upper()}] {task['description']}")
            print(f"      Effort: {task['estimated_effort']}")

        # Performance recommendations
        print(f"\n💡 Top Performance Recommendations:")
        overall_recs = performance_results.get("overall_recommendations", [])
        for i, rec in enumerate(overall_recs[:5], 1):
            print(f"   {i}. {rec}")

        # Save results
        results_dir = Path(__file__).parent / "benchmark_results"
        results_dir.mkdir(exist_ok=True)

        # Save performance results
        perf_file = results_dir / "performance_results.json"
        with open(perf_file, "w") as f:
            json.dump(performance_results, f, indent=2, default=str)

        # Save optimization report
        opt_file = results_dir / "optimization_report.json"
        with open(opt_file, "w") as f:
            json.dump(optimization_report, f, indent=2, default=str)

        # Save implementation plan
        plan_file = results_dir / "implementation_plan.json"
        with open(plan_file, "w") as f:
            json.dump(implementation_plan, f, indent=2, default=str)

        print(f"\n💾 Results saved to: {results_dir}")

        # Performance score calculation
        score = 100
        if avg_conn_time > 50:
            score -= 20
        if total_camera_time > 500:
            score -= 20
        if len(high_priority_ops) > 0:
            score -= 15 * len(high_priority_ops)
        if len(quick_wins) > 3:
            score -= 10

        score = max(0, score)  # Ensure score doesn't go negative

        print(f"\n🏆 Overall Performance Score: {score}/100")
        if score >= 90:
            print("   Status: ✅ EXCELLENT - Database performance is optimal")
        elif score >= 70:
            print("   Status: ✅ GOOD - Minor optimizations recommended")
        elif score >= 50:
            print("   Status: ⚠️  FAIR - Several optimizations needed")
        else:
            print("   Status: ❌ POOR - Immediate optimization required")

        print("\n" + "=" * 80)
        print("BENCHMARKING COMPLETE")
        print("=" * 80)

    except Exception as e:
        logger.error(f"Benchmarking failed: {e}")
        print(f"❌ Benchmarking failed: {e}")
        return 1
    finally:
        await db.close()
        print("✅ Database connection closed")

    return 0


if __name__ == "__main__":
    exit(asyncio.run(main()))
