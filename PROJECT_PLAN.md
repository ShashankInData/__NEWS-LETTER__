# AI Pulse — Project Plan & Build Log

## What This Is

A personal AI/ML newsletter automation pipeline. Runs weekly to collect, filter, summarise, and deliver trending AI content — then learns your taste over time via 👍/👎 feedback.

---

## Architecture

```text
┌──────────────────────────────────────────────────────────────┐
│                    SCHEDULER (APScheduler)                    │
│         Newsletter: Sunday 9am  |  LinkedIn: Wednesday 10am  │
└───────────────────────────┬──────────────────────────────────┘
                            │
                            ▼
┌──────────────────────────────────────────────────────────────┐
│                     COLLECT (collectors/)                     │
│                                                              │
│  Reddit (RSS)  │  Twitter/X (Apify)  │  arXiv  │  HF Papers │
│                       Tech Blogs (RSS)                       │
└───────────────────────────┬──────────────────────────────────┘
                            │ raw items
                            ▼
┌──────────────────────────────────────────────────────────────┐
│               FILTER & RANK (processing/)                    │
│                                                              │
│  1. Deduplicate (URL + title)                                │
│  2. Enrich with ChromaDB memory:                             │
│       novelty_score  — how similar to past content?          │
│       pref_score     — how similar to 👍'd content?          │
│  3. Composite score:                                         │
│       topic tags × 10  +  engagement  +  novelty × 8        │
│       +  preference × 12                                     │
│  4. Source diversity cap (no single source > 1/3 of slots)   │
└───────────────────────────┬──────────────────────────────────┘
                            │ top 15 items
                            ▼
┌──────────────────────────────────────────────────────────────┐
│              SUMMARISE (processing/hf_summarizer.py)         │
│  HuggingFace BART (facebook/bart-large-cnn) — free           │
│  Falls back to extractive summary if API is down             │
└───────────────────────────┬──────────────────────────────────┘
                            │ summarised items
                            ▼
┌──────────────────────────────────────────────────────────────┐
│               ANALYSE (processing/analyst.py)                │
│  Claude Sonnet — the expensive call, used once per run       │
│  Outputs: weekly theme, connections, implications,           │
│           hot take, skills radar                             │
└──────────┬────────────────────────────────┬─────────────────┘
           │                                │
           ▼                                ▼
┌────────────────────┐          ┌───────────────────────────┐
│  EMAIL (SMTP)      │          │  TELEGRAM                 │
│  HTML digest       │          │  Per-story messages with  │
│  Jinja2 template   │          │  👍/👎 inline buttons     │
└────────────────────┘          └───────────────┬───────────┘
                                                │ button tap
                                                ▼
┌──────────────────────────────────────────────────────────────┐
│                  LEARN (memory/chroma_store.py)               │
│  Telegram callback → webhook server (main.py --webhook)      │
│  record_feedback(item_id, score=+1/-1)                       │
│  ChromaDB + sentence-transformers (all-MiniLM-L6-v2)         │
│  Persists locally in memory/db/ — never wiped                │
└──────────────────────────────────────────────────────────────┘

On-demand LinkedIn flow:
Collect → Rank → Summarise → GPT-4o drafts → Telegram + output/
```

---

## Tech Stack

| Component | Tool | Cost |
| --------- | ---- | ---- |
| Reddit | Public RSS (feedparser) | Free |
| arXiv | arxiv Python package | Free |
| HuggingFace papers | HF Daily Papers API | Free |
| Tech blogs | RSS (feedparser) | Free |
| Twitter/X | Apify pay-per-result | ~$0.25/1K tweets |
| Summarisation | HuggingFace BART (inference API) | Free |
| Analysis | Claude Sonnet (Anthropic) | ~$0.10–0.20/run |
| LinkedIn drafts | OpenAI GPT-4o | ~$0.01–0.03/run |
| Embeddings | sentence-transformers (local) | Free |
| Memory | ChromaDB (local persistent) | Free |
| Email | SMTP / Gmail App Password | Free |
| Telegram | python-telegram-bot + webhook | Free |
| Scheduling | APScheduler | Free |

