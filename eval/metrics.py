"""
metrics.py — the numeric core of the psychomanteum eval harness.

This module is the *delegated compute* called by `agents/eval-scorer.md`. It turns
captured generations into the raw numbers behind the dashboard. It does NOT make
the dashboard, run the LLM pairwise judge, or decide anything—the agent does
that. Here we only measure.

The epistemics this module is built to honor (see `prompts/eval-methodology.md`):

  * STYLE and CONTENT are DIFFERENT axes and must never be conflated. The style
    axis is the headline ("how it says"); the content axis is the x-axis of the
    transfer curve ("what it says about"). Mixing them resurrects topic-as-voice,
    the cardinal trap (Trap 1).
  * Dashboard, never one number. This module returns *components* — distances,
    intervals, effect sizes, curve points—not a verdict.
  * The transfer curve plots style-shift (y, content-masked, baseline-subtracted)
    against measured content-distance (x). Flat = robust transfer; decaying =
    home-turf-only.
  * SIGN CONVENTION — ONE defined direction: toward-corpus is POSITIVE,
    everywhere. Distances are lower-is-closer, so every facet-vs-baseline shift
    is computed as (baseline_dist-facet_dist): a facet that moves CLOSER to the
    corpus centroid than the baseline yields a POSITIVE mean_shift / style-shift.
    `paired_stats` and `fit_transfer`'s y-axis share this convention so the
    headline number and the transfer curve never disagree in sign.

Engineering contract:
  * RUNS with ONLY numpy + scikit-learn (+ scipy optional). No model downloads,
    no network. TF-IDF + classical stylometry are the always-on floor.
  * Neural embeddings (sentence-transformers; StyleDistance/STEL) are OPTIONAL,
    behind guarded imports. When absent we fall back and record `method` so the
    caller can SEE which path ran (a missing signal is reported, never hidden).
  * Determinism: the ONLY randomness is the seeded bootstrap in `paired_stats`,
    using numpy.random.default_rng(0).

Public functions (signatures are a hard contract with eval-scorer):
  style_distance(texts, corpus_passages, corpus_weights=None)    -> list[float]
  content_distance(texts, corpus_passages, corpus_weights=None)  -> list[float]
  paired_stats(facet_vals, baseline_vals)           -> dict   (toward-corpus +)
  fit_transfer(distance, style_shift, tier)         -> dict
  collapse_rate(facet_path)                          -> dict

Round-3 additions (new diagnostics; do not change the contract above):
  centroid_confound_check(corpus_held_out_high_voice, distractor_outputs,
                          corpus_passages, corpus_weights=None)   -> dict
      Auto-detects a GENRE-confounded style-centroid (the "ranks Fisher above
      Sexton" tripwire): if the corpus's own held-out high-voice passages score
      FARTHER from the style-centroid than wrong-lineage distractor outputs, the
      ruler is measuring genre not voice -> fall back to the pairwise headline.
  verbatim_echo(texts, corpus_passages, n_lo=4, n_hi=8)          -> list[dict]
      Measures the "hollow tell": how much each text recites the corpus verbatim
      (per-n echo fractions + longest contiguous verbatim span). Only MEASURES;
      the scorer owns the "hollow" threshold. The strangeness substrate.

`corpus_weights` (round-2) is an OPTIONAL list parallel to corpus_passages that
voice-stratifies the centroid: each passage's contribution to the corpus centroid
is weighted (high voice_charge -> 1.0, medium -> 0.5, low -> 0.0 by convention,
but weights are taken as given). Default None = uniform (the original behavior).
A corpus entry may instead be a dict carrying a `voice_charge` field, from which
the weight is derived. This points the ruler at the voice-bearing fragments
rather than letting encyclopedic scaffolding dilute the centroid.

Each distance function also exposes a sibling `*_introspect` that returns the
same distances PLUS a `method` record (which feature path actually ran), so the
agent can report availability honestly. The bare functions return just the list,
matching the contract exactly.
"""

from __future__ import annotations

import math
import re
from collections import Counter
from typing import Dict, List, Optional, Tuple

import numpy as np

# scikit-learn is a hard dependency of the always-on floor.
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity


# --------------------------------------------------------------------------- #
# Built-in English function-word list (shipped — no download).
#
# Function words carry STYLE (how a mind distributes the, of, but, would...) and
# almost no TOPIC. They are the classical backbone of authorship/stylometry
# (Mosteller & Wallace forward). We ship our own list so the module has zero
# network/download dependency. ~165 high-frequency closed-class words: articles,
# pronouns, prepositions, conjunctions, auxiliaries/modals, particles, common
# determiners/quantifiers. Deliberately NOT content nouns/verbs/adjectives.
# --------------------------------------------------------------------------- #
FUNCTION_WORDS: Tuple[str, ...] = (
    # articles / determiners
    "a", "an", "the", "this", "that", "these", "those", "each", "every",
    "either", "neither", "another", "such", "what", "which", "whatever",
    "whichever",
    # quantifiers
    "all", "any", "both", "few", "many", "most", "much", "no", "none", "some",
    "several", "enough", "more", "less", "least", "fewer", "lot", "lots",
    # personal / possessive / reflexive pronouns
    "i", "me", "my", "mine", "myself",
    "we", "us", "our", "ours", "ourselves",
    "you", "your", "yours", "yourself", "yourselves",
    "he", "him", "his", "himself",
    "she", "her", "hers", "herself",
    "it", "its", "itself",
    "they", "them", "their", "theirs", "themselves",
    "one", "ones", "oneself",
    # demonstrative / relative / interrogative
    "who", "whom", "whose", "where", "when", "why", "how",
    "there", "here", "then",
    # prepositions
    "about", "above", "across", "after", "against", "along", "among", "around",
    "at", "before", "behind", "below", "beneath", "beside", "besides",
    "between", "beyond", "by", "down", "during", "for", "from", "in", "inside",
    "into", "near", "of", "off", "on", "onto", "out", "outside", "over",
    "past", "since", "through", "throughout", "to", "toward", "towards",
    "under", "underneath", "until", "up", "upon", "with", "within", "without",
    # conjunctions
    "and", "but", "or", "nor", "so", "yet", "for", "because", "although",
    "though", "while", "whereas", "if", "unless", "until", "as", "than",
    "whether", "however", "therefore", "thus", "hence", "moreover",
    # auxiliaries / modals / copula
    "be", "am", "is", "are", "was", "were", "been", "being",
    "have", "has", "had", "having",
    "do", "does", "did", "doing", "done",
    "will", "would", "shall", "should", "can", "could", "may", "might",
    "must", "ought",
    # particles / negation / common adverbs of degree
    "not", "no", "yes", "very", "too", "just", "only", "even", "also",
    "still", "again", "ever", "never", "always", "almost", "quite", "rather",
    "perhaps", "maybe", "indeed", "anyway", "somewhat",
    # high-freq misc closed-class
    "now", "well", "back", "out", "up",
)

# A frozenset for O(1) membership; de-duplicated (the tuple has a few intentional
# repeats like "for"/"until"/"up" across categories for readability).
_FUNCTION_WORD_SET = frozenset(FUNCTION_WORDS)

# Token pattern: words (letters + internal apostrophes) OR single punctuation.
_WORD_RE = re.compile(r"[A-Za-z]+(?:'[A-Za-z]+)?")
_SENT_SPLIT_RE = re.compile(r"[.!?]+")

# Punctuation marks whose RATE is a style feature.
_PUNCT_MARKS = (",", ".", ";", ":", "?", "!", "-", "—", "(", ")", "'", '"',
                "…", "/")


# --------------------------------------------------------------------------- #
# Optional neural backends (guarded — module imports & runs without them).
# --------------------------------------------------------------------------- #
# StyleDistance / STEL model id (the content-masked style embedding upgrade).
_STYLE_MODEL_ID = "StyleDistance/styledistance"
# General content embedding (small, fast) used for the x-axis when available.
_CONTENT_MODEL_ID = "sentence-transformers/all-MiniLM-L6-v2"

# Module-level caches so we don't reload a model per call within a process.
_ST_AVAILABLE: Optional[bool] = None
_style_model = None
_content_model = None


def _sentence_transformers_available() -> bool:
    """True iff sentence-transformers can be imported. Cached; no network here."""
    global _ST_AVAILABLE
    if _ST_AVAILABLE is None:
        try:
            import sentence_transformers  # noqa: F401
            _ST_AVAILABLE = True
        except Exception:
            # ImportError, or any heavy-dep failure (torch missing, etc.)
            _ST_AVAILABLE = False
    return _ST_AVAILABLE


def _load_style_model():
    """Load the StyleDistance/STEL model if possible; else None (no raise)."""
    global _style_model
    if _style_model is not None:
        return _style_model
    if not _sentence_transformers_available():
        return None
    try:
        from sentence_transformers import SentenceTransformer
        _style_model = SentenceTransformer(_STYLE_MODEL_ID)
    except Exception:
        # Model not cached locally / download blocked / id moved — fall back.
        _style_model = None
    return _style_model


def _load_content_model():
    """Load the content embedding model if possible; else None (no raise)."""
    global _content_model
    if _content_model is not None:
        return _content_model
    if not _sentence_transformers_available():
        return None
    try:
        from sentence_transformers import SentenceTransformer
        _content_model = SentenceTransformer(_CONTENT_MODEL_ID)
    except Exception:
        _content_model = None
    return _content_model


def _encode_independent(model, texts: List[str]) -> np.ndarray:
    """Embed each text in its OWN encode() call (batch size 1), then stack.

    WHY (the batch-leak fix): SentenceTransformer.encode() pads every text in a
    call to the longest sequence in that BATCH, and these models run in reduced
    precision (e.g. bfloat16). The two together make a single text's embedding
    depend on its batch-mates—the same text encoded alone vs alongside a longer
    text differs at the ~1e-3 level. That batch coupling silently leaks into the
    distance, so f([A], C) != f([A, B], C)[0]. Encoding each text separately
    removes the padding/precision coupling entirely: a text's embedding (and thus
    its distance-to-corpus-centroid) is identical regardless of what else is in
    the batch. Slightly slower, but correctness-critical for batch-independence.

    Empty input -> a (0, 0) array so callers can hstack/centroid without a
    special case.
    """
    if not texts:
        return np.zeros((0, 0), dtype=np.float64)
    rows = [
        np.asarray(
            model.encode([t], convert_to_numpy=True,
                         normalize_embeddings=True)[0],
            dtype=np.float64,
        )
        for t in texts
    ]
    return np.vstack(rows)


