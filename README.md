# News Pipeline Automation

An autonomous 7-stage news publishing pipeline that discovers trending stories, fact-checks them, writes original AI-generated articles, and publishes them to WordPress — fully automated on a schedule.

---

## How It Works

```
[Discovery] → [Fact Check] → [AI Writing] → [Editor Review] → [Publish] → [Analytics]
```

| Stage | What it does |
|-------|-------------|
| **1+2 Discovery** | Fetches stories from RSS feeds, NewsAPI, Reddit every 30 min |
| **3 Verification** | Fact-checks each story against 3+ credible sources |
| **4 AI Writing** | Generates a full SEO-optimised article using Gemini / Claude / GPT |
| **5 Editor Dashboard** | Web UI to review, approve, or reject each draft |
| **6 Publishing** | Auto-publishes approved articles to WordPress, Buffer, Mailchimp |
| **7 Analytics** | Pulls GA4 + Search Console data, feeds performance back to discovery |

---

## Quick Start

### 1. Clone and set up environment

```bash
git clone https://github.com/dxtprashant07/news_pipeline_automation.git
cd news_pipeline_automation

python -m venv venv
venv\Scripts\activate        # Windows
# source venv/bin/activate   # Mac / Linux

pip install -r requirements.txt
```

### 2. Configure environment

```bash
copy .env.example .env       # Windows
# cp .env.example .env       # Mac / Linux
```

Fill in your API keys in `.env` (minimum required to start):

```env
NEWSAPI_KEY=your_key        # newsapi.org — free tier
GEMINI_API_KEY=your_key     # aistudio.google.com — free tier
```

Generate secure random keys for the dashboard (run this once, paste the output into `.env`):

```bash
python -c "import secrets; print('DASHBOARD_SECRET_KEY=' + secrets.token_hex(32))"
python -c "import secrets; print('DASHBOARD_API_KEY=' + secrets.token_hex(32))"
```

Copy the printed values directly into your `.env` file. These are random strings you generate yourself — there is no external service needed.

### 3. Run everything with one command

```bash
python manage.py start --dev
```

Open **http://127.0.0.1:8000** to see the editor dashboard.

---

## All Commands

```bash
python manage.py start        # Init DB + full pipeline + dashboard (one command)
python manage.py discover     # Fetch latest stories from all sources
python manage.py verify       # Fact-check new stories
python manage.py write        # Generate AI articles
python manage.py dashboard    # Start editor review dashboard
python manage.py publish      # Publish approved articles to WordPress
python manage.py analytics    # Collect GA4 + Search Console metrics
python manage.py status       # Print pipeline stats
python manage.py db-init      # Initialise or migrate the database
```

Add `--once` to any pipeline command to run once and exit instead of starting the scheduler.  
Add `--dev` to `start` or `dashboard` to enable hot-reload.

---

## Project Structure

```
news_pipeline_automation/
├── manage.py                   # Unified CLI entry point
├── Dockerfile
├── docker-compose.yml
├── requirements.txt
├── .env.example
│
├── core/                       # Shared across all stages
│   ├── config/settings.py      # All env vars in one place (Pydantic)
│   ├── db/
│   │   ├── models.py           # SQLAlchemy ORM — 5 models
│   │   ├── repository.py       # DB operations for all stages
│   │   └── session.py          # Engine, session factory, init_db
│   └── utils/
│       ├── logger.py           # Structured logging + secret redaction
│       ├── rate_limiter.py     # Per-source token bucket rate limiter
│       └── retry.py            # Retry decorator with circuit breaker
│
├── discovery/                  # Stage 1+2
│   ├── pipeline.py
│   ├── sources/                # rss.py, newsapi.py, reddit.py, google_trends.py
│   ├── processors/             # normalizer, sanitizer, deduplicator, classifier, credibility, scorer
│   └── config/categories.py   # RSS feeds, subreddits, category keywords
│
├── verification/               # Stage 3
│   ├── pipeline.py
│   └── fact_checker.py         # Bing Search primary + credibility score fallback
│
├── writing/                    # Stage 4
│   ├── pipeline.py
│   ├── ai_client.py            # Provider routing: Gemini / Claude / OpenAI
│   ├── writer.py               # Article generation
│   ├── seo_optimizer.py        # Meta title, description, keywords, schema markup
│   └── image_generator.py      # DALL-E image generation (optional)
│
├── dashboard/                  # Stage 5
│   ├── app.py                  # FastAPI app
│   ├── auth.py                 # API key authentication
│   ├── routes/                 # articles.py, stats.py
│   ├── schemas/article.py      # Pydantic request/response schemas
│   └── templates/index.html    # Vanilla JS editor UI
│
├── publisher/                  # Stage 6
│   ├── pipeline.py
│   ├── wordpress.py            # WordPress REST API
│   ├── social/buffer.py        # Buffer social distribution
│   └── newsletter/mailchimp.py # Mailchimp campaigns
│
├── analytics/                  # Stage 7
│   ├── collector.py            # GA4 + Search Console data pull
│   └── scorer.py               # Feeds performance back to discovery priority
│
├── scheduler/
│   └── runner.py               # APScheduler — all pipeline jobs
│
└── tests/
    ├── conftest.py             # In-memory SQLite fixtures
    ├── test_discovery/
    ├── test_verification/
    ├── test_writing/
    ├── test_dashboard/
    └── test_publisher/
```

