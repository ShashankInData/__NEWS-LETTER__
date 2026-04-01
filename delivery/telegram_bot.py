import hashlib
import requests
import logging

from templates.telegram_format import (
    format_newsletter,
    format_newsletter_header,
    format_item_with_buttons,
    format_linkedin_header,
    format_single_draft,
)

logger = logging.getLogger(__name__)

TELEGRAM_API = "https://api.telegram.org/bot{token}"


def _item_id(url: str, title: str) -> str:
    raw = url.strip() if url.strip() else title.strip()
    return hashlib.md5(raw.encode()).hexdigest()


def _send_chunks(text: str, bot_token: str, chat_id: str) -> bool:
    """
    Split text into Telegram-safe chunks (≤4000 chars) and send each one.
    Falls back to plain text if Markdown parsing fails.
    """
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

            # If Markdown fails, retry as plain text
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
            logger.error(f"Telegram error on chunk {i+1}: {e}")
            success = False

    return success


def _send_message_with_buttons(text: str, buttons: list, bot_token: str, chat_id: str) -> bool:
    """Send a single message with an inline keyboard. buttons = [[{text, callback_data}]]"""
    url = f"{TELEGRAM_API.format(token=bot_token)}/sendMessage"
    try:
        resp = requests.post(
            url,
            json={
                "chat_id": chat_id,
                "text": text,
                "parse_mode": "Markdown",
                "disable_web_page_preview": True,
                "reply_markup": {"inline_keyboard": buttons},
            },
            timeout=15,
        )
        if resp.status_code != 200:
            # Retry as plain text
            plain = text.replace("*", "").replace("_", "").replace("`", "")
            resp = requests.post(
                url,
                json={
                    "chat_id": chat_id,
                    "text": plain,
                    "disable_web_page_preview": True,
                    "reply_markup": {"inline_keyboard": buttons},
                },
                timeout=15,
            )
        return resp.status_code == 200
    except Exception as e:
        logger.error(f"Telegram button message error: {e}")
        return False


def send_newsletter_with_feedback(
    newsletter: list,
    analysis: dict,
    bot_token: str,
    chat_id: str,
) -> bool:
    """
    Send weekly digest to Telegram with 👍/👎 buttons on each story.

    Flow:
    1. Header message (theme, analysis, hot take)
    2. One message per story with inline 👍/👎 buttons
       callback_data format: "fb:{item_id}:{+1|-1}"
    """
    # Header (analysis section) — no buttons needed
    header = format_newsletter_header(analysis)
    _send_chunks(header, bot_token, chat_id)

    success = True
    for item in newsletter:
        item_id = _item_id(item.get("url", ""), item.get("title", ""))
        text = format_item_with_buttons(item)
        buttons = [[
            {"text": "👍 Good pick", "callback_data": f"fb:{item_id}:1"},
            {"text": "👎 Skip next time", "callback_data": f"fb:{item_id}:-1"},
        ]]
        if not _send_message_with_buttons(text, buttons, bot_token, chat_id):
            success = False

    return success


def handle_feedback_update(update: dict) -> None:
    """
    Process a Telegram callback_query (👍/👎 tap) and write to ChromaDB.

    Telegram sends callback queries to the webhook endpoint. Parse the
    callback_data ("fb:{item_id}:{score}"), look up the item title from
    ChromaDB history, and record the preference score.

    Call this from the webhook handler in main.py.
    """
    try:
        callback = update.get("callback_query", {})
        data = callback.get("data", "")
        if not data.startswith("fb:"):
            return

        parts = data.split(":")
        if len(parts) != 3:
            return

        _, item_id, score_str = parts
        score = float(score_str)

        # Look up the title from ChromaDB so we can re-embed it
        try:
            from memory.chroma_store import _get_client, record_feedback
            client = _get_client()
            if client:
                import chromadb
                col = client.get_or_create_collection("content_history")
                result = col.get(ids=[item_id], include=["documents"])
                docs = result.get("documents", [[]])
                title = docs[0] if docs else item_id
            else:
                title = item_id
            record_feedback(item_id, title, score)
        except Exception as e:
            logger.error(f"handle_feedback_update: ChromaDB error — {e}")

    except Exception as e:
        logger.error(f"handle_feedback_update failed: {e}")


def send_telegram(
    newsletter: list,
    analysis: dict,
    bot_token: str,
    chat_id: str,
) -> bool:
    """Send weekly newsletter + analysis digest to Telegram."""
    message = format_newsletter(newsletter, analysis)
    return _send_chunks(message, bot_token, chat_id)


def send_linkedin_drafts_telegram(
    posts: list,
    bot_token: str,
    chat_id: str,
    label: str = "LinkedIn Drafts",
) -> bool:
    """
    Send generated LinkedIn post drafts to Telegram.
    Each draft is sent as a separate message for easy reading + copy-paste.
    """
    if not posts:
        return False

    # Header message
    _send_chunks(format_linkedin_header(label), bot_token, chat_id)

    success = True
    for i, post in enumerate(posts, 1):
        post_text = format_single_draft(post, i)
        if not _send_chunks(post_text, bot_token, chat_id):
            success = False

    return success
