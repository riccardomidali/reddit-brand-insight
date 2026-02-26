from dataclasses import dataclass
from datetime import datetime, timezone
from collections import Counter, defaultdict
import math
import os
import re

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
import praw
from vaderSentiment.vaderSentiment import SentimentIntensityAnalyzer
from dotenv import load_dotenv

app = FastAPI(title="SentiScan API")

ENV_PATH = os.path.join(os.path.dirname(__file__), "..", "..", "backend", ".env")
load_dotenv(dotenv_path=ENV_PATH, override=True)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:8080", "http://127.0.0.1:8080"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

analyzer = SentimentIntensityAnalyzer()

URL_PATTERN = re.compile(r"(https?://\S+|www\.\S+|\b[a-z0-9.-]+\.(?:com|org|net|io|co)\b)", re.IGNORECASE)
TOKEN_PATTERN = re.compile(r"[A-Za-z0-9][A-Za-z0-9&'_/-]*")
MONTHS_WINDOW = 24
MAX_KEYWORDS = 30
MAX_SUGGESTIONS = 5

# ── Marketing-oriented query templates ────────────────────────────────────────
# Each template is (label, keywords_to_search).
# label is shown to the user; keywords are used to score which templates
# actually have data in the fetched posts, so irrelevant ones rank lower.
MARKETING_TEMPLATES: list[tuple[str, list[str]]] = [
    ("customer experience",    ["experience", "customer", "service", "support", "satisfaction"]),
    ("product quality",        ["quality", "durability", "material", "build", "defect", "review"]),
    ("brand reputation",       ["reputation", "trust", "credibility", "image", "perception", "opinion"]),
    ("sustainability",         ["sustainable", "eco", "environment", "recycled", "carbon", "green"]),
    ("innovation",             ["innovation", "technology", "new", "design", "feature", "patent"]),
    ("pricing & value",        ["price", "value", "expensive", "cheap", "worth", "cost", "deal"]),
    ("community & culture",    ["community", "culture", "lifestyle", "identity", "movement", "belong"]),
    ("competition",            ["vs", "versus", "competitor", "alternative", "better", "compared"]),
    ("marketing & campaigns",  ["ad", "campaign", "commercial", "ambassador", "sponsor", "influencer"]),
    ("customer loyalty",       ["loyal", "repeat", "fan", "love", "return", "favourite", "best"]),
]

ENGLISH_STOPWORDS = {
    "a", "about", "above", "after", "again", "against", "all", "am", "an", "and", "any", "are",
    "as", "at", "be", "because", "been", "before", "being", "below", "between", "both", "but",
    "by", "can", "cannot", "could", "did", "do", "does", "doing", "down", "during", "each", "few",
    "for", "from", "further", "had", "has", "have", "having", "he", "her", "here", "hers",
    "herself", "him", "himself", "his", "how", "i", "if", "in", "into", "is", "it", "its",
    "itself", "just", "me", "more", "most", "my", "myself", "no", "nor", "not", "now", "of", "off",
    "on", "once", "only", "or", "other", "our", "ours", "ourselves", "out", "over", "own", "same",
    "she", "should", "so", "some", "such", "than", "that", "the", "their", "theirs", "them",
    "themselves", "then", "there", "these", "they", "this", "those", "through", "to", "too", "under",
    "until", "up", "very", "was", "we", "were", "what", "when", "where", "which", "while", "who",
    "whom", "why", "will", "with", "you", "your", "yours", "yourself", "yourselves", "also", "else",
    "ever", "never", "may", "might", "must", "yet", "let", "lets", "dont", "doesnt", "didnt", "cant",
    "wont", "im", "ive", "ill", "theyre", "youre", "thats", "whats", "heres", "therefore", "however",
}

REDDIT_JUNK_WORDS = {
    "post", "posts", "comment", "comments", "thread", "threads", "reddit", "redditor", "subreddit",
    "people", "really", "would", "could", "should", "much", "such", "also", "just", "like", "know",
    "thing", "things", "stuff", "anyone", "everyone", "someone", "something", "anything", "nothing",
    "today", "tomorrow", "yesterday", "question", "answer", "asking", "edit", "title", "video", "link",
    "links", "self", "deleted", "removed", "using", "used", "use", "make", "made", "getting", "got",
    "maybe", "still", "even", "seems", "seem", "around", "across", "without", "within", "about", "into",
}

