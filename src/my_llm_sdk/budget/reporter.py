from typing import List, Dict, Any, Literal
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
import json
from .ledger import Ledger

@dataclass
class TodaySummary:
    total_cost: float
    request_count: int
    total_tokens: int
    error_rate: float

@dataclass
class DailyTrend:
    day: str
    cost: float
    tokens: int
    reqs: int

@dataclass
class TopConsumer:
    key: str
    cost: float
    reqs: int

@dataclass
class HealthReport:
    total_reqs: int
    error_rate: float
    p50_total_ms: float
    p95_total_ms: float

@dataclass
class HealthMetrics:
    total_reqs: int
    error_rate: float
    avg_latency: float
    breaker_open: bool = False

class Reporter:
    def __init__(self, ledger: Ledger):
        self.ledger = ledger
        
    def _get_conn(self):
        # Access internal ledger connection method
        return self.ledger._get_conn()

    def today_summary(self) -> TodaySummary:
        """Get summary for today (local time)."""
        with self._get_conn() as conn:
            # Note: 'localtime' modifier in SQLite uses system time
            row = conn.execute("""
                WITH base AS (
                    SELECT
                        date(ts_start/1000, 'unixepoch', 'localtime') AS day_key,
                        cost_usd,
                        COALESCE(input_tokens,0) + COALESCE(output_tokens,0) AS tokens,
                        status
                    FROM request_facts
                )
                SELECT
                    SUM(COALESCE(cost_usd, 0)) AS total_cost,
                    COUNT(*) AS request_count,
                    SUM(tokens) AS total_tokens,
                    SUM(CASE WHEN status='error' THEN 1 ELSE 0 END) * 1.0 / COUNT(*) AS error_rate
                FROM base
                WHERE day_key = date('now', 'localtime')
            """).fetchone()

            if not row or row[1] == 0:
                return TodaySummary(0.0, 0, 0, 0.0)

            return TodaySummary(
                total_cost=row[0] or 0.0,
                request_count=row[1],
                total_tokens=row[2] or 0,
                error_rate=row[3] or 0.0
            )

    def daily_trend(self, days: int = 7) -> List[DailyTrend]:
        """Get daily trend for last N days."""
        with self._get_conn() as conn:
            cursor = conn.execute("""
                WITH base AS (
                  SELECT
                    date(ts_start/1000, 'unixepoch', 'localtime') AS day_key,
                    cost_usd,
                    COALESCE(input_tokens,0) + COALESCE(output_tokens,0) AS tokens
                  FROM request_facts
                  WHERE ts_start >= (strftime('%s','now') - ? * 86400) * 1000
                )
                SELECT
                  day_key,
                  SUM(COALESCE(cost_usd, 0)) AS cost,
                  SUM(tokens) AS tokens,
                  COUNT(*) AS reqs
                FROM base
                GROUP BY day_key
                ORDER BY day_key ASC;
            """, (days,))
            
            return [
                DailyTrend(day=r[0], cost=r[1] or 0.0, tokens=r[2] or 0, reqs=r[3])
                for r in cursor.fetchall()
            ]

    def top_consumers(self, by: Literal["provider", "model"], days: int = 7) -> List[TopConsumer]:
        """Get top 5 consumers by cost."""
        column = "provider" if by == "provider" else "model"
        # Validate column name against injection (Literal helps, but good practice)
        if column not in ["provider", "model"]:
            raise ValueError("Invalid dimension")

        with self._get_conn() as conn:
            cursor = conn.execute(f"""
                SELECT
                  {column} AS dim,
                  SUM(COALESCE(cost_usd, 0)) AS cost,
                  COUNT(*) AS reqs
                FROM request_facts
                WHERE ts_start >= (strftime('%s','now') - ? * 86400) * 1000
                GROUP BY dim
                ORDER BY cost DESC
                LIMIT 5;
            """, (days,))
            
            return [
                TopConsumer(key=r[0], cost=r[1] or 0.0, reqs=r[2])
                for r in cursor.fetchall()
            ]
            
    def health_check(self, days: int = 7) -> HealthReport:
        """Get health metrics (Error Rate, Latency P50/P95)."""
        with self._get_conn() as conn:
            # 1. Basic Stats
            basics = conn.execute("""
                SELECT COUNT(*), SUM(CASE WHEN status='error' THEN 1 ELSE 0 END)
                FROM request_facts
                WHERE ts_start >= (strftime('%s','now') - ? * 86400) * 1000
            """, (days,)).fetchone()
            
            total = basics[0]
            if not total:
                return HealthReport(0, 0.0, 0.0, 0.0)
                
            error_rate = basics[1] / total
            
            # 2. Latency Percentiles (Approx via Sort)
            def get_percentile(p: float):
                # P is 0.0 to 1.0 (e.g. 0.95)
                row = conn.execute("""
                    SELECT total_ms FROM request_facts 
                    WHERE ts_start >= (strftime('%s','now') - ? * 86400) * 1000
                      AND total_ms IS NOT NULL
                    ORDER BY total_ms ASC
                    LIMIT 1 OFFSET (SELECT CAST(COUNT(*)*? AS INT) - 1 FROM request_facts 
                                    WHERE ts_start >= (strftime('%s','now') - ? * 86400) * 1000 
                                      AND total_ms IS NOT NULL)
                """, (days, p, days)).fetchone()
                return row[0] if row else 0.0

            p50 = get_percentile(0.5)
            p95 = get_percentile(0.95)
            
            return HealthReport(total, error_rate, p50, p95)

    def get_health_snapshot(self, window_minutes: int = 5) -> Dict[str, HealthMetrics]:
        """
        Get recent health metrics for ALL providers in the looksback window.
        Returns: Dict[provider_name, HealthMetrics]
        Used by Router to filter healthy providers.
        """
        with self._get_conn() as conn:
            # Group by provider
            cursor = conn.execute("""
                SELECT 
                    provider, 
                    COUNT(*) as total,
                    SUM(CASE WHEN status='error' THEN 1 ELSE 0 END) as errors,
                    AVG(total_ms) as avg_lat
                FROM request_facts
                WHERE ts_start >= (strftime('%s','now') - ? * 60) * 1000
                GROUP BY provider
            """, (window_minutes,))
            
            results = {}
            for row in cursor.fetchall():
                provider = row[0]
                total = row[1]
                errors = row[2]
                avg_lat = row[3] or 0.0
                
                error_rate = errors / total if total > 0 else 0.0
                
                results[provider] = HealthMetrics(
                    total_reqs=total,
                    error_rate=error_rate,
                    avg_latency=avg_lat,
                    breaker_open=False # Logic handled by Router policy
                )
            return results

    def get_cost_snapshot(self, days: int = 7) -> Dict[str, float]:
        """
        Get average cost per request for ALL models.
        Returns: Dict[model_id, avg_cost_usd]
        Used by Router 'LowestCost' strategy.
        """
        with self._get_conn() as conn:
            cursor = conn.execute("""
                SELECT 
                    model,
                    AVG(cost_usd) as avg_cost
                FROM request_facts
                WHERE ts_start >= (strftime('%s','now') - ? * 86400) * 1000
                  AND cost_usd > 0
                GROUP BY model
            """, (days,))
            
            return {row[0]: row[1] for row in cursor.fetchall()}