# --------------------------------------------------------------------------- #
# Small numeric helpers.
# --------------------------------------------------------------------------- #
def _cosine_distance_to_centroid(vectors: np.ndarray,
                                 centroid: np.ndarray) -> List[float]:
    """Cosine distance (1 - cosine similarity) of each row to a centroid vector.

    We choose COSINE because both axes are high-dimensional sparse/ratio feature
    spaces where direction (the *profile* of feature emphasis) matters far more
    than magnitude (raw text length). Distance is in [0, 2]; for non-negative
    feature spaces (counts/ratios) it sits in [0, 1].
    """
    centroid = centroid.reshape(1, -1)
    sims = cosine_similarity(vectors, centroid).reshape(-1)
    return [float(1.0 - s) for s in sims]


def _safe_div(a: float, b: float) -> float:
    return float(a) / float(b) if b else 0.0


# --------------------------------------------------------------------------- #
# Voice-stratified centroid (round-2).
#
# The corpus mixes encyclopedic scaffolding (low voice) with voice-bearing
# source (high voice). A UNIFORM centroid is diluted by the scaffolding and ends
# up pointing at TOPIC rather than VOICE. `corpus_weights` lets the caller weight
# each passage's contribution to the centroid. The canonical mapping from a
# `voice_charge` label to a weight is high=1.0 / medium=0.5 / low=0.0, but the
# functions take numeric weights AS GIVEN; this map is only used to derive a
# weight when a corpus entry is a dict carrying a `voice_charge` field.
# --------------------------------------------------------------------------- #
_VOICE_CHARGE_WEIGHTS: Dict[str, float] = {"high": 1.0, "medium": 0.5, "low": 0.0}


def _voice_charge_to_weight(charge) -> float:
    """Map a voice_charge value to a centroid weight.

    Accepts the string labels high/medium/low (case-insensitive) or a numeric
    value (passed through). Unknown labels fall back to 1.0 (treat as voice-
    bearing rather than silently dropping a passage).
    """
    if isinstance(charge, (int, float)) and not isinstance(charge, bool):
        return float(charge)
    if isinstance(charge, str):
        return _VOICE_CHARGE_WEIGHTS.get(charge.strip().lower(), 1.0)
    return 1.0


def _normalize_corpus(
    corpus_passages: List,
    corpus_weights: Optional[List[float]] = None,
) -> Tuple[List[str], Optional[List[float]]]:
    """Split a corpus into (passage strings, optional weights).

    A corpus entry may be a plain string OR a dict carrying at least a text field
    (`text` / `passage` / `content`) and optionally `voice_charge` (or `weight`).
    Returns the list of passage strings plus a parallel weight list.

    Precedence for weights:
      1. an explicit `corpus_weights` argument (used verbatim) wins;
      2. else, per-entry dict weights (`weight`, or derived from `voice_charge`);
      3. else None (uniform — preserves the original behavior and all old tests).
    """
    passages: List[str] = []
    derived: List[float] = []
    saw_dict_weight = False
    for entry in corpus_passages:
        if isinstance(entry, dict):
            text = (entry.get("text") or entry.get("passage")
                    or entry.get("content") or "")
            passages.append(str(text))
            if "weight" in entry:
                derived.append(float(entry["weight"]))
                saw_dict_weight = True
            elif "voice_charge" in entry:
                derived.append(_voice_charge_to_weight(entry["voice_charge"]))
                saw_dict_weight = True
            else:
                derived.append(1.0)
        else:
            passages.append(str(entry))
            derived.append(1.0)

    if corpus_weights is not None:
        weights = [float(w) for w in corpus_weights]
        if len(weights) != len(passages):
            raise ValueError(
                f"corpus_weights length ({len(weights)}) must match "
                f"corpus_passages length ({len(passages)}).")
        return passages, weights
    if saw_dict_weight:
        return passages, derived
    return passages, None


def _weighted_centroid(rows: np.ndarray,
                       weights: Optional[List[float]]) -> np.ndarray:
    """Centroid of `rows`; weighted mean if `weights` given, else plain mean.

    Weights are the per-row contribution to the centroid (voice-stratification).
    A degenerate all-zero (or empty/negative-sum) weight vector falls back to the
    uniform mean so the ruler is never undefined.
    """
    if weights is None:
        return rows.mean(axis=0)
    w = np.asarray(weights, dtype=np.float64)
    total = float(w.sum())
    if not np.isfinite(total) or total <= 0.0:
        return rows.mean(axis=0)
    return (rows * w.reshape(-1, 1)).sum(axis=0) / total


# --------------------------------------------------------------------------- #
# STYLE axis — content-masked classical stylometry (always-on).
# --------------------------------------------------------------------------- #
def _function_word_freqs(tokens: List[str]) -> np.ndarray:
    """Relative frequency of each function word over ALL word tokens.

    Content-masked by construction: only closed-class function words are counted;
    content nouns/verbs/adjectives contribute to the denominator but never to a
    feature dimension, so topic cannot move this vector's direction.
    """
    n = len(tokens)
    counts = Counter(t for t in tokens if t in _FUNCTION_WORD_SET)
    return np.array([_safe_div(counts.get(w, 0), n) for w in FUNCTION_WORDS],
                    dtype=np.float64)


def _mask_content_for_char_ngrams(text: str) -> str:
    """Mask content tokens so char n-grams capture STYLE, not topic.

    Char n-grams normally leak topic (they pick up content-word substrings). To
    keep the style axis content-masked we rebuild the string keeping ONLY:
      * function words (verbatim — their spelling/morphology is style),
      * punctuation and whitespace (style),
    and replacing every content word with a single placeholder char "x" repeated
    to preserve its length (length/rhythm is style; the letters are topic). This
    way char n-grams encode the *shape* of the prose (how punctuation, function
    words, and word-lengths interleave) without encoding which content words
    appear.
    """
    out = []
    i = 0
    for m in _WORD_RE.finditer(text):
        # keep inter-token chars (spaces/punct) verbatim
        out.append(text[i:m.start()])
        word = m.group(0)
        if word.lower() in _FUNCTION_WORD_SET:
            out.append(word.lower())
        else:
            out.append("x" * len(word))
        i = m.end()
    out.append(text[i:])
    return "".join(out).lower()


def _char_ngram_counts(masked_text: str, lo: int = 2, hi: int = 4) -> Counter:
    """Char n-gram (lo..hi) counts over the content-MASKED string."""
    c: Counter = Counter()
    s = masked_text
    L = len(s)
    for n in range(lo, hi + 1):
        if L < n:
            continue
        for k in range(L - n + 1):
            c[s[k:k + n]] += 1
    return c


def _punctuation_whitespace_rates(text: str) -> np.ndarray:
    """Per-character rates of each punctuation mark + whitespace + uppercase."""
    L = max(len(text), 1)
    feats = [_safe_div(text.count(p), L) for p in _PUNCT_MARKS]
    feats.append(_safe_div(sum(ch.isspace() for ch in text), L))
    feats.append(_safe_div(sum(ch.isupper() for ch in text), L))
    return np.array(feats, dtype=np.float64)


def _sentence_length_stats(text: str) -> np.ndarray:
    """Distribution stats of sentence lengths (in word tokens)."""
    sents = [s for s in _SENT_SPLIT_RE.split(text) if s.strip()]
    lengths = [len(_WORD_RE.findall(s)) for s in sents]
    lengths = [x for x in lengths if x > 0]
    if not lengths:
        return np.zeros(5, dtype=np.float64)
    arr = np.array(lengths, dtype=np.float64)
    return np.array([
        float(arr.mean()),
        float(arr.std()),
        float(arr.min()),
        float(arr.max()),
        float(np.median(arr)),
    ], dtype=np.float64)


def _type_token_ratio(tokens: List[str]) -> float:
    """Lexical-diversity ratio: distinct word types / total word tokens.

    A whole-vocabulary count (not masked) — TTR is a *rate*, a single scalar,
    and reflects repetition/variety of the writing rather than which topics are
    present. One scalar cannot encode topic the way a per-word vector could.
    """
    if not tokens:
        return 0.0
    return _safe_div(len(set(tokens)), len(tokens))


def _raw_style_matrix(texts: List[str],
                      char_vocab_idx: Dict[str, int]) -> np.ndarray:
    """Build the RAW (un-scaled) content-masked style matrix for `texts`.

    Uses a FIXED char-ngram vocabulary (`char_vocab_idx`) so the column space is
    defined externally (by the corpus) and identical across calls — text n-grams
    outside that vocabulary are dropped (OOV -> 0 columns). The function-word,
    punctuation, sentence-length, and TTR blocks are intrinsically fixed-width.

    Components, concatenated (scaling happens later, corpus-only):
      [function-word freqs] [char n-gram freqs, masked, corpus vocab]
      [punct/ws rates] [sentence-length stats] [type-token ratio]
    """
    tok_lists = [[t.lower() for t in _WORD_RE.findall(t)] for t in texts]

    # Function-word block.
    fw = np.vstack([_function_word_freqs(tl) for tl in tok_lists])

    # Char n-gram block (content-masked) projected onto the FIXED corpus vocab.
    masked = [_mask_content_for_char_ngrams(t) for t in texts]
    counts = [_char_ngram_counts(m) for m in masked]
    cg = np.zeros((len(texts), len(char_vocab_idx)), dtype=np.float64)
    for r, c in enumerate(counts):
        total = sum(c.values()) or 1
        for g, v in c.items():
            j = char_vocab_idx.get(g)
            if j is not None:                # OOV n-grams drop (no new columns)
                cg[r, j] = v / total         # relative freq
    if not char_vocab_idx:                   # corpus had no char-ngrams
        cg = np.zeros((len(texts), 0), dtype=np.float64)

    # Punctuation/whitespace block.
    pw = np.vstack([_punctuation_whitespace_rates(t) for t in texts])

    # Sentence-length-distribution block.
    sl = np.vstack([_sentence_length_stats(t) for t in texts])

    # Type-token-ratio block (single column).
    ttr = np.array([[_type_token_ratio(tl)] for tl in tok_lists],
                   dtype=np.float64)

    return np.hstack([fw, cg, pw, sl, ttr])


