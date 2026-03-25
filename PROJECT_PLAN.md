# AI Pulse — Personal AI/ML Newsletter & LinkedIn Draft Automation

## What This Does
A Python automation that runs weekly (or daily) to:
1. **Scrape** trending AI/ML content from Reddit, Twitter/X, arXiv, HuggingFace, and tech blogs
2. **Filter** by your topic tags (RAG, fine-tuning, agents, benchmarks, new models, etc.)
3. **Summarize** into a clean newsletter digest
4. **Email** it to you
5. **Send** it to your Telegram
6. **Optionally** generate a LinkedIn post draft in your voice (Content DNA)
7. Runs on a server — laptop off, still works

---

## Architecture

```
┌─────────────────────────────────────────────────────┐
│                   CRON (weekly/daily)                │
└──────────────────────┬──────────────────────────────┘
                       │
                       ▼
┌─────────────────────────────────────────────────────┐
│              SCRAPER LAYER (collectors)              │
│                                                     │
│  ┌───────────┐ ┌──────────┐ ┌────────────────────┐ │
│  │  Reddit    │ │ Twitter  │ │ arXiv / HF Papers  │ │
│  │  (PRAW)   │ │ (Apify / │ │ (RSS / API)        │ │
│  │           │ │  RSS)    │ │                    │ │
│  └───────────┘ └──────────┘ └────────────────────┘ │
│  ┌───────────────────────────────────────────────┐  │
│  │  Tech Blogs (OpenAI, Anthropic, DeepMind)     │  │
│  │  (RSS feeds / web scraping)                   │  │
│  └───────────────────────────────────────────────┘  │
└──────────────────────┬──────────────────────────────┘
                       │ raw posts/articles
                       ▼
┌─────────────────────────────────────────────────────┐
│              FILTER & RANK                          │
│  - Match against your topic tags                    │
│  - Deduplicate                                      │
│  - Rank by engagement / relevance                   │
└──────────────────────┬──────────────────────────────┘
                       │ filtered content
                       ▼
┌─────────────────────────────────────────────────────┐
│              SUMMARIZER (Claude Haiku)               │
│  - Per-item summary (2-3 sentences)                 │
│  - Newsletter assembly (grouped by category)        │
└──────────┬───────────────────────┬──────────────────┘
           │                       │
           ▼                       ▼
┌──────────────────┐   ┌─────────────────────────────┐
│  EMAIL (SMTP)    │   │  TELEGRAM BOT               │
│  - HTML digest   │   │  - Formatted digest message  │
│  - To your inbox │   │  - To your chat             │
└──────────────────┘   └─────────────────────────────┘
                       │
                       ▼ (optional, on-demand)
┌─────────────────────────────────────────────────────┐
│     LINKEDIN DRAFT GENERATOR (Claude Sonnet)        │
│  - Uses your Content DNA prompt                     │
│  - Generates 1-2 post drafts                        │
│  - Sent via Telegram for review                     │
│  - You copy-paste manually to LinkedIn              │
└─────────────────────────────────────────────────────┘
```

---

## Tech Stack

| Component         | Tool                              | Cost          |
|--------------------|-----------------------------------|---------------|
| Language           | Python 3.11+                      | Free          |
| Reddit scraping    | PRAW (Reddit API)                 | Free          |
| Twitter/X scraping | Option A: Apify Twitter Scraper   | ~$5/mo        |
|                    | Option B: Nitter RSS (free, fragile) | Free       |
|                    | Option C: socialdata.tools API    | Pay-per-call  |
| arXiv              | arxiv Python package / RSS        | Free          |
| HuggingFace Papers | HF Daily Papers API / RSS         | Free          |
| Tech Blogs         | RSS feeds (feedparser)            | Free          |
| Summarization      | Claude Haiku via Anthropic API    | ~$0.10/run    |
| LinkedIn drafts    | Claude Sonnet via Anthropic API   | ~$0.15/run    |
| Email              | SMTP (Gmail App Password or Resend) | Free       |
| Telegram           | python-telegram-bot               | Free          |
| Scheduling         | APScheduler or system cron        | Free          |
| Hosting            | Railway / Render / Hetzner VPS    | $0-7/mo       |
| Config             | .env + YAML for topic tags        | Free          |

**Estimated total cost: $5-12/month** (mostly Apify if you use it for Twitter)

---

## Project Structure

```
ai-pulse/
├── config/
│   ├── settings.yaml          # Topic tags, source configs, schedule
│   └── content_dna.yaml       # Your writing voice profile for LinkedIn drafts
├── collectors/
│   ├── __init__.py
│   ├── base.py                # Abstract base collector
│   ├── reddit.py              # PRAW-based Reddit collector
│   ├── twitter.py             # Twitter/X collector (Apify or RSS)
│   ├── arxiv_hf.py            # arXiv + HuggingFace papers
│   └── tech_blogs.py          # RSS feed collector for company blogs
├── processing/
│   ├── __init__.py
│   ├── filter.py              # Topic matching & deduplication
│   ├── ranker.py              # Engagement/relevance ranking
│   └── summarizer.py          # Claude Haiku summarization
├── delivery/
│   ├── __init__.py
│   ├── email_sender.py        # SMTP email with HTML template
│   ├── telegram_bot.py        # Telegram delivery + command handling
│   └── linkedin_drafter.py    # Claude Sonnet LinkedIn post generator
├── templates/
│   ├── newsletter_email.html  # HTML email template
│   └── telegram_format.py     # Telegram message formatter
├── main.py                    # Entry point — orchestrates the pipeline
├── scheduler.py               # APScheduler setup for cron-like runs
├── requirements.txt
├── .env.example               # API keys template
├── Dockerfile                 # For deployment
└── README.md
```

