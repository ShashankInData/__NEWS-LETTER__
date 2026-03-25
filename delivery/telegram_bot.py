import requests
import logging

logger = logging.getLogger(__name__)

TELEGRAM_API = "https://api.telegram.org/bot{token}"


def _format_message(newsletter: list, analysis: dict = None) -> str:
    """Format newsletter + analysis into Telegram message."""

    lines = ["*AI Pulse — Weekly Digest*\n"]

    # ── Analysis first (the brain's take) ─────────────────
    if analysis:
        theme = analysis.get("weekly_theme", "")
        if theme:
            lines.append(f"*This Week's Theme:* {theme}\n")

        connections = analysis.get("connections", "")
        if connections:
            lines.append(f"*How It Connects:*\n{connections[:600]}\n")

        implications = analysis.get("implications", {})
        if implications:
            lines.append("*Implications:*")
            for key, label in [("industry", "Industry"), ("economic", "Economic"),
                               ("geopolitical", "Geopolitical"), ("for_builders", "For Builders")]:
                val = implications.get(key)
                if val:
                    lines.append(f"  {label}: {val}")
            lines.append("")

        hot_take = analysis.get("hot_take", "")
        if hot_take:
            lines.append(f"*Hot Take:* {hot_take}\n")

        skills = analysis.get("skills_radar", [])
        if skills:
            lines.append(f"*Skills Radar:* {', '.join(skills)}\n")

        lines.append("─" * 30)

    # ── News items ────────────────────────────────────────
    lines.append("\n*This Week's Stories:*\n")

    for item in newsletter:
        title = item.get("title", "Untitled")
        source = item.get("source", "")
        summary = item.get("summary", "")
        url = item.get("url", "")
        tags = ", ".join(item.get("tags", []))

        lines.append(f"[{title}]({url})")
        lines.append(f"_{source}_")
        lines.append(f"{summary}")
        if tags:
            lines.append(f"`{tags}`")
        lines.append("")

    lines.append("─" * 30)
    lines.append("_AI Pulse | BART + Claude Sonnet | Python_")

    return "\n".join(lines)


def _send_chunks(text: str, bot_token: str, chat_id: str) -> bool:
    """Split text into Telegram-safe chunks and send each one."""

    chunks = []
    if len(text) > 4000:
        current_chunk = ""
        for line in text.split("\n"):
            if len(current_chunk) + len(line) + 1 > 4000:
                chunks.append(current_chunk)
                current_chunk = line
            else:
                current_chunk += "\n" + line if current_chunk else line
        if current_chunk:
            chunks.append(current_chunk)
    else:
        chunks = [text]

    url = f"{TELEGRAM_API.format(token=bot_token)}/sendMessage"
    success = True

    for i, chunk in enumerate(chunks):
        try:
            resp = requests.post(
                url,
                json={
                    "chat_id": chat_id,
                    "text": chunk,
                    "parse_mode": "Markdown",
                    "disable_web_page_preview": True,
                },
                timeout=15,
            )

            if resp.status_code != 200:
                resp = requests.post(
                    url,
                    json={
                        "chat_id": chat_id,
                        "text": chunk.replace("*", "").replace("_", "").replace("`", ""),
                        "disable_web_page_preview": True,
                    },
                    timeout=15,
                )

            if resp.status_code == 200:
                logger.info(f"Telegram chunk {i+1}/{len(chunks)} sent")
            else:
                logger.error(f"Telegram failed: {resp.status_code} {resp.text[:200]}")
                success = False

        except Exception as e:
            logger.error(f"Telegram error: {e}")
            success = False

    return success


def send_linkedin_drafts_telegram(
    posts: list,
    bot_token: str,
    chat_id: str,
    label: str = "LinkedIn Drafts",
) -> bool:
    """
    Send generated LinkedIn post drafts to Telegram.
    Each post is sent as a separate message for easy reading + copy-paste.
    """

    if not posts:
        return False

    from datetime import datetime
    date_str = datetime.now().strftime("%d %b %Y")

    # Header message
    header = f"*AI Pulse — {label}*\n_{date_str} | OpenAI gpt-4o + your Content DNA_\n\nHere are your LinkedIn drafts. Copy-paste what you like:"
    _send_chunks(header, bot_token, chat_id)

    success = True
    for i, post in enumerate(posts, 1):
        post_type = post.get("post_type", "unknown").replace("_", " ").title()
        story = post.get("story_used", "")
        word_count = post.get("word_count", "?")
        content = post.get("content", "")
        changes = post.get("changes_made", "")

        lines = [
            f"*Post {i} — {post_type}*",
        ]
        if story:
            lines.append(f"_Story: {story}_")
        lines.append(f"_~{word_count} words_")
        if changes:
            lines.append(f"_Changes: {changes}_")
        lines.append("")
        lines.append(content)
        lines.append("")
        lines.append(f"─ To rewrite: `python main.py --rewrite`")

        post_text = "\n".join(lines)
        if not _send_chunks(post_text, bot_token, chat_id):
            success = False

    return success


def send_telegram(
    newsletter: list,
    analysis: dict,
    bot_token: str,
    chat_id: str,
) -> bool:
    """Send newsletter + analysis digest to Telegram."""

    message = _format_message(newsletter, analysis)

    # Telegram 4096 char limit — split if needed
    chunks = []
    if len(message) > 4000:
        current_chunk = ""
        for line in message.split("\n"):
            if len(current_chunk) + len(line) + 1 > 4000:
                chunks.append(current_chunk)
                current_chunk = line
            else:
                current_chunk += "\n" + line if current_chunk else line
        if current_chunk:
            chunks.append(current_chunk)
    else:
        chunks = [message]

    return _send_chunks(message, bot_token, chat_id)
