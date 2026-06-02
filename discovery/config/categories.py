"""
Content categories, keywords, subreddits, RSS feeds, and Twitter accounts.
CATEGORY_RULES drives the weighted classifier -- edit this to tune accuracy.
"""

# ── Weighted classification rules ─────────────────────────────────────────────
#
# Each category has three tiers:
#   "high"   (3 pts): highly specific terms rarely found outside this category
#   "medium" (2 pts): fairly specific terms, occasional overlap
#   "low"    (1 pt):  generic indicator words, only count when others also fire
#   "sources": source_name substrings that give a +6 bonus (e.g. "techcrunch")
#
# Single-word keywords use whole-word matching (\b boundaries).
# Multi-word phrases use simple substring match (already specific enough).
# Title hits are weighted 3x over summary hits.
# Minimum score of 4 required to classify; else falls back to DEFAULT_CATEGORY.

CATEGORY_RULES: dict[str, dict] = {

    "technology": {
        "high": [
            "artificial intelligence", "machine learning", "deep learning",
            "neural network", "large language model", "generative ai", "llm",
            "chatgpt", "openai", "anthropic", "gemini", "mistral",
            "semiconductor", "microchip", "transistor", "gpu", "tpu",
            "cybersecurity", "ransomware", "data breach", "malware", "phishing",
            "zero-day", "encryption", "firewall",
            "open source", "github", "saas", "devops", "kubernetes", "docker",
            "cloud computing", "aws", "azure", "google cloud",
            "5g", "broadband", "wi-fi 7", "fiber optic",
            "electric vehicle", "self-driving", "autonomous vehicle",
            "augmented reality", "virtual reality", "metaverse",
            "quantum computing", "edge computing", "iot",
            "spacex", "rocket launch", "mars mission", "moon landing",
            "drone technology", "robotics",
        ],
        "medium": [
            "software", "hardware", "smartphone", "iphone", "android",
            "laptop", "tablet", "wearable", "processor", "nvidia", "intel", "amd",
            "apple", "microsoft", "google", "meta platforms", "twitter",
            "app store", "play store", "operating system", "update", "upgrade",
            "startup", "tech company", "silicon valley", "tech giant",
            "satellite", "telecom", "isro", "nasa",
            "data center", "server", "bandwidth", "latency",
            "programming", "developer", "algorithm", "code", "python", "javascript",
            "digital", "automation", "technology",
        ],
        "low": [
            "tech", "app", "platform", "launch", "release", "version",
            "device", "chip", "network", "internet", "online",
        ],
        "sources": [
            "techcrunch", "verge", "wired", "ars technica", "engadget",
            "venturebeat", "gadgetsnow", "91mobiles", "gizmodo",
            "reddit/r/technology", "reddit/r/machinelearning",
            "twitter/@techcrunch", "twitter/@verge", "twitter/@wired",
        ],
    },

    "finance": {
        "high": [
            "stock market", "stock exchange", "sensex", "nifty 50", "nse", "bse",
            "nasdaq", "dow jones", "s&p 500", "ftse", "nikkei",
            "rbi", "sebi", "reserve bank", "monetary policy", "repo rate",
            "inflation rate", "gdp growth", "fiscal deficit", "current account",
            "bitcoin", "ethereum", "cryptocurrency", "crypto market", "defi",
            "nft", "blockchain", "altcoin",
            "ipo", "initial public offering", "mutual fund", "etf",
            "interest rate hike", "interest rate cut", "federal reserve", "fed rate",
            "rupee depreciation", "dollar index", "forex", "exchange rate",
            "bond yield", "treasury", "sovereign debt",
            "quarterly earnings", "quarterly results", "eps", "ebitda",
        ],
        "medium": [
            "stock", "share price", "market cap", "valuation", "equity",
            "portfolio", "investment", "investor", "dividend",
            "bull market", "bear market", "market rally", "market crash",
            "rupee", "dollar", "yen", "euro", "pound",
            "bank", "banking", "nbfc", "insurance", "pension",
            "tax", "gst", "income tax", "tax relief", "budget",
            "profit", "revenue", "earnings", "loss", "turnover",
            "funding", "venture capital", "private equity",
            "trade war", "tariff", "import duty", "export",
        ],
        "low": [
            "economy", "economic", "finance", "financial", "market",
            "capital", "fund", "growth", "recession",
        ],
        "sources": [
            "economictimes", "moneycontrol", "livemint", "bloomberg",
            "reuters finance", "cnbc", "financial express",
            "reddit/r/investing", "reddit/r/indiaInvestments",
            "twitter/@economictimes", "twitter/@moneycontrol", "twitter/@livemint",
        ],
    },

    "politics": {
        "high": [
            "lok sabha", "rajya sabha", "parliament session", "budget session",
            "prime minister modi", "narendra modi", "rahul gandhi", "amit shah",
            "bjp", "indian national congress", "aam aadmi party", "aap", "shiv sena",
            "election commission", "general election", "by-election", "vote count",
            "exit poll", "opinion poll", "constituency",
            "supreme court verdict", "high court judgment", "cbi", "enforcement directorate",
            "geopolitics", "united nations", "nato", "g20 summit", "g7",
            "ceasefire", "sanctions", "diplomatic", "bilateral talks",
            "president of india", "vice president", "governor",
        ],
        "medium": [
            "government", "parliament", "minister", "ministry",
            "chief minister", "opposition", "ruling party", "coalition",
            "election", "vote", "voting", "ballot", "candidate",
            "policy", "legislation", "bill passed", "ordinance", "amendment",
            "court", "verdict", "judgment", "fir", "arrest", "bail",
            "protest", "rally", "agitation", "strike",
            "foreign policy", "diplomacy", "treaty", "agreement",
            "defence", "military", "army", "border",
        ],
        "low": [
            "political", "politician", "law", "legal", "rights",
            "democracy", "constitution", "federal", "state",
        ],
        "sources": [
            "ndtv politics", "the hindu politics", "india today",
            "republic", "print", "wire",
            "reddit/r/india", "reddit/r/worldnews",
            "twitter/@BJP4India", "twitter/@INCIndia",
        ],
    },

    "sports": {
        "high": [
            "indian premier league", "ipl 2024", "ipl 2025", "bcci",
            "test match", "one day international", "odi", "t20 world cup",
            "virat kohli", "rohit sharma", "ms dhoni", "jasprit bumrah",
            "wimbledon", "us open", "french open", "australian open", "grand slam",
            "fifa world cup", "champions league", "premier league", "la liga",
            "olympic games", "commonwealth games", "asian games",
            "pv sindhu", "neeraj chopra", "mirabai chanu",
            "world cup final", "match result", "scorecard", "wickets",
        ],
        "medium": [
            "cricket", "football", "tennis", "badminton", "hockey",
            "kabaddi", "wrestling", "boxing", "swimming", "athletics",
            "championship", "tournament", "league", "series", "cup",
            "match", "game", "squad", "team", "player", "coach",
            "goal", "wicket", "century", "hat-trick", "penalty",
            "transfer", "contract", "draft", "auction",
            "medal", "gold medal", "silver medal", "bronze medal",
        ],
        "low": [
            "sport", "sports", "win", "defeat", "victory", "champion",
            "score", "innings", "quarter", "final", "semi-final",
        ],
        "sources": [
            "espncricinfo", "cricbuzz", "bcci", "sportskeeda",
            "goal.com", "skysports", "bleacher report",
            "reddit/r/cricket", "reddit/r/ipl", "reddit/r/soccer",
            "twitter/@bcci", "twitter/@ipl", "twitter/@espncricinfo",
        ],
    },

    "health": {
        "high": [
            "clinical trial", "randomised controlled trial", "peer-reviewed",
            "cancer treatment", "cancer research", "chemotherapy", "immunotherapy",
            "covid-19", "coronavirus", "mpox", "ebola", "dengue outbreak",
            "vaccine rollout", "vaccination drive", "booster dose",
            "fda approval", "dcgi approval", "drug approval",
            "mental health crisis", "depression treatment", "anxiety disorder",
            "aiims", "who recommendation", "cdc guideline",
            "pandemic", "epidemic", "outbreak",
            "organ transplant", "heart surgery", "bypass surgery",
            "diabetes management", "insulin", "blood pressure",
        ],
        "medium": [
            "hospital", "doctor", "nurse", "patient", "icu", "ward",
            "disease", "illness", "condition", "syndrome", "infection",
            "vaccine", "medicine", "drug", "pharma", "dosage", "prescription",
            "surgery", "operation", "procedure", "diagnosis", "treatment",
            "health ministry", "public health", "healthcare",
            "nutrition", "diet", "fitness", "obesity", "weight loss",
            "mental health", "therapy", "counselling", "psychiatry",
            "virus", "bacteria", "antibiotic", "antiviral",
        ],
        "low": [
            "health", "medical", "wellness", "wellbeing", "care",
            "research", "study", "scientist",
        ],
        "sources": [
            "who", "cdc", "lancet", "nature medicine", "healthline",
            "webmd", "medical news", "pharma", "medscape",
            "reddit/r/health", "reddit/r/medicine",
        ],
    },

    "business": {
        "high": [
            "merger and acquisition", "hostile takeover", "buyout",
            "reliance industries", "tata group", "adani group", "mahindra",
            "infosys", "wipro", "tcs", "hcl technologies",
            "zomato", "swiggy", "ola", "uber india", "flipkart", "meesho",
            "series a", "series b", "series c", "seed funding", "pre-ipo",
            "unicorn startup", "decacorn", "ipo filing",
            "layoffs", "mass layoff", "job cuts", "retrenchment",
            "product launch", "market expansion", "overseas expansion",
            "ecommerce", "d2c", "supply chain",
            "annual report", "agm", "quarterly report",
        ],
        "medium": [
            "company", "corporation", "firm", "enterprise", "conglomerate",
            "ceo", "cfo", "cto", "managing director", "chairman", "board",
            "merger", "acquisition", "partnership", "joint venture", "deal",
            "brand", "retail", "franchise", "distribution",
            "amazon", "apple store", "google ads",
            "entrepreneur", "founder", "co-founder",
            "hiring", "recruitment", "talent", "workforce",
            "market share", "competition", "competitor",
            "profit margin", "operating profit", "net profit",
        ],
        "low": [
            "business", "industry", "sector", "corporate", "commercial",
            "trade", "sales", "marketing", "strategy",
        ],
        "sources": [
            "business standard", "economic times business", "inc42",
            "your story", "entrackr", "forbes india",
            "reddit/r/business", "reddit/r/startups", "reddit/r/IndiaStartups",
            "twitter/@business_std", "twitter/@forbesindia", "twitter/@Inc42Media",
        ],
    },

    "science": {
        "high": [
            "peer-reviewed study", "scientific journal", "nature", "science journal",
            "quantum mechanics", "quantum entanglement", "particle physics",
            "cern", "large hadron collider", "dark matter", "dark energy",
            "black hole", "neutron star", "supernova", "exoplanet",
            "dna sequencing", "genome", "crispr", "gene editing",
            "fossil discovery", "dinosaur", "palaeontology",
            "climate change", "global warming", "carbon emissions",
            "biodiversity", "endangered species", "extinction",
            "mars rover", "james webb telescope", "lunar mission",
            "archaeology", "ancient civilisation",
        ],
        "medium": [
            "scientists", "researchers", "study finds", "new discovery",
            "space", "planet", "asteroid", "comet", "galaxy", "universe",
            "biology", "chemistry", "physics", "geology", "neuroscience",
            "evolution", "species", "dna", "gene", "protein", "cell",
            "environment", "ecosystem", "ocean", "glacier", "deforestation",
            "experiment", "laboratory", "telescope", "satellite imagery",
        ],
        "low": [
            "research", "science", "discovery", "experiment",
            "finding", "breakthrough", "innovation",
        ],
        "sources": [
            "nature", "science magazine", "sciencealert", "phys.org",
            "new scientist", "scientific american", "isro",
            "reddit/r/science", "reddit/r/space",
            "twitter/@NASAHubble", "twitter/@ISRO", "twitter/@ScienceAlert",
        ],
    },

    "entertainment": {
        "high": [
            "bollywood", "box office collection", "opening weekend",
            "oscar award", "bafta", "filmfare award", "golden globe",
            "netflix original", "amazon prime video", "disney+ hotstar",
            "web series", "ott release", "streaming platform",
            "bigg boss", "indian idol", "kbc", "reality show",
            "grammy award", "billboard chart", "music album drop",
            "celebrity wedding", "celebrity divorce", "celebrity baby",
            "film review", "movie trailer", "teaser launch",
        ],
        "medium": [
            "film", "movie", "bollywood", "hollywood", "tollywood",
            "actor", "actress", "director", "producer", "screenplay",
            "music", "album", "single", "song", "concert", "tour",
            "netflix", "amazon prime", "hotstar", "zee5", "sonyliv",
            "award", "nomination", "ceremony",
            "celebrity", "star", "fame", "debut",
            "television", "serial", "episode", "season",
            "comedy", "drama", "thriller", "horror", "romance",
        ],
        "low": [
            "entertainment", "show", "event", "performance",
            "release", "premiere", "screening",
        ],
        "sources": [
            "bollywood hungama", "film companion", "pinkvilla", "koimoi",
            "filmfare", "screen", "galatta", "bollywood life",
            "reddit/r/bollywood", "reddit/r/movies",
            "twitter/@bollywood_life", "twitter/@FilmCompanion",
        ],
    },
}