URL_JUNK_TOKENS = {"http", "https", "www", "com", "org", "net", "io", "co", "amp"}

# ── Topic keyword sets (weighted) ─────────────────────────────────────────────
# Format: {keyword: weight} — higher weight = more signal for that topic.

ECO_KEYWORD_WEIGHTS: dict[str, float] = {
    "sustainable": 3.0, "sustainability": 3.0, "recycled": 3.0, "recyclable": 3.0,
    "recycling": 2.5, "carbon": 2.5, "emission": 2.5, "emissions": 2.5,
    "climate": 2.0, "renewable": 3.0, "ethical": 2.0, "ethically": 2.0,
    "responsible": 1.5, "green": 2.0, "eco": 2.5, "environment": 2.0,
    "environmental": 2.0, "biodiversity": 3.0, "biodegradable": 3.5, "compostable": 3.5,
    "packaging": 1.5, "plastic": 2.0, "waste": 2.0, "footprint": 2.5,
    "offset": 2.5, "offsets": 2.5, "regenerative": 3.5, "fairtrade": 3.0,
    "sourcing": 1.5, "circular": 2.5, "organic": 2.5, "energy": 1.5,
    "reforestation": 4.0, "deforestation": 3.5, "vegan": 2.5, "cruelty": 2.5,
}

ECO_PHRASE_WEIGHTS: dict[str, float] = {
    "carbon footprint": 4.0, "net zero": 4.5, "supply chain": 2.5,
    "ethical sourcing": 4.0, "fair trade": 3.5, "renewable energy": 4.0,
    "circular economy": 4.5, "zero waste": 4.0, "plastic free": 4.0,
    "climate impact": 4.0, "sustainable materials": 4.0, "recycled materials": 4.0,
    "responsible sourcing": 4.0, "carbon neutral": 5.0, "scope emissions": 4.0,
}

INNOVATION_KEYWORD_WEIGHTS: dict[str, float] = {
    "innovation": 3.0, "innovative": 3.0, "technology": 2.5, "tech": 2.0,
    "ai": 2.5, "automation": 2.5, "digital": 2.0, "prototype": 3.0,
    "prototyping": 3.0, "research": 2.0, "development": 2.0, "materials": 2.0,
    "material": 2.0, "patent": 3.0, "engineering": 2.5, "engineered": 2.5,
    "algorithm": 3.0, "algorithms": 3.0, "software": 2.0, "hardware": 2.0,
    "design": 1.5, "breakthrough": 3.5, "roadmap": 2.5, "platform": 2.0,
    "performance": 1.5, "scientific": 2.5, "robotics": 3.5, "sensor": 3.0,
    "nanotechnology": 4.0, "3d printing": 4.0, "augmented": 3.0, "virtual": 2.5,
}

INNOVATION_PHRASE_WEIGHTS: dict[str, float] = {
    "artificial intelligence": 4.5, "machine learning": 4.5, "new technology": 3.5,
    "product design": 3.0, "research development": 3.5, "material innovation": 4.0,
    "new materials": 3.5, "patent portfolio": 4.0, "digital platform": 3.5,
    "computer vision": 4.0, "data science": 3.5, "technical innovation": 4.0,
    "deep learning": 4.5, "generative ai": 4.5, "natural language": 4.0,
}

# Unigrams that are too generic to be useful as top keywords regardless of frequency
GENERIC_KEYWORD_BLOCKLIST = {
    "brand", "company", "product", "products", "price", "buy", "bought",
    "get", "got", "good", "great", "bad", "best", "worst", "new", "old",
    "one", "two", "three", "year", "years", "time", "way", "say", "said",
    "going", "want", "look", "looking", "come", "came", "first", "last",
    "big", "small", "lot", "lots", "far", "near", "high", "low", "long", "short",
    "need", "needed", "needs", "take", "took", "gives", "given", "find", "found",
}


