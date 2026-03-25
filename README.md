# AI Pulse

Personal AI/ML newsletter automation — collects trending content from Reddit, arXiv, HuggingFace, and tech blogs, summarises it, and delivers a weekly digest to email and Telegram. Also generates LinkedIn post drafts in your own writing voice.

Built by [Shashank Bodapati](https://www.linkedin.com/in/shashankbodapati) | AI Engineer | MSc Applied AI & Data Science

---

## What it does

1. **Collects** top posts from AI/ML subreddits (read-only, via PRAW) + arXiv papers + HuggingFace daily papers + company tech blogs
2. **Filters** by topic relevance (RAG, LLMs, multi-agent, benchmarks, etc.) and deduplicates
3. **Summarises** each item using HuggingFace BART (free inference API)
4. **Analyses** the week's themes using Claude Sonnet — cross-story connections, implications, hot take
5. **Delivers** a formatted digest via HTML email + Telegram
6. **Drafts** LinkedIn posts in your voice using OpenAI gpt-4o + a personal Content DNA profile

---

## Reddit API usage

This project uses the [PRAW](https://praw.readthedocs.io/) library with **read-only OAuth** (`read` scope only).

- Accesses: `r/MachineLearning`, `r/LocalLLaMA`, `r/artificial`, `r/deeplearning`, `r/LangChain`
- Reads: post titles, URLs, upvote scores, comment counts — **no user data, no DMs, no account actions**
- Frequency: once per week via cron scheduler
- Rate limiting: PRAW's built-in compliance (max 60 req/min); ~5–10 calls per run
- Data storage: **none** — stateless pipeline, all data processed in memory and discarded after delivery
- Data sharing: **none** — not stored, not shared, not used for AI training

---

## Quick Start

```bash
git clone https://github.com/shashankbodapati/ai-pulse
cd ai-pulse
python -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate
pip install -r requirements.txt

cp .env.example .env
# Add your API keys to .env

python main.py                  # Run newsletter pipeline once
python main.py --linkedin       # Generate LinkedIn drafts
python main.py --rewrite        # Rewrite a draft interactively
python scheduler.py             # Start cron scheduler (VPS deployment)
```

---

## Configuration

| File                     | Purpose                          |
| ------------------------ | -------------------------------- |
| `config/settings.yaml`   | Topic tags, sources, cron schedule |
| `config/content_dna.yaml` | LinkedIn voice/persona profile  |
| `.env`                   | API keys (see `.env.example`)    |

---

## Architecture

```
Collect → Filter & Rank → Summarise (HF BART) → Analyse (Claude Sonnet) → Deliver (Email + Telegram)
                                                                         → LinkedIn Drafts (OpenAI gpt-4o)
```

See [PROJECT_PLAN.md](PROJECT_PLAN.md) for full design decisions and build phases.

---

## Tech Stack

Python 3.11+ | PRAW | feedparser | arxiv | anthropic | openai | python-telegram-bot | APScheduler | Jinja2

## Cost

~$5–12/month total (Apify for Twitter optional; Claude + OpenAI ~$1/month at weekly cadence)
