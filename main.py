"""
AI Pulse — Main Pipeline (v2)

Flow:
  Collect (Reddit, arXiv, HF, Blogs, Twitter)
  → Filter & Rank  (+ ChromaDB novelty/preference enrichment)
  → Summarize (HuggingFace BART — free)
  → Analyze (Claude Sonnet — the brain, opinions + implications)
  → Deliver (Email + Telegram with 👍/👎 feedback buttons)
  → Store items in ChromaDB for next-run memory

LinkedIn Flow (on-demand):
  python main.py --linkedin          → generate 2 fresh posts from latest stories
  python main.py --rewrite           → rewrite a post interactively with feedback

Feedback webhook:
  python main.py --webhook           → start lightweight HTTP server that receives
                                       Telegram callback queries (👍/👎 taps) and
                                       writes preference scores to ChromaDB

Cost model:
  - Summarization: FREE (HuggingFace Inference API)
  - Analysis: ~$0.10-0.20 per run (Claude Sonnet)
  - LinkedIn drafts: ~$0.02-0.05 per run (OpenAI gpt-4o)
  - Embeddings: FREE (sentence-transformers, runs locally)
  - Memory/ChromaDB: FREE (local persistent storage)
  - Everything else: free
"""

import os
import sys
import yaml
import logging
from pathlib import Path
from dotenv import load_dotenv

from collectors.reddit import RedditCollector
from collectors.arxiv_hf import ArxivCollector, HuggingFaceCollector
from collectors.tech_blogs import TechBlogCollector
from collectors.twitter import TwitterCollector
from processing.filter import filter_and_rank
from processing.hf_summarizer import summarize_all_items
from processing.analyst import generate_analysis
from processing.linkedin_drafter import generate_drafts, rewrite_post, save_drafts_to_file
from delivery.email_sender import send_email
from delivery.telegram_bot import (
    send_telegram,
    send_newsletter_with_feedback,
    send_linkedin_drafts_telegram,
    handle_feedback_update,
)

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("ai-pulse")


def load_config() -> dict:
    config_path = Path(__file__).parent / "config" / "settings.yaml"
    with open(config_path, "r") as f:
        return yaml.safe_load(f)


def run_pipeline():
    """Execute the full pipeline: Collect → Filter → Summarize → Analyze → Deliver"""

    load_dotenv()
    config = load_config()
    topic_tags = config.get("topic_tags", [])

    logger.info("=" * 60)
    logger.info("AI Pulse v2 — Starting pipeline")
    logger.info(f"Topic tags: {', '.join(topic_tags)}")
    logger.info("=" * 60)

    # ══════════════════════════════════════════════════════
    # STEPS 1-3: Collect → Filter → Summarize
    # ══════════════════════════════════════════════════════
    summarized = _collect_and_summarize(config)
    logger.info(f"Summarized: {len(summarized)} items")

    if not summarized:
        logger.warning("No items collected. Check API keys and topic tags.")
        return

    # ══════════════════════════════════════════════════════
    # STEP 4: Analyze with Claude Sonnet (THE BRAIN)
    # ══════════════════════════════════════════════════════
    anthropic_key = os.getenv("ANTHROPIC_API_KEY")
    analysis = None

    if anthropic_key:
        analysis = generate_analysis(summarized, anthropic_key)
        logger.info(f"Analysis complete. Theme: {analysis.get('weekly_theme', 'N/A')}")
    else:
        logger.warning("ANTHROPIC_API_KEY not set — skipping analysis layer")
        analysis = {
            "weekly_theme": "Analysis unavailable (no API key)",
            "analysis_sections": [],
            "connections": "",
            "implications": {},
            "hot_take": "",
            "skills_radar": [],
        }

    # ══════════════════════════════════════════════════════
    # STEP 5: Deliver
    # ══════════════════════════════════════════════════════

    # Email
    smtp_host = os.getenv("SMTP_HOST")
    smtp_user = os.getenv("SMTP_USER")
    smtp_password = os.getenv("SMTP_PASSWORD")
    email_to = os.getenv("EMAIL_TO")

    if all([smtp_host, smtp_user, smtp_password, email_to]):
        send_email(
            newsletter=summarized,
            analysis=analysis,
            smtp_host=smtp_host,
            smtp_port=int(os.getenv("SMTP_PORT", 587)),
            smtp_user=smtp_user,
            smtp_password=smtp_password,
            to_email=email_to,
        )
    else:
        logger.warning("Email: skipped (missing SMTP config)")

    # Telegram — send with 👍/👎 feedback buttons if webhook is configured
    tg_token = os.getenv("TELEGRAM_BOT_TOKEN")
    tg_chat_id = os.getenv("TELEGRAM_CHAT_ID")
    webhook_url = os.getenv("TELEGRAM_WEBHOOK_URL")

    if tg_token and tg_chat_id:
        if webhook_url:
            send_newsletter_with_feedback(
                newsletter=summarized,
                analysis=analysis,
                bot_token=tg_token,
                chat_id=tg_chat_id,
            )
        else:
            send_telegram(
                newsletter=summarized,
                analysis=analysis,
                bot_token=tg_token,
                chat_id=tg_chat_id,
            )
    else:
        logger.warning("Telegram: skipped (missing config)")

    # Store items in ChromaDB for next-run novelty + preference enrichment
    try:
        from memory.chroma_store import store_items
        store_items(summarized)
    except Exception as e:
        logger.warning(f"Memory: store_items skipped — {e}")

    logger.info("=" * 60)
    logger.info("AI Pulse v2 — Pipeline complete")
    logger.info("=" * 60)