@dataclass
class PreparedPost:
    text: str
    sentiment: float
    score: int
    created_utc: int
    year: int
    month_key: str
    tokens: list[str]
    token_set: set[str]
    token_string: str
    ngrams: list[str]
    engagement_weight: float


def get_reddit_client():
    client_id = os.getenv("REDDIT_CLIENT_ID")
    client_secret = os.getenv("REDDIT_CLIENT_SECRET")
    user_agent = os.getenv("REDDIT_USER_AGENT")

    if not client_id or not client_secret or not user_agent:
        raise RuntimeError("Missing REDDIT_CLIENT_ID / REDDIT_CLIENT_SECRET / REDDIT_USER_AGENT in backend/.env")

    return praw.Reddit(
        client_id=client_id,
        client_secret=client_secret,
        user_agent=user_agent,
    )

def sentiment(text: str) -> float:
    return analyzer.polarity_scores(text or "")["compound"]

def clamp(value: float, min_value: float, max_value: float) -> float:
    return max(min_value, min(max_value, value))


def remove_urls(text: str) -> str:
    return URL_PATTERN.sub(" ", text or "")


def normalize_token(raw: str) -> str:
    token = raw.lower().strip("'-_/")
    token = token.replace("&", "and")
    if token.endswith("'s"):
        token = token[:-2]
    return re.sub(r"(^[^a-z0-9]+|[^a-z0-9]+$)", "", token)


def is_number_token(token: str) -> bool:
    return bool(re.fullmatch(r"\d+(?:[.,]\d+)?", token))


def build_brand_tokens(brand: str) -> tuple[set[str], str]:
    brand_tokens = {normalize_token(tok) for tok in TOKEN_PATTERN.findall(brand.lower())}
    brand_tokens.discard("")
    brand_compact = re.sub(r"[^a-z0-9]+", "", brand.lower())
    return brand_tokens, brand_compact


def token_is_noise(token: str, brand_tokens: set[str]) -> bool:
    if not token:
        return True
    if token in brand_tokens:
        return True
    if token in URL_JUNK_TOKENS:
        return True
    if token in ENGLISH_STOPWORDS or token in REDDIT_JUNK_WORDS:
        return True
    if is_number_token(token):
        return True
    if "http" in token:
        return True
    return False


def tokenize_text(text: str, brand_tokens: set[str]) -> list[str]:
    cleaned = remove_urls(text)
    tokens: list[str] = []
    for raw in TOKEN_PATTERN.findall(cleaned):
        token = normalize_token(raw)
        if token_is_noise(token, brand_tokens):
            continue
        if len(token) < 2:
            continue
        tokens.append(token)
    return tokens


def build_ngrams(tokens: list[str], sizes: tuple[int, ...] = (3, 2)) -> list[str]:
    ngrams: list[str] = []
    for size in sizes:
        if len(tokens) < size:
            continue
        for idx in range(len(tokens) - size + 1):
            chunk = tokens[idx : idx + size]
            if any(word in URL_JUNK_TOKENS for word in chunk):
                continue
            if all(len(word) < 4 for word in chunk):
                continue
            ngrams.append(" ".join(chunk))
    return ngrams


def phrase_contains_brand(phrase: str, brand_tokens: set[str], brand_compact: str) -> bool:
    phrase_tokens = phrase.split()
    if any(token in brand_tokens for token in phrase_tokens):
        return True
    if brand_compact:
        phrase_compact = re.sub(r"[^a-z0-9]+", "", phrase)
        if brand_compact in phrase_compact:
            return True
    return False


def month_keys_last_n(months: int) -> list[str]:
    now = datetime.now(timezone.utc)
    current_index = now.year * 12 + (now.month - 1)
    keys: list[str] = []
    for offset in range(months - 1, -1, -1):
        idx = current_index - offset
        year = idx // 12
        month = idx % 12 + 1
        keys.append(f"{year:04d}-{month:02d}")
    return keys