# ── Domain → category map (strongest signal — checked before keywords) ────────
#
# Keys are exact domain strings (without www.).
# The classifier adds DOMAIN_BONUS to the mapped category's score.
DOMAIN_CATEGORIES: dict[str, str] = {
    # Sports
    "espncricinfo.com":           "sports",
    "cricbuzz.com":               "sports",
    "sportskeeda.com":            "sports",
    "sportstar.thehindu.com":     "sports",
    "goal.com":                   "sports",
    "skysports.com":              "sports",
    "bleacherreport.com":         "sports",
    "icc-cricket.com":            "sports",
    "bcci.tv":                    "sports",
    "iplt20.com":                 "sports",
    "fifa.com":                   "sports",
    "olympics.com":               "sports",
    "wrestlingtvhd.com":          "sports",
    "kreedon.com":                "sports",
    # Finance / Markets
    "moneycontrol.com":           "finance",
    "livemint.com":               "finance",
    "zeebiz.com":                 "finance",
    "financialexpress.com":       "finance",
    "bloomberg.com":              "finance",
    "cnbc.com":                   "finance",
    "marketwatch.com":            "finance",
    "investing.com":              "finance",
    "coindesk.com":               "finance",
    "coingecko.com":              "finance",
    "wsj.com":                    "finance",
    "ft.com":                     "finance",
    # Technology
    "techcrunch.com":             "technology",
    "wired.com":                  "technology",
    "theverge.com":               "technology",
    "arstechnica.com":            "technology",
    "engadget.com":               "technology",
    "gizmodo.com":                "technology",
    "venturebeat.com":            "technology",
    "thenextweb.com":             "technology",
    "91mobiles.com":              "technology",
    "gadgetsnow.com":             "technology",
    "bgr.in":                     "technology",
    "digit.in":                   "technology",
    # Entertainment
    "bollywoodhungama.com":       "entertainment",
    "pinkvilla.com":              "entertainment",
    "koimoi.com":                 "entertainment",
    "filmfare.com":               "entertainment",
    "galatta.com":                "entertainment",
    "indiaglitz.com":             "entertainment",
    "rottentomatoes.com":         "entertainment",
    "imdb.com":                   "entertainment",
    "hollywoodreporter.com":      "entertainment",
    "variety.com":                "entertainment",
    # Health
    "webmd.com":                  "health",
    "healthline.com":             "health",
    "medscape.com":               "health",
    "medicalnewstoday.com":       "health",
    "nhp.gov.in":                 "health",
    # Science
    "nature.com":                 "science",
    "sciencealert.com":           "science",
    "phys.org":                   "science",
    "newscientist.com":           "science",
    "scientificamerican.com":     "science",
    "space.com":                  "science",
    "nasa.gov":                   "science",
    # Business
    "inc42.com":                  "business",
    "yourstory.com":              "business",
    "entrackr.com":               "business",
    "startupstory.in":            "business",
    "forbesindia.com":            "business",
}

