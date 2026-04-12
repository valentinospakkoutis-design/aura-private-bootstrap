import asyncio
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from scheduler.cron_tasks import (
    task_fetch_news,
    task_weekly_retrain,
    task_fear_greed_update,
    task_monthly_rl_retrain,
)

TASK_MAP = {
    "fetch_news": task_fetch_news,
    "weekly_retrain": task_weekly_retrain,
    "fear_greed": task_fear_greed_update,
    "monthly_rl": task_monthly_rl_retrain,
}


if __name__ == "__main__":
    task_name = sys.argv[1] if len(sys.argv) > 1 else None
    if task_name not in TASK_MAP:
        print(f"Unknown task: {task_name}. Available: {list(TASK_MAP.keys())}")
        sys.exit(1)
    asyncio.run(TASK_MAP[task_name]())
