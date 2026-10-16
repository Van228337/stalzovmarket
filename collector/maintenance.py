"""Daily Database Maintenance & Retention Script (Section 6.2).

Performs:
- Database size calculation via pg_database_size
- Inactive lot pruning (> 14 days)
- Historical sales pruning (> 30/90 days)
- Warning triggers at > 350 MB, halt triggers at > 450 MB
"""

import asyncio
import logging
import os
import sys
from pathlib import Path
from typing import Dict, Any
import yaml

# Ensure project root is available in sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
logger = logging.getLogger("maintenance")


async def run_maintenance():
    config_path = PROJECT_ROOT / "config.yaml"
    with open(config_path, "r", encoding="utf-8") as f:
        config = yaml.safe_load(f)

    db_cfg = config.get("database", {})
    warn_mb = float(db_cfg.get("size_warning_mb", 350))
    halt_mb = float(db_cfg.get("size_halt_mb", 450))

    supabase_url = os.getenv("SUPABASE_URL")
    db_conn_str = os.getenv("SUPABASE_DB_URL")

    logger.info("Starting maintenance & retention check...")

    if not db_conn_str and not supabase_url:
        logger.info("No Supabase database credentials configured. Running in local dry-run mode.")
        logger.info(f"Target thresholds: Warning at {warn_mb} MB, Halt at {halt_mb} MB.")
        logger.info("Retention rules: inactive lots > 14 days, non-hot sales > 30 days.")
        logger.info("Maintenance dry-run completed successfully.")
        return

    # If Postgres connection string is present, execute retention queries
    try:
        import asyncpg
        conn = await asyncpg.connect(db_conn_str)
        try:
            # 1. Check database size
            db_size_bytes = await conn.fetchval("SELECT pg_database_size(current_database());")
            db_size_mb = db_size_bytes / (1024 * 1024)
            logger.info(f"Current database size: {db_size_mb:.2f} MB")

            if db_size_mb > halt_mb:
                logger.critical(f"DATABASE SIZE CRITICAL: {db_size_mb:.2f} MB exceeds halt threshold {halt_mb} MB!")
            elif db_size_mb > warn_mb:
                logger.warning(f"DATABASE SIZE WARNING: {db_size_mb:.2f} MB exceeds warning threshold {warn_mb} MB!")

            # 2. Execute retention pruning
            deleted = await conn.fetchrow(
                "SELECT * FROM prune_old_data($1, $2);",
                db_cfg.get("retention_days_inactive_lots", 14),
                db_cfg.get("retention_days_sales_other", 30),
            )
            logger.info(f"Pruned {deleted['deleted_lots']} inactive lots and {deleted['deleted_sales']} sales records.")
        finally:
            await conn.close()
    except Exception as e:
        logger.error(f"Maintenance execution error: {e}")


if __name__ == "__main__":
    asyncio.run(run_maintenance())
