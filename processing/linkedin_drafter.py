"""
LinkedIn Draft Generator — Phase 6

Uses OpenAI gpt-4o + your content_dna.yaml to generate LinkedIn posts
that sound like YOU wrote them.

Modes:
  generate(items, config, api_key)        → generate 2 fresh posts from top stories
  rewrite(post_text, feedback, api_key)   → rewrite a post with your feedback + deeper research angle

Output: saved to output/linkedin_drafts_YYYY-MM-DD.md (manual copy-paste to LinkedIn)

No LinkedIn API. No automation. You pick what to post.
"""

import os
import json
import logging
import yaml
from datetime import datetime
from pathlib import Path
from typing import Optional
from openai import OpenAI

logger = logging.getLogger(__name__)


# ──────────────────────────────────────────────────────────────
# Load content DNA
# ──────────────────────────────────────────────────────────────

def _load_content_dna(dna_path: str) -> dict:
    path = Path(dna_path)
    if not path.is_absolute():
        path = Path(__file__).parent.parent / dna_path
    with open(path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def _build_system_prompt(dna: dict) -> str:
    """Build a rich system prompt from content_dna.yaml so GPT-4o writes in SK's voice."""

    persona = dna.get("persona", {})
    voice = dna.get("voice", {})
    structure = dna.get("structure", {})
    formatting = dna.get("formatting", {})
    language = dna.get("language", {})
    generation_rules = dna.get("generation_rules", {})
    analysis_fw = dna.get("analysis_framework", {})

    core_tone = "\n".join(f"- {t}" for t in voice.get("core_tone", []))
    emotional_reg = "\n".join(f"- {e}" for e in voice.get("emotional_register", []))
    personality = "\n".join(f"- {p}" for p in voice.get("personality_markers", []))

    must_rules = "\n".join(f"- {r}" for r in generation_rules.get("must", []))
    must_not_rules = "\n".join(f"- {r}" for r in generation_rules.get("must_not", []))

    sig_phrases = ", ".join(f'"{p}"' for p in language.get("signature_phrases", []))
    words_use = ", ".join(language.get("words_sk_uses", []))
    words_avoid = ", ".join(language.get("words_sk_never_uses", []))

    opening_hooks = "\n".join(f"- {h}" for h in language.get("opening_hooks", []))
    closing_patterns = "\n".join(f"- {c}" for c in language.get("closing_patterns", []))

    arrow_rules = "\n".join(f"- {r}" for r in formatting.get("arrow_lists", {}).get("rules", []))
    emoji_rules = "\n".join(f"- {r}" for r in formatting.get("emoji_usage", {}).get("rules", []))
    text_fmt = "\n".join(f"- {r}" for r in formatting.get("text_formatting", []))

    lenses = "\n".join(f"- {l}" for l in analysis_fw.get("lenses", []))

    lengths = generation_rules.get("length", {})

    templates = dna.get("templates", {})
    hot_take_template = templates.get("hot_take", "")
    geopolitical_template = templates.get("geopolitical_analysis", "")
    project_template = templates.get("project_showcase", "")

    return f"""You are a ghostwriter for {persona.get('name', 'Shashank Bodapati')}, an {persona.get('role', 'AI Engineer')}.

Your ONLY job is to write LinkedIn posts that sound EXACTLY like {persona.get('name')} wrote them — not like an AI assistant.

═══ PERSONA ═══
{persona.get('positioning', '')}

═══ VOICE & TONE ═══
Core tone:
{core_tone}

Emotional register:
{emotional_reg}

Personality markers:
{personality}

═══ GENERATION RULES ═══
MUST:
{must_rules}

MUST NOT:
{must_not_rules}

═══ SIGNATURE FORMATTING ═══
Arrow lists (SK's signature — use → not • or -):
{arrow_rules}

Emoji usage:
{emoji_rules}

Text formatting:
{text_fmt}

Hashtags: 5-8 per post, always relevant, mix broad (#AI) with niche tags.

═══ LANGUAGE ═══
Signature phrases (use naturally, not all at once): {sig_phrases}
Words SK uses: {words_use}
Words SK NEVER uses: {words_avoid}

Opening hook patterns:
{opening_hooks}

Closing patterns:
{closing_patterns}

═══ ANALYSIS FRAMEWORK (for industry/geopolitical posts) ═══
Always break down through these lenses when relevant:
{lenses}
Always include a "Here's the catch:" counter-argument. Never one-sided.

═══ POST LENGTH ═══
Short (hot takes): {lengths.get('short_post', '150-300 words')}
Standard: {lengths.get('standard_post', '300-600 words')}
Deep dive: {lengths.get('deep_dive', '600-900 words')}
Rule: {lengths.get('rule', 'Never exceed 900 words.')}

═══ POST TEMPLATES ═══

HOT TAKE template:
{hot_take_template}

GEOPOLITICAL ANALYSIS template:
{geopolitical_template}

PROJECT SHOWCASE template:
{project_template}

═══ OUTPUT FORMAT ═══
Return ONLY valid JSON — no markdown, no backticks, no preamble:
{{
  "posts": [
    {{
      "post_type": "hot_take | geopolitical_analysis | project_showcase",
      "story_used": "One-line title of the source story",
      "word_count": 320,
      "content": "Full post text ready to copy-paste into LinkedIn"
    }}
  ]
}}"""


# ──────────────────────────────────────────────────────────────
# Post selection: pick best stories for each post type
# ──────────────────────────────────────────────────────────────

def _select_stories(summarized_items: list, posts_per_run: int = 2) -> list:
    """
    Pick the best items for LinkedIn posts.
    - Prefers high engagement + strong topic match
    - Tries to vary post types (hot_take vs geopolitical_analysis)
    - Returns list of (item, suggested_post_type) tuples
    """

    if not summarized_items:
        return []

    # Score items: tags × 10 + capped engagement
    def item_score(item):
        tags = len(item.get("tags", []))
        score = min(item.get("score", 0), 500) / 50
        return tags * 10 + score

    ranked = sorted(summarized_items, key=item_score, reverse=True)

    selected = []
    used_sources = set()

    for item in ranked:
        if len(selected) >= posts_per_run:
            break

        source = item.get("source", "")
        if source in used_sources:
            continue

        # Assign post type based on source
        if source.lower() in ("arxiv", "huggingface"):
            post_type = "geopolitical_analysis"
        elif source.lower() in ("openai", "anthropic", "google", "meta", "mistral"):
            post_type = "hot_take"
        else:
            # Reddit/Twitter — alternate between types
            post_type = "hot_take" if len(selected) == 0 else "geopolitical_analysis"

        selected.append((item, post_type))
        used_sources.add(source)

    # If we didn't fill slots due to source dedup, relax constraint
    if len(selected) < posts_per_run:
        for item in ranked:
            if len(selected) >= posts_per_run:
                break
            if item not in [s[0] for s in selected]:
                post_type = "hot_take" if len(selected) % 2 == 0 else "geopolitical_analysis"
                selected.append((item, post_type))

    return selected


# ──────────────────────────────────────────────────────────────
# Core generation
# ──────────────────────────────────────────────────────────────

def generate_drafts(
    summarized_items: list,
    config: dict,
    api_key: str,
) -> list:
    """
    Generate LinkedIn post drafts from top stories.
    Returns list of post dicts: {post_type, story_used, word_count, content}
    """

    linkedin_config = config.get("linkedin_draft", {})
    posts_per_run = linkedin_config.get("posts_per_run", 2)
    dna_path = linkedin_config.get("content_dna_path", "config/content_dna.yaml")

    dna = _load_content_dna(dna_path)
    system_prompt = _build_system_prompt(dna)

    selected = _select_stories(summarized_items, posts_per_run)

    if not selected:
        logger.warning("LinkedIn drafter: no stories available to draft posts from")
        return []

    # Build user message with selected stories
    story_blocks = []
    for item, post_type in selected:
        story_blocks.append(
            f"Story: {item.get('title', 'Untitled')}\n"
            f"Source: {item.get('source', 'Unknown')}\n"
            f"Summary: {item.get('summary', '')}\n"
            f"Detail: {item.get('content_snippet', '')[:400]}\n"
            f"Engagement: {item.get('score', 0)} points\n"
            f"Topics: {', '.join(item.get('tags', []))}\n"
            f"Suggested post type: {post_type}"
        )

    user_message = (
        f"Write {len(selected)} LinkedIn post(s) for Shashank based on these stories.\n"
        f"Each post should use the suggested post type as a guide.\n"
        f"Make each post feel fresh and distinct — different angles, different hooks.\n\n"
        + "\n\n---\n\n".join(story_blocks)
    )

    logger.info(f"LinkedIn drafter: generating {len(selected)} posts via OpenAI gpt-4o")

    try:
        client = OpenAI(api_key=api_key)

        response = client.chat.completions.create(
            model="gpt-4o",
            max_tokens=3000,
            temperature=0.85,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_message},
            ],
        )

        raw_text = response.choices[0].message.content.strip()

        # Parse JSON
        try:
            result = json.loads(raw_text)
            posts = result.get("posts", [])
        except json.JSONDecodeError:
            import re
            json_match = re.search(r"\{[\s\S]*\}", raw_text)
            if json_match:
                result = json.loads(json_match.group())
                posts = result.get("posts", [])
            else:
                logger.error("LinkedIn drafter: failed to parse JSON response")
                posts = [{"post_type": "unknown", "story_used": "parse error", "word_count": 0, "content": raw_text}]

        usage = response.usage
        logger.info(
            f"LinkedIn drafts complete. Tokens: {usage.prompt_tokens} in / {usage.completion_tokens} out "
            f"(~${(usage.prompt_tokens * 2.5 + usage.completion_tokens * 10) / 1_000_000:.4f})"
        )

        return posts

    except Exception as e:
        logger.error(f"LinkedIn drafter failed: {e}")
        return []