def compute_topic_score(
    posts: list[PreparedPost],
    token_weights: dict[str, float],
    phrase_weights: dict[str, float],
) -> float:
    """
    Score 0-100 for a topic (eco / innovation).

    For each post we compute:
      keyword_score = sum of weights for each matching token / (token_count * avg_weight)
      phrase_score  = sum of weights for each matching phrase / (max possible phrase weight)
    Combined with engagement weight and sentiment boost, then averaged across all posts.

    Using weights (instead of raw hit counts) makes the score more meaningful:
    a post mentioning "carbon neutral" (weight 5) scores much higher than
    one mentioning only "energy" (weight 1.5).
    """
    if not posts:
        return 0.0

    token_keyword_set = set(token_weights.keys())
    phrase_keyword_set = set(phrase_weights.keys())
    max_phrase_weight = max(phrase_weights.values()) if phrase_weights else 1.0

    weighted_sum = 0.0
    total_weight = 0.0

    for post in posts:
        token_count = len(post.tokens)
        if token_count == 0:
            continue

        # Weighted token hits
        token_score_raw = sum(
            token_weights[t] for t in post.tokens if t in token_keyword_set
        )
        avg_kw_weight = sum(token_weights.values()) / max(len(token_weights), 1)
        token_relevance = clamp(token_score_raw / max(token_count * avg_kw_weight, 1e-6), 0.0, 1.0)

        # Weighted phrase hits
        phrase_score_raw = sum(
            phrase_weights[p] for p in post.ngrams if p in phrase_keyword_set
        )
        phrase_relevance = clamp(phrase_score_raw / (max_phrase_weight * 2), 0.0, 1.0)

        # Combined relevance: phrases count more (they are higher signal)
        combined_relevance = clamp(0.4 * token_relevance + 0.6 * phrase_relevance, 0.0, 1.0)

        # Sentiment boost: negative sentiment slightly lowers the score
        # (a brand discussed negatively on eco topics scores lower than one praised)
        sentiment_norm = (post.sentiment + 1) / 2  # 0..1
        sentiment_boost = 0.7 + 0.6 * sentiment_norm  # 0.7..1.3

        contribution = combined_relevance * sentiment_boost
        weighted_sum += contribution * post.engagement_weight
        total_weight += post.engagement_weight

    if total_weight == 0:
        return 0.0
    return round(clamp((weighted_sum / total_weight) * 100, 0.0, 100.0), 1)


def compute_query_score(posts: list[PreparedPost], query: str, overall_sentiment_pct: float) -> float:
    if not posts:
        return 0.0

    brand_tokens: set[str] = set()
    query_tokens = [token for token in tokenize_text(query, brand_tokens=set()) if len(token) >= 3]
    if not query_tokens:
        return overall_sentiment_pct

    phrase_query = " ".join(query_tokens)
    weighted_hits = 0.0
    total_weight = 0.0
    for post in posts:
        hits = sum(1 for token in query_tokens if token in post.token_set)
        phrase_hit = 1 if len(query_tokens) > 1 and phrase_query in post.token_string else 0
        relevance = clamp((hits + phrase_hit) / len(query_tokens), 0.0, 1.0)

        weighted_hits += relevance * post.engagement_weight
        total_weight += post.engagement_weight

    avg_relevance = weighted_hits / total_weight if total_weight > 0 else 0.0
    sentiment_component = overall_sentiment_pct / 100
    score = (0.7 * avg_relevance + 0.3 * sentiment_component) * 100
    return round(clamp(score, 0.0, 100.0), 1)


