# backend/app/utils/micro_optimizations.py
"""
Database Micro-Optimizations

Automated identification and implementation of micro-optimizations
for database operations including query optimization, connection reuse,
and memory management improvements.
"""

import time
from typing import Dict, Any, List, Optional, Callable, Tuple
from datetime import datetime
from .database_helpers import DatabaseConnectionBatcher
from ..database.core import AsyncDatabase


class QueryOptimizer:
    """
    Query optimization utility for identifying and suggesting query improvements.
    """

    @staticmethod
    def analyze_query_plan(
        query: str, params: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Analyze a query's execution plan for optimization opportunities.

        Args:
            query: SQL query to analyze
            params: Query parameters

        Returns:
            Dictionary containing optimization suggestions
        """
        suggestions = []

        # Basic query analysis
        query_lower = query.lower().strip()

        # Check for missing WHERE clauses on large tables
        if "select" in query_lower and "from" in query_lower:
            if (
                "cameras" in query_lower
                or "images" in query_lower
                or "logs" in query_lower
            ):
                if "where" not in query_lower and "limit" not in query_lower:
                    suggestions.append(
                        {
                            "type": "missing_where_clause",
                            "severity": "high",
                            "message": "Query on large table without WHERE clause or LIMIT",
                            "recommendation": "Add WHERE clause or LIMIT to prevent full table scan",
                        }
                    )

        # Check for SELECT * usage
        if "select *" in query_lower:
            suggestions.append(
                {
                    "type": "select_star",
                    "severity": "medium",
                    "message": "Using SELECT * may fetch unnecessary columns",
                    "recommendation": "Specify only needed columns in SELECT clause",
                }
            )

        # Check for missing ORDER BY with LIMIT
        if "limit" in query_lower and "order by" not in query_lower:
            suggestions.append(
                {
                    "type": "limit_without_order",
                    "severity": "medium",
                    "message": "LIMIT without ORDER BY may return inconsistent results",
                    "recommendation": "Add ORDER BY clause for consistent pagination",
                }
            )

        # Check for potential N+1 query pattern indicators
        if query_lower.count("select") > 1:
            suggestions.append(
                {
                    "type": "potential_n_plus_one",
                    "severity": "high",
                    "message": "Multiple SELECT statements may indicate N+1 query pattern",
                    "recommendation": "Consider using JOINs or batch queries",
                }
            )

        # Check for unoptimized JOIN patterns
        if "left join" in query_lower and "on" in query_lower:
            # Look for potential LATERAL JOIN alternatives
            if "lateral" not in query_lower and "correlated" in query_lower:
                suggestions.append(
                    {
                        "type": "suboptimal_join",
                        "severity": "medium",
                        "message": "Correlated subquery might be optimized with different JOIN strategy",
                        "recommendation": "Consider restructuring JOIN or using window functions",
                    }
                )

        return {
            "query": query,
            "analysis_timestamp": datetime.now().isoformat(),
            "suggestions": suggestions,
            "complexity_score": len(suggestions),
        }

    @staticmethod
    def suggest_index_opportunities(
        query: str, table_schema: Dict[str, List[str]]
    ) -> List[Dict[str, Any]]:
        """
        Suggest potential database indexes based on query patterns.

        Args:
            query: SQL query to analyze
            table_schema: Dictionary mapping table names to column lists

        Returns:
            List of index suggestions
        """
        suggestions = []
        query_lower = query.lower()

        # Extract table and column references
        for table_name, columns in table_schema.items():
            if table_name.lower() in query_lower:
                # Check for WHERE clause columns
                for column in columns:
                    if (
                        f"where {column}" in query_lower
                        or f"and {column}" in query_lower
                    ):
                        suggestions.append(
                            {
                                "type": "where_clause_index",
                                "table": table_name,
                                "column": column,
                                "priority": "high",
                                "suggestion": f"Consider index on {table_name}.{column} for WHERE clause optimization",
                            }
                        )

                # Check for ORDER BY columns
                for column in columns:
                    if f"order by {column}" in query_lower:
                        suggestions.append(
                            {
                                "type": "order_by_index",
                                "table": table_name,
                                "column": column,
                                "priority": "medium",
                                "suggestion": f"Consider index on {table_name}.{column} for ORDER BY optimization",
                            }
                        )

        return suggestions


class ConnectionOptimizer:
    """
    Connection and transaction optimization utility.
    """

    def __init__(self, db: AsyncDatabase):
        """Initialize with database instance."""
        self.db = db
        self.connection_metrics = []

    async def analyze_connection_patterns(
        self, operations: List[Callable]
    ) -> Dict[str, Any]:
        """
        Analyze connection usage patterns and suggest optimizations.

        Args:
            operations: List of database operations to analyze

        Returns:
            Analysis results with optimization suggestions
        """
        results = {
            "operation_count": len(operations),
            "connection_reuse_opportunities": [],
            "transaction_optimization": [],
            "batch_opportunities": [],
        }

        # Simulate operations to measure connection overhead
        individual_times = []
        for operation in operations[:5]:  # Limit to first 5 for analysis
            start_time = time.time()
            try:
                await operation()
                execution_time = (time.time() - start_time) * 1000
                individual_times.append(execution_time)
            except Exception as e:
                pass

        # Test batched execution
        if len(operations) > 1:
            batcher = DatabaseConnectionBatcher(self.db)
            batch_operations = []
            for operation in operations[:5]:
                batch_operations.append(
                    {
                        "type": "async_call",
                        "operation": operation,
                        "args": [],
                        "kwargs": {},
                    }
                )

            start_time = time.time()
            try:
                await batcher.execute_batch_async(batch_operations)
                batch_time = (time.time() - start_time) * 1000

                total_individual_time = sum(individual_times)
                if (
                    batch_time < total_individual_time * 0.8
                ):  # 20% improvement threshold
                    results["batch_opportunities"].append(
                        {
                            "individual_total_ms": round(total_individual_time, 2),
                            "batch_total_ms": round(batch_time, 2),
                            "improvement_percent": round(
                                (total_individual_time - batch_time)
                                / total_individual_time
                                * 100,
                                2,
                            ),
                            "recommendation": "Use connection batching for these operations",
                        }
                    )
            except Exception as e:
                pass

        return results


class MemoryOptimizer:
    """
    Memory usage optimization for database operations.
    """

    @staticmethod
    def analyze_result_set_size(
        query: str, estimated_rows: int, avg_row_size_bytes: int
    ) -> Dict[str, Any]:
        """
        Analyze result set size and suggest memory optimizations.

        Args:
            query: SQL query
            estimated_rows: Estimated number of rows in result
            avg_row_size_bytes: Average size per row in bytes

        Returns:
            Memory optimization analysis
        """
        estimated_memory_mb = (estimated_rows * avg_row_size_bytes) / (1024 * 1024)

        suggestions = []

        if estimated_memory_mb > 100:  # 100MB threshold
            suggestions.append(
                {
                    "type": "large_result_set",
                    "severity": "high",
                    "estimated_memory_mb": round(estimated_memory_mb, 2),
                    "recommendation": "Consider pagination or streaming for large result sets",
                }
            )

        if estimated_rows > 10000:
            suggestions.append(
                {
                    "type": "high_row_count",
                    "severity": "medium",
                    "estimated_rows": estimated_rows,
                    "recommendation": "Use LIMIT/OFFSET or cursor-based pagination",
                }
            )

        return {
            "query": query,
            "estimated_memory_mb": round(estimated_memory_mb, 2),
            "estimated_rows": estimated_rows,
            "suggestions": suggestions,
        }


class DatabaseMicroOptimizer:
    """
    Comprehensive micro-optimization engine for database operations.
    """

    def __init__(self, db: AsyncDatabase):
        """Initialize with database instance."""
        self.db = db
        self.query_optimizer = QueryOptimizer()
        self.connection_optimizer = ConnectionOptimizer(db)
        self.memory_optimizer = MemoryOptimizer()

        # Common table schemas for analysis
        self.table_schemas = {
            "cameras": [
                "id",
                "name",
                "rtsp_url",
                "enabled",
                "created_at",
                "updated_at",
            ],
            "images": [
                "id",
                "camera_id",
                "timelapse_id",
                "file_path",
                "captured_at",
                "file_size",
            ],
            "timelapses": ["id", "camera_id", "name", "status", "created_at"],
            "settings": ["id", "key", "value", "created_at", "updated_at"],
            "logs": ["id", "level", "message", "timestamp", "camera_id"],
        }

    async def analyze_operation(
        self, operation_name: str, query: str, estimated_rows: int = 100
    ) -> Dict[str, Any]:
        """
        Perform comprehensive micro-optimization analysis on a database operation.

        Args:
            operation_name: Name of the operation being analyzed
            query: SQL query for the operation
            estimated_rows: Estimated number of rows in result

        Returns:
            Comprehensive optimization analysis
        """
        analysis = {
            "operation_name": operation_name,
            "analysis_timestamp": datetime.now().isoformat(),
            "query_optimization": self.query_optimizer.analyze_query_plan(query),
            "index_suggestions": self.query_optimizer.suggest_index_opportunities(
                query, self.table_schemas
            ),
            "memory_analysis": self.memory_optimizer.analyze_result_set_size(
                query, estimated_rows, 500
            ),  # 500 bytes avg row
            "overall_priority": "medium",
        }

        # Calculate overall priority
        high_priority_issues = sum(
            1
            for suggestion in analysis["query_optimization"]["suggestions"]
            if suggestion.get("severity") == "high"
        )

        if high_priority_issues > 0:
            analysis["overall_priority"] = "high"
        elif len(analysis["index_suggestions"]) > 2:
            analysis["overall_priority"] = "high"

        return analysis

    async def generate_optimization_report(
        self, operations: List[Tuple[str, str, int]]
    ) -> Dict[str, Any]:
        """
        Generate a comprehensive optimization report for multiple operations.

        Args:
            operations: List of tuples (operation_name, query, estimated_rows)

        Returns:
            Comprehensive optimization report
        """
        report = {
            "report_timestamp": datetime.now().isoformat(),
            "operations_analyzed": len(operations),
            "individual_analyses": [],
            "summary": {
                "high_priority_operations": [],
                "quick_wins": [],
                "index_recommendations": [],
                "memory_concerns": [],
            },
        }

        for operation_name, query, estimated_rows in operations:
            analysis = await self.analyze_operation(
                operation_name, query, estimated_rows
            )
            report["individual_analyses"].append(analysis)

            # Categorize findings
            if analysis["overall_priority"] == "high":
                report["summary"]["high_priority_operations"].append(operation_name)

            # Quick wins (easy fixes)
            for suggestion in analysis["query_optimization"]["suggestions"]:
                if suggestion["type"] in ["select_star", "limit_without_order"]:
                    report["summary"]["quick_wins"].append(
                        {
                            "operation": operation_name,
                            "fix": suggestion["recommendation"],
                        }
                    )

            # Index recommendations
            if analysis["index_suggestions"]:
                report["summary"]["index_recommendations"].extend(
                    analysis["index_suggestions"]
                )

            # Memory concerns
            if analysis["memory_analysis"]["estimated_memory_mb"] > 50:
                report["summary"]["memory_concerns"].append(
                    {
                        "operation": operation_name,
                        "estimated_memory_mb": analysis["memory_analysis"][
                            "estimated_memory_mb"
                        ],
                    }
                )

        return report

    def generate_implementation_plan(
        self, optimization_report: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        """
        Generate a prioritized implementation plan for optimizations.

        Args:
            optimization_report: Report from generate_optimization_report

        Returns:
            Prioritized list of optimization tasks
        """
        plan = []

        # High priority fixes first
        for operation in optimization_report["summary"]["high_priority_operations"]:
            plan.append(
                {
                    "priority": 1,
                    "type": "critical_fix",
                    "operation": operation,
                    "description": f"Address critical performance issues in {operation}",
                    "estimated_effort": "high",
                }
            )

        # Quick wins second
        for quick_win in optimization_report["summary"]["quick_wins"]:
            plan.append(
                {
                    "priority": 2,
                    "type": "quick_win",
                    "operation": quick_win["operation"],
                    "description": quick_win["fix"],
                    "estimated_effort": "low",
                }
            )

        # Index optimizations third
        unique_indexes = {}
        for index_rec in optimization_report["summary"]["index_recommendations"]:
            key = f"{index_rec['table']}.{index_rec['column']}"
            if key not in unique_indexes:
                unique_indexes[key] = index_rec
                plan.append(
                    {
                        "priority": 3,
                        "type": "index_optimization",
                        "operation": f"CREATE INDEX on {index_rec['table']}.{index_rec['column']}",
                        "description": index_rec["suggestion"],
                        "estimated_effort": "medium",
                    }
                )

        # Memory optimizations fourth
        for memory_concern in optimization_report["summary"]["memory_concerns"]:
            plan.append(
                {
                    "priority": 4,
                    "type": "memory_optimization",
                    "operation": memory_concern["operation"],
                    "description": f"Optimize memory usage ({memory_concern['estimated_memory_mb']:.2f}MB)",
                    "estimated_effort": "medium",
                }
            )

        return sorted(plan, key=lambda x: x["priority"])


# Global instance
micro_optimizer: Optional[DatabaseMicroOptimizer] = None


def initialize_micro_optimizer(db: AsyncDatabase) -> None:
    """Initialize the global micro-optimizer instance."""
    global micro_optimizer
    micro_optimizer = DatabaseMicroOptimizer(db)


def get_micro_optimizer() -> Optional[DatabaseMicroOptimizer]:
    """Get the global micro-optimizer instance."""
    return micro_optimizer
