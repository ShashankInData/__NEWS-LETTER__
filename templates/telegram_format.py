"""
Telegram message formatters for AI Pulse.

Extracted from delivery/telegram_bot.py so that formatting logic
lives in one place and can be tested independently.

Functions:
  format_newsletter()           — weekly digest (summaries + analysis), single message
  format_newsletter_header()    — analysis/theme section only (used by feedback flow)
  format_item_with_buttons()    — single story card (used by feedback flow)
  format_linkedin_drafts()      — LinkedIn post drafts header message
  format_single_draft()         — a single LinkedIn post draft
"""


def format_newsletter(newsletter: list, analysis: dict = None) -> str:
    """
    Format the weekly newsletter digest into Telegram Markdown.

    Sections (when analysis is present):
      1. This Week's Theme
      2. How It Connects
      3. Implications
      4. Hot Take
      5. Skills Radar
      6. Divider
      7. News items (title, source, summary, tags)
      8. Footer
    """
    lines = ["*AI Pulse — Weekly Digest*\n"]

    # ── Analysis first (the brain's take) ─────────────────────
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
            for key, label in [
                ("industry",     "Industry"),
                ("economic",     "Economic"),
                ("geopolitical", "Geopolitical"),
                ("for_builders", "For Builders"),
            ]:
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

    # ── News items ─────────────────────────────────────────────
    lines.append("\n*This Week's Stories:*\n")

    for item in newsletter:
        title   = item.get("title", "Untitled")
        source  = item.get("source", "")
        summary = item.get("summary", "")
        url     = item.get("url", "")
        tags    = ", ".join(item.get("tags", []))

        lines.append(f"[{title}]({url})")
        lines.append(f"_{source}_")
        lines.append(summary)
        if tags:
            lines.append(f"`{tags}`")
        lines.append("")

    lines.append("─" * 30)
    lines.append("_AI Pulse | BART + Claude Sonnet | Python_")

    return "\n".join(lines)


def format_newsletter_header(analysis: dict = None) -> str:
    """
    Analysis-only header sent as the first message in the feedback flow.
    Does not include individual stories (those come as separate messages).
    """
    lines = ["*AI Pulse — Weekly Digest*\n"]

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
            for key, label in [
                ("industry",     "Industry"),
                ("economic",     "Economic"),
                ("geopolitical", "Geopolitical"),
                ("for_builders", "For Builders"),
            ]:
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
    lines.append("_Rate each story below to personalise next week's digest:_")
    return "\n".join(lines)


def format_item_with_buttons(item: dict) -> str:
    """
    Single story card for the feedback flow.
    Sent as an individual message so inline 👍/👎 buttons can attach to it.
    """
    title   = item.get("title", "Untitled")
    source  = item.get("source", "")
    summary = item.get("summary", "")
    url     = item.get("url", "")
    tags    = ", ".join(item.get("tags", []))

    lines = [f"[{title}]({url})", f"_{source}_", summary]
    if tags:
        lines.append(f"`{tags}`")
    return "\n".join(lines)


def format_linkedin_header(label: str = "LinkedIn Drafts") -> str:
    """Header message sent before the individual draft messages."""
    from datetime import datetime
    date_str = datetime.now().strftime("%d %b %Y")
    return (
        f"*AI Pulse — {label}*\n"
        f"_{date_str} | OpenAI gpt-4o + your Content DNA_\n\n"
        f"Here are your LinkedIn drafts. Copy-paste what you like:"
    )


def format_single_draft(post: dict, index: int) -> str:
    """
    Format a single LinkedIn draft for Telegram.

    Args:
        post:  draft dict (content, post_type, story_used, word_count, changes_made)
        index: 1-based position number
    """
    post_type  = post.get("post_type", "unknown").replace("_", " ").title()
    story      = post.get("story_used", "")
    word_count = post.get("word_count", "?")
    content    = post.get("content", "")
    changes    = post.get("changes_made", "")

    lines = [f"*Post {index} — {post_type}*"]
    if story:
        lines.append(f"_Story: {story}_")
    lines.append(f"_~{word_count} words_")
    if changes:
        lines.append(f"_Changes: {changes}_")
    lines.append("")
    lines.append(content)
    lines.append("")
    lines.append("`python main.py --rewrite`  ← to rewrite this post")

    return "\n".join(lines)
