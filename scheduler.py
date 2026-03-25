"""
AI Pulse — Scheduler

Runs pipelines on cron schedules.
Deploy this on a VPS and it keeps running.

Schedules (configured in config/settings.yaml):
  newsletter_cron      — weekly digest (default: Sunday 9am UTC)
  linkedin_draft_cron  — LinkedIn drafts (default: Wednesday 10am UTC, optional)

On-demand commands (don't need the scheduler running):
  python main.py --linkedin    → generate LinkedIn drafts right now
  python main.py --rewrite     → rewrite a post interactively
  python main.py               → run the full newsletter pipeline now
"""

from apscheduler.schedulers.blocking import BlockingScheduler
from apscheduler.triggers.cron import CronTrigger
import yaml
import logging
from pathlib import Path

from main import run_pipeline, run_linkedin_pipeline

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("ai-pulse.scheduler")


def _parse_cron(cron_expr: str) -> CronTrigger:
    """Parse a cron expression string into a CronTrigger."""
    parts = cron_expr.split()
    return CronTrigger(
        minute=parts[0],
        hour=parts[1],
        day=parts[2],
        month=parts[3],
        day_of_week=parts[4],
    )


def start_scheduler():
    """Start the cron scheduler with all configured jobs."""

    config_path = Path(__file__).parent / "config" / "settings.yaml"
    with open(config_path, "r") as f:
        config = yaml.safe_load(f)

    schedule_config = config.get("schedule", {})

    scheduler = BlockingScheduler()

    # ── Newsletter job (always on) ─────────────────────────
    newsletter_cron = schedule_config.get("newsletter_cron", "0 9 * * 0")
    scheduler.add_job(
        run_pipeline,
        _parse_cron(newsletter_cron),
        id="newsletter",
        name="AI Pulse Newsletter",
    )
    logger.info(f"Newsletter job scheduled: {newsletter_cron}")

    # ── LinkedIn drafts job (optional — only if cron is set) ─
    linkedin_cron = schedule_config.get("linkedin_draft_cron")
    if linkedin_cron:
        scheduler.add_job(
            run_linkedin_pipeline,
            _parse_cron(linkedin_cron),
            id="linkedin_drafts",
            name="AI Pulse LinkedIn Drafts",
        )
        logger.info(f"LinkedIn drafts job scheduled: {linkedin_cron}")
    else:
        logger.info("LinkedIn drafts: no cron set — run on demand with: python main.py --linkedin")

    logger.info("Scheduler started. Press Ctrl+C to stop.")
    logger.info("Tip: python main.py --linkedin   → generate LinkedIn drafts right now")
    logger.info("Tip: python main.py --rewrite    → rewrite a post interactively")

    try:
        scheduler.start()
    except (KeyboardInterrupt, SystemExit):
        logger.info("Scheduler stopped.")


if __name__ == "__main__":
    start_scheduler()
