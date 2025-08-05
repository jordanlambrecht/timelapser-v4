#!/usr/bin/env python3
"""
Database Performance Analysis Script

Run comprehensive performance analysis on the database operations
to identify bottlenecks and optimization opportunities.
"""

import asyncio
import json
import sys
from pathlib import Path


from app.database.core import AsyncDatabase
from app.enums import LoggerName
from app.services.logger import get_service_logger
from app.utils.database_performance_profiler import DatabasePerformanceProfiler

# Add backend to path
sys.path.insert(0, str(Path(__file__).parent.parent))
logger = get_service_logger(LoggerName.TEST)


async def main():
    """Run comprehensive database performance analysis."""
    print("=" * 80)
    print("DATABASE PERFORMANCE ANALYSIS")
    print("=" * 80)

    # Initialize database
    db = AsyncDatabase()
    try:
        await db.initialize()
        print("✅ Database connection established")

        # Initialize profiler
        profiler = DatabasePerformanceProfiler(db)
        print("✅ Performance profiler initialized")

        # Run comprehensive profiling
        print("\n🔍 Running comprehensive performance analysis...")
        results = await profiler.run_comprehensive_profile()

        # Display results
        print("\n" + "=" * 80)
        print("PERFORMANCE ANALYSIS RESULTS")
        print("=" * 80)

        # Profile summary
        summary = results["profile_summary"]
        print("\n📊 Profile Summary:")
        print(f"   Timestamp: {summary['timestamp']}")
        print(f"   Total Analysis Time: {summary['total_profile_time_seconds']}s")
        print(f"   Categories Analyzed: {', '.join(summary['categories_analyzed'])}")

        # Camera operations
        print("\n🎥 Camera Operations Analysis:")
        camera_ops = results["camera_operations"]
        for operation, data in camera_ops.items():
            metrics = data["metrics"]
            print(f"   {operation}:")
            print(
                f"     ⏱️  Execution Time: {metrics.get('execution_time_ms', 0):.2f}ms"
            )
            print(f"     📝 Memory Usage: {metrics.get('memory_usage_mb', 0):.2f}MB")
            if "result_count" in data:
                print(f"     📊 Results: {data['result_count']} records")
            print("     💡 Recommendations:")
            for rec in data["recommendations"]:
                print(f"        • {rec}")

        # Image operations
        print("\n🖼️  Image Operations Analysis:")
        image_ops = results["image_operations"]
        for operation, data in image_ops.items():
            metrics = data["metrics"]
            print(f"   {operation}:")
            print(
                f"     ⏱️  Execution Time: {metrics.get('execution_time_ms', 0):.2f}ms"
            )
            print(f"     📝 Memory Usage: {metrics.get('memory_usage_mb', 0):.2f}MB")
            if "result_count" in data:
                print(f"     📊 Results: {data['result_count']} records")
            print("     💡 Recommendations:")
            for rec in data["recommendations"]:
                print(f"        • {rec}")

        # Settings operations
        print("\n⚙️  Settings Operations Analysis:")
        settings_ops = results["settings_operations"]
        for operation, data in settings_ops.items():
            metrics = data["metrics"]
            print(f"   {operation}:")
            print(
                f"     ⏱️  Execution Time: {metrics.get('execution_time_ms', 0):.2f}ms"
            )
            print(f"     📝 Memory Usage: {metrics.get('memory_usage_mb', 0):.2f}MB")
            if "settings_count" in data:
                print(f"     📊 Settings: {data['settings_count']} items")
            print("     💡 Recommendations:")
            for rec in data["recommendations"]:
                print(f"        • {rec}")

        # Connection pool analysis
        print("\n🔗 Connection Pool Analysis:")
        pool_data = results["connection_pool"]
        pool_stats = pool_data["pool_stats"]
        conn_perf = pool_data["connection_performance"]

        print(f"   Pool Status: {pool_stats.get('status', 'unknown')}")
        print(f"   Success Rate: {pool_stats.get('success_rate', 0):.1f}%")
        print("   Connection Performance:")
        print(f"     ⏱️  Average: {conn_perf['average_time_ms']}ms")
        print(f"     ⏱️  Max: {conn_perf['max_time_ms']}ms")
        print(f"     ⏱️  Min: {conn_perf['min_time_ms']}ms")
        print("   💡 Recommendations:")
        for rec in pool_data["recommendations"]:
            print(f"      • {rec}")

        # Overall recommendations
        print("\n🎯 Overall Recommendations:")
        for rec in results["overall_recommendations"]:
            print(f"   • {rec}")

        # Benchmark summary
        print("\n📈 Performance Benchmarks:")
        bench_summary = results["performance_benchmarks"]
        if bench_summary.get("total_operations", 0) > 0:
            print(f"   Total Operations: {bench_summary['total_operations']}")
            print(
                f"   Average Execution Time: {bench_summary.get('average_execution_time_ms', 0):.2f}ms"
            )
            print(
                f"   Total Memory Used: {bench_summary.get('total_memory_mb', 0):.2f}MB"
            )

        # Save detailed results to file
        output_file = Path(__file__).parent / "performance_analysis_results.json"
        with open(output_file, "w") as f:
            json.dump(results, f, indent=2, default=str)
        print(f"\n💾 Detailed results saved to: {output_file}")

        print("\n" + "=" * 80)
        print("ANALYSIS COMPLETE")
        print("=" * 80)

    except Exception as e:
        logger.error(f"Performance analysis failed: {e}")
        print(f"❌ Analysis failed: {e}")
        return 1
    finally:
        await db.close()
        print("✅ Database connection closed")

    return 0


if __name__ == "__main__":
    exit(asyncio.run(main()))