def _collect_and_summarize(config: dict) -> list:
    """Shared helper: collect from all sources → filter → summarize. Used by both pipelines."""

    topic_tags = config.get("topic_tags", [])
    max_items = config.get("newsletter", {}).get("max_items", 15)
    all_items = []

    # Reddit
    reddit_config = config.get("sources", {}).get("reddit", {})
    if reddit_config:
        all_items.extend(RedditCollector(reddit_config, topic_tags).collect())

    # arXiv
    arxiv_config = config.get("sources", {}).get("arxiv", {})
    if arxiv_config:
        all_items.extend(ArxivCollector(arxiv_config, topic_tags).collect())

    # HuggingFace
    hf_config = config.get("sources", {}).get("huggingface", {})
    if hf_config and hf_config.get("daily_papers"):
        all_items.extend(HuggingFaceCollector(hf_config, topic_tags).collect())

    # Tech blogs
    blog_config = config.get("sources", {}).get("tech_blogs", {})
    if blog_config and blog_config.get("rss_feeds"):
        all_items.extend(TechBlogCollector(blog_config, topic_tags).collect())

    # Twitter
    twitter_config = config.get("sources", {}).get("twitter", {})
    if twitter_config:
        apify_token = os.getenv("APIFY_API_TOKEN")
        all_items.extend(TwitterCollector(twitter_config, topic_tags, apify_token).collect())

    logger.info(f"Total raw items collected: {len(all_items)}")

    if not all_items:
        return []

    top_items = filter_and_rank(all_items, max_items=max_items)
    hf_token = os.getenv("HF_API_TOKEN")
    summarized = summarize_all_items(top_items, hf_token=hf_token)
    return summarized


def run_linkedin_pipeline():
    """
    LinkedIn draft generation pipeline — runs on demand.
    Collects fresh content → picks best 2 stories → generates posts via OpenAI gpt-4o
    → saves to output/linkedin_drafts_YYYY-MM-DD.md → sends to Telegram.

    Run: python main.py --linkedin
    """

    load_dotenv()
    config = load_config()

    openai_key = os.getenv("OPENAI_API_KEY")
    if not openai_key:
        logger.error("OPENAI_API_KEY not set — LinkedIn pipeline requires OpenAI API key")
        return

    logger.info("=" * 60)
    logger.info("AI Pulse — LinkedIn Draft Pipeline")
    logger.info("=" * 60)

    # Collect + summarize fresh content
    summarized = _collect_and_summarize(config)
    if not summarized:
        logger.warning("No content collected. Check API keys and sources.")
        return

    # Generate LinkedIn drafts via OpenAI gpt-4o
    posts = generate_drafts(summarized, config, openai_key)
    if not posts:
        logger.warning("No drafts generated.")
        return

    logger.info(f"Generated {len(posts)} LinkedIn draft(s)")

    # Save to file
    output_file = save_drafts_to_file(posts)
    logger.info(f"Drafts saved: {output_file}")

    # Send to Telegram
    tg_token = os.getenv("TELEGRAM_BOT_TOKEN")
    tg_chat_id = os.getenv("TELEGRAM_CHAT_ID")
    if tg_token and tg_chat_id:
        send_linkedin_drafts_telegram(posts, tg_token, tg_chat_id)
    else:
        logger.warning("Telegram: skipped (missing config)")

    logger.info("=" * 60)
    logger.info("LinkedIn pipeline complete. Check output/ folder or Telegram.")
    logger.info("=" * 60)