# ── URL path substrings → category (checked before keywords) ──────────────────
#
# Ordered list of (path_substring, category) tuples.
# First match wins — put more specific paths before generic ones.
URL_PATH_CATEGORIES: list[tuple[str, str]] = [
    # Sports
    ("/cricket/",          "sports"),
    ("/ipl/",              "sports"),
    ("/football/",         "sports"),
    ("/tennis/",           "sports"),
    ("/badminton/",        "sports"),
    ("/hockey/",           "sports"),
    ("/kabaddi/",          "sports"),
    ("/sports/",           "sports"),
    ("/sport/",            "sports"),
    # Finance
    ("/markets/",          "finance"),
    ("/sensex/",           "finance"),
    ("/nifty/",            "finance"),
    ("/stocks/",           "finance"),
    ("/cryptocurrency/",   "finance"),
    ("/crypto/",           "finance"),
    ("/mutual-funds/",     "finance"),
    ("/personal-finance/", "finance"),
    ("/economy/",          "finance"),
    # Technology
    ("/technology/",       "technology"),
    ("/tech/",             "technology"),
    ("/artificial-intelligence/", "technology"),
    ("/gadgets/",          "technology"),
    ("/cybersecurity/",    "technology"),
    ("/startups/",         "technology"),
    # Entertainment
    ("/bollywood/",        "entertainment"),
    ("/hollywood/",        "entertainment"),
    ("/entertainment/",    "entertainment"),
    ("/movies/",           "entertainment"),
    ("/music/",            "entertainment"),
    ("/ott/",              "entertainment"),
    # Politics
    ("/politics/",         "politics"),
    ("/election/",         "politics"),
    ("/parliament/",       "politics"),
    # Health
    ("/health/",           "health"),
    ("/wellness/",         "health"),
    ("/fitness/",          "health"),
    # Science
    ("/science/",          "science"),
    ("/space/",            "science"),
    ("/environment/",      "science"),
    # Business
    ("/business/",         "business"),
    ("/companies/",        "business"),
    ("/industry/",         "business"),
]

