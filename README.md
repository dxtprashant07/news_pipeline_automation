# Phase 1 — News Discovery Pipeline

Automatically scans NewsAPI, Reddit, RSS feeds, and Google Trends every 30 minutes.
Deduplicates, classifies, scores credibility, and stores results ready for Phase 2.

---

## Current Status

| Source | Status | Notes |
|---|---|---|
| RSS Feeds | Working | Fetches ~80 stories per run |
| NewsAPI | Needs key | Free tier: 100 req/day |
| Reddit | Needs credentials | Add to `.env` |
| Google Trends | Broken | API endpoint returns 404 — needs fix |

**DB as of last run:** 182 stories stored, all with `status = new`.

---

## Quick Start

### 1. Set up environment

```bash
cd files
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
```

### 2. Configure API keys

```bash
copy .env.example .env
```

Edit `.env` and fill in your keys:

| Key | Where to get it | Free tier |
|---|---|---|
| `NEWSAPI_KEY` | https://newsapi.org | 100 req/day |
| `REDDIT_CLIENT_ID` | https://www.reddit.com/prefs/apps | Yes |
| `REDDIT_CLIENT_SECRET` | Same as above | Yes |

Google Trends and RSS feeds need no API key.

### 3. Run once (fetch fresh stories)

```bash
python -m phase1_discovery --once
```

### 4. Check what was found

```bash
python check_stories.py
```

### 5. Start the scheduler (runs every 30 minutes)

```bash
python -m phase1_discovery
```

Press `Ctrl+C` to stop.

### 6. Check DB stats only

```bash
python -m phase1_discovery --stats
```

---

## Project Structure

```
files/
├── check_stories.py         # Quick script to browse the DB
├── news.db                  # SQLite database (auto-created)
├── requirements.txt
├── .env                     # Your API keys (not committed)
├── .env.example             # Template
└── phase1_discovery/
    ├── main.py              # Entry point logic
    ├── pipeline.py          # Orchestrates all stages
    ├── sources/             # One file per data source
    │   ├── google_trends.py
    │   ├── newsapi.py
    │   ├── reddit.py
    │   └── rss_feeds.py
    ├── processors/          # Processing stages in order
    │   ├── normalizer.py
    │   ├── sanitizer.py
    │   ├── deduplicator.py
    │   ├── classifier.py
    │   ├── credibility.py
    │   └── scorer.py
    ├── scheduler/
    │   └── runner.py        # APScheduler wrapper
    ├── storage/
    │   ├── models.py        # SQLAlchemy ORM models
    │   ├── database.py      # DB init and session factory
    │   └── repository.py    # CRUD operations
    ├── config/
    │   ├── settings.py      # Pydantic settings (reads .env)
    │   └── categories.py    # Category keywords + RSS feeds + subreddits
    ├── utils/
    │   ├── helpers.py       # URL hashing, normalization, truncation
    │   ├── logger.py        # Structured logging with secret redaction
    │   ├── retry.py         # Retry decorator with circuit breaker
    │   ├── rate_limiter.py  # Per-source rate limiting
    │   └── base.py          # BaseSource abstract class
    └── tests/
        ├── test_sources.py
        ├── test_processors.py
        └── test_storage.py
```

---

## Configuration

All settings live in `.env`:

| Variable | Default | Description |
|---|---|---|
| `NEWSAPI_KEY` | `""` | NewsAPI key |
| `REDDIT_CLIENT_ID` | `""` | Reddit app client ID |
| `REDDIT_CLIENT_SECRET` | `""` | Reddit app client secret |
| `SCHEDULER_INTERVAL_MINUTES` | `30` | How often to run |
| `MAX_STORIES_PER_RUN` | `100` | Cap per pipeline run |
| `MIN_CREDIBILITY_SCORE` | `40` | Stories below this are dropped |
| `GEO_FOCUS` | `IN` | `IN`, `US`, `GB`, or `GLOBAL` |
| `DATABASE_URL` | SQLite | Change to PostgreSQL if needed |

---

## Switching to PostgreSQL

```bash
# In .env:
DATABASE_URL=postgresql://user:password@localhost:5432/news_pipeline
```

No code changes needed — SQLAlchemy handles it.

---

## Running Tests

```bash
pytest phase1_discovery/tests/ -v
```

Tests use an in-memory SQLite DB — no setup needed.

---

## Adding a New Source

1. Create `sources/my_source.py`
2. Inherit from `BaseSource` (`utils/base.py`)
3. Implement `fetch() -> list[RawStory]`
4. Add it to the `self.sources` list in `pipeline.py`

---

## Data Flow

```
[Sources] -> [Normalizer] -> [Sanitizer] -> [Deduplicator]
          -> [Classifier] -> [CredibilityScorer] -> [PriorityScorer]
          -> [Database]   -> [Phase 2 queue]
```

Stories are stored with `status = "new"`. Phase 2 will pick them up and move them through:

```
new -> fact_checked -> written -> published
                              -> rejected
```

---

## Known Issues

- **Google Trends:** The API endpoint returns 404. The `google_trends.py` source needs updating to the new endpoint.
- **Reddit:** Requires valid `REDDIT_CLIENT_ID` and `REDDIT_CLIENT_SECRET` in `.env`.
- **Classifier accuracy:** Currently keyword-based — some stories are miscategorised (e.g. general news tagged as `technology`). A Claude API classifier is planned for Phase 2.