def run_rewrite_mode():
    """
    Interactive rewrite mode.
    Paste a post you liked, give feedback, get a rewritten version.

    Run: python main.py --rewrite
    """

    load_dotenv()
    config = load_config()

    openai_key = os.getenv("OPENAI_API_KEY")
    if not openai_key:
        logger.error("OPENAI_API_KEY not set — rewrite mode requires OpenAI API key")
        return

    print("\n" + "=" * 60)
    print("AI Pulse — LinkedIn Post Rewriter")
    print("=" * 60)
    print("Paste your post below. When done, type END on a new line:")
    print()

    lines = []
    while True:
        line = input()
        if line.strip() == "END":
            break
        lines.append(line)

    original_post = "\n".join(lines).strip()
    if not original_post:
        print("No post provided. Exiting.")
        return

    print("\nWhat do you want to change? (e.g. 'stronger hook', 'shorter', 'add UK angle', 'more technical depth')")
    feedback = input("> ").strip()
    if not feedback:
        print("No feedback provided. Exiting.")
        return

    print("\nRewriting...")
    rewritten = rewrite_post(original_post, feedback, config, openai_key)

    if not rewritten:
        print("Rewrite failed. Check logs.")
        return

    # Save as new file
    posts = [rewritten]
    output_file = save_drafts_to_file(posts)

    print(f"\n{'=' * 60}")
    print(f"REWRITTEN POST ({rewritten.get('word_count', '?')} words)")
    print(f"{'=' * 60}\n")
    print(rewritten.get("content", ""))

    changes = rewritten.get("changes_made", "")
    if changes:
        print(f"\n--- Changes made ---\n{changes}")

    print(f"\nSaved to: {output_file}")

    # Send to Telegram
    tg_token = os.getenv("TELEGRAM_BOT_TOKEN")
    tg_chat_id = os.getenv("TELEGRAM_CHAT_ID")
    if tg_token and tg_chat_id:
        send_linkedin_drafts_telegram(posts, tg_token, tg_chat_id, label="Rewritten Post")
        print("Sent to Telegram.")


def run_webhook_server():
    """
    Lightweight HTTP server that receives Telegram callback queries (👍/👎)
    and writes preference scores to ChromaDB.

    Setup:
      1. Expose this server to the internet (e.g. ngrok, a VPS, or any tunnel)
      2. Set TELEGRAM_WEBHOOK_URL=https://your-domain/webhook in .env
      3. Register the webhook with Telegram once:
           python main.py --set-webhook
      4. Run: python main.py --webhook  (keep this running alongside your scheduler)

    Telegram will POST every update (including callback_query) to /webhook.
    """
    import json
    from http.server import BaseHTTPRequestHandler, HTTPServer

    load_dotenv()
    port = int(os.getenv("WEBHOOK_PORT", 8443))

    class WebhookHandler(BaseHTTPRequestHandler):
        def do_POST(self):
            if self.path != "/webhook":
                self.send_response(404)
                self.end_headers()
                return
            length = int(self.headers.get("Content-Length", 0))
            body = self.rfile.read(length)
            try:
                update = json.loads(body)
                handle_feedback_update(update)
            except Exception as e:
                logger.error(f"Webhook: failed to process update — {e}")
            self.send_response(200)
            self.end_headers()
            self.wfile.write(b"OK")

        def log_message(self, format, *args):  # silence default access logs
            pass

    logger.info(f"Webhook server listening on port {port} at /webhook")
    HTTPServer(("0.0.0.0", port), WebhookHandler).serve_forever()


def set_telegram_webhook():
    """Register the webhook URL with Telegram. Run once after deployment."""
    import requests as req
    load_dotenv()
    token = os.getenv("TELEGRAM_BOT_TOKEN")
    url = os.getenv("TELEGRAM_WEBHOOK_URL")
    if not token or not url:
        logger.error("TELEGRAM_BOT_TOKEN and TELEGRAM_WEBHOOK_URL must be set in .env")
        return
    webhook_endpoint = f"{url.rstrip('/')}/webhook"
    resp = req.post(
        f"https://api.telegram.org/bot{token}/setWebhook",
        json={"url": webhook_endpoint},
    )
    logger.info(f"setWebhook response: {resp.json()}")


if __name__ == "__main__":
    args = sys.argv[1:]

    if "--linkedin" in args:
        run_linkedin_pipeline()
    elif "--rewrite" in args:
        run_rewrite_mode()
    elif "--webhook" in args:
        run_webhook_server()
    elif "--set-webhook" in args:
        set_telegram_webhook()
    else:
        run_pipeline()