**Estimated total: ~$1–3/month** at weekly cadence.

---

## File Map

```text
collectors/
  base.py           ContentItem dataclass + BaseCollector ABC
  reddit.py         Reddit RSS (no API key — feedparser)
  arxiv_hf.py       arXiv API + HuggingFace daily papers
  tech_blogs.py     RSS feeds for OpenAI, Anthropic, Google AI, Meta, Mistral
  twitter.py        Apify actor (kaitoeasyapi/twitter-x-data-tweet-scraper-pay-per-result-cheapest)
                    Fallback: Nitter RSS

processing/
  filter.py         Entry point: dedup → enrich (ChromaDB) → rank
  ranker.py         Composite scoring + source diversity
  hf_summarizer.py  HF BART summarisation + extractive fallback
  analyst.py        Claude Sonnet analysis (one call per run)
  linkedin_drafter.py  GPT-4o post generation using content_dna.yaml

delivery/
  email_sender.py   SMTP HTML email
  telegram_bot.py   Delivery + send_newsletter_with_feedback() + handle_feedback_update()

memory/
  chroma_store.py   store_items(), get_novelty_and_preference(), record_feedback()
  db/               ChromaDB persistent storage (gitignored — personal to each user)

templates/
  newsletter_email.html   HTML email template (Jinja2)
  telegram_format.py      format_newsletter(), format_newsletter_header(),
                          format_item_with_buttons(), format_single_draft()

config/
  settings.yaml     Topic tags, source configs, cron schedule
  content_dna.yaml  Personal writing voice profile (persona, tone, structure, language)

main.py             Entry point — run_pipeline(), run_linkedin_pipeline(),
                    run_rewrite_mode(), run_webhook_server(), set_telegram_webhook()
scheduler.py        APScheduler cron runner
app.py              Gradio UI (run locally or deploy to Railway alongside pipeline)
```

---

## Key Decisions

| Decision | Choice | Reason |
| -------- | ------ | ------ |
| Reddit scraping | Public RSS via feedparser | No API key needed, PRAW requires OAuth |
| Twitter | Apify pay-per-result | Official API too expensive; Nitter RSS as free fallback |
| Summarisation model | HF BART (free inference API) | Saves LLM tokens for actual reasoning |
| Analysis LLM | Claude Sonnet | One call per run — quality over cost |
| LinkedIn drafts LLM | OpenAI GPT-4o | Separate concern, good instruction following |
| Memory/ranking | ChromaDB + sentence-transformers | Local, free, persistent, no external service |
| Feedback mechanism | Telegram inline buttons + webhook | Natural in-flow — no separate UI needed |
| Deployment | Railway (persistent VPS-like) | Scheduler + webhook need always-on process + stable URL |
| LinkedIn publishing | Manual copy-paste | No personal profile API; automation risks account ban |

---

## Build Phases (completed)

### Phase 1 — Core pipeline

Reddit (PRAW → switched to RSS) + arXiv + HF papers + Tech blogs → filter → HF BART summarise → Claude Sonnet analyse → Email + Telegram deliver

### Phase 2 — Twitter/X

Apify integration with `kaitoeasyapi` actor. Nitter RSS fallback available via `settings.yaml`.

### Phase 3 — LinkedIn draft generator

GPT-4o + `content_dna.yaml` persona profile. Three post types: hot take, project showcase, geopolitical analysis. Interactive rewrite mode (`--rewrite`).

### Phase 4 — Memory & personalisation

ChromaDB + sentence-transformers (`all-MiniLM-L6-v2`, runs locally). Two collections:

- `content_history` — embeddings of all past items for novelty scoring
- `preferences` — 👍/👎 signals for preference scoring

Ranker incorporates both. Webhook server receives Telegram callback queries and writes to ChromaDB.

---

## What's Next (possible)

- **Railway deployment** — permanent URL solves the ngrok-per-session problem for the webhook
- **Gradio UI** (`app.py` exists) — on-demand pipeline trigger + memory stats viewer, runs on Railway alongside the scheduler
- **Email HTML polish** — the template works but could be improved visually
- **More sources** — newsletters (Substack RSS), YouTube transcripts, podcasts