def merge_keyword_counters(
    phrase_counter: Counter[str],
    unigram_counter: Counter[str],
    limit: int,
    brand_tokens: set[str],
) -> list[dict]:
    """
    Merge phrase and unigram counters into a ranked keyword list.
    Applies an extra quality filter:
    - Removes phrases where ALL tokens are in the generic blocklist
    - Removes single-word entries in the generic blocklist
    - Boosts phrases (they carry more meaning than single words)
    Returns dicts with text, value, and sentiment_label (positive/neutral/negative).
    """
    # Boost phrase counts so they rank above same-frequency unigrams
    boosted_phrases: list[tuple[str, float]] = []
    for text, count in phrase_counter.items():
        words = text.split()
        if all(w in GENERIC_KEYWORD_BLOCKLIST or w in brand_tokens for w in words):
            continue
        boosted_phrases.append((text, count * 1.5))

    boosted_unigrams: list[tuple[str, float]] = [
        (text, float(count))
        for text, count in unigram_counter.items()
        if text not in GENERIC_KEYWORD_BLOCKLIST and text not in brand_tokens
    ]

    ranked = sorted(boosted_phrases + boosted_unigrams, key=lambda x: (-x[1], x[0]))

    seen: set[str] = set()
    results: list[dict] = []
    for text, score in ranked:
        if text in seen:
            continue
        seen.add(text)
        # Check sub-phrase deduplication: skip unigrams already covered by a ranked phrase
        covered = any(text in phrase for phrase in seen if " " in phrase)
        if covered and " " not in text:
            continue
        results.append({"text": text, "value": int(score)})
        if len(results) >= limit:
            break
    return results


