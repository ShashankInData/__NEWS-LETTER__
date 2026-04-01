# AI Pulse

Personal AI/ML newsletter automation. Collects trending content from Reddit, arXiv, HuggingFace, Twitter/X, and tech blogs — summarises it, analyses it with Claude, and delivers a weekly digest to your email and Telegram. Also generates LinkedIn post drafts in your own writing voice.

Built by [Shashank Bodapati](https://www.linkedin.com/in/shashankbodapati) | AI Engineer | MSc Applied AI & Data Science

---

## What It Does

1. **Collects** top posts from AI/ML subreddits (via RSS, no API key needed), arXiv papers, HuggingFace daily papers, Twitter/X accounts (via Apify), and company tech blogs
2. **Ranks** content by topic relevance, engagement, novelty, and your personal preference history
3. **Summarises** each item using HuggingFace BART (free, runs via inference API)
4. **Analyses** the week's themes using Claude Sonnet — cross-story connections, implications, hot take, skills radar
5. **Delivers** a formatted digest via HTML email + Telegram
6. **Learns** your preferences — tap 👍/👎 on Telegram stories and the ranker adapts over time using ChromaDB + local embeddings

LinkedIn flow (on-demand):

1. **Drafts** 2 LinkedIn posts per week in your voice using OpenAI GPT-4o + a personal Content DNA profile
2. **Rewrites** any draft interactively based on your feedback

---

## Architecture

```text
Collect → Filter & Rank → Summarise (HF BART) → Analyse (Claude Sonnet) → Deliver (Email + Telegram)
           ↑                                                                        ↓
      ChromaDB memory                                                        👍/👎 feedback
      (novelty + preference)                                                 (updates ChromaDB)

On-demand:
Collect → Rank → Summarise → LinkedIn Drafts (GPT-4o) → Telegram + output/
```

---

## Project Structure

```text
ai-pulse/
├── collectors/
│   ├── base.py              # Abstract base class + ContentItem dataclass
│   ├── reddit.py            # Reddit via public RSS (no API key needed)
│   ├── arxiv_hf.py          # arXiv API + HuggingFace daily papers
│   ├── tech_blogs.py        # RSS feeds for OpenAI, Anthropic, Google AI, etc.
│   └── twitter.py           # Twitter/X via Apify or Nitter RSS fallback
├── processing/
│   ├── filter.py            # Dedup + memory enrichment entry point
│   ├── ranker.py            # Composite scoring (relevance + engagement + novelty + preference)
│   ├── hf_summarizer.py     # HuggingFace BART summarisation (free)
│   ├── analyst.py           # Claude Sonnet analysis — themes, implications, hot take
│   └── linkedin_drafter.py  # GPT-4o LinkedIn post generator using Content DNA
├── delivery/
│   ├── email_sender.py      # HTML email via SMTP
│   └── telegram_bot.py      # Telegram delivery + 👍/👎 inline buttons + feedback handler
├── memory/
│   └── chroma_store.py      # ChromaDB + sentence-transformers — novelty & preference memory
├── templates/
│   ├── newsletter_email.html  # HTML email template
│   └── telegram_format.py     # Telegram message formatters
├── config/
│   ├── settings.yaml        # Topic tags, sources, cron schedule
│   └── content_dna.yaml     # YOUR writing voice profile for LinkedIn drafts
├── main.py                  # Entry point — all pipeline modes
├── scheduler.py             # APScheduler cron runner
├── requirements.txt
├── Dockerfile
└── .env.example             # API keys template
```

---

## Quick Start

### 1. Clone and install

```bash
git clone https://github.com/ShashankInData/__NEWS-LETTER__
cd __NEWS-LETTER__
python -m venv venv
source venv/bin/activate   # Windows: venv\Scripts\activate
pip install -r requirements.txt
```

### 2. Set up your API keys

```bash
cp .env.example .env
```

Open `.env` and fill in your credentials. See [Required API Keys](#required-api-keys) below.

### 3. Configure your topics

Edit `config/settings.yaml` to set your topic tags, subreddits, Twitter accounts, and arXiv categories.

### 4. Personalise the LinkedIn voice (optional)

Edit `config/content_dna.yaml` to describe your writing style, tone, and content pillars. The more specific you are, the better the drafts.

### 5. Run

```bash
# Weekly newsletter pipeline (collect → summarise → analyse → deliver)
python main.py

# Generate LinkedIn drafts on-demand
python main.py --linkedin

# Rewrite a draft interactively
python main.py --rewrite

# Start the cron scheduler (runs newsletter every Sunday 9am + LinkedIn every Wednesday 10am)
python scheduler.py
```

---

## Required API Keys

| Key | Where to get it | Required? |
| --- | --------------- | --------- |
| `ANTHROPIC_API_KEY` | [console.anthropic.com](https://console.anthropic.com/) | Yes — analysis layer |
| `OPENAI_API_KEY` | [platform.openai.com](https://platform.openai.com/api-keys) | Yes — LinkedIn drafts |
| `TELEGRAM_BOT_TOKEN` | Message [@BotFather](https://t.me/botfather) on Telegram | Yes — delivery |
| `TELEGRAM_CHAT_ID` | Visit `https://api.telegram.org/bot<TOKEN>/getUpdates` after messaging your bot | Yes — delivery |
| `APIFY_API_TOKEN` | [apify.com](https://apify.com/) → API & Integrations | Optional — Twitter/X |
| `HF_API_TOKEN` | [huggingface.co/settings/tokens](https://huggingface.co/settings/tokens) | Optional — raises rate limits |
| `SMTP_HOST/USER/PASSWORD` | Gmail App Password or [Resend](https://resend.com) | Optional — email delivery |
| `TELEGRAM_WEBHOOK_URL` | Your public URL (see below) | Optional — enables 👍/👎 buttons |

Reddit uses **public RSS feeds** — no API key or account needed.

---

## 👍/👎 Feedback Loop (optional but recommended)

The memory layer learns your preferences over time. After a few weeks of feedback, the ranker starts surfacing content you historically engage with and suppressing what you skip.

To enable it, you need a public HTTPS URL for your webhook. The easiest way is [ngrok](https://ngrok.com):

```bash
# Terminal 1 — start the tunnel
ngrok http 8443
# Copy the https URL into .env as TELEGRAM_WEBHOOK_URL

# Terminal 2 — register with Telegram (run once per ngrok session)
python main.py --set-webhook

# Terminal 3 — keep the webhook server running
python main.py --webhook
```

Then run `python main.py` as normal. Each story in your Telegram digest will have 👍/👎 buttons. Tap them — preferences are stored locally in `memory/db/` (ChromaDB) and used on the next run.

> **Note:** ngrok free tier gives a new URL on each restart. Re-run `--set-webhook` when that happens. For a permanent URL, deploy to [Railway](https://railway.app) or use a Cloudflare Tunnel.

---

## Cost Model

| Component | Tool | Cost |
| --------- | ---- | ---- |
| Summarisation | HuggingFace BART (free inference API) | Free |
| Analysis | Claude Sonnet | ~$0.10–0.20 / run |
| LinkedIn drafts | OpenAI GPT-4o | ~$0.01–0.03 / run |
| Twitter/X | Apify pay-per-result | ~$0.25 / 1K tweets |
| Embeddings | sentence-transformers (local) | Free |
| Memory | ChromaDB (local) | Free |
| Reddit, arXiv, HF, Blogs | RSS / public APIs | Free |

**Estimated: ~$1–3/month** at weekly cadence with Twitter enabled.

---

## Tech Stack

Python 3.11+ · feedparser · arxiv · anthropic · openai · requests · chromadb · sentence-transformers · APScheduler · Jinja2 · PyYAML · python-dotenv

---

## Deployment

The scheduler and webhook server need a persistent process. Recommended options:

- **[Railway](https://railway.app)** — cheapest, simplest, persistent disk, permanent URL. Deploy from GitHub in one click.
- **Render** — similar to Railway, free tier available
- **VPS (Hetzner/DigitalOcean)** — most control, ~€4/month

Docker support is included (`Dockerfile`).
