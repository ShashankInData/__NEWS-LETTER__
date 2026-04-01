"""
AI Pulse — Gradio Dashboard
Runs on HuggingFace Spaces (or locally: python app.py)

Tabs:
  1. Run Pipeline     — collect → rank → summarize → analyze → deliver
  2. LinkedIn Drafts  — generate 2 posts from latest content
  3. Memory Stats     — view ChromaDB preference history
  4. Settings Preview — show active config (no secrets exposed)
"""

import os
import io
import logging
import traceback
from datetime import datetime
from contextlib import redirect_stdout, redirect_stderr
from dotenv import load_dotenv

load_dotenv()

import gradio as gr

# ── logging → string capture ──────────────────────────────────
class _LogCapture(logging.Handler):
    def __init__(self):
        super().__init__()
        self.records = []

    def emit(self, record):
        self.records.append(self.format(record))

    def flush_text(self) -> str:
        out = "\n".join(self.records)
        self.records.clear()
        return out


_log_capture = _LogCapture()
_log_capture.setFormatter(logging.Formatter("%(asctime)s [%(levelname)s] %(name)s: %(message)s", "%H:%M:%S"))
logging.getLogger().addHandler(_log_capture)
logging.getLogger().setLevel(logging.INFO)

logger = logging.getLogger("ai-pulse.ui")


# ── helpers ───────────────────────────────────────────────────

def _env_ok() -> tuple[bool, str]:
    """Check required env vars are present. Returns (ok, message)."""
    missing = []
    for key in ["ANTHROPIC_API_KEY", "OPENAI_API_KEY", "TELEGRAM_BOT_TOKEN", "TELEGRAM_CHAT_ID"]:
        if not os.getenv(key):
            missing.append(key)
    if missing:
        return False, f"Missing env vars: {', '.join(missing)}\nSet them in HF Spaces Secrets or your .env file."
    return True, "All required keys present."


def _format_newsletter_md(items: list, analysis: dict) -> str:
    """Render summarized items + analysis as Markdown for the UI."""
    lines = []

    if analysis:
        theme = analysis.get("weekly_theme", "")
        if theme:
            lines += [f"## {theme}", ""]

        hot_take = analysis.get("hot_take", "")
        if hot_take:
            lines += [f"> **Hot Take:** {hot_take}", ""]

        skills = analysis.get("skills_radar", [])
        if skills:
            lines += [f"**Skills Radar:** {' · '.join(skills)}", ""]

        implications = analysis.get("implications", {})
        for_builders = implications.get("for_builders", "")
        if for_builders:
            lines += [f"**For Builders:** {for_builders}", ""]

        lines += ["---", ""]

    lines += ["## Stories", ""]
    for i, item in enumerate(items, 1):
        title   = item.get("title", "Untitled")
        url     = item.get("url", "")
        source  = item.get("source", "")
        summary = item.get("summary", "")
        tags    = ", ".join(item.get("tags", []))

        lines.append(f"### {i}. [{title}]({url})")
        lines.append(f"*{source}*")
        lines.append(summary)
        if tags:
            lines.append(f"`{tags}`")
        lines.append("")

    return "\n".join(lines)


def _format_drafts_md(posts: list) -> str:
    lines = []
    for i, post in enumerate(posts, 1):
        post_type  = post.get("post_type", "").replace("_", " ").title()
        story      = post.get("story_used", "")
        word_count = post.get("word_count", "?")
        content    = post.get("content", "")
        lines += [
            f"## Post {i} — {post_type}",
            f"*Story: {story} | ~{word_count} words*",
            "",
            content,
            "",
            "---",
            "",
        ]
    return "\n".join(lines)


# ── Tab 1: Run Pipeline ───────────────────────────────────────

def run_pipeline_ui(deliver_email: bool, deliver_telegram: bool, progress=gr.Progress()):
    ok, msg = _env_ok()
    if not ok:
        return msg, ""

    try:
        progress(0.05, desc="Loading config...")
        import yaml
        from pathlib import Path

        config_path = Path(__file__).parent / "config" / "settings.yaml"
        with open(config_path) as f:
            config = yaml.safe_load(f)

        progress(0.1, desc="Collecting content...")
        from main import _collect_and_summarize
        summarized = _collect_and_summarize(config)

        if not summarized:
            return "No items collected. Check API keys and sources.", ""

        progress(0.5, desc="Analysing with Claude Sonnet...")
        from processing.analyst import generate_analysis
        anthropic_key = os.getenv("ANTHROPIC_API_KEY")
        analysis = {}
        if anthropic_key:
            analysis = generate_analysis(summarized, anthropic_key)

        progress(0.7, desc="Delivering...")
        if deliver_telegram:
            tg_token = os.getenv("TELEGRAM_BOT_TOKEN")
            tg_chat_id = os.getenv("TELEGRAM_CHAT_ID")
            webhook_url = os.getenv("TELEGRAM_WEBHOOK_URL")
            if tg_token and tg_chat_id:
                from delivery.telegram_bot import send_telegram, send_newsletter_with_feedback
                if webhook_url:
                    send_newsletter_with_feedback(summarized, analysis, tg_token, tg_chat_id)
                else:
                    send_telegram(summarized, analysis, tg_token, tg_chat_id)

        if deliver_email:
            smtp_host = os.getenv("SMTP_HOST")
            smtp_user = os.getenv("SMTP_USER")
            smtp_pass = os.getenv("SMTP_PASSWORD")
            email_to  = os.getenv("EMAIL_TO")
            if all([smtp_host, smtp_user, smtp_pass, email_to]):
                from delivery.email_sender import send_email
                send_email(
                    newsletter=summarized, analysis=analysis,
                    smtp_host=smtp_host, smtp_port=int(os.getenv("SMTP_PORT", 587)),
                    smtp_user=smtp_user, smtp_password=smtp_pass, to_email=email_to,
                )

        progress(0.9, desc="Storing to memory...")
        try:
            from memory.chroma_store import store_items
            store_items(summarized)
        except Exception:
            pass

        progress(1.0, desc="Done.")
        logs = _log_capture.flush_text()
        digest_md = _format_newsletter_md(summarized, analysis)
        return digest_md, logs

    except Exception as e:
        tb = traceback.format_exc()
        logs = _log_capture.flush_text()
        return f"**Error:** {e}\n\n```\n{tb}\n```", logs