def prepare_posts(
    brand: str,
    subreddit: str,
    search_query: str,
    limit_posts: int,
) -> list[PreparedPost]:
    """
    Fetch posts from Reddit using multiple sort strategies to maximise diversity.
    We fetch with 'relevance' and 'top' separately and merge by ID to deduplicate.
    This effectively doubles the sample size without exceeding API limits.
    """
    reddit = get_reddit_client()
    sr = reddit.subreddit(subreddit)
    brand_tokens, _ = build_brand_tokens(brand)

    seen_ids: set[str] = set()
    prepared: list[PreparedPost] = []

    # Use multiple sort strategies for richer, more representative samples
    sort_strategies = [
        ("relevance", "all"),
        ("top", "all"),
        ("new", "year"),
    ]

    per_strategy = max(limit_posts // len(sort_strategies), 30)

    try:
        for sort_mode, time_filter in sort_strategies:
            for post in sr.search(
                search_query,
                limit=per_strategy,
                sort=sort_mode,
                time_filter=time_filter,
            ):
                if post.id in seen_ids:
                    continue
                seen_ids.add(post.id)

                text = f"{post.title or ''} {post.selftext or ''}".strip()
                tokens = tokenize_text(text, brand_tokens=brand_tokens)
                ngrams = build_ngrams(tokens)
                created = datetime.fromtimestamp(post.created_utc, tz=timezone.utc)
                engagement_weight = 1.0 + min(1.5, math.log1p(max(post.score, 0)) / 3.0)

                prepared.append(
                    PreparedPost(
                        text=text,
                        sentiment=sentiment(text),
                        score=post.score,
                        created_utc=int(post.created_utc),
                        year=created.year,
                        month_key=created.strftime("%Y-%m"),
                        tokens=tokens,
                        token_set=set(tokens),
                        token_string=" ".join(tokens),
                        ngrams=ngrams,
                        engagement_weight=engagement_weight,
                    )
                )
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Reddit search failed: {exc}") from exc

    return prepared


def build_marketing_suggestions(
    posts: list[PreparedPost],
    brand: str,
    limit: int = MAX_SUGGESTIONS,
) -> list[dict[str, float]]:
    """
    Score each marketing template against the fetched posts.
    A template scores higher if its keywords appear frequently in high-engagement posts.
    This ensures suggestions are marketing-oriented AND data-backed.
    """
    if not posts:
        return []

    results: list[dict] = []

    for label, keywords in MARKETING_TEMPLATES:
        kw_set = set(keywords)
        weighted_hits = 0.0
        total_weight = 0.0

        for post in posts:
            hits = sum(1 for kw in kw_set if kw in post.token_set)
            relevance = clamp(hits / len(kw_set), 0.0, 1.0)
            weighted_hits += relevance * post.engagement_weight
            total_weight += post.engagement_weight

        avg_relevance = weighted_hits / total_weight if total_weight > 0 else 0.0
        # Score 0-1: pure data signal (no sentiment boost so ranking is neutral)
        results.append({"text": label, "score": round(avg_relevance, 4)})

    # Sort by score desc, take top N, ensure at least MIN_SCORE_THRESHOLD presence
    results.sort(key=lambda x: -x["score"])

    # Always return at least `limit` suggestions — if many have 0 score, keep top by order
    return results[:limit]


@app.get("/api/health")
def health():
    return {"ok": True}

@app.get("/api/suggest")
def suggest(
    brand: str = Query(..., min_length=1),
    subreddit: str = Query("all", min_length=1),
    limit_posts: int = Query(200, ge=50, le=500),
):
    clean_brand = brand.strip()
    posts = prepare_posts(
        brand=clean_brand,
        subreddit=subreddit,
        search_query=clean_brand,
        limit_posts=limit_posts,
    )

    return {
        "brand": clean_brand,
        "subreddit": subreddit,
        "suggestions": build_marketing_suggestions(posts, clean_brand, limit=MAX_SUGGESTIONS),
    }


@app.get("/api/analyze")
def analyze(
    brand: str = Query(..., min_length=1),
    query: str = Query("", min_length=0),
    subreddit: str = Query("all", min_length=1),
    limit_posts: int = Query(300, ge=1, le=1000),
):
    clean_brand = brand.strip()
    search_q = clean_brand if not query else f"{clean_brand} {query}"
    posts = prepare_posts(
        brand=clean_brand,
        subreddit=subreddit,
        search_query=search_q,
        limit_posts=limit_posts,
    )

    brand_tokens, _ = build_brand_tokens(clean_brand)

    yearly_counter: Counter[int] = Counter()
    monthly_counter: Counter[str] = Counter()
    phrase_keywords: Counter[str] = Counter()
    unigram_keywords: Counter[str] = Counter()

    for post in posts:
        yearly_counter[post.year] += 1
        monthly_counter[post.month_key] += 1
        phrase_keywords.update(set(post.ngrams))
        unigram_keywords.update({token for token in post.tokens if len(token) >= 4})

    if not posts:
        timeline_monthly = [
            {"month": month_key, "mentions": 0}
            for month_key in month_keys_last_n(MONTHS_WINDOW)
        ]
        scores = {
            "overallSentiment": 0.0,
            "queryScore": 0.0,
            "ecoScore": 0.0,
            "innovationScore": 0.0,
        }
        return {
            "brand": clean_brand,
            "query": query,
            "subreddit": subreddit,
            "samplesCount": 0,
            "overallSentiment": scores["overallSentiment"],
            "queryScore": scores["queryScore"],
            "scores": scores,
            "timeline": [],
            "timelineYearly": [],
            "timelineMonthly": timeline_monthly,
            "topKeywords": [],
        }

    sentiments = [post.sentiment for post in posts]
    overall_sentiment = sum(sentiments) / len(sentiments)
    overall_sentiment_pct = round((overall_sentiment + 1) * 50, 1)

    query_score = compute_query_score(posts, query=query, overall_sentiment_pct=overall_sentiment_pct)
    eco_score = compute_topic_score(posts, ECO_KEYWORD_WEIGHTS, ECO_PHRASE_WEIGHTS)
    innovation_score = compute_topic_score(posts, INNOVATION_KEYWORD_WEIGHTS, INNOVATION_PHRASE_WEIGHTS)

    timeline_yearly = [{"year": year, "mentions": yearly_counter[year]} for year in sorted(yearly_counter.keys())]
    timeline_monthly = [
        {"month": month_key, "mentions": monthly_counter.get(month_key, 0)}
        for month_key in month_keys_last_n(MONTHS_WINDOW)
    ]
    top_keywords = merge_keyword_counters(phrase_keywords, unigram_keywords, limit=MAX_KEYWORDS, brand_tokens=brand_tokens)

    scores = {
        "overallSentiment": overall_sentiment_pct,
        "queryScore": query_score,
        "ecoScore": eco_score,
        "innovationScore": innovation_score,
    }

    return {
        "brand": clean_brand,
        "query": query,
        "subreddit": subreddit,
        "samplesCount": len(posts),
        "overallSentiment": overall_sentiment_pct,
        "queryScore": query_score,
        "scores": scores,
        "timeline": timeline_yearly,
        "timelineYearly": timeline_yearly,
        "timelineMonthly": timeline_monthly,
        "topKeywords": top_keywords,
    }