---

## Configuration (settings.yaml)

```yaml
# Topic tags — content must match at least one to be included
topic_tags:
  - LLM fine-tuning
  - RAG applications
  - multi-agent systems
  - new model releases
  - benchmarks
  - prompt engineering
  - computer vision
  - LangChain
  - LangGraph
  - CrewAI
  - open source models
  - AI agents
  - MLOps
  - vector databases

# Sources
sources:
  reddit:
    subreddits:
      - MachineLearning
      - LocalLLaMA
      - artificial
      - deeplearning
      - LangChain
    top_n: 20  # top posts to fetch per subreddit
    time_filter: week  # day, week, month

  twitter:
    method: apify  # apify | nitter_rss
    accounts:
      - "@kaborepat"
      - "@ylecun"
      - "@AndrewYNg"
      - "@sama"
      - "@ClementDelworAI"
      - "@_jasonwei"
      - "@hardmaru"
      # Add your own follows
    search_terms:
      - "LLM fine-tuning"
      - "RAG pipeline"
      - "new AI model"

  arxiv:
    categories:
      - cs.AI
      - cs.CL
      - cs.LG
      - cs.CV
    max_results: 30

  huggingface:
    daily_papers: true

  tech_blogs:
    rss_feeds:
      - https://openai.com/blog/rss.xml
      - https://www.anthropic.com/research/rss.xml
      - https://blog.google/technology/ai/rss/
      - https://ai.meta.com/blog/rss/
      - https://mistral.ai/feed.xml

# Delivery
delivery:
  email:
    to: "your-email@gmail.com"
    from: "your-sender@gmail.com"
  telegram:
    chat_id: "your-chat-id"

# Schedule
schedule:
  newsletter: "every sunday 9am"
  linkedin_draft: "every wednesday 10am"
```

---

## Prerequisites — What You Need Before Coding

### Accounts & API Keys (get these first)
1. **Anthropic API key** — you likely have this already
2. **Reddit API credentials** — go to reddit.com/prefs/apps, create a "script" app, get client_id + client_secret
3. **Twitter/X scraping** — sign up for Apify free tier (or find Nitter RSS endpoints)
4. **Telegram Bot** — message @BotFather on Telegram, create bot, get token, get your chat_id
5. **Email SMTP** — Gmail App Password (Settings > 2FA > App Passwords) or sign up for Resend (free tier)
6. **Hosting account** — Railway.app (free tier with $5 credit) or Render.com (free tier)

### Local Setup
```bash
mkdir ai-pulse && cd ai-pulse
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate
pip install praw feedparser arxiv anthropic python-telegram-bot apscheduler jinja2 pyyaml python-dotenv requests
```

---

## Build Order (Phase by Phase)

### Phase 1: Reddit + arXiv collector → Summarize → Email (Week 1)
- Get Reddit and arXiv scraping working
- Filter by topic tags
- Summarize with Claude Haiku
- Send email digest
- **This alone is useful. Ship it.**

### Phase 2: Add Telegram delivery (Week 1-2)
- Set up Telegram bot
- Format and send digest via Telegram
- Add `/digest` command to trigger on-demand

### Phase 3: Add Twitter + Tech Blogs (Week 2)
- Integrate Apify or Nitter RSS for Twitter
- Add RSS parsing for tech blogs
- Merge all sources into unified pipeline

### Phase 4: LinkedIn draft generator (Week 3)
- Create Content DNA prompt template
- Generate 1-2 LinkedIn post drafts per week
- Send drafts to Telegram for review
- You copy-paste to LinkedIn

### Phase 5: Deploy & schedule (Week 3)
- Dockerize
- Deploy to Railway/Render
- Set up cron schedule
- Test end-to-end

### Phase 6 (Future): Jarvis expansion
- Add job alert agents
- Add more Telegram commands
- Add content publishing automation
- This becomes your Jarvis foundation

---

## Key Decisions Made

| Decision | Choice | Reason |
|----------|--------|--------|
| Build approach | Python code, not n8n/Make | Portfolio value, full control, you know the stack |
| Twitter scraping | Start with Apify, fallback to Nitter RSS | Official API too expensive, Apify is reliable |
| LinkedIn posting | Manual copy-paste from drafts | No personal profile API, automation risks account ban |
| LLM | Claude Haiku (summaries) + Sonnet (drafts) | Cost-optimized, you know the API |
| Hosting | Railway or Render free tier | Always-on, no laptop dependency, free to start |
| Newsletter delivery | Email + Telegram both | You asked for both |