# ── Tab 2: LinkedIn Drafts ─────────────────────────────────────

def run_linkedin_ui(progress=gr.Progress()):
    ok, msg = _env_ok()
    if not ok:
        return msg, ""

    openai_key = os.getenv("OPENAI_API_KEY")
    if not openai_key:
        return "OPENAI_API_KEY not set.", ""

    try:
        progress(0.1, desc="Collecting content...")
        import yaml
        from pathlib import Path

        config_path = Path(__file__).parent / "config" / "settings.yaml"
        with open(config_path) as f:
            config = yaml.safe_load(f)

        from main import _collect_and_summarize
        summarized = _collect_and_summarize(config)

        if not summarized:
            return "No content collected.", ""

        progress(0.6, desc="Generating LinkedIn drafts via GPT-4o...")
        from processing.linkedin_drafter import generate_drafts, save_drafts_to_file
        posts = generate_drafts(summarized, config, openai_key)

        if not posts:
            return "No drafts generated.", _log_capture.flush_text()

        save_drafts_to_file(posts)

        progress(0.9, desc="Sending to Telegram...")
        tg_token = os.getenv("TELEGRAM_BOT_TOKEN")
        tg_chat_id = os.getenv("TELEGRAM_CHAT_ID")
        if tg_token and tg_chat_id:
            from delivery.telegram_bot import send_linkedin_drafts_telegram
            send_linkedin_drafts_telegram(posts, tg_token, tg_chat_id)

        progress(1.0, desc="Done.")
        logs = _log_capture.flush_text()
        return _format_drafts_md(posts), logs

    except Exception as e:
        tb = traceback.format_exc()
        logs = _log_capture.flush_text()
        return f"**Error:** {e}\n\n```\n{tb}\n```", logs


# ── Tab 3: Memory Stats ───────────────────────────────────────

def get_memory_stats():
    try:
        from memory.chroma_store import _get_client
        client = _get_client()
        if client is None:
            return "ChromaDB not available. Install: `pip install chromadb sentence-transformers`"

        lines = ["## Memory Stats", ""]

        try:
            history = client.get_or_create_collection("content_history")
            count = history.count()
            lines.append(f"**Items stored in history:** {count}")
            if count > 0:
                sample = history.get(limit=5, include=["metadatas"])
                lines.append("\n**Recent items:**")
                for m in sample.get("metadatas", []):
                    title = m.get("title", "?")[:80]
                    source = m.get("source", "?")
                    stored = m.get("stored_at", "?")[:10]
                    lines.append(f"- `{stored}` [{source}] {title}")
        except Exception as e:
            lines.append(f"History collection error: {e}")

        lines.append("")

        try:
            prefs = client.get_or_create_collection("preferences")
            pcount = prefs.count()
            lines.append(f"**Preference signals recorded:** {pcount}")
            if pcount > 0:
                all_prefs = prefs.get(limit=50, include=["metadatas"])
                thumbs_up = []
                thumbs_down = []
                for m in all_prefs.get("metadatas", []):
                    score = float(m.get("score", 0))
                    title = m.get("title", "?")[:70]
                    if score > 0:
                        thumbs_up.append(title)
                    else:
                        thumbs_down.append(title)

                if thumbs_up:
                    lines += ["", "**👍 Topics you liked:**"]
                    for t in thumbs_up[:10]:
                        lines.append(f"  - {t}")

                if thumbs_down:
                    lines += ["", "**👎 Topics to skip:**"]
                    for t in thumbs_down[:10]:
                        lines.append(f"  - {t}")
        except Exception as e:
            lines.append(f"Preferences collection error: {e}")

        return "\n".join(lines)

    except Exception as e:
        return f"Error reading memory: {e}"


# ── Tab 4: Settings Preview ───────────────────────────────────