# Backward-compatible flat keyword lists (used by RSS source hints, etc.)
CATEGORIES: dict[str, list[str]] = {
    cat: rules["high"] + rules["medium"] + rules["low"]
    for cat, rules in CATEGORY_RULES.items()
}

REDDIT_SUBREDDITS: dict[str, list[str]] = {
    "technology":    ["technology", "tech", "artificial", "MachineLearning"],
    "finance":       ["investing", "IndiaInvestments", "CryptoCurrency", "stocks"],
    "politics":      ["india", "worldnews", "geopolitics"],
    "sports":        ["cricket", "ipl", "soccer", "sports"],
    "health":        ["health", "medicine", "science"],
    "business":      ["business", "startups", "IndiaStartups"],
    "science":       ["science", "space", "technology"],
    "entertainment": ["bollywood", "movies", "entertainment"],
}

RSS_FEEDS: list[dict] = [
    # ── General Indian news ────────────────────────────────────────────────────
    {"url": "https://feeds.feedburner.com/ndtvnews-top-stories",                                "category": "general"},
    {"url": "https://timesofindia.indiatimes.com/rssfeedstopstories.cms",                       "category": "general"},
    {"url": "https://www.thehindu.com/news/feeder/default.rss",                                 "category": "general"},
    {"url": "https://www.hindustantimes.com/rss/topnews/rssfeed.xml",                           "category": "general"},
    {"url": "https://indianexpress.com/feed/",                                                  "category": "general"},
    {"url": "https://www.indiatoday.in/rss/home",                                               "category": "general"},
    {"url": "https://feeds.feedburner.com/ndtvnews-india-news",                                 "category": "general"},
    {"url": "https://theprint.in/feed/",                                                        "category": "general"},
    {"url": "https://thewire.in/feed",                                                          "category": "general"},

    # ── Technology ─────────────────────────────────────────────────────────────
    {"url": "https://techcrunch.com/feed/",                                                     "category": "technology"},
    {"url": "https://feeds.feedburner.com/venturebeat/SZYF",                                    "category": "technology"},
    {"url": "https://feeds.feedburner.com/gadgets360-top-story",                                "category": "technology"},
    {"url": "https://www.91mobiles.com/hub/feed/",                                              "category": "technology"},
    {"url": "https://bgr.in/feed/",                                                             "category": "technology"},
    {"url": "https://www.androidauthority.com/feed/",                                           "category": "technology"},
    {"url": "https://www.digit.in/rss.xml",                                                     "category": "technology"},
    {"url": "https://tech.hindustantimes.com/rss.xml",                                          "category": "technology"},

    # ── Finance ────────────────────────────────────────────────────────────────
    {"url": "https://economictimes.indiatimes.com/markets/rssfeeds/1977021501.cms",             "category": "finance"},
    {"url": "https://economictimes.indiatimes.com/rssfeedstopstories.cms",                      "category": "finance"},
    {"url": "https://www.moneycontrol.com/rss/MCtopnews.xml",                                   "category": "finance"},
    {"url": "https://www.livemint.com/rss/markets",                                             "category": "finance"},
    {"url": "https://www.business-standard.com/rss/markets-106.rss",                            "category": "finance"},
    {"url": "https://feeds.feedburner.com/business-standard/latest",                            "category": "finance"},
    {"url": "https://www.zeebiz.com/feed",                                                      "category": "finance"},

    # ── Sports ─────────────────────────────────────────────────────────────────
    {"url": "https://www.espncricinfo.com/rss/content/story/feeds/0.xml",                       "category": "sports"},
    {"url": "https://sports.ndtv.com/rss/cricket",                                              "category": "sports"},
    {"url": "https://timesofindia.indiatimes.com/rssfeeds/4719158.cms",                         "category": "sports"},
    {"url": "https://www.indiatoday.in/rss/1206577",                                            "category": "sports"},
    {"url": "https://sportskeeda.com/feed",                                                     "category": "sports"},
    {"url": "https://www.hindustantimes.com/rss/sports/rssfeed.xml",                            "category": "sports"},

    # ── Health ─────────────────────────────────────────────────────────────────
    {"url": "https://health.economictimes.indiatimes.com/rss/topstories",                       "category": "health"},
    {"url": "https://www.thehindu.com/sci-tech/health/feeder/default.rss",                      "category": "health"},
    {"url": "https://www.hindustantimes.com/rss/lifestyle/rssfeed.xml",                         "category": "health"},

    # ── Entertainment ──────────────────────────────────────────────────────────
    {"url": "https://www.bollywoodhungama.com/rss/news.xml",                                    "category": "entertainment"},
    {"url": "https://www.pinkvilla.com/feed",                                                   "category": "entertainment"},
    {"url": "https://timesofindia.indiatimes.com/rssfeeds/1081479906.cms",                      "category": "entertainment"},
    {"url": "https://movies.ndtv.com/rss/movies",                                               "category": "entertainment"},
    {"url": "https://www.koimoi.com/feed/",                                                     "category": "entertainment"},

    # ── Business ───────────────────────────────────────────────────────────────
    {"url": "https://inc42.com/feed/",                                                          "category": "business"},
    {"url": "https://yourstory.com/feed",                                                       "category": "business"},
    {"url": "https://economictimes.indiatimes.com/industry/rssfeeds/13352306.cms",              "category": "business"},
    {"url": "https://www.forbesindia.com/feed/",                                                "category": "business"},

    # ── Science ────────────────────────────────────────────────────────────────
    {"url": "https://www.thehindu.com/sci-tech/science/feeder/default.rss",                     "category": "science"},
    {"url": "https://www.sciencealert.com/feed",                                                "category": "science"},
    {"url": "https://www.space.com/feeds/all",                                                  "category": "science"},
    {"url": "https://feeds.feedburner.com/isro-news",                                           "category": "science"},

    # ── Politics ───────────────────────────────────────────────────────────────
    {"url": "https://www.thehindu.com/news/national/feeder/default.rss",                        "category": "politics"},
    {"url": "https://www.thehindu.com/news/international/feeder/default.rss",                   "category": "politics"},
    {"url": "https://indianexpress.com/section/india/feed/",                                    "category": "politics"},
]

TWITTER_NEWS_ACCOUNTS: dict[str, list[str]] = {
    "general":       ["ANI", "PTI_News", "ndtv", "timesofindia", "the_hindu", "htTweets"],
    "technology":    ["TechCrunch", "verge", "WIRED", "gadgetsnow"],
    "finance":       ["EconomicTimes", "moneycontrol", "livemint", "BloombergIndia"],
    "politics":      ["BJP4India", "INCIndia", "ndtvnews", "republic"],
    "sports":        ["BCCI", "IPL", "ESPNcricinfo", "BFIBoxing"],
    "business":      ["business_std", "forbesindia", "Inc42Media"],
    "science":       ["NASAHubble", "ISRO", "ScienceAlert"],
    "entertainment": ["bollywood_life", "FilmCompanion", "galatta"],
}

DEFAULT_CATEGORY = "general"