def _fit_style_space(corpus_passages: List[str],
                     corpus_weights: Optional[List[float]] = None
                     ) -> Dict[str, object]:
    """Fit the classical style space on the CORPUS ONLY (the ruler).

    Returns the fixed char-ngram vocabulary, the per-column scale (corpus STD,
    used WITHOUT mean-subtraction so vectors stay non-negative and the corpus
    centroid is a meaningful non-zero direction), and the corpus centroid in the
    scaled space. The text under test never participates in defining any of these
    — it is only ever projected in (no train/test leakage; the thing being
    measured does not shape the ruler).

    `corpus_weights` (round-2 voice-stratification): when given, the CENTROID is
    the weighted mean of the scaled corpus rows (voice-bearing passages pull the
    ruler harder). The SCALE stays the unweighted corpus column STD — it only
    normalizes feature dimensions and should reflect the whole corpus's spread.
    """
    # Char-ngram vocabulary from the corpus only.
    masked = [_mask_content_for_char_ngrams(t) for t in corpus_passages]
    counts = [_char_ngram_counts(m) for m in masked]
    vocab = sorted({g for c in counts for g in c})
    char_vocab_idx = {g: j for j, g in enumerate(vocab)}

    corpus_raw = _raw_style_matrix(corpus_passages, char_vocab_idx)

    # Scale = corpus column STD ONLY (no mean subtraction). Guard zero-variance
    # columns with 1.0 so a feature constant across the corpus is left as-is.
    scale = corpus_raw.std(axis=0, keepdims=True)
    scale[scale == 0] = 1.0
    corpus_scaled = corpus_raw / scale
    centroid = _weighted_centroid(corpus_scaled, corpus_weights)
    return {"char_vocab_idx": char_vocab_idx, "scale": scale,
            "centroid": centroid}


def _project_style(texts: List[str], space: Dict[str, object]) -> np.ndarray:
    """Project `texts` into a style space already fit on the corpus.

    Applies the corpus-derived char vocab and corpus-derived column scale. The
    result is directly comparable (cosine) to the corpus centroid in `space`.
    """
    raw = _raw_style_matrix(texts, space["char_vocab_idx"])  # type: ignore[arg-type]
    return raw / space["scale"]  # type: ignore[operator]


def _style_distance_impl(texts: List[str],
                         corpus_passages: List,
                         corpus_weights: Optional[List[float]] = None
                         ) -> Tuple[List[float], Dict]:
    """Core style-distance with method introspection.

    The neural StyleDistance/STEL embedding is used ONLY if importable AND the
    model loads locally; otherwise we fall back to classical stylometry. When
    both are available we still report classical as primary (it is the
    always-on, audited floor) and attach neural as an additional component by
    concatenation, so an upgrade strictly *adds* signal without changing the
    contract. The `method` dict tells the caller exactly what ran.

    `corpus_weights` (round-2 voice-stratification): optional list parallel to
    `corpus_passages` weighting each passage's contribution to the centroid (see
    `_weighted_centroid`). When a corpus entry is a dict with a `voice_charge`
    field, the weight is derived from it; an explicit `corpus_weights` argument
    overrides any per-entry weights. Default None = uniform (original behavior).
    """
    if not texts:
        return [], {"method": "none", "reason": "no input texts"}
    if not corpus_passages:
        raise ValueError("style_distance: corpus_passages must be non-empty "
                         "(it defines the style-centroid).")

    corpus_texts, weights = _normalize_corpus(corpus_passages, corpus_weights)

    method: Dict[str, object] = {
        "method": "classical_stylometry",
        "content_masked": True,
        "components": ["function_words", "char_ngrams_2_4_masked",
                       "punct_whitespace_rates", "sentence_length_stats",
                       "type_token_ratio"],
        "distance": "cosine",
        "scaling": "corpus_std_only_no_mean_subtraction",
        "space_fit_on": "corpus_passages_only",
        "centroid_weighting": "voice_stratified" if weights is not None
                              else "uniform",
        "neural_style_embedding": False,
        "neural_model_id": None,
    }
    # corpus_weights is NEAR-INERT on the content-MASKED style axis (round-2
    # finding: weighting moves the masked-style centroid only ~1e-04 cosine,
    # because voice_charge varies along CONTENT, which this axis masks). The
    # parameter is honored (the centroid IS the weighted mean) but the effect is
    # negligible here; the right lever on the style axis is a curated / genre-
    # matched corpus SUBSET passed by the caller (e.g. verse-only for a poetry
    # lineage), NOT per-passage weights. Flag it so the caller does not mistake a
    # ~no-op for a working knob. (On the CONTENT axis weights are effective — no
    # warning there.) See eval/README.md "Voice-stratified centroid".
    if weights is not None:
        method["style_weighting_warning"] = (
            "corpus_weights is near-inert on the content-masked style axis "
            "(voice_charge varies along content, which this axis masks; effect "
            "~1e-04 cosine). To point the style ruler at voice, pass a curated / "
            "genre-matched corpus SUBSET instead of weights.")

    # ---- Fit the measurement space on the CORPUS ONLY, then project texts. ----
    # The corpus defines the ruler (vocabulary, scale, centroid); the texts under
    # test are only ever projected into that fixed space. This makes each text's
    # distance independent of which other texts share the batch, and well-defined
    # for a single text (no mean-centering over [text + corpus] degeneracy).
    space = _fit_style_space(corpus_texts, weights)
    text_vecs = _project_style(texts, space)
    centroid = np.asarray(space["centroid"], dtype=np.float64)

    style_model = _load_style_model()
    if style_model is not None:
        try:
            # CONTENT-MASK before the neural encode — same discipline as the
            # classical block. StyleDistance is *meant* to be content-independent,
            # but on short passages the raw embedding still leaks topic, and the
            # (larger-magnitude) neural block then dominates the concatenated
            # cosine and can rank an off-register text CLOSER to the corpus than
            # an on-register one (topic-as-voice, Trap 1). Feeding the SAME masked
            # surface the classical path uses (function words + punctuation kept,
            # content words length-preserved as "x") keeps the neural block on the
            # style axis instead of collapsing toward topic.
            masked_corpus = [_mask_content_for_char_ngrams(t)
                             for t in corpus_texts]
            masked_texts = [_mask_content_for_char_ngrams(t) for t in texts]

            # Encode corpus and texts separately. Texts are encoded INDEPENDENTLY
            # (one encode() call each) so a text's embedding — and its distance —
            # never depends on its batch-mates (see `_encode_independent`: bf16 +
            # batch-padding otherwise couples them at ~1e-3). The corpus is fixed
            # input, so we encode it the same independent way to keep its centroid
            # bit-for-bit stable across calls. Scale by CORPUS-only column STD (no
            # mean subtraction); centroid from corpus rows — corpus-defines-the-
            # ruler, exactly as the classical block.
            corpus_emb = _encode_independent(style_model, masked_corpus)
            text_emb = _encode_independent(style_model, masked_texts)
            scale = corpus_emb.std(axis=0, keepdims=True)
            scale[scale == 0] = 1.0
            corpus_emb_s = corpus_emb / scale
            text_emb_s = text_emb / scale
            # Concatenate neural block onto the classical projection + centroid.
            # The neural centroid is voice-stratified with the SAME weights.
            text_vecs = np.hstack([text_vecs, text_emb_s])
            centroid = np.concatenate(
                [centroid, _weighted_centroid(corpus_emb_s, weights)])
            method["method"] = "classical_stylometry+neural_style"
            method["content_masked"] = True
            method["neural_style_embedding"] = True
            method["neural_style_content_masked"] = True
            method["neural_model_id"] = _STYLE_MODEL_ID
        except Exception:
            pass  # keep classical-only

    return _cosine_distance_to_centroid(text_vecs, centroid), method


def style_distance(texts: List[str],
                   corpus_passages: List,
                   corpus_weights: Optional[List[float]] = None) -> List[float]:
    """Distance of each text to the corpus STYLE-centroid (content-masked).

    See module docstring & methodology Trap 1. Returns cosine distances (higher
    = stylistically farther from the corpus). For the method that ran, call
    `style_distance_introspect`.

    `corpus_weights` (round-2): optional voice-stratification of the centroid —
    a list parallel to `corpus_passages` (high voice_charge -> 1.0, medium ->
    0.5, low -> 0.0 by convention, but taken as given). Alternatively pass
    corpus entries as dicts with a `voice_charge` field and the weights are
    derived. Default None = uniform centroid (original behavior).

    NOTE — corpus_weights is NEAR-INERT on this (content-MASKED) style axis.
    The round-2 cohort measured it moving the masked-style centroid only
    ~1e-04 cosine: `voice_charge` varies along CONTENT, and the style axis
    masks content by construction (function words + punctuation + length, with
    content words length-preserved as "x"), so down-weighting "low-voice"
    encyclopedic passages barely moves a centroid that never saw their topic in
    the first place. The parameter is still honored (the centroid is the
    weighted mean) and the param is KEPT for API stability and for the content
    axis — but on the STYLE axis it is effectively a no-op. The correct lever
    here is to pass a CURATED / GENRE-MATCHED corpus SUBSET (e.g. verse-only
    for a poetry lineage) as `corpus_passages`, which reshapes the ruler itself.
    When weights are supplied, `style_distance_introspect`'s `method` carries a
    `style_weighting_warning` to make this explicit. (On `content_distance`,
    weights ARE effective — that axis is where voice-stratification belongs.)
    """
    distances, _ = _style_distance_impl(texts, corpus_passages, corpus_weights)
    return distances


def style_distance_introspect(
    texts: List[str],
    corpus_passages: List,
    corpus_weights: Optional[List[float]] = None,
) -> Dict:
    """Like `style_distance` but returns {'distances', 'method'}."""
    distances, method = _style_distance_impl(texts, corpus_passages,
                                             corpus_weights)
    return {"distances": distances, "method": method}


