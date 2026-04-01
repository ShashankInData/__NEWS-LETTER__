"""
Analysis Layer — The "Brain"

Takes summarized content and generates:
1. Cross-cutting analysis: how different items connect
2. Implications: what this means for the industry, markets, geopolitics
3. Personal relevance: why this matters for an AI engineer job-seeking in the UK
4. Hot take: a bold, opinionated perspective

This is the ONLY module that uses Claude Sonnet — the expensive model
is reserved for actual thinking, not grunt work.
"""

import anthropic
import json
import logging
from typing import List

logger = logging.getLogger(__name__)

ANALYSIS_SYSTEM_PROMPT = """You are an insightful AI/ML industry analyst with deep knowledge of technology, geopolitics, economics, and the job market. You think like a seasoned tech strategist who connects dots that others miss.

You receive a set of summarized AI/ML news items for the week. Your job is to provide ANALYSIS, not just summaries. Think about:

1. **Connections**: How do these items relate to each other? What patterns emerge?
2. **Implications**: What are the second and third-order effects?
   - Industry impact: Who wins, who loses?
   - Economic/market impact: How might this affect tech stocks, funding, hiring?
   - Geopolitical angle: Any international dynamics at play (US-China AI race, EU regulation, etc.)?
   - Supply chain: Any hardware, compute, or resource implications?
3. **What it means for AI engineers**: How does this affect someone building AI products, job-hunting in AI/ML, or deciding what skills to learn next?
4. **Hot take**: Give one bold, opinionated prediction or observation. Be specific and contrarian if warranted — don't play it safe.

Your tone: Smart, direct, conversational. Like a brilliant friend who reads everything and tells you what actually matters over coffee. Not academic, not corporate. Use concrete examples.

Output format: Return valid JSON:
{
  "weekly_theme": "One sentence capturing the week's dominant narrative",
  "analysis_sections": [
    {
      "heading": "Short punchy heading",
      "body": "2-4 paragraphs of analysis. Be specific. Name companies, models, numbers.",
      "relevance": "One sentence on why an AI engineer should care"
    }
  ],
  "connections": "1-2 paragraphs on how the week's stories connect to each other",
  "implications": {
    "industry": "Key industry implications",
    "economic": "Market/economic implications if any",
    "geopolitical": "Geopolitical angle if relevant, otherwise null",
    "for_builders": "What AI engineers/builders should do or watch"
  },
  "hot_take": "Your boldest, most specific take on what this week means",
  "skills_radar": ["skill1", "skill2", "skill3"]
}

skills_radar = top 3 skills/tools that are gaining momentum based on this week's content.

Return ONLY valid JSON. No markdown, no backticks, no preamble."""


def generate_analysis(
    summarized_items: List[dict],
    api_key: str,
) -> dict:
    """
    Send summarized items to Claude Sonnet for deep analysis.
    This is the expensive call — used sparingly, only for thinking.
    """

    if not summarized_items:
        return {
            "weekly_theme": "Quiet week in AI.",
            "analysis_sections": [],
            "connections": "",
            "implications": {},
            "hot_take": "No strong signal this week.",
            "skills_radar": [],
        }

    # Build the input
    items_text = []
    for i, item in enumerate(summarized_items, 1):
        items_text.append(
            f"{i}. [{item['source']}] {item['title']}\n"
            f"   Summary: {item['summary']}\n"
            f"   Detail: {item.get('content_snippet', '')}\n"
            f"   Engagement: {item.get('score', 0)} points\n"
            f"   Topics: {', '.join(item.get('tags', []))}"
        )

    user_message = (
        f"Here are this week's {len(summarized_items)} top AI/ML stories, "
        f"already summarized. Now give me your ANALYSIS — what does it all mean?\n\n"
        + "\n\n".join(items_text)
    )

    logger.info(f"Sending {len(summarized_items)} items to Claude Sonnet for analysis")

    try:
        client = anthropic.Anthropic(api_key=api_key)

        response = client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=2500,
            system=ANALYSIS_SYSTEM_PROMPT,
            messages=[{"role": "user", "content": user_message}],
        )

        raw_text = response.content[0].text.strip()

        # Parse JSON
        try:
            result = json.loads(raw_text)
        except json.JSONDecodeError:
            import re
            json_match = re.search(r"\{[\s\S]*\}", raw_text)
            if json_match:
                result = json.loads(json_match.group())
            else:
                logger.error("Failed to parse analysis response as JSON")
                result = {
                    "weekly_theme": "Analysis generation encountered an issue.",
                    "analysis_sections": [],
                    "connections": raw_text[:500],
                    "implications": {},
                    "hot_take": "",
                    "skills_radar": [],
                }

        # Log token usage
        input_tokens = response.usage.input_tokens
        output_tokens = response.usage.output_tokens
        logger.info(
            f"Analysis complete. Tokens: {input_tokens} in / {output_tokens} out "
            f"(~${(input_tokens * 3 + output_tokens * 15) / 1_000_000:.4f})"
        )

        return result

    except Exception as e:
        logger.error(f"Analysis generation failed: {e}")
        return {
            "weekly_theme": f"Analysis error: {str(e)}",
            "analysis_sections": [],
            "connections": "",
            "implications": {},
            "hot_take": "",
            "skills_radar": [],
        }
