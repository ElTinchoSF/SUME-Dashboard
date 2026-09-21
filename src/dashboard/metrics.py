"""
Lightweight runtime metrics for SUME Dashboard.

Tracks page views, load times, and errors in-memory.
Exposes a health check function for Docker/CI probes.

No external dependencies — uses only stdlib + sqlite3.
"""

import threading
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

from src.dashboard.logging_config import get_logger

logger = get_logger("metrics")


@dataclass
class PageMetrics:
    """Metrics for a single page."""

    views: int = 0
    total_load_ms: float = 0.0
    errors: int = 0
    last_viewed: str = ""

    @property
    def avg_load_ms(self) -> float:
        return self.total_load_ms / self.views if self.views > 0 else 0.0


@dataclass
class DashboardMetrics:
    """Aggregated metrics across all pages."""

    start_time: float = field(default_factory=time.time)
    page_views: dict[str, PageMetrics] = field(default_factory=dict)
    total_errors: int = 0
    db_health_checks: int = 0
    db_health_ok: int = 0

    @property
    def uptime_seconds(self) -> float:
        return time.time() - self.start_time

    @property
    def total_views(self) -> int:
        return sum(p.views for p in self.page_metrics.values())

    @property
    def page_metrics(self) -> dict[str, PageMetrics]:
        return self.page_views


# Global singleton (thread-safe for Streamlit's single-threaded model)
_lock = threading.Lock()
_metrics = DashboardMetrics()


def track_page_view(page_name: str, load_ms: float = 0.0) -> None:
    """Record a page view with optional load time."""
    with _lock:
        if page_name not in _metrics.page_views:
            _metrics.page_views[page_name] = PageMetrics()
        pm = _metrics.page_views[page_name]
        pm.views += 1
        pm.total_load_ms += load_ms
        pm.last_viewed = datetime.now(timezone.utc).isoformat()


def track_error(page_name: str, error: Exception) -> None:
    """Record an error on a page."""
    with _lock:
        _metrics.total_errors += 1
        if page_name not in _metrics.page_views:
            _metrics.page_views[page_name] = PageMetrics()
        _metrics.page_views[page_name].errors += 1
        logger.error("Error on %s: %s", page_name, error)


def record_db_health(healthy: bool) -> None:
    """Record a DB health check result."""
    with _lock:
        _metrics.db_health_checks += 1
        if healthy:
            _metrics.db_health_ok += 1


def get_metrics_summary() -> dict:
    """Return a snapshot of current metrics."""
    with _lock:
        return {
            "uptime_seconds": round(_metrics.uptime_seconds, 1),
            "total_views": _metrics.total_views,
            "total_errors": _metrics.total_errors,
            "db_health_checks": _metrics.db_health_checks,
            "db_health_ok": _metrics.db_health_ok,
            "pages": {
                name: {
                    "views": pm.views,
                    "avg_load_ms": round(pm.avg_load_ms, 1),
                    "errors": pm.errors,
                    "last_viewed": pm.last_viewed,
                }
                for name, pm in _metrics.page_views.items()
            },
        }


def health_check() -> dict:
    """
    Run a quick health check and return status dict.

    Checks:
    1. Python process is alive
    2. Database file exists and is readable
    3. Database responds to query

    Returns:
        Dict with 'status' ('ok' | 'degraded' | 'error') and details.
    """
    result = {
        "status": "ok",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "uptime_seconds": round(_metrics.uptime_seconds, 1),
        "checks": {},
    }

    # Check 1: DB file exists
    try:
        from src.config import get_settings

        settings = get_settings()
        db_path = Path(settings.database.path)
        result["checks"]["db_file"] = {
            "status": "ok" if db_path.exists() else "error",
            "path": str(db_path),
            "exists": db_path.exists(),
            "size_mb": round(db_path.stat().st_size / (1024 * 1024), 2) if db_path.exists() else 0,
        }
    except Exception as e:
        result["checks"]["db_file"] = {"status": "error", "error": str(e)}
        result["status"] = "error"

    # Check 2: DB responds to query
    try:
        from src.database.connection import get_connection

        conn = get_connection()
        cursor = conn.execute("SELECT COUNT(*) FROM expedientes")
        count = cursor.fetchone()[0]
        result["checks"]["db_query"] = {
            "status": "ok",
            "expedientes_count": count,
        }
        record_db_health(True)
    except Exception as e:
        result["checks"]["db_query"] = {"status": "error", "error": str(e)}
        result["status"] = "error"
        record_db_health(False)

    # Check 3: Logs directory writable
    try:
        log_dir = Path("logs")
        log_dir.mkdir(exist_ok=True)
        test_file = log_dir / ".health_check"
        test_file.write_text("ok")
        test_file.unlink()
        result["checks"]["logs_writable"] = {"status": "ok"}
    except Exception as e:
        result["checks"]["logs_writable"] = {"status": "degraded", "error": str(e)}
        if result["status"] == "ok":
            result["status"] = "degraded"

    return result