# --------------------------------------------------------------------------- #
# AUTO-CONFOUND DIAGNOSTIC — is the style-centroid measuring VOICE or GENRE?
#
# The "ranks Fisher above Sexton" tripwire (round-2 confessional-poet failure).
# When the available corpus is *about* the voice (commentary / biography / verse
# prose) rather than *in* it, the content-masked style-centroid measures GENRE,
# not voice: it scored real held-out confessional VERSE (avg ~0.466) as FARTHER
# from the "confessional" centroid than a wrong-lineage distractor's expository
# prose (~0.21) — i.e. it ranked capital-realist as "more confessional than
# Sexton." That is a confounded ruler, and it is auto-detectable: distance BOTH
# the corpus's own held-out high-voice passages AND the wrong-lineage distractor
# outputs against the same centroid; if the held-out passages score WORSE
# (farther) on average, the centroid is confounded and the caller should fall
# back to the pairwise headline for that lineage.
# --------------------------------------------------------------------------- #
def centroid_confound_check(
    corpus_held_out_high_voice: List,
    distractor_outputs: List,
    corpus_passages: List,
    corpus_weights: Optional[List[float]] = None,
) -> Dict:
    """Detect a GENRE-confounded style-centroid (the "ranks Fisher above Sexton").

    Builds the style-centroid from `corpus_passages` (reusing the exact
    `_style_distance_impl` internals—same masking, scaling, neural-upgrade, and
    `corpus_weights` handling as `style_distance`), then style-distances TWO
    populations against it:

      * `corpus_held_out_high_voice` — passages from the corpus's OWN voice that
        were held OUT of the centroid (genuinely voice-bearing fragments). These
        SHOULD be close: they are the corpus's own register.
      * `distractor_outputs` — generations from a WRONG lineage (the negative
        control). These SHOULD be far: a different voice entirely.

    If the held-out passages score WORSE (farther, larger mean distance) than the
    distractor outputs, the centroid ranks a wrong-lineage text as MORE on-voice
    than the corpus's own voice — it is measuring genre/surface, not voice, and
    is confounded. This is the auto-diagnostic that makes the confessional-poet
    round-2 failure detectable without a human in the loop.

    This function only MEASURES and FLAGS. The decision to fall back lives with
    the scorer, but a clear `recommendation` is returned for convenience.

    Args:
        corpus_held_out_high_voice: held-out high-voice corpus passages (the
            corpus's own register; strings, or dicts with a text field).
        distractor_outputs: wrong-lineage generations (the negative control).
        corpus_passages: the corpus that DEFINES the style-centroid (strings or
            dicts; same shape `style_distance` accepts).
        corpus_weights: optional voice-stratification of the centroid, passed
            straight through to the style-distance internals. (Near-inert on the
            masked-style axis — see `style_distance`.)

    Returns:
        {
          "confounded": bool,                 # held_out farther than distractor?
          "held_out_mean_dist": float,        # mean style-distance, held-out set
          "distractor_mean_dist": float,      # mean style-distance, distractor
          "margin": float,                    # held_out_mean - distractor_mean;
                                              #   POSITIVE => confounded (held-out
                                              #   is farther than the wrong voice)
          "n_held_out": int,
          "n_distractor": int,
          "method": dict,                     # the style-distance method that ran
          "recommendation": str,              # human-readable fallback guidance
        }

    Raises:
        ValueError if either population is empty, or if `corpus_passages` is empty
        (the centroid is undefined) — mirroring `style_distance`'s contract.
    """
    if not corpus_held_out_high_voice:
        raise ValueError("centroid_confound_check: corpus_held_out_high_voice "
                         "must be non-empty (it is the corpus's own-voice probe).")
    if not distractor_outputs:
        raise ValueError("centroid_confound_check: distractor_outputs must be "
                         "non-empty (it is the wrong-lineage control).")
    if not corpus_passages:
        raise ValueError("centroid_confound_check: corpus_passages must be "
                         "non-empty (it defines the style-centroid).")

    # Reuse the SAME ruler for both populations: distance each against the
    # centroid built from corpus_passages. `_style_distance_impl` fits the space
    # on corpus_passages only and projects the given texts in, so the two calls
    # share an identical centroid (the corpus, not the probes, defines it).
    held_out_dists, method = _style_distance_impl(
        list(corpus_held_out_high_voice), corpus_passages, corpus_weights)
    distractor_dists, _ = _style_distance_impl(
        list(distractor_outputs), corpus_passages, corpus_weights)

    held_out_mean = float(np.mean(held_out_dists))
    distractor_mean = float(np.mean(distractor_dists))
    margin = held_out_mean - distractor_mean
    confounded = margin > 0.0  # corpus's own voice is FARTHER than wrong lineage

    recommendation = (
        "fall back to pairwise headline" if confounded
        else "style-centroid usable")

    return {
        "confounded": bool(confounded),
        "held_out_mean_dist": held_out_mean,
        "distractor_mean_dist": distractor_mean,
        "margin": float(margin),
        "n_held_out": int(len(held_out_dists)),
        "n_distractor": int(len(distractor_dists)),
        "method": method,
        "recommendation": recommendation,
    }


# --------------------------------------------------------------------------- #
# CONTENT axis — the x-axis of the transfer curve.
# --------------------------------------------------------------------------- #
def _content_distance_impl(texts: List[str],
                           corpus_passages: List,
                           corpus_weights: Optional[List[float]] = None
                           ) -> Tuple[List[float], Dict]:
    """Core content-distance with method introspection.

    Neural sentence embedding if importable & loadable; TF-IDF cosine otherwise
    (the no-download fallback). This axis is *supposed* to encode topic—it is
    the rehabilitated cosine of the methodology's form-vs-content instrument.

    `corpus_weights` (round-2 voice-stratification): optional list parallel to
    `corpus_passages` weighting each passage's contribution to the content
    centroid (same mechanism as the style axis). Default None = uniform.
    """
    if not texts:
        return [], {"method": "none", "reason": "no input texts"}
    if not corpus_passages:
        raise ValueError("content_distance: corpus_passages must be non-empty "
                         "(it defines the content-centroid).")

    corpus_texts, weights = _normalize_corpus(corpus_passages, corpus_weights)
    weighting = "voice_stratified" if weights is not None else "uniform"

    content_model = _load_content_model()
    if content_model is not None:
        try:
            # Encode corpus and texts separately; centroid from corpus rows only.
            # (Transformer embeddings are per-text independent, so this matches
            # the corpus-defines-the-space discipline with no batch coupling.)
            corpus_emb = np.asarray(
                content_model.encode(corpus_texts, convert_to_numpy=True,
                                     normalize_embeddings=True),
                dtype=np.float64,
            )
            text_emb = np.asarray(
                content_model.encode(texts, convert_to_numpy=True,
                                     normalize_embeddings=True),
                dtype=np.float64,
            )
            centroid = _weighted_centroid(corpus_emb, weights)
            distances = _cosine_distance_to_centroid(text_emb, centroid)
            return distances, {
                "method": "neural_content_embedding",
                "model_id": _CONTENT_MODEL_ID,
                "distance": "cosine",
                "space_fit_on": "corpus_passages_only",
                "centroid_weighting": weighting,
            }
        except Exception:
            pass  # fall through to TF-IDF

    # TF-IDF fallback (always available with scikit-learn).
    # The vocabulary AND IDF weights are FIT ON THE CORPUS ONLY, then texts are
    # .transform()-ed into that fixed space (text terms outside the corpus vocab
    # drop to OOV/0). This is the train/test-leakage fix one level down: the
    # corpus defines the measurement space; the text under test does not reshape
    # it, so a text's distance does not depend on its batch-mates.
    # Try with English stop-words removed (so TOPIC dominates the axis). If the
    # corpus is degenerate — e.g. stop-word-only -> empty vocabulary — retry
    # WITHOUT stop-word removal rather than crash.
    used_stop_words = "english"
    try:
        vec = TfidfVectorizer(
            lowercase=True,
            stop_words="english",    # drop closed-class so topic dominates
            ngram_range=(1, 2),
            sublinear_tf=True,
            min_df=1,
        )
        corpus_m = vec.fit_transform(corpus_texts)  # FIT on corpus only
    except ValueError:
        used_stop_words = None
        vec = TfidfVectorizer(
            lowercase=True,
            stop_words=None,
            ngram_range=(1, 2),
            sublinear_tf=True,
            min_df=1,
        )
        corpus_m = vec.fit_transform(corpus_texts)
    text_m = vec.transform(texts)                       # PROJECT texts in
    # Centroid = (weighted) mean of the dense corpus TF-IDF rows. The weighted
    # mean voice-stratifies the topic centroid exactly as the style axis does.
    corpus_dense = np.asarray(corpus_m.todense(), dtype=np.float64)
    centroid = _weighted_centroid(corpus_dense, weights).reshape(1, -1)
    sims = cosine_similarity(text_m, centroid).reshape(-1)
    # cosine_similarity returns 0 for all-zero rows (a text whose terms are all
    # OOV vs the corpus) -> distance 1.0, the right "maximally far on a topic the
    # corpus lacks."
    distances = [float(1.0 - s) for s in sims]
    return distances, {
        "method": "tfidf_cosine",
        "ngram_range": [1, 2],
        "stop_words": used_stop_words,
        "distance": "cosine",
        "space_fit_on": "corpus_passages_only",
        "centroid_weighting": weighting,
    }


def content_distance(texts: List[str],
                     corpus_passages: List,
                     corpus_weights: Optional[List[float]] = None
                     ) -> List[float]:
    """Distance of each text to the corpus CONTENT-centroid (topic axis).

    Neural embedding if available; TF-IDF cosine fallback otherwise. For the
    method that ran, call `content_distance_introspect`.

    `corpus_weights` (round-2): optional voice-stratification of the centroid —
    see `style_distance`. Default None = uniform centroid (original behavior).
    """
    distances, _ = _content_distance_impl(texts, corpus_passages, corpus_weights)
    return distances


def content_distance_introspect(
    texts: List[str],
    corpus_passages: List,
    corpus_weights: Optional[List[float]] = None,
) -> Dict:
    """Like `content_distance` but returns {'distances', 'method'}."""
    distances, method = _content_distance_impl(texts, corpus_passages,
                                               corpus_weights)
    return {"distances": distances, "method": method}


