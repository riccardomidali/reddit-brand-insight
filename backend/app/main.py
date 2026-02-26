from dataclasses import dataclass
from datetime import datetime, timezone
from collections import Counter, defaultdict
import logging
import math
import os
import re

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
import praw
from vaderSentiment.vaderSentiment import SentimentIntensityAnalyzer
from dotenv import load_dotenv
from functools import lru_cache
from typing import Any, Optional

app = FastAPI(title="SentiScan API")
logger = logging.getLogger(__name__)

# Load env from backend/.env (same folder as the backend project root)
ENV_PATH = os.path.join(os.path.dirname(__file__), "..", ".env")
load_dotenv(dotenv_path=ENV_PATH, override=True)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:8080", "http://127.0.0.1:8080"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

analyzer = SentimentIntensityAnalyzer()

# ── Optional AI (Transformers) ───────────────────────────────────────────────
# Enable by setting USE_AI=1 in backend/.env (or environment).
# Models are loaded lazily; if transformers isn't installed, we fall back to VADER + keyword heuristics.
USE_AI = os.getenv("USE_AI", "0").strip() in {"1", "true", "True", "YES", "yes"}
AI_SENTIMENT_MODEL = os.getenv(
    "AI_SENTIMENT_MODEL",
    "cardiffnlp/twitter-roberta-base-sentiment-latest",
).strip()
AI_ZEROSHOT_MODEL = os.getenv(
    "AI_ZEROSHOT_MODEL",
    "valhalla/distilbart-mnli-12-1",
).strip()
AI_ZEROSHOT_THRESHOLD = float(os.getenv("AI_ZEROSHOT_THRESHOLD", "0.35"))
AI_MAX_CHARS = int(os.getenv("AI_MAX_CHARS", "900"))
AI_BATCH_SIZE = int(os.getenv("AI_BATCH_SIZE", "16"))
AI_EMBED_MODEL = os.getenv(
    "AI_EMBED_MODEL",
    "sentence-transformers/all-MiniLM-L6-v2",
).strip()
AI_SIM_THRESHOLD = float(os.getenv("AI_SIM_THRESHOLD", "0.32"))

# Token-level truncation for transformers models (keeps us safely under model max length)
AI_TOKEN_MAX_LEN = int(os.getenv("AI_TOKEN_MAX_LEN", "256"))

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
    "eco": 2.5, "environment": 2.0,
    "environmental": 2.0, "biodiversity": 3.0, "biodegradable": 3.5, "compostable": 3.5,
    "plastic": 2.0, "waste": 2.0, "footprint": 2.5,
    "offset": 2.5, "offsets": 2.5, "regenerative": 3.5, "fairtrade": 3.0,
    "sourcing": 1.5, "circular": 2.5,
    "reforestation": 4.0, "deforestation": 3.5, "vegan": 2.5, "cruelty": 2.5,
    "responsible": 2.0, "durable": 2.5, "repairable": 2.5, "repair": 2.0, "longevity": 2.5,
    "bcorp": 2.5, "b-corp": 2.5, "organic": 2.5, "fair-trade": 3.0,
}

