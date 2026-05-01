"""
Content categories with keywords used by the classifier.
Add/remove categories and keywords to match your news site's focus.
"""

CATEGORIES: dict[str, list[str]] = {
    "technology": [
        "ai", "artificial intelligence", "machine learning", "startup",
        "software", "hardware", "app", "tech", "robot", "chip", "semiconductor",
        "cybersecurity", "hack", "data breach", "cloud", "5g", "smartphone",
        "electric vehicle", "ev", "spacex", "nasa", "satellite",
    ],
    "finance": [
        "stock", "market", "economy", "gdp", "inflation", "rbi", "sebi",
        "rupee", "dollar", "crypto", "bitcoin", "ethereum", "nse", "bse",
        "sensex", "nifty", "ipo", "fund", "interest rate", "bank", "loan",
        "budget", "tax", "fiscal", "revenue", "profit", "earnings",
    ],
    "politics": [
        "government", "parliament", "minister", "election", "vote", "policy",
        "law", "bill", "court", "supreme court", "modi", "opposition",
        "congress", "bjp", "treaty", "geopolitics", "sanction", "president",
    ],
    "sports": [
        "cricket", "ipl", "bcci", "football", "fifa", "tennis", "olympics",
        "hockey", "kabaddi", "badminton", "wrestling", "champion", "tournament",
        "match", "series", "player", "team", "goal", "wicket",
    ],
    "health": [
        "health", "hospital", "disease", "virus", "vaccine", "medicine",
        "doctor", "drug", "clinical", "fda", "who", "pandemic", "cancer",
        "mental health", "nutrition", "fitness", "surgery", "research",
    ],
    "business": [
        "company", "merger", "acquisition", "ceo", "billion", "revenue",
        "layoff", "hiring", "expansion", "product launch", "brand",
        "ecommerce", "amazon", "flipkart", "reliance", "tata", "infosys",
        "wipro", "entrepreneur", "funding", "series a", "unicorn",
    ],
    "science": [
        "research", "study", "discovery", "scientist", "experiment",
        "climate", "environment", "space", "planet", "asteroid", "gene",
        "dna", "quantum", "physics", "chemistry", "biology", "fossil",
    ],
    "entertainment": [
        "movie", "film", "bollywood", "ott", "netflix", "amazon prime",
        "music", "album", "celebrity", "award", "oscar", "grammy",
        "web series", "actor", "director", "box office",
    ],
}

# Subreddits to scan per category
REDDIT_SUBREDDITS: dict[str, list[str]] = {
    "technology": ["technology", "tech", "artificial", "MachineLearning"],
    "finance":    ["investing", "IndiaInvestments", "CryptoCurrency", "stocks"],
    "politics":   ["india", "worldnews", "geopolitics"],
    "sports":     ["cricket", "ipl", "soccer", "sports"],
    "health":     ["health", "medicine", "science"],
    "business":   ["business", "startups", "IndiaStartups"],
    "science":    ["science", "space", "technology"],
    "entertainment": ["bollywood", "movies", "entertainment"],
}

# RSS feeds to monitor
RSS_FEEDS: list[dict] = [
    {"url": "https://feeds.feedburner.com/ndtvnews-top-stories",      "category": "general"},
    {"url": "https://timesofindia.indiatimes.com/rssfeedstopstories.cms", "category": "general"},
    {"url": "https://www.thehindu.com/news/feeder/default.rss",        "category": "general"},
    {"url": "https://techcrunch.com/feed/",                            "category": "technology"},
    {"url": "https://feeds.feedburner.com/venturebeat/SZYF",           "category": "technology"},
    {"url": "https://economictimes.indiatimes.com/markets/rssfeeds/1977021501.cms", "category": "finance"},
]

DEFAULT_CATEGORY = "general"