# --------------------------------------------------------------------------- #
# Paired statistics — facet vs baseline, bootstrap CI, Cohen's d.
# --------------------------------------------------------------------------- #
def paired_stats(facet_vals: List[float],
                 baseline_vals: List[float],
                 n_boot: int = 10000,
                 ci: float = 0.95) -> Dict:
    """Paired (baseline - facet) shift with bootstrap CI and paired Cohen's d.

    Pairs element-wise — index i is the SAME probe under facet vs baseline, so
    we subtract per-probe and analyze the differences. This is the headline
    "did the facet move the voice toward the corpus, beyond the bare model."

    SIGN CONVENTION (round-2 fix — ONE defined direction, toward-corpus POSITIVE):
        These functions take DISTANCES (lower = closer to the corpus centroid).
        The shift is therefore computed as

            mean_shift = mean(baseline_dist - facet_dist)

        so a facet that moves CLOSER to the corpus than the baseline (smaller
        facet distance) yields a POSITIVE mean_shift. Positive = toward corpus,
        EVERYWHERE in this module and the dashboard. This matches `fit_transfer`'s
        y-axis (style-shift = baseline_dist - facet_dist), so the headline number
        and the transfer curve agree in sign. (Round 1 reported toward-corpus as
        NEGATIVE for one facet and POSITIVE for another — this fixes that.)

    Returns:
        {
          'mean_shift': float,    # mean of paired (baseline - facet) diffs;
                                  #   POSITIVE = facet closer to corpus than
                                  #   baseline = toward corpus.
          'ci_low': float,        # percentile bootstrap CI lower bound
          'ci_high': float,       # percentile bootstrap CI upper bound
          'cohens_d': float,      # paired Cohen's d = mean(diff)/std(diff);
                                  #   same sign convention (positive = toward).
          'n': int,               # number of pairs
          'n_boot': int,
        }

    Determinism: the ONLY randomness in this module — numpy default_rng(0).
    """
    f = np.asarray(facet_vals, dtype=np.float64)
    b = np.asarray(baseline_vals, dtype=np.float64)
    if f.shape != b.shape:
        raise ValueError(
            f"paired_stats: facet_vals ({f.shape}) and baseline_vals "
            f"({b.shape}) must be the same length (paired element-wise).")
    n = f.shape[0]
    if n == 0:
        raise ValueError("paired_stats: need at least one pair.")

    # Toward-corpus = POSITIVE: baseline distance minus facet distance, so a
    # facet nearer the centroid (smaller distance) gives a positive shift.
    diffs = b - f
    mean_shift = float(diffs.mean())

    # Paired Cohen's d: mean of differences over SD of differences (ddof=1).
    # This is the standard effect size for a paired design.
    if n > 1:
        sd = float(diffs.std(ddof=1))
    else:
        sd = 0.0
    cohens_d = float(mean_shift / sd) if sd > 0 else 0.0

    # Percentile bootstrap CI of the mean paired difference, SEEDED.
    rng = np.random.default_rng(0)
    if n > 1:
        idx = rng.integers(0, n, size=(n_boot, n))
        boot_means = diffs[idx].mean(axis=1)
        alpha = (1.0 - ci) / 2.0
        ci_low = float(np.percentile(boot_means, 100 * alpha))
        ci_high = float(np.percentile(boot_means, 100 * (1.0 - alpha)))
    else:
        # Single pair: CI is degenerate at the point estimate.
        ci_low = ci_high = mean_shift

    return {
        "mean_shift": mean_shift,
        "ci_low": ci_low,
        "ci_high": ci_high,
        "cohens_d": cohens_d,
        "n": int(n),
        "n_boot": int(n_boot),
    }


# --------------------------------------------------------------------------- #
# ENACT delta — the describe-vs-enact difference-in-differences (the verb axis).
#
# The describe/enact axis asks: does the facet ENACT its lineage on its own, or
# only when the PROMPT commands it to? The metric is a DIFFERENCE-IN-DIFFERENCES
# over the scorer's per-(keyword) Enactment judgments (each in [0,1]), captured
# under two verb framings (`describe` / `enact`) x two conditions (`facet` /
# `baseline`). For each keyword k:
#
#     prompt_lift         = E(baseline, enact)  - E(baseline, describe)
#     facet_lift_describe = E(facet,   describe)- E(baseline, describe)
#     facet_lift_enact    = E(facet,   enact)   - E(baseline, enact)
#     facet_induced_delta = facet_lift_enact    - facet_lift_describe
#
# `prompt_lift` is the pure VERB effect (the axis control: how much the bare
# model enacts more when simply told "Enact ..." vs "Describe ..."). The headline
# is `facet_induced_delta`: a LARGE positive value means the facet only enacts
# when the prompt commands it (weak, prompt-dependent); a NEAR-ZERO value with a
# real `facet_lift_describe` means the facet already enacts under plain "describe"
# (the IDEAL: robust, prompt-independent enactment). Toward-corpus is POSITIVE,
# matching `paired_stats` (a facet that moves a score UP relative to its control
# yields a positive lift).
#
# THE SCALE TRAP (a known, load-bearing hazard): the diff-in-diff is only valid
# if every Enactment judgment is on the SAME [0,1] scale. A mix (e.g. some cells
# scored 0-3, others 0-1) FABRICATES a spurious delta — a 0-3 cell looks like a
# huge "lift" over a 0-1 cell purely from the scale change. So `enact_delta`
# VALIDATES every input score is in [0,1] and FAILS LOUDLY otherwise. Pure-
# numeric (numpy only), no LLM, deterministic seeded bootstrap (default_rng(0)),
# exactly like `paired_stats`.
# --------------------------------------------------------------------------- #
_ENACT_CONDITIONS = ("facet", "baseline")
_ENACT_VERBS = ("describe", "enact")


def _coerce_enact_score(value, where: str) -> float:
    """Coerce one Enactment score to a float in [0,1] or raise loudly.

    The scale trap: a 0-3-vs-0-1 mix fabricates a spurious delta, so every score
    MUST already be on the [0,1] Enactment scale. A NaN, a non-number, or any
    value outside [0,1] is a calling/scoring bug, not data to silently clamp.
    """
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(
            "enact_delta: Enactment score must be a number in [0,1] (%s got "
            "%r). Enactment is scored on a 0-1 scale; a non-number is a bug."
            % (where, value))
    v = float(value)
    if not math.isfinite(v):
        raise ValueError(
            "enact_delta: Enactment score must be finite (%s got %r)."
            % (where, value))
    if v < 0.0 or v > 1.0:
        raise ValueError(
            "enact_delta: Enactment score %r at %s is outside [0,1]. Every "
            "score must be on the SAME 0-1 Enactment scale — a 0-3-vs-0-1 mix "
            "fabricates a spurious difference-in-differences delta. Rescale to "
            "[0,1] before calling." % (value, where))
    return v


def _parse_enact_scores(scores) -> Dict[str, Dict[Tuple[str, str], float]]:
    """Validate the enact-score input and index it as {keyword: {(cond,verb): E}}.

    Input schema (a list of records — the shape the scorer emits):

        [{"keyword": "loss", "condition": "facet"|"baseline",
          "verb": "describe"|"enact", "score": <float in [0,1]>}, ...]

    A `dict` mapping keyword -> {"facet": {"describe": x, "enact": y},
    "baseline": {...}} is ALSO accepted (the nested form). Either way EVERY
    keyword must carry the full 2x2 grid (facet/baseline x describe/enact); a
    missing or duplicate cell raises (the diff-in-diff is undefined otherwise).
    """
    grid: Dict[str, Dict[Tuple[str, str], float]] = {}

    def _put(keyword, condition, verb, score):
        kw = str(keyword)
        cond = str(condition)
        vb = str(verb)
        if cond not in _ENACT_CONDITIONS:
            raise ValueError(
                "enact_delta: condition must be one of %s (keyword %r got %r)."
                % (list(_ENACT_CONDITIONS), kw, cond))
        if vb not in _ENACT_VERBS:
            raise ValueError(
                "enact_delta: verb must be one of %s (keyword %r got %r)."
                % (list(_ENACT_VERBS), kw, vb))
        cell = grid.setdefault(kw, {})
        key = (cond, vb)
        if key in cell:
            raise ValueError(
                "enact_delta: duplicate score for keyword %r (%s, %s)."
                % (kw, cond, vb))
        cell[key] = _coerce_enact_score(
            score, "keyword %r (%s, %s)" % (kw, cond, vb))

    if isinstance(scores, dict):
        for keyword, conds in scores.items():
            if not isinstance(conds, dict):
                raise ValueError(
                    "enact_delta: nested form needs keyword -> {condition -> "
                    "{verb -> score}} (keyword %r got %r)." % (keyword, conds))
            for condition, verbs in conds.items():
                if not isinstance(verbs, dict):
                    raise ValueError(
                        "enact_delta: nested form needs condition -> {verb -> "
                        "score} (keyword %r, condition %r got %r)."
                        % (keyword, condition, verbs))
                for verb, score in verbs.items():
                    _put(keyword, condition, verb, score)
    elif isinstance(scores, (list, tuple)):
        for i, rec in enumerate(scores):
            if not isinstance(rec, dict):
                raise ValueError(
                    "enact_delta: each score record must be a dict with "
                    "keyword/condition/verb/score (index %d got %r)." % (i, rec))
            try:
                keyword = rec["keyword"]
                condition = rec["condition"]
                verb = rec["verb"]
                score = rec["score"]
            except KeyError as e:
                raise ValueError(
                    "enact_delta: score record %d missing required key %s "
                    "(need keyword/condition/verb/score)." % (i, e))
            _put(keyword, condition, verb, score)
    else:
        raise ValueError(
            "enact_delta: `scores` must be a list of {keyword,condition,verb,"
            "score} records or the nested keyword->condition->verb dict (got "
            "%s)." % type(scores).__name__)

    if not grid:
        raise ValueError("enact_delta: need at least one keyword's scores.")

    # Every keyword needs the full 2x2 grid or its diff-in-diff is undefined.
    required = {(c, v) for c in _ENACT_CONDITIONS for v in _ENACT_VERBS}
    for kw, cell in grid.items():
        missing = required - set(cell)
        if missing:
            pretty = ", ".join("%s/%s" % (c, v) for c, v in sorted(missing))
            raise ValueError(
                "enact_delta: keyword %r is missing cell(s): %s. Each keyword "
                "needs all four facet/baseline x describe/enact scores."
                % (kw, pretty))
    return grid