def get_settings_preview():
    try:
        import yaml
        from pathlib import Path
        config_path = Path(__file__).parent / "config" / "settings.yaml"
        with open(config_path) as f:
            config = yaml.safe_load(f)

        lines = ["## Active Configuration", ""]

        tags = config.get("topic_tags", [])
        lines += [f"**Topic tags ({len(tags)}):** {', '.join(tags)}", ""]

        sources = config.get("sources", {})

        reddit = sources.get("reddit", {})
        subs = reddit.get("subreddits", [])
        lines += [f"**Reddit subreddits:** {', '.join(subs)}", ""]

        twitter = sources.get("twitter", {})
        accounts = twitter.get("accounts", [])
        method = twitter.get("method", "?")
        lines += [f"**Twitter method:** {method} | **Accounts:** {len(accounts)}", ""]

        arxiv = sources.get("arxiv", {})
        cats = arxiv.get("categories", [])
        lines += [f"**arXiv categories:** {', '.join(cats)}", ""]

        blogs = sources.get("tech_blogs", {})
        feeds = blogs.get("rss_feeds", [])
        lines += [f"**Tech blog feeds:** {len(feeds)}", ""]

        schedule = config.get("schedule", {})
        lines += [
            "",
            "**Schedule:**",
            f"  - Newsletter: `{schedule.get('newsletter_cron', '?')}`",
            f"  - LinkedIn drafts: `{schedule.get('linkedin_draft_cron', '?')}`",
        ]

        lines += ["", "---", "**API Keys Status:**"]
        for key, label in [
            ("ANTHROPIC_API_KEY",  "Anthropic (Claude Sonnet)"),
            ("OPENAI_API_KEY",     "OpenAI (GPT-4o)"),
            ("HF_API_TOKEN",       "HuggingFace (optional)"),
            ("APIFY_API_TOKEN",    "Apify (Twitter)"),
            ("TELEGRAM_BOT_TOKEN", "Telegram Bot"),
            ("SMTP_HOST",          "Email SMTP"),
        ]:
            status = "✅ set" if os.getenv(key) else "❌ missing"
            lines.append(f"  - {label}: {status}")

        return "\n".join(lines)

    except Exception as e:
        return f"Error reading config: {e}"


# ── Build UI ──────────────────────────────────────────────────

with gr.Blocks(
    title="AI Pulse",
    theme=gr.themes.Soft(primary_hue="indigo"),
) as demo:

    gr.Markdown("""
# AI Pulse
**Personal AI/ML newsletter automation** — collects trending content, summarises it, delivers to Telegram & email, and drafts LinkedIn posts in your voice.

Built by [Shashank Bodapati](https://www.linkedin.com/in/shashankbodapati) | AI Engineer | MSc Applied AI & Data Science
""")

    with gr.Tabs():

        # ── Tab 1 ──────────────────────────────────────────────
        with gr.Tab("Run Pipeline"):
            gr.Markdown("Collect → Rank (memory-aware) → Summarise → Analyse → Deliver")
            with gr.Row():
                chk_telegram = gr.Checkbox(label="Send to Telegram", value=True)
                chk_email    = gr.Checkbox(label="Send Email", value=False)
            btn_run = gr.Button("Run Pipeline", variant="primary", size="lg")

            with gr.Row():
                with gr.Column(scale=2):
                    out_digest = gr.Markdown(label="Digest Output")
                with gr.Column(scale=1):
                    out_logs_run = gr.Textbox(label="Logs", lines=20, max_lines=30)

            btn_run.click(
                fn=run_pipeline_ui,
                inputs=[chk_telegram, chk_email],
                outputs=[out_digest, out_logs_run],
            )

        # ── Tab 2 ──────────────────────────────────────────────
        with gr.Tab("LinkedIn Drafts"):
            gr.Markdown("Generate 2 LinkedIn post drafts in your voice via GPT-4o. Drafts are sent to Telegram and saved to `output/`.")
            btn_linkedin = gr.Button("Generate Drafts", variant="primary", size="lg")

            with gr.Row():
                with gr.Column(scale=2):
                    out_drafts = gr.Markdown(label="Generated Drafts")
                with gr.Column(scale=1):
                    out_logs_li = gr.Textbox(label="Logs", lines=20, max_lines=30)

            btn_linkedin.click(
                fn=run_linkedin_ui,
                inputs=[],
                outputs=[out_drafts, out_logs_li],
            )

        # ── Tab 3 ──────────────────────────────────────────────
        with gr.Tab("Memory Stats"):
            gr.Markdown("Your preference history — built from 👍/👎 taps on Telegram. This shapes next week's ranking.")
            btn_refresh = gr.Button("Refresh Stats")
            out_memory  = gr.Markdown()

            btn_refresh.click(fn=get_memory_stats, inputs=[], outputs=[out_memory])
            demo.load(fn=get_memory_stats, inputs=[], outputs=[out_memory])

        # ── Tab 4 ──────────────────────────────────────────────
        with gr.Tab("Settings"):
            gr.Markdown("Active configuration — no secrets shown.")
            out_settings = gr.Markdown()
            demo.load(fn=get_settings_preview, inputs=[], outputs=[out_settings])


if __name__ == "__main__":
    demo.launch()