# ──────────────────────────────────────────────────────────────
# Rewrite mode — user liked a post, wants it improved
# ──────────────────────────────────────────────────────────────

def rewrite_post(
    original_post: str,
    feedback: str,
    config: dict,
    api_key: str,
) -> dict:
    """
    Rewrite a post based on user feedback.
    The LLM researches deeper angles and rewrites with the same voice.

    Args:
        original_post: The post text the user wants rewritten
        feedback: What to change — e.g. "make it shorter", "stronger hook",
                  "add more technical depth", "more UK angle"
        config: settings.yaml config dict
        api_key: OpenAI API key

    Returns:
        dict with {post_type, story_used, word_count, content, changes_made}
    """

    dna_path = config.get("linkedin_draft", {}).get("content_dna_path", "config/content_dna.yaml")
    dna = _load_content_dna(dna_path)
    system_prompt = _build_system_prompt(dna)

    rewrite_instruction = f"""The user has a LinkedIn post draft they like but want improved.

ORIGINAL POST:
---
{original_post}
---

USER FEEDBACK / WHAT TO CHANGE:
{feedback}

Your task:
1. Analyze what works well in the original post — keep those elements
2. Apply the user's feedback precisely
3. Think about deeper angles: stronger hook, more specific numbers, better counter-argument, tighter close
4. Rewrite the full post in Shashank's voice following all the rules above
5. The rewrite should feel like an evolution of the original, not a completely new post

Return ONLY valid JSON:
{{
  "posts": [
    {{
      "post_type": "same type as original",
      "story_used": "same story as original",
      "word_count": 350,
      "content": "Full rewritten post ready to copy-paste",
      "changes_made": "2-3 bullet points of what specifically changed"
    }}
  ]
}}"""

    logger.info("LinkedIn drafter: rewriting post based on feedback")

    try:
        client = OpenAI(api_key=api_key)

        response = client.chat.completions.create(
            model="gpt-4o",
            max_tokens=2000,
            temperature=0.75,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": rewrite_instruction},
            ],
        )

        raw_text = response.choices[0].message.content.strip()

        try:
            result = json.loads(raw_text)
            posts = result.get("posts", [])
            return posts[0] if posts else {}
        except json.JSONDecodeError:
            import re
            json_match = re.search(r"\{[\s\S]*\}", raw_text)
            if json_match:
                result = json.loads(json_match.group())
                posts = result.get("posts", [])
                return posts[0] if posts else {}
            return {"content": raw_text, "changes_made": "parse error"}

    except Exception as e:
        logger.error(f"LinkedIn rewrite failed: {e}")
        return {}