def enact_delta(scores,
                n_boot: int = 10000,
                ci: float = 0.95) -> Dict:
    """Describe-vs-enact difference-in-differences over per-keyword Enactment.

    Consumes the SCORER's per-keyword Enactment judgments (each in [0,1]) under
    the 2x2 grid of condition (facet/baseline) x verb (describe/enact) and
    returns the verb-axis decomposition per keyword and in aggregate. It NEVER
    calls an LLM — it only does arithmetic on judgments the scorer produced.

    Input (`scores`): a list of records (the canonical form) ::

        [{"keyword": "loss", "condition": "facet",    "verb": "describe", "score": 0.4},
         {"keyword": "loss", "condition": "facet",    "verb": "enact",    "score": 0.5},
         {"keyword": "loss", "condition": "baseline", "verb": "describe", "score": 0.1},
         {"keyword": "loss", "condition": "baseline", "verb": "enact",    "score": 0.3},
         ... (one such 2x2 block per keyword) ]

    or equivalently the nested dict
    ``{keyword: {condition: {verb: score}}}``. Every keyword MUST carry the full
    2x2 grid; every score MUST be in [0,1] (a 0-3-vs-0-1 scale mix fabricates a
    spurious delta and is rejected — see the section comment).

    Per keyword and as the aggregate MEAN across keywords:
        prompt_lift         = E(baseline,enact)  - E(baseline,describe)
        facet_lift_describe = E(facet,describe)  - E(baseline,describe)
        facet_lift_enact    = E(facet,enact)     - E(baseline,enact)
        facet_induced_delta = facet_lift_enact   - facet_lift_describe
    Toward-corpus POSITIVE (a higher Enactment score than the control = a
    positive lift), matching `paired_stats`'s sign convention.

    Returns::

        {
          "per_pair": {keyword: {prompt_lift, facet_lift_describe,
                                 facet_lift_enact, facet_induced_delta,
                                 E_facet_describe, E_facet_enact,
                                 E_baseline_describe, E_baseline_enact}, ...},
          "prompt_lift": float,           # aggregate means across keywords
          "facet_lift_describe": float,
          "facet_lift_enact": float,
          "facet_induced_delta": float,   # the headline
          "ci": {                         # seeded bootstrap CI per aggregate
            "prompt_lift": [lo, hi],
            "facet_lift_describe": [lo, hi],
            "facet_lift_enact": [lo, hi],
            "facet_induced_delta": [lo, hi],
          },
          "n": int,                       # number of keywords (pairs)
          "n_boot": int,
        }

    Determinism: the ONLY randomness is the seeded bootstrap (default_rng(0)),
    exactly as `paired_stats`.
    """
    grid = _parse_enact_scores(scores)

    keywords = sorted(grid)
    per_pair: Dict[str, Dict[str, float]] = {}
    # Parallel arrays (one entry per keyword) for the aggregate + bootstrap.
    prompt_lift_arr: List[float] = []
    facet_lift_describe_arr: List[float] = []
    facet_lift_enact_arr: List[float] = []
    facet_induced_delta_arr: List[float] = []

    for kw in keywords:
        cell = grid[kw]
        e_fd = cell[("facet", "describe")]
        e_fe = cell[("facet", "enact")]
        e_bd = cell[("baseline", "describe")]
        e_be = cell[("baseline", "enact")]

        prompt_lift = e_be - e_bd
        facet_lift_describe = e_fd - e_bd
        facet_lift_enact = e_fe - e_be
        facet_induced_delta = facet_lift_enact - facet_lift_describe

        prompt_lift_arr.append(prompt_lift)
        facet_lift_describe_arr.append(facet_lift_describe)
        facet_lift_enact_arr.append(facet_lift_enact)
        facet_induced_delta_arr.append(facet_induced_delta)

        per_pair[kw] = {
            "prompt_lift": float(prompt_lift),
            "facet_lift_describe": float(facet_lift_describe),
            "facet_lift_enact": float(facet_lift_enact),
            "facet_induced_delta": float(facet_induced_delta),
            "E_facet_describe": float(e_fd),
            "E_facet_enact": float(e_fe),
            "E_baseline_describe": float(e_bd),
            "E_baseline_enact": float(e_be),
        }

    n = len(keywords)

    # Seeded percentile bootstrap CI of each aggregate mean — ONE rng, drawn
    # once over keyword indices so the four aggregates share resamples (they are
    # the same keywords) and the result is deterministic (default_rng(0)), just
    # like `paired_stats`.
    rng = np.random.default_rng(0)
    metrics_arrs = {
        "prompt_lift": np.asarray(prompt_lift_arr, dtype=np.float64),
        "facet_lift_describe": np.asarray(facet_lift_describe_arr, dtype=np.float64),
        "facet_lift_enact": np.asarray(facet_lift_enact_arr, dtype=np.float64),
        "facet_induced_delta": np.asarray(facet_induced_delta_arr, dtype=np.float64),
    }
    alpha = (1.0 - ci) / 2.0
    ci_out: Dict[str, List[float]] = {}
    if n > 1:
        idx = rng.integers(0, n, size=(n_boot, n))
        for key, arr in metrics_arrs.items():
            boot_means = arr[idx].mean(axis=1)
            ci_out[key] = [float(np.percentile(boot_means, 100 * alpha)),
                           float(np.percentile(boot_means, 100 * (1.0 - alpha)))]
    else:
        # Single keyword: CI degenerate at the point estimate.
        for key, arr in metrics_arrs.items():
            point = float(arr.mean())
            ci_out[key] = [point, point]

    return {
        "per_pair": per_pair,
        "prompt_lift": float(metrics_arrs["prompt_lift"].mean()),
        "facet_lift_describe": float(metrics_arrs["facet_lift_describe"].mean()),
        "facet_lift_enact": float(metrics_arrs["facet_lift_enact"].mean()),
        "facet_induced_delta": float(metrics_arrs["facet_induced_delta"].mean()),
        "ci": ci_out,
        "n": int(n),
        "n_boot": int(n_boot),
    }


# --------------------------------------------------------------------------- #
# Transfer curve — style-shift (y) vs measured content-distance (x).
# --------------------------------------------------------------------------- #
# Classification thresholds (documented, tunable). style_shift here is the
# facet's marginal move TOWARD the corpus, baseline-subtracted, so MORE-POSITIVE
# = more toward-corpus. This is the SAME sign convention as `paired_stats`
# (style-shift per probe = baseline_dist - facet_dist), so the y-axis the caller
# passes is exactly the per-probe paired difference — no re-orientation needed
# (see eval-scorer Step 5).
#
#   * |slope| <= _FLAT_SLOPE_EPS  -> 'flat'  (style holds as content-distance
#                                    grows: robust transfer / "stranger").
#   * slope <  -_FLAT_SLOPE_EPS   -> 'decaying' (style collapses as topic moves
#                                    away: home-turf-only).
#   * slope >   _FLAT_SLOPE_EPS   -> also 'flat' for shape purposes (style does
#                                    not *decay*; an increasing trend is not a
#                                    breakdown — reported via slope sign).
#   * 'breakdown' is reserved for an empirically detected collapse point (a far
#     bin/point whose style_shift drops below _BREAKDOWN_FRAC of the near level),
#     surfaced as `breakdown_distance`. The methodology's breakdown ZONE (style
#     holds, coherence fails) is an LLM coherence call the agent makes; here we
#     can only flag the *style* collapse location numerically.
_FLAT_SLOPE_EPS = 0.05        # slope magnitude (style-shift per unit distance)
_BREAKDOWN_FRAC = 0.5         # far-level < 50% of near-level => breakdown flag


def _linfit(x: np.ndarray, y: np.ndarray) -> Tuple[float, float, float]:
    """Least-squares line y = slope*x + intercept; return (slope, intercept, r2)."""
    if x.size < 2 or np.allclose(x, x[0]):
        return 0.0, float(y.mean()) if y.size else 0.0, 0.0
    A = np.vstack([x, np.ones_like(x)]).T
    (slope, intercept), *_ = np.linalg.lstsq(A, y, rcond=None)
    yhat = slope * x + intercept
    ss_res = float(np.sum((y - yhat) ** 2))
    ss_tot = float(np.sum((y - y.mean()) ** 2))
    r2 = 1.0 - ss_res / ss_tot if ss_tot > 0 else 0.0
    return float(slope), float(intercept), float(r2)


def _try_exp_decay_fit(x: np.ndarray, y: np.ndarray) -> Optional[Dict]:
    """Optional exponential-decay fit y = a*exp(-k*x) + c via scipy, if present.

    Returns {'a','k','c','r2'} or None (scipy missing / fit failed / not enough
    points). Purely additive: the linear fit is always the primary trend.
    """
    if x.size < 4:
        return None
    try:
        from scipy.optimize import curve_fit
    except Exception:
        return None

    def model(xx, a, k, c):
        return a * np.exp(-k * xx) + c

    try:
        span = max(float(x.max() - x.min()), 1e-6)
        p0 = [float(y.max() - y.min()) or 1.0, 1.0 / span, float(y.min())]
        popt, _ = curve_fit(model, x, y, p0=p0, maxfev=10000)
        yhat = model(x, *popt)
        ss_res = float(np.sum((y - yhat) ** 2))
        ss_tot = float(np.sum((y - y.mean()) ** 2))
        r2 = 1.0 - ss_res / ss_tot if ss_tot > 0 else 0.0
        return {"a": float(popt[0]), "k": float(popt[1]),
                "c": float(popt[2]), "r2": float(r2)}
    except Exception:
        return None