ECO_PHRASE_WEIGHTS: dict[str, float] = {
    "carbon footprint": 4.0, "net zero": 4.5, "supply chain": 2.5,
    "ethical sourcing": 4.0, "fair trade": 3.5, "renewable energy": 4.0,
    "circular economy": 4.5, "zero waste": 4.0, "plastic free": 4.0,
    "climate impact": 4.0, "sustainable materials": 4.0, "recycled materials": 4.0,
    "responsible sourcing": 4.0, "carbon neutral": 5.0, "scope emissions": 4.0,
    "ethical brand": 4.0, "ethical company": 4.0, "responsible company": 4.0,
    "sustainable brand": 4.5, "sustainable company": 4.5, "buy it for life": 4.0,
    "repair program": 4.0, "repair service": 4.0, "worn wear": 4.5,
    "dont buy this jacket": 4.5, "don\u2019t buy this jacket": 4.5,
    "reduce consumption": 4.0, "reduce waste": 4.0, "high quality and durable": 4.0,
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
    subreddit_name: str


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

# --- Helper to build robust Reddit search queries from camelCase/PascalCase brand names ---
def build_brand_search_query(brand: str) -> str:
    """Build a more robust Reddit search query for a brand.

    Handles camelCase / PascalCase (e.g., PatagoniaClothing -> "Patagonia Clothing")
    and includes a compact fallback token.

    We keep the original brand too, because some posts mention it exactly.
    """
    b = (brand or "").strip()
    if not b:
        return ""

    # Insert spaces between camelCase / PascalCase boundaries
    spaced = re.sub(r"([a-z])([A-Z])", r"\1 \2", b).strip()
    # Also try a compact variant without separators
    compact = re.sub(r"[^A-Za-z0-9]+", "", b)

    variants = []
    for v in [b, spaced, compact]:
        v = (v or "").strip()
        if not v:
            continue
        if v.lower() not in {x.lower() for x in variants}:
            variants.append(v)

    # Quote variants that contain spaces
    parts = [f'"{v}"' if " " in v else v for v in variants]
    if len(parts) == 1:
        return parts[0]
    return "(" + " OR ".join(parts) + ")"


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


def text_mentions_brand(text: str, brand_tokens: set[str], brand_compact: str) -> bool:
    """
    Hard brand filter on raw text.
    Uses both compact substring matching and token-level matching.
    """
    raw = (text or "").lower().strip()
    if not raw:
        return False

    compact_text = re.sub(r"[^a-z0-9]+", "", raw)
    if brand_compact and brand_compact in compact_text:
        return True

    text_tokens = {normalize_token(tok) for tok in TOKEN_PATTERN.findall(raw)}
    text_tokens.discard("")
    return any(tok in text_tokens for tok in brand_tokens)


def shrink_score_with_confidence(
    score: float,
    sample_size: int,
    neutral_score: float = 50.0,
    prior_weight: float = 15.0,
) -> float:
    """
    Bayesian-style shrinkage: small samples are pulled toward neutral (50).
    """
    if sample_size <= 0:
        return 0.0

    confidence = sample_size / (sample_size + prior_weight)
    shrunk = neutral_score + confidence * (score - neutral_score)
    return round(clamp(shrunk, 0.0, 100.0), 1)


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
    Score 0-100 for a topic (eco / innovation), intended to be interpretable.

    We compute two components on the provided dataset:
      1) Coverage: how often the topic appears (share of engagement-weighted posts that hit)
      2) Topic sentiment: average VADER sentiment among topic-hitting posts (engagement-weighted)

    Final score:
        score = 100 * (0.6 * coverage + 0.4 * normalized_topic_sentiment)

    where normalized_topic_sentiment maps VADER compound [-1..1] -> [0..1].

    This avoids the previous "density" normalization that tended to collapse scores
    near zero for long texts with few keyword mentions.
    """
    if not posts:
        return 0.0

    token_keyword_set = set(token_weights.keys())
    phrase_keyword_set = set(phrase_weights.keys())

    total_weight = 0.0
    hit_weight = 0.0
    hit_sent_sum = 0.0

    for post in posts:
        w = float(post.engagement_weight or 1.0)
        total_weight += w

        token_hit = any(t in token_keyword_set for t in post.token_set)
        phrase_hit = any(p in phrase_keyword_set for p in post.ngrams)

        if token_hit or phrase_hit:
            hit_weight += w
            hit_sent_sum += float(post.sentiment) * w

    if total_weight <= 0.0 or hit_weight <= 0.0:
        return 0.0

    coverage = hit_weight / total_weight  # 0..1
    topic_sent = hit_sent_sum / hit_weight  # -1..1
    topic_sent_norm = (topic_sent + 1.0) / 2.0  # 0..1

    score = 100.0 * (0.6 * coverage + 0.4 * topic_sent_norm)
    return round(clamp(score, 0.0, 100.0), 1)


# --- New calibrated topic score helpers ---
def compute_topic_coverage(
    posts: list[PreparedPost],
    token_weights: dict[str, float],
    phrase_weights: dict[str, float],
) -> float:
    """
    Coverage 0..1: share of engagement-weighted posts that mention the topic.
    This should be computed on an unbiased dataset (e.g. brand-only posts),
    otherwise topic-focused retrieval would artificially inflate coverage.
    """
    if not posts:
        return 0.0

    token_keyword_set = set(token_weights.keys())
    phrase_keyword_set = set(phrase_weights.keys())

    total_weight = 0.0
    hit_weight = 0.0

    for post in posts:
        w = float(post.engagement_weight or 1.0)
        total_weight += w

        token_hit = any(t in token_keyword_set for t in post.token_set)
        phrase_hit = any(p in phrase_keyword_set for p in post.ngrams)

        if token_hit or phrase_hit:
            hit_weight += w

    if total_weight <= 0.0:
        return 0.0
    return clamp(hit_weight / total_weight, 0.0, 1.0)


def compute_topic_sentiment_norm(
    posts: list[PreparedPost],
    token_weights: dict[str, float],
    phrase_weights: dict[str, float],
) -> float:
    """
    Sentiment 0..1 among posts that mention the topic (engagement-weighted).
    Can be computed on a topic-focused dataset to better sample relevant discussion.
    """
    if not posts:
        return 0.5

    token_keyword_set = set(token_weights.keys())
    phrase_keyword_set = set(phrase_weights.keys())

    hit_weight = 0.0
    hit_sent_sum = 0.0

    for post in posts:
        token_hit = any(t in token_keyword_set for t in post.token_set)
        phrase_hit = any(p in phrase_keyword_set for p in post.ngrams)
        if not (token_hit or phrase_hit):
            continue

        w = float(post.engagement_weight or 1.0)
        hit_weight += w
        hit_sent_sum += float(post.sentiment) * w

    if hit_weight <= 0.0:
        return 0.5

    topic_sent = hit_sent_sum / hit_weight  # -1..1
    return clamp((topic_sent + 1.0) / 2.0, 0.0, 1.0)


# Helper to compute total engagement weight for a set of posts
def total_weight(posts: list[PreparedPost]) -> float:
    return sum(float(p.engagement_weight or 1.0) for p in posts) if posts else 0.0


# New helper: sum engagement_weight for posts with actual topic hit (token or phrase)
def topic_hit_weight(
    posts: list[PreparedPost],
    token_weights: dict[str, float],
    phrase_weights: dict[str, float],
) -> float:
    """
    Sum of engagement_weight for posts that actually contain a topic signal
    (keyword or phrase hit) after our preprocessing.
    This prevents Reddit search quirks from inflating topic volume.
    """
    if not posts:
        return 0.0

    token_keyword_set = set(token_weights.keys())
    phrase_keyword_set = set(phrase_weights.keys())

    hit_w = 0.0
    for post in posts:
        token_hit = any(t in token_keyword_set for t in post.token_set)
        phrase_hit = any(p in phrase_keyword_set for p in post.ngrams)
        if token_hit or phrase_hit:
            hit_w += float(post.engagement_weight or 1.0)
    return hit_w

def _truncate_for_ai(text: str) -> str:
    text = (text or "").strip()
    if not text:
        return ""
    if len(text) <= AI_MAX_CHARS:
        return text
    return text[:AI_MAX_CHARS]


@lru_cache(maxsize=1)
def _get_transformers_pipelines() -> Optional[dict[str, Any]]:
    """
    Lazily load transformers pipelines.
    Returns None if transformers isn't available.
    """
    try:
        from transformers import pipeline  # type: ignore
    except Exception:
        return None

    device_env = os.getenv("AI_DEVICE", "-1").strip()
    try:
        device = int(device_env)
    except Exception:
        device = -1

    try:
        sentiment_pipe = pipeline(
            "sentiment-analysis",
            model=AI_SENTIMENT_MODEL,
            device=device,
        )
        zeroshot_pipe = pipeline(
            "zero-shot-classification",
            model=AI_ZEROSHOT_MODEL,
            device=device,
        )
    except Exception as exc:
        logger.warning("Transformers pipelines unavailable; using non-AI sentiment fallback: %s", exc)
        return None
    return {"sentiment": sentiment_pipe, "zeroshot": zeroshot_pipe}


# --- Embedding-based semantic similarity helpers ---
@lru_cache(maxsize=1)
def _get_embedding_components() -> Optional[dict[str, Any]]:
    """Lazily load a lightweight embedding model for semantic similarity."""
    try:
        import torch  # type: ignore
        from transformers import AutoModel, AutoTokenizer  # type: ignore
    except Exception:
        return None

    device_env = os.getenv("AI_DEVICE", "-1").strip()
    try:
        device_i = int(device_env)
    except Exception:
        device_i = -1

    device = torch.device("cpu") if device_i < 0 else torch.device(f"cuda:{device_i}")

    try:
        tokenizer = AutoTokenizer.from_pretrained(AI_EMBED_MODEL)
        model = AutoModel.from_pretrained(AI_EMBED_MODEL)
        model.to(device)
        model.eval()
    except Exception as exc:
        logger.warning("Embedding model unavailable; using heuristic topic scoring fallback: %s", exc)
        return None

    return {"tokenizer": tokenizer, "model": model, "device": device, "torch": torch}


def _mean_pool(last_hidden_state, attention_mask, torch_mod):
    # last_hidden_state: [B, T, H]
    mask = attention_mask.unsqueeze(-1).type_as(last_hidden_state)
    summed = (last_hidden_state * mask).sum(dim=1)
    denom = mask.sum(dim=1).clamp(min=1e-9)
    return summed / denom


def _embed_texts(texts: list[str]) -> list[list[float]]:
    """Return L2-normalized sentence embeddings as python lists."""
    comps = _get_embedding_components()
    if comps is None:
        return []

    tokenizer = comps["tokenizer"]
    model = comps["model"]
    device = comps["device"]
    torch_mod = comps["torch"]

    embs: list[list[float]] = []
    bs = max(1, int(AI_BATCH_SIZE))

    with torch_mod.no_grad():
        for i in range(0, len(texts), bs):
            batch = texts[i : i + bs]
            enc = tokenizer(
                batch,
                padding=True,
                truncation=True,
                max_length=256,
                return_tensors="pt",
            )
            enc = {k: v.to(device) for k, v in enc.items()}
            out = model(**enc)
            pooled = _mean_pool(out.last_hidden_state, enc["attention_mask"], torch_mod)
            pooled = torch_mod.nn.functional.normalize(pooled, p=2, dim=1)
            embs.extend(pooled.detach().cpu().tolist())

    return embs


def _cosine_sim(a: list[float], b: list[float]) -> float:
    # embeddings are L2-normalized -> dot product = cosine
    if not a or not b:
        return 0.0
    return float(sum(x * y for x, y in zip(a, b)))


def _adaptive_similarity_threshold(similarities: list[float], base_threshold: float) -> float:
    """
    If no item reaches the configured threshold, relax it to a high-percentile
    value from the current batch to avoid all-zero topic scores.
    """
    if not similarities:
        return base_threshold
    if any(sim >= base_threshold for sim in similarities):
        return base_threshold

    non_negative = [sim for sim in similarities if sim >= 0.0]
    if not non_negative:
        return base_threshold

    ordered = sorted(non_negative, reverse=True)
    # Keep only the strongest ~12% matches when adapting
    k = max(1, math.ceil(len(ordered) * 0.12))
    candidate = ordered[k - 1]

    # Clamp to avoid over-relaxing to near-random matches
    return clamp(candidate, 0.12, base_threshold)


def _topic_description(topic_label: str) -> str:
    t = (topic_label or "").strip().lower()
    if t == "sustainability":
        return (
            "Discussion about sustainability, environment, carbon footprint, recycling, ethical sourcing, "
            "fair trade, renewable energy, circular economy, emissions, climate impact, eco-friendly materials."
        )
    if t == "innovation":
        return (
            "Discussion about innovation, new technology, engineering, patents, research and development, "
            "AI, machine learning, product design, new materials, performance improvements, technical breakthroughs."
        )
    return f"Discussion about {t}."


def _ai_sentiment_compound(texts: list[str]) -> list[float]:
    """
    Return VADER-like compound in [-1..1] using a transformer sentiment model.
    Uses pos - neg; neutral is implicitly in the middle.
    """
    pipes = _get_transformers_pipelines()
    if pipes is None:
        return [sentiment(t) for t in texts]

    sentiment_pipe = pipes["sentiment"]
    out = sentiment_pipe(
        texts,
        batch_size=AI_BATCH_SIZE,
        truncation=True,
        padding=True,
        max_length=AI_TOKEN_MAX_LEN,
    )

    compounds: list[float] = []
    for item in out:
        label = str(item.get("label", "")).lower()
        score = float(item.get("score", 0.0))

        if "pos" in label:
            pos = score
            neg = 0.0
        elif "neg" in label:
            pos = 0.0
            neg = score
        else:
            pos = 0.0
            neg = 0.0

        compounds.append(clamp(pos - neg, -1.0, 1.0))
    return compounds


def _ai_topic_multilabel(texts: list[str], labels: list[str]) -> list[dict[str, float]]:
    """
    Zero-shot multi-label scores per text: returns list of {label: score}.
    """
    pipes = _get_transformers_pipelines()
    if pipes is None:
        return [{label: 0.0 for label in labels} for _ in texts]

    zs = pipes["zeroshot"]
    results = zs(
        texts,
        candidate_labels=labels,
        multi_label=True,
        hypothesis_template="This text is about {}.",
        truncation=True,
        padding=True,
        max_length=AI_TOKEN_MAX_LEN,
    )

    if isinstance(results, dict):
        results = [results]

    scored: list[dict[str, float]] = []
    for res in results:
        res_labels = [str(x) for x in res.get("labels", [])]
        res_scores = [float(x) for x in res.get("scores", [])]
        d = {lab: 0.0 for lab in labels}
        for lab, sc in zip(res_labels, res_scores):
            if lab in d:
                d[lab] = sc
        scored.append(d)
    return scored


def compute_topic_score_ai(
    brand_posts: list[PreparedPost],
    topic_label: str,
    topic_posts: Optional[list[PreparedPost]] = None,
) -> tuple[float, float, list[dict[str, Any]]]:
    """ 
    Compute (score_0_100, volume_0_1, evidence_posts) for a topic using:
    - semantic similarity (embeddings) for topic detection
    - transformer sentiment for sentiment (fallback to VADER)

    volume: share of engagement-weighted brand posts classified as topic
    sentiment_norm: avg sentiment among topic posts in [0..1]
    score: 100*(0.6*volume + 0.4*sentiment_norm)

    Evidence: top 3 topic posts by (engagement_weight * similarity).
    """
    if not brand_posts:
        return 0.0, 0.0, []
    source_posts = topic_posts if topic_posts else brand_posts
    if not source_posts:
        return 0.0, 0.0, []

    # Prepare texts
    texts = [_truncate_for_ai(p.text) for p in source_posts]
    # Sentiment (AI if available, otherwise VADER)
    sentiments = _ai_sentiment_compound(texts)

    # Topic similarity via embeddings
    topic_desc = _topic_description(topic_label)
    topic_emb_list = _embed_texts([topic_desc])
    text_embs = _embed_texts(texts)

    # If embeddings not available, fall back to a conservative 0 score (avoid misleading output)
    if not topic_emb_list or not text_embs:
        return 0.0, 0.0, []

    topic_emb = topic_emb_list[0]

    # Select keyword sets based on topic_label for hybrid semantic + keyword detection
    topic_lower = (topic_label or "").strip().lower()
    if topic_lower == "sustainability":
        token_weights = ECO_KEYWORD_WEIGHTS
        phrase_weights = ECO_PHRASE_WEIGHTS
    elif topic_lower == "innovation":
        token_weights = INNOVATION_KEYWORD_WEIGHTS
        phrase_weights = INNOVATION_PHRASE_WEIGHTS
    else:
        token_weights = {}
        phrase_weights = {}

    token_keyword_set = set(token_weights.keys())
    phrase_keyword_set = set(phrase_weights.keys())

    # ---- VOLUME: compute on brand_posts ----
    brand_texts = [_truncate_for_ai(p.text) for p in brand_posts]
    brand_embs = _embed_texts(brand_texts)

    total_w = total_weight(brand_posts)
    hit_w = 0.0
    brand_sims = [_cosine_sim(emb, topic_emb) for emb in brand_embs]
    if not brand_sims:
        return 0.0, 0.0, []

    sim_threshold = AI_SIM_THRESHOLD

    # 1) Semantic-first topic detection on brand_posts (coverage dataset)
    for post, sim in zip(brand_posts, brand_sims):
        w = float(post.engagement_weight or 1.0)
        if sim >= sim_threshold:
            hit_w += w

    # 2) Keyword fallback only if semantic coverage has no signal
    if hit_w <= 0.0:
        for post in brand_posts:
            token_hit = any(t in token_keyword_set for t in post.token_set)
            phrase_hit = any(p in phrase_keyword_set for p in post.ngrams)
            if token_hit or phrase_hit:
                hit_w += float(post.engagement_weight or 1.0)

    # ---- SENTIMENT + EVIDENCE: compute on topic-focused posts ----
    hit_sent_sum = 0.0
    source_hit_w = 0.0
    evidence: list[tuple[float, PreparedPost, float]] = []
    source_sims = [_cosine_sim(emb, topic_emb) for emb in text_embs]

    # 1) Semantic-first sentiment/evidence on topic_posts
    for post, sent_c, sim in zip(source_posts, sentiments, source_sims):
        w = float(post.engagement_weight or 1.0)
        if sim >= sim_threshold:
            source_hit_w += w
            hit_sent_sum += ((sent_c + 1.0) / 2.0) * w
            evidence.append((w * sim, post, sim))

    # 2) Keyword fallback only if semantic sentiment/evidence has no signal
    if source_hit_w <= 0.0:
        for post, sent_c, sim in zip(source_posts, sentiments, source_sims):
            w = float(post.engagement_weight or 1.0)
            token_hit = any(t in token_keyword_set for t in post.token_set)
            phrase_hit = any(p in phrase_keyword_set for p in post.ngrams)
            if token_hit or phrase_hit:
                source_hit_w += w
                hit_sent_sum += ((sent_c + 1.0) / 2.0) * w
                evidence.append((w * max(sim, 0.0), post, sim))
    if total_w <= 0.0 or hit_w <= 0.0:
        return 0.0, 0.0, []

    volume = clamp(
        hit_w / total_w,
        0.0,
        1.0,
    )
    sent_norm = clamp(
        (hit_sent_sum / source_hit_w) if source_hit_w > 0.0 else 0.5,
        0.0,
        1.0,
    )
    score = round(clamp(100.0 * (0.6 * volume + 0.4 * sent_norm), 0.0, 100.0), 1)

    evidence.sort(key=lambda x: x[0], reverse=True)
    ev_out: list[dict[str, Any]] = []
    for _, p, sim in evidence[:3]:
        snippet = (p.text or "").strip().replace("\n", " ")
        if len(snippet) > 220:
            snippet = snippet[:220] + "..."
        ev_out.append(
            {
                "subreddit": p.subreddit_name,
                "prob": round(sim, 3),
                "snippet": snippet,
            }
        )

    return score, volume, ev_out

def compute_query_score(posts: list[PreparedPost], query: str, overall_sentiment_pct: float) -> float:
    if not posts:
        return 0.0

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


def scale_coverage_log(coverage: float) -> float:
    if coverage <= 0:
        return 0.0

    scaled = math.log(1 + coverage * 15) / math.log(16)
    return clamp(scaled, 0.0, 1.0)


def compute_topic_scores_heuristic(
    brand_posts: list[PreparedPost],
    eco_posts: list[PreparedPost],
    innovation_posts: list[PreparedPost],
) -> tuple[float, float]:
    eco_coverage = compute_topic_coverage(brand_posts, ECO_KEYWORD_WEIGHTS, ECO_PHRASE_WEIGHTS)
    eco_sent_norm = compute_topic_sentiment_norm(eco_posts, ECO_KEYWORD_WEIGHTS, ECO_PHRASE_WEIGHTS)
    eco_coverage_scaled = scale_coverage_log(eco_coverage)
    eco_score = round(
        100 * (
            0.85 * eco_coverage_scaled +
            0.15 * eco_sent_norm
        ),
        1,
    )

    innov_coverage = compute_topic_coverage(brand_posts, INNOVATION_KEYWORD_WEIGHTS, INNOVATION_PHRASE_WEIGHTS)
    innov_sent_norm = compute_topic_sentiment_norm(innovation_posts, INNOVATION_KEYWORD_WEIGHTS, INNOVATION_PHRASE_WEIGHTS)
    innov_coverage_scaled = scale_coverage_log(innov_coverage)
    innovation_score = round(
        100 * (
            0.85 * innov_coverage_scaled +
            0.15 * innov_sent_norm
        ),
        1,
    )

    print(f"ECO | coverage={eco_coverage:.3f} scaled={eco_coverage_scaled:.3f} sent={eco_sent_norm:.3f} score={eco_score}", flush=True)
    print(f"INNOV | coverage={innov_coverage:.3f} scaled={innov_coverage_scaled:.3f} sent={innov_sent_norm:.3f} score={innovation_score}", flush=True)

    return eco_score, innovation_score


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
                # Engagement weight: combine upvotes + comments for a more stable importance signal
                engagement = max(int(post.score or 0), 0) + max(int(post.num_comments or 0), 0)
                engagement_weight = 1.0 + min(2.0, math.log1p(engagement) / 3.0)

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
                        subreddit_name=post.subreddit.display_name,
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
    brand_q = build_brand_search_query(clean_brand)
    search_q = brand_q if not query else f"{brand_q} {query}"
    posts = prepare_posts(
        brand=clean_brand,
        subreddit=subreddit,
        search_query=search_q,
        limit_posts=limit_posts,
    )

    # Fetch brand-only posts for brand perception scores (ecoScore, innovationScore)
    brand_posts = prepare_posts(
        brand=clean_brand,
        subreddit=subreddit,
        search_query=brand_q,
        limit_posts=limit_posts,
    )

    # Topic-focused datasets (still independent from the user's query):
    # we intentionally bias retrieval toward eco / innovation discussions to make scores meaningful.
    eco_focus_query = (
        f'{brand_q} (sustainability OR sustainable OR recycled OR recyclable OR recycling OR '
        f'"carbon footprint" OR "net zero" OR "carbon neutral" OR emissions OR climate OR renewable OR '
        f'"ethical sourcing" OR "fair trade" OR "circular economy" OR "zero waste")'
    )
    innovation_focus_query = (
        f'{brand_q} (innovation OR innovative OR technology OR tech OR "artificial intelligence" OR '
        f'"machine learning" OR "generative ai" OR "new technology" OR patent OR engineering OR '
        f'"product design" OR "new materials" OR "data science")'
    )

    # Keep these separate from user query to represent brand perception by topic
    eco_posts = prepare_posts(
        brand=clean_brand,
        subreddit=subreddit,
        search_query=eco_focus_query,
        limit_posts=max(200, min(800, limit_posts)),
    )
    innovation_posts = prepare_posts(
        brand=clean_brand,
        subreddit=subreddit,
        search_query=innovation_focus_query,
        limit_posts=max(200, min(800, limit_posts)),
    )

    brand_tokens, brand_compact = build_brand_tokens(clean_brand)

    print(f"DEBUG | brand_posts before filter={len(brand_posts)}", flush=True)
    # Hard brand filter to remove topic-query noise not truly about the brand
    brand_posts = [p for p in brand_posts if text_mentions_brand(p.text, brand_tokens, brand_compact)]
    eco_posts = [p for p in eco_posts if text_mentions_brand(p.text, brand_tokens, brand_compact)]
    innovation_posts = [p for p in innovation_posts if text_mentions_brand(p.text, brand_tokens, brand_compact)]
    print(f"DEBUG | brand_posts after filter={len(brand_posts)} eco_posts={len(eco_posts)} innov_posts={len(innovation_posts)}", flush=True)

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


    # Eco and Innovation scores are query-independent.
    # Preferred (if enabled): AI zero-shot topic classification on brand-only posts.
    # Fallback: topic-focused retrieval + keyword/phrase heuristics.
    topic_evidence = {"eco": [], "innovation": []}
    heuristic_eco_score, heuristic_innovation_score = compute_topic_scores_heuristic(
        brand_posts=brand_posts,
        eco_posts=eco_posts,
        innovation_posts=innovation_posts,
    )

    if USE_AI and _get_embedding_components() is not None:
        try:
            eco_ai_score, eco_volume, eco_ev = compute_topic_score_ai(
                brand_posts, topic_label="sustainability", topic_posts=eco_posts
            )
            innovation_ai_score, innovation_volume, innov_ev = compute_topic_score_ai(
                brand_posts, topic_label="innovation", topic_posts=innovation_posts
            )

            # Per-topic fallback: AI can succeed technically but still return no signal.
            if eco_volume > 0.0 and eco_ev:
                eco_score = eco_ai_score
                topic_evidence["eco"] = eco_ev
            else:
                eco_score = heuristic_eco_score

            if innovation_volume > 0.0 and innov_ev:
                innovation_score = innovation_ai_score
                topic_evidence["innovation"] = innov_ev
            else:
                innovation_score = heuristic_innovation_score
        except Exception as exc:
            logger.warning("AI topic scoring failed; using heuristic fallback: %s", exc)
            eco_score, innovation_score = heuristic_eco_score, heuristic_innovation_score
    else:
        eco_score, innovation_score = heuristic_eco_score, heuristic_innovation_score

    # Confidence shrinkage to stabilize scores when sample size is small
    eco_hit_posts = sum(
        1 for p in brand_posts
        if any(t in ECO_KEYWORD_WEIGHTS for t in p.token_set)
        or any(ph in ECO_PHRASE_WEIGHTS for ph in p.ngrams)
    )
    innov_hit_posts = sum(
        1 for p in brand_posts
        if any(t in INNOVATION_KEYWORD_WEIGHTS for t in p.token_set)
        or any(ph in INNOVATION_PHRASE_WEIGHTS for ph in p.ngrams)
    )
    prior_weight = clamp(10.0 + 0.05 * len(brand_posts), 10.0, 40.0)
    if eco_score > 0.0:
        eco_score = shrink_score_with_confidence(
            eco_score,
            eco_hit_posts,
            neutral_score=30.0,
            prior_weight=prior_weight,
        )
    if innovation_score > 0.0:
        innovation_score = shrink_score_with_confidence(
            innovation_score,
            innov_hit_posts,
            neutral_score=35.0,
            prior_weight=prior_weight,
        )

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

    print(f"FINAL | eco_score={eco_score} innovation_score={innovation_score}", flush=True)

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
        "topicEvidence": topic_evidence,
    }