---

## API Keys

| Key | Stage | Where to get | Cost |
|-----|-------|-------------|------|
| `NEWSAPI_KEY` | Discovery | newsapi.org | Free: 100 req/day |
| `GEMINI_API_KEY` | AI Writing | aistudio.google.com | Free tier |
| `REDDIT_CLIENT_ID` + `SECRET` | Discovery | reddit.com/prefs/apps | Free |
| `BING_SEARCH_API_KEY` | Verification | portal.azure.com | Free: 1,000/month |
| `ANTHROPIC_API_KEY` | AI Writing (alt) | console.anthropic.com | Paid |
| `OPENAI_API_KEY` | AI Writing (alt) | platform.openai.com | Paid |
| `WORDPRESS_APP_PASSWORD` | Publishing | WordPress admin panel | Free |
| `BUFFER_ACCESS_TOKEN` | Social | buffer.com/developers | Free tier |
| `MAILCHIMP_API_KEY` | Newsletter | mailchimp.com | Free: 500 contacts |
| `GA4_PROPERTY_ID` | Analytics | analytics.google.com | Free |

---

## AI Model Configuration

The pipeline routes to different AI providers based on the model name prefix:

```env
ARTICLE_MODEL=gemini-2.5-flash   # uses GEMINI_API_KEY
# ARTICLE_MODEL=claude-sonnet-4-6  # uses ANTHROPIC_API_KEY
# ARTICLE_MODEL=gpt-4o             # uses OPENAI_API_KEY
```

---

## Database

SQLite by default. Switch to PostgreSQL for production — one line change:

```env
DATABASE_URL=postgresql://user:password@localhost:5432/news_pipeline
```

Install the driver:
```bash
pip install psycopg2-binary
```

Then run `python manage.py db-init` — all tables are created automatically.

---

## Docker Deployment

```bash
# Build and start both dashboard + pipeline scheduler
docker-compose up --build -d

# View logs
docker-compose logs -f
```

Make sure your `.env` is filled in before running Docker.

---

## Deploying to a Server (DigitalOcean / any VPS)

```bash
# On your server
git clone https://github.com/dxtprashant07/news_pipeline_automation.git
cd news_pipeline_automation
cp .env.example .env    # fill in your keys
docker-compose up -d
```

The dashboard will be available on port 8000. Put nginx in front for SSL.

---

## Adding More News Sources

Edit [discovery/config/categories.py](discovery/config/categories.py) to add RSS feeds:

```python
RSS_FEEDS = [
    {"url": "https://www.bbc.com/news/rss.xml",   "category": "general"},
    {"url": "https://indianexpress.com/feed/",     "category": "general"},
    # add as many as you want
]
```

---

## Running Tests

```bash
pytest tests/ -v
```

Tests use an in-memory SQLite database — no setup required.

---

## Configuration Reference

| Variable | Default | Description |
|----------|---------|-------------|
| `DATABASE_URL` | `sqlite:///./news.db` | Database connection string |
| `GEO_FOCUS` | `IN` | `IN`, `US`, `GB`, or `GLOBAL` |
| `ARTICLE_MODEL` | `gemini-2.5-flash` | AI model for writing |
| `ARTICLE_WORD_COUNT` | `700` | Target word count per article |
| `MIN_CREDIBILITY_SCORE` | `40` | Stories below this are dropped |
| `CREDIBILITY_THRESHOLD` | `75` | Minimum score to pass fact-check |
| `MIN_VERIFICATION_SOURCES` | `3` | Sources required to verify a story |
| `DISCOVERY_INTERVAL_MINUTES` | `30` | How often discovery runs |
| `PIPELINE_INTERVAL_MINUTES` | `60` | How often verify+write runs |
| `DASHBOARD_HOST` | `127.0.0.1` | Dashboard bind address |
| `DASHBOARD_PORT` | `8000` | Dashboard port |
| `IMAGE_GENERATION_ENABLED` | `false` | Enable DALL-E image generation |