def _classify_shape(slope: float, points: List[Dict]) -> Tuple[str, Optional[float]]:
    """Return (shape, breakdown_distance) from slope sign and a far-collapse check."""
    breakdown_distance: Optional[float] = None

    # Empirical breakdown: did style_shift collapse at the far end relative to
    # the near end? Compare the mean of the nearest third vs the farthest third.
    if len(points) >= 3:
        pts = sorted(points, key=lambda p: p["distance"])
        k = max(1, len(pts) // 3)
        near_level = float(np.mean([p["style_shift"] for p in pts[:k]]))
        far_pts = pts[-k:]
        far_level = float(np.mean([p["style_shift"] for p in far_pts]))
        if near_level > 0 and far_level < _BREAKDOWN_FRAC * near_level:
            breakdown_distance = float(far_pts[0]["distance"])

    if breakdown_distance is not None:
        return "breakdown", breakdown_distance
    if slope < -_FLAT_SLOPE_EPS:
        return "decaying", None
    return "flat", None


def fit_transfer(distance: List[float],
                 style_shift: List[float],
                 tier: str) -> Dict:
    """Fit / bin the transfer curve: style-shift (y) vs content-distance (x).

    SIGN CONVENTION: `style_shift` is per-probe TOWARD-corpus, i.e. (baseline_dist
    - facet_dist) — the SAME convention as `paired_stats.mean_shift` (positive =
    facet closer to the corpus). A POSITIVE-and-flat curve is robust transfer; a
    curve that DECAYS toward zero as content-distance grows is home-turf-only.

    `tier == 'full'`: fit a linear trend (always) and optionally an exponential
        decay (if scipy present and >=4 points). Returns shape, slope, breakdown
        estimate, the raw points, and the fit details.
    `tier == 'lean'`: tertile-bin x into near/mid/far and return per-bin mean
        style-shift (coarse binned curve), still classifying shape from a line
        fit through the bin centers.

    Envelope (same keys for both tiers):
        {
          'shape': 'flat' | 'decaying' | 'breakdown',
          'slope': float,
          'breakdown_distance': float | None,
          'points': [{'distance':.., 'style_shift':..}, ...],
          'fit': {...}      # tier-specific details
        }
    """
    x = np.asarray(distance, dtype=np.float64)
    y = np.asarray(style_shift, dtype=np.float64)
    if x.shape != y.shape:
        raise ValueError("fit_transfer: distance and style_shift must align.")
    if x.size == 0:
        return {"shape": "flat", "slope": 0.0, "breakdown_distance": None,
                "points": [], "fit": {"tier": tier, "note": "no points"}}

    if tier == "lean":
        # Tertile binning by content-distance. Bins are near/mid/far.
        order = np.argsort(x)
        xs, ys = x[order], y[order]
        n = xs.size
        # Split indices into 3 (as even as possible).
        splits = np.array_split(np.arange(n), 3)
        bin_names = ["near", "mid", "far"]
        points: List[Dict] = []
        fit_bins = {}
        for name, idxs in zip(bin_names, splits):
            if len(idxs) == 0:
                continue
            cx = float(xs[idxs].mean())
            cy = float(ys[idxs].mean())
            points.append({"distance": cx, "style_shift": cy})
            fit_bins[name] = {"mean_distance": cx, "mean_style_shift": cy,
                              "n": int(len(idxs))}
        # Slope through bin centers (line fit on the few bin points).
        bx = np.array([p["distance"] for p in points], dtype=np.float64)
        by = np.array([p["style_shift"] for p in points], dtype=np.float64)
        slope, intercept, r2 = _linfit(bx, by)
        shape, breakdown_distance = _classify_shape(slope, points)
        return {
            "shape": shape,
            "slope": slope,
            "breakdown_distance": breakdown_distance,
            "points": points,
            "fit": {"tier": "lean", "bins": fit_bins,
                    "line_through_bins": {"slope": slope,
                                          "intercept": intercept, "r2": r2}},
        }

    # tier == 'full' (default for anything not 'lean').
    points = [{"distance": float(xi), "style_shift": float(yi)}
              for xi, yi in zip(x, y)]
    slope, intercept, r2 = _linfit(x, y)
    fit: Dict[str, object] = {
        "tier": "full",
        "linear": {"slope": slope, "intercept": intercept, "r2": r2},
    }
    exp_fit = _try_exp_decay_fit(x, y)
    if exp_fit is not None:
        fit["exp_decay"] = exp_fit
    shape, breakdown_distance = _classify_shape(slope, points)
    return {
        "shape": shape,
        "slope": slope,
        "breakdown_distance": breakdown_distance,
        "points": points,
        "fit": fit,
    }


# --------------------------------------------------------------------------- #
# Structural collapse-rate — function -> section discretization diagnostic.
# --------------------------------------------------------------------------- #
# The seven functions a facet body serves (methodology / facet-schema). Used as
# the denominator: ratio = blocks / 7. ~1.0 means the body discretized into one
# block per function (Phase 1's "residual gravity"); a free body that braids the
# functions has fewer (or differently-shaped) blocks and a ratio that departs
# from 1.0 — that departure is the signal.
N_FUNCTIONS = 7


def collapse_rate(facet_path: str) -> Dict:
    """Estimate function->section collapse from the facet markdown body.

    Parsing:
      1. Strip the YAML frontmatter (the leading `---` ... `---`).
      2. Drop the closing epigraph (a trailing `---`-delimited italic line).
      3. Count distinct CONTENT BLOCKS in the remaining body. A block boundary
         is a top-level/section heading (`#`, `##`, `###`) OR a horizontal rule
         (`---`). The opening prose before the first heading (the 'situate'
         block) counts as one block if non-empty.

    Returns:
        {'blocks': int, 'functions': 7, 'ratio': blocks/7}

    The ratio is a STRUCTURAL-FIDELITY diagnostic, NOT a resonance signal (see
    methodology — it informs the distill-unit decision; it does not say the
    facet points at its region).
    """
    with open(facet_path, "r", encoding="utf-8") as fh:
        raw = fh.read()

    body = _strip_frontmatter(raw)
    body = _strip_closing_epigraph(body)

    blocks = _count_content_blocks(body)
    return {
        "blocks": int(blocks),
        "functions": int(N_FUNCTIONS),
        "ratio": float(blocks) / float(N_FUNCTIONS),
    }


def _strip_frontmatter(raw: str) -> str:
    """Remove a leading YAML frontmatter block delimited by `---` lines."""
    lines = raw.splitlines()
    if lines and lines[0].strip() == "---":
        for i in range(1, len(lines)):
            if lines[i].strip() == "---":
                return "\n".join(lines[i + 1:])
    return raw


def _strip_closing_epigraph(body: str) -> str:
    """Drop a trailing `---`-delimited closing block (the epigraph line)."""
    lines = body.splitlines()
    # Find the last horizontal rule.
    last_hr = None
    for i, ln in enumerate(lines):
        if ln.strip() == "---":
            last_hr = i
    if last_hr is None:
        return body
    tail = [ln for ln in lines[last_hr + 1:] if ln.strip()]
    # Heuristic: a short, mostly-italic tail is the epigraph -> drop from the HR.
    if tail and len(tail) <= 3:
        joined = " ".join(tail)
        if joined.startswith("*") or joined.startswith("_") or len(joined) < 400:
            return "\n".join(lines[:last_hr])
    return body


def _count_content_blocks(body: str) -> int:
    """Count content blocks delimited by headings or horizontal rules.

    A new block starts at any markdown heading line (`#`..`######`) or a `---`
    horizontal rule. Leading prose (before the first delimiter) counts as one
    block if it contains non-whitespace text. Empty segments are not counted.
    """
    lines = body.splitlines()
    heading_re = re.compile(r"^\s{0,3}#{1,6}\s+\S")
    blocks = 0
    current_has_content = False

    def flush():
        nonlocal blocks, current_has_content
        if current_has_content:
            blocks += 1
        current_has_content = False

    for ln in lines:
        stripped = ln.strip()
        if heading_re.match(ln):
            # close previous segment, start the heading's block
            flush()
            current_has_content = True       # the heading itself is content
        elif stripped == "---":
            # horizontal rule: close previous segment; rule itself starts nothing
            flush()
        else:
            if stripped:
                current_has_content = True
    flush()
    return blocks


# --------------------------------------------------------------------------- #
# VERBATIM-ECHO DETECTOR — the "hollow tell" (strangeness substrate).
#
# A facet that recites greatest-hits CORPUS phrases verbatim reads HOLLOW: it has
# flattened the corpus to its quotable surface and lost the surprise-within-corpus
# (the singular non-compressible moves) that make a lineage *strange* and not just
# *strong* ("THE NEW FRONTIER — STRANGER"). Region-match is
# *satisfied* by greatest-hits flattening, so the style/pairwise axes cannot see
# this; a verbatim-echo measure can. HIGH echo = reciting the corpus, not thinking
# in its register.
#
# This function ONLY MEASURES (echo fractions + the longest verbatim span). It
# does NOT decide "hollow" — the SCORER owns that threshold (a little echo is the
# natural gravity of a strong lineage voice; a lot is recitation). Deterministic,
# core-deps only: word tokenization + set membership, no neural, no network.
# --------------------------------------------------------------------------- #
def _word_tokens_lower(text: str) -> List[str]:
    """Lowercased word tokens (same `_WORD_RE` the rest of the module uses)."""
    return [t.lower() for t in _WORD_RE.findall(text)]


def _ngrams(tokens: List[str], n: int):
    """Yield the word n-grams (as tuples) of a token list, for a given n."""
    if n <= 0 or len(tokens) < n:
        return
    for i in range(len(tokens) - n + 1):
        yield tuple(tokens[i:i + n])


def _longest_verbatim_span(text_tokens: List[str],
                           corpus_token_lists: List[List[str]]) -> int:
    """Longest run of consecutive `text_tokens` that appears VERBATIM, contiguous,
    within a SINGLE corpus passage. Returns the length in tokens (0 if none, i.e.
    no shared token at all).

    Exact greedy scan: for each start in the text, extend the match as far as the
    growing window remains a contiguous subsequence of some corpus passage. We
    seed candidate (passage, offset) positions from a first-token index so we only
    extend where the run can actually begin, then walk each candidate forward. A
    span never crosses a passage boundary — verbatim recitation means lifting a
    contiguous stretch of one source, not stitching two.
    """
    if not text_tokens or not corpus_token_lists:
        return 0
    # Index: token -> list of (passage_idx, offset) where it occurs in the corpus.
    first_pos: Dict[str, List[Tuple[int, int]]] = {}
    for pi, toks in enumerate(corpus_token_lists):
        for off, tok in enumerate(toks):
            first_pos.setdefault(tok, []).append((pi, off))

    longest = 0
    n_text = len(text_tokens)
    for i in range(n_text):
        starts = first_pos.get(text_tokens[i])
        if not starts:
            continue
        # Extend each candidate start as far as the corpus passage matches.
        for (pi, off) in starts:
            toks = corpus_token_lists[pi]
            length = 0
            ti, ci = i, off
            while (ti < n_text and ci < len(toks)
                   and text_tokens[ti] == toks[ci]):
                length += 1
                ti += 1
                ci += 1
            if length > longest:
                longest = length
                if longest == n_text:        # cannot do better than the whole text
                    return longest
    return longest


def verbatim_echo(texts: List[str],
                  corpus_passages: List,
                  n_lo: int = 4,
                  n_hi: int = 8) -> List[Dict]:
    """Measure how much each text RECITES the corpus verbatim (the "hollow tell").

    For each text and each n in `n_lo..n_hi`, computes the fraction of the text's
    word n-grams that appear VERBATIM among the corpus's word n-grams; aggregates
    those into a single `echo_fraction`; and reports the longest contiguous
    verbatim corpus-matching span (in tokens). All matching is on lowercased word
    tokens (punctuation ignored — recitation is a word-sequence phenomenon).

    This function only MEASURES. It does NOT decide a "hollow" threshold — the
    SCORER owns that call (a strong lineage voice naturally re-uses a little of its
    corpus's phrasing; wholesale recitation is the failure). Deterministic and
    core-deps only (no neural, no network).

    Args:
        texts: the generations under test.
        corpus_passages: the corpus to match against (strings, or dicts with a
            text field — same shape `style_distance` accepts; weights/voice_charge
            are ignored here, this is a surface phenomenon).
        n_lo, n_hi: inclusive word-n-gram range scanned for the echo fraction
            (default 4..8 — long enough that an incidental shared function-word
            bigram is not flagged, short enough to catch a lifted phrase). The
            longest-span metric is NOT capped by `n_hi`; it reports the true
            longest contiguous match however long.

    Returns one dict per text (in input order):
        {
          "echo_fraction": float,                  # mean over n of per-n fractions
                                                   #   (n with no text n-grams skip)
          "per_n": {n: float, ...},                # fraction of n-grams that echo,
                                                   #   per n in n_lo..n_hi
          "longest_verbatim_span_tokens": int,     # longest contiguous lift, tokens
          "n_tokens": int,                         # text length in word tokens
        }

    Raises:
        ValueError if `corpus_passages` is empty (nothing to match against) or if
        `n_lo`/`n_hi` are not a valid positive range.
    """
    if not corpus_passages:
        raise ValueError("verbatim_echo: corpus_passages must be non-empty "
                         "(it is what an echo is measured against).")
    if n_lo < 1 or n_hi < n_lo:
        raise ValueError(
            f"verbatim_echo: need 1 <= n_lo <= n_hi (got n_lo={n_lo}, "
            f"n_hi={n_hi}).")

    # Normalize the corpus to plain strings (ignore weights/voice_charge — echo is
    # a surface phenomenon), then tokenize once.
    corpus_texts, _ = _normalize_corpus(corpus_passages, None)
    corpus_token_lists = [_word_tokens_lower(c) for c in corpus_texts]

    # Build the corpus n-gram set per n ONCE (reused across all texts).
    corpus_ngrams: Dict[int, set] = {}
    for n in range(n_lo, n_hi + 1):
        s: set = set()
        for toks in corpus_token_lists:
            s.update(_ngrams(toks, n))
        corpus_ngrams[n] = s

    results: List[Dict] = []
    for text in texts:
        toks = _word_tokens_lower(text)
        per_n: Dict[int, float] = {}
        fracs: List[float] = []
        for n in range(n_lo, n_hi + 1):
            text_ngrams = list(_ngrams(toks, n))
            if not text_ngrams:
                # Text too short for this n: no n-grams to score. Skip from the
                # aggregate rather than counting a misleading 0 (absence of a
                # measurement, not a measured zero).
                per_n[n] = 0.0
                continue
            hits = sum(1 for g in text_ngrams if g in corpus_ngrams[n])
            frac = hits / len(text_ngrams)
            per_n[n] = float(frac)
            fracs.append(frac)
        echo_fraction = float(np.mean(fracs)) if fracs else 0.0
        longest = _longest_verbatim_span(toks, corpus_token_lists)
        results.append({
            "echo_fraction": echo_fraction,
            "per_n": per_n,
            "longest_verbatim_span_tokens": int(longest),
            "n_tokens": int(len(toks)),
        })
    return results


# --------------------------------------------------------------------------- #
# SEMANTIC-ECHO DETECTOR — the paraphrase-tell (the surprise substrate, depth 2).
#
# verbatim_echo catches LEXICAL recitation; it is blind to the too-familiar
# PARAPHRASE of a famous corpus move — the same idea recited in other words
# ("tomorrow was quietly called off" for "the slow cancellation of the future":
# 0.0 verbatim echo, yet semantically the corpus's greatest hit). That paraphrase
# is the subtler half of the "hollow" failure (round-3 Q2).
# semantic_echo measures it in CONTENT-embedding space: how close is each output
# sentence to its NEAREST corpus sentence? HIGH = semantic recitation.
#
# Intentionally CONTENT-FULL — the OPPOSITE discipline from style_distance (which
# masks content): a paraphrase shares MEANING while changing surface, so meaning
# is exactly what must be compared. Reuses the MiniLM content model so it lives in
# the same content space as content_distance. Needs that neural model; when absent
# it reports "unavailable" (a missing signal is reported, never hidden —
# verbatim_echo is the always-on lexical floor). The SCORER owns the "hollow"
# threshold AND the per-stratum reading (in-domain probes echo naturally; HIGH
# echo on a CROSS-DOMAIN probe is the shoehorning tell — corpus sentences forced
# onto a foreign topic instead of the operation transferring).
# --------------------------------------------------------------------------- #
def _split_sentences(text: str) -> List[str]:
    """Split into non-empty, stripped sentences (the module's `.!?` splitter)."""
    return [s.strip() for s in _SENT_SPLIT_RE.split(text) if s.strip()]


def semantic_echo(texts: List[str],
                  corpus_passages: List,
                  min_chars: int = 12) -> List[Dict]:
    """Measure how much each text PARAPHRASES the corpus (the semantic hollow-tell).

    For each text, split into sentences and, for each sentence, take the MAX cosine
    similarity to any corpus sentence in content-embedding space (MiniLM). Report
    the per-text max (the single most-recited move) and mean (overall semantic
    closeness). HIGH max = at least one output sentence is a near-duplicate-in-
    MEANING of a corpus sentence — the paraphrase that verbatim_echo cannot see.

    Complements verbatim_echo (lexical). Intentionally CONTENT-FULL. Needs the
    neural content model; if unavailable, every text returns available=False and
    the scorer falls back to verbatim_echo alone. The SCORER owns the "hollow"
    threshold and the per-stratum interpretation (see the section comment).

    Args:
        texts: the generations under test.
        corpus_passages: the corpus (strings or dicts with a text field; weights
            ignored — echo is not voice-weighted).
        min_chars: sentences shorter than this are dropped before embedding (a bare
            "Yes." is not a meaningful semantic comparand).

    Returns one dict per text (input order):
        {
          "semantic_echo_max": float|None,   # max over the text's sentences of the
                                             #   nearest-corpus-sentence cosine
          "semantic_echo_mean": float|None,  # mean of those per-sentence maxima
          "n_sentences": int,                # scored sentences (>= min_chars)
          "available": bool,                 # False iff the neural model is absent
          "method": str,                     # "neural_content_embedding"|"unavailable"
        }

    Raises:
        ValueError if corpus_passages is empty.
    """
    if not corpus_passages:
        raise ValueError("semantic_echo: corpus_passages must be non-empty "
                         "(it is what an echo is measured against).")

    def _unavail() -> Dict:
        return {"semantic_echo_max": None, "semantic_echo_mean": None,
                "n_sentences": 0, "available": False, "method": "unavailable"}

    model = _load_content_model()
    if model is None:
        return [_unavail() for _ in texts]

    corpus_texts, _ = _normalize_corpus(corpus_passages, None)
    corpus_sents = [s for c in corpus_texts for s in _split_sentences(c)
                    if len(s) >= min_chars]
    if not corpus_sents:
        return [_unavail() for _ in texts]

    try:
        corpus_emb = np.asarray(
            model.encode(corpus_sents, convert_to_numpy=True,
                         normalize_embeddings=True), dtype=np.float64)
    except Exception:
        return [_unavail() for _ in texts]

    results: List[Dict] = []
    for text in texts:
        sents = [s for s in _split_sentences(text) if len(s) >= min_chars]
        if not sents:
            results.append({"semantic_echo_max": 0.0, "semantic_echo_mean": 0.0,
                            "n_sentences": 0, "available": True,
                            "method": "neural_content_embedding"})
            continue
        try:
            sent_emb = np.asarray(
                model.encode(sents, convert_to_numpy=True,
                             normalize_embeddings=True), dtype=np.float64)
        except Exception:
            results.append(_unavail())
            continue
        # Each output sentence's nearest corpus sentence (cosine). Max across the
        # text = the single most-recited move; mean = overall paraphrase closeness.
        sims = cosine_similarity(sent_emb, corpus_emb)
        per_sentence_max = sims.max(axis=1)
        results.append({
            "semantic_echo_max": float(per_sentence_max.max()),
            "semantic_echo_mean": float(per_sentence_max.mean()),
            "n_sentences": int(len(sents)),
            "available": True,
            "method": "neural_content_embedding",
        })
    return results


# --------------------------------------------------------------------------- #
# CLI convenience (optional) — lets the agent call a function from Bash with
# JSON in / JSON out, without writing a wrapper each time.
# --------------------------------------------------------------------------- #
def _cli() -> None:  # pragma: no cover - thin dispatch
    import json
    import sys
    if len(sys.argv) < 2:
        print(json.dumps({"error": "usage: metrics.py <fn> <json-args>"}))
        return
    fn = sys.argv[1]
    payload = json.loads(sys.argv[2]) if len(sys.argv) > 2 else {}
    dispatch = {
        "style_distance": lambda: style_distance_introspect(**payload),
        "content_distance": lambda: content_distance_introspect(**payload),
        "paired_stats": lambda: paired_stats(**payload),
        "enact_delta": lambda: enact_delta(**payload),
        "fit_transfer": lambda: fit_transfer(**payload),
        "collapse_rate": lambda: collapse_rate(**payload),
        "centroid_confound_check": lambda: centroid_confound_check(**payload),
        "verbatim_echo": lambda: verbatim_echo(**payload),
        "semantic_echo": lambda: semantic_echo(**payload),
    }
    if fn not in dispatch:
        print(json.dumps({"error": f"unknown fn '{fn}'",
                          "available": list(dispatch)}))
        return
    print(json.dumps(dispatch[fn]()))


if __name__ == "__main__":
    _cli()