# ──────────────────────────────────────────────────────────────
# Save drafts to file
# ──────────────────────────────────────────────────────────────

def save_drafts_to_file(posts: list, output_dir: str = None) -> str:
    """
    Save generated posts to output/linkedin_drafts_YYYY-MM-DD.md
    Returns the file path.
    """

    if output_dir is None:
        output_dir = Path(__file__).parent.parent / "output"
    else:
        output_dir = Path(output_dir)

    output_dir.mkdir(exist_ok=True)

    date_str = datetime.now().strftime("%Y-%m-%d")
    filename = output_dir / f"linkedin_drafts_{date_str}.md"

    lines = [
        f"# LinkedIn Drafts — {date_str}",
        f"Generated by AI Pulse | OpenAI gpt-4o + your Content DNA",
        f"Copy-paste manually to LinkedIn. Edit as needed.",
        "",
        "---",
        "",
    ]

    for i, post in enumerate(posts, 1):
        post_type = post.get("post_type", "unknown").replace("_", " ").title()
        story = post.get("story_used", "")
        word_count = post.get("word_count", "?")
        content = post.get("content", "")
        changes = post.get("changes_made", "")

        lines.append(f"## Post {i} — {post_type}")
        if story:
            lines.append(f"**Story:** {story}")
        lines.append(f"**Words:** ~{word_count}")
        if changes:
            lines.append(f"**Changes from original:** {changes}")
        lines.append("")
        lines.append(content)
        lines.append("")
        lines.append("---")
        lines.append("")

    lines.append("*To rewrite a post: copy the post text and run `python main.py --rewrite`*")

    with open(filename, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))

    logger.info(f"LinkedIn drafts saved to: {filename}")
    return str(filename)
