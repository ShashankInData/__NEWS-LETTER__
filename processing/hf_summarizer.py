"""
Lightweight summarizer using HuggingFace Inference API (free tier).

Uses facebook/bart-large-cnn for basic summarization — no Claude tokens burned.
Falls back to simple extractive summarization if HF API is down.

HuggingFace free Inference API: no token needed for public models,
but rate-limited. Optional HF_API_TOKEN for higher limits.
"""

import requests
import logging
from typing import List, Optional

from collectors import ContentItem

logger = logging.getLogger(__name__)

HF_INFERENCE_URL = "https://router.huggingface.co/hf-inference/models/{model}"
DEFAULT_MODEL = "facebook/bart-large-cnn"


def _summarize_with_hf(
    text: str,
    model: str = DEFAULT_MODEL,
    hf_token: Optional[str] = None,
    max_length: int = 120,
    min_length: int = 30,
) -> str:
    """Call HuggingFace Inference API for summarization."""

    url = HF_INFERENCE_URL.format(model=model)
    headers = {}
    if hf_token:
        headers["Authorization"] = f"Bearer {hf_token}"

    payload = {
        "inputs": text[:1024],  # BART has 1024 token context
        "parameters": {
            "max_length": max_length,
            "min_length": min_length,
            "do_sample": False,
        },
    }

    try:
        resp = requests.post(url, headers=headers, json=payload, timeout=30)

        # Model might be loading (cold start) — retry once
        if resp.status_code == 503:
            import time
            wait_time = resp.json().get("estimated_time", 20)
            logger.info(f"HF model loading, waiting {wait_time:.0f}s...")
            time.sleep(min(wait_time, 30))
            resp = requests.post(url, headers=headers, json=payload, timeout=60)

        if resp.status_code == 200:
            result = resp.json()
            if isinstance(result, list) and len(result) > 0:
                return result[0].get("summary_text", "").strip()

        logger.warning(f"HF API returned {resp.status_code}: {resp.text[:200]}")
        return ""

    except Exception as e:
        logger.error(f"HF inference failed: {e}")
        return ""


def _extractive_fallback(text: str, num_sentences: int = 2) -> str:
    """
    Dead-simple extractive summary: pick the first N sentences.
    Used when HuggingFace API is unavailable.
    """
    import re
    sentences = re.split(r"(?<=[.!?])\s+", text.strip())
    return " ".join(sentences[:num_sentences])


def summarize_item(
    item: ContentItem,
    hf_token: Optional[str] = None,
) -> str:
    """Summarize a single content item using HF model with fallback."""

    # Build input text: title + content
    input_text = f"{item.title}. {item.content}"

    if not input_text.strip() or len(input_text.strip()) < 50:
        return item.title  # Too short to summarize

    summary = _summarize_with_hf(input_text, hf_token=hf_token)

    if not summary:
        logger.debug(f"HF failed for '{item.title[:50]}', using extractive fallback")
        summary = _extractive_fallback(input_text)

    return summary


def summarize_all_items(
    items: List[ContentItem],
    hf_token: Optional[str] = None,
) -> List[dict]:
    """
    Summarize all items using HuggingFace (free).
    Returns list of dicts with title, url, source, summary, tags.
    """
    logger.info(f"Summarizing {len(items)} items with HuggingFace ({DEFAULT_MODEL})")

    results = []
    for i, item in enumerate(items):
        logger.debug(f"  [{i+1}/{len(items)}] {item.title[:60]}...")
        summary = summarize_item(item, hf_token=hf_token)

        results.append({
            "title": item.title,
            "url": item.url,
            "source": f"{item.source} — {item.subreddit_or_account}",
            "summary": summary,
            "tags": item.tags_matched,
            "score": item.score,
            "content_snippet": item.content[:300],  # Keep for analysis layer
        })

    logger.info(f"Summarization complete: {len(results)} items processed")
    return results
