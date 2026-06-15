"""
test_metrics.py — OFFLINE self-test for the eval numeric core.

Runs with ONLY numpy + scikit-learn (+ scipy). No network, no model downloads,
no test framework. Run it directly:

    python eval/test_metrics.py

Prints PASS/FAIL per check and exits non-zero if any check fails.

The synthetic fixtures are designed to decouple STYLE from CONTENT so the checks
actually exercise the epistemics (esp. that the style axis is content-masked):
the style "corpus" is a fixed, punchy, fragmentary register; a "similar-style"
probe matches that register on a DIFFERENT topic; a "divergent-style" probe is
long, flowing, comma-spliced academic prose. A pure-topic check builds two texts
on the SAME topic but in opposite registers to confirm topic alone does not pull
the style distance.
"""

from __future__ import annotations

import os
import sys
import tempfile
import traceback

# Make sibling import work regardless of CWD.
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import metrics  # noqa: E402


# --------------------------------------------------------------------------- #
# Test harness (tiny, dependency-free).
# --------------------------------------------------------------------------- #
_RESULTS = []


def check(name: str, cond: bool, detail: str = "") -> None:
    _RESULTS.append((name, bool(cond), detail))
    status = "PASS" if cond else "FAIL"
    line = f"[{status}] {name}"
    if detail:
        line += f"  ::  {detail}"
    print(line)


def section(title: str) -> None:
    print("\n" + "=" * 72)
    print(title)
    print("=" * 72)


# --------------------------------------------------------------------------- #
# Fixtures.
# --------------------------------------------------------------------------- #
# Style "corpus": short, declarative, em-dash-pivoting, fragmentary. Topic =
# weather/sea. The register is the point, not the topic.
CORPUS_STYLE = [
    "The storm came. It broke the pier—then nothing. No warning. Just water.",
    "Wind first. Then rain—hard, flat, sideways. The boats turned over. Gone.",
    "Cold morning. Grey sea—still as glass. Then the swell. It rose. It fell.",
    "Salt on the rail. The fog lifted—slowly. A gull cried once. Then silence.",
]

# Similar-style probe: SAME punchy fragmentary register, DIFFERENT topic (a
# kitchen). If the style axis is content-masked, this should land NEAR the
# corpus despite zero topical overlap.
SIMILAR_STYLE_DIFF_TOPIC = (
    "The kettle screamed. She killed the flame—then quiet. No fuss. Just steam."
)

# Divergent-style probe: long, flowing, subordinate-clause academic prose. SAME
# topic as the corpus (the sea/storm) so that if the axis leaked topic it would
# look deceptively close — it must NOT.
DIVERGENT_STYLE_SAME_TOPIC = (
    "Although the storm, which had been gathering across the bay for the "
    "better part of the afternoon, eventually made landfall near the pier, it "
    "is perhaps more accurate to say that the sea, in its slow and "
    "deliberate accumulation of force, had been preparing this arrival for "
    "many hours, such that the boats, moored as they were along the harbor, "
    "could hardly have been expected to withstand the swell that followed."
)

# Content fixtures: corpus is about ECONOMICS; probes vary topic distance.
CORPUS_CONTENT = [
    "Capital accumulates through the extraction of surplus value from labor.",
    "Markets allocate scarce resources via the price mechanism and exchange.",
    "Wages, profit, and rent divide the social product among the classes.",
    "Economic crisis follows from the falling rate of profit and overproduction.",
]
CONTENT_NEAR = "The economy distributes profit and wages across the market."   # on-topic
CONTENT_FAR = "The heron stood in the reeds at dawn, waiting for a silver fish."  # off-topic


# --------------------------------------------------------------------------- #
# 1. style_distance — content-masked behavior.
# --------------------------------------------------------------------------- #
def test_style_distance() -> None:
    section("style_distance (content-masked stylometry)")

    intro = metrics.style_distance_introspect(
        [SIMILAR_STYLE_DIFF_TOPIC, DIVERGENT_STYLE_SAME_TOPIC],
        CORPUS_STYLE,
    )
    d_similar, d_divergent = intro["distances"]
    method = intro["method"]
    print(f"  method = {method.get('method')}  (content_masked="
          f"{method.get('content_masked')})")
    print(f"  d(similar-style, diff-topic) = {d_similar:.4f}")
    print(f"  d(divergent-style, same-topic) = {d_divergent:.4f}")

    # Core claim: a stylistically-similar text (even on a different topic) is
    # CLOSER to the corpus style-centroid than a stylistically-divergent text
    # (even on the same topic). This is the whole content-masked thesis.
    check(
        "similar-style text closer than divergent-style text",
        d_similar < d_divergent,
        f"{d_similar:.4f} < {d_divergent:.4f}",
    )

    # Distances are valid cosine distances in [0, 2].
    check(
        "style distances in [0,2]",
        all(0.0 <= d <= 2.0 for d in intro["distances"]),
        f"{[round(x,4) for x in intro['distances']]}",
    )

    # The always-on path must be classical stylometry, content-masked, cosine.
    check(
        "method records content-masked classical stylometry + cosine",
        method.get("content_masked") is True
        and method.get("distance") == "cosine"
        and "classical_stylometry" in str(method.get("method")),
        str(method.get("method")),
    )

    # Topic must NOT dominate the style axis: two SAME-topic texts in OPPOSITE
    # registers must not both be near the (different-topic) similar-style probe's
    # closeness. Concretely: divergent-same-topic should be farther from corpus
    # than similar-diff-topic by a clear margin.
    check(
        "topic does not leak into style axis (margin > 0.02)",
        (d_divergent - d_similar) > 0.02,
        f"margin = {d_divergent - d_similar:.4f}",
    )


# --------------------------------------------------------------------------- #
# 2. content_distance — topic behavior + fallback method.
# --------------------------------------------------------------------------- #
def test_content_distance() -> None:
    section("content_distance (topic axis)")

    intro = metrics.content_distance_introspect(
        [CONTENT_NEAR, CONTENT_FAR], CORPUS_CONTENT
    )
    d_near, d_far = intro["distances"]
    method = intro["method"]
    print(f"  method = {method.get('method')}")
    print(f"  d(on-topic) = {d_near:.4f}   d(off-topic) = {d_far:.4f}")

    check(
        "on-topic text closer to content-centroid than off-topic",
        d_near < d_far,
        f"{d_near:.4f} < {d_far:.4f}",
    )
    check(
        "content distances in [0,2]",
        all(0.0 <= d <= 2.0 for d in intro["distances"]),
        f"{[round(x,4) for x in intro['distances']]}",
    )
    # With no sentence-transformers installed, the fallback MUST be TF-IDF and
    # must be reported (no silent default).
    check(
        "content method is reported (tfidf fallback or neural)",
        method.get("method") in ("tfidf_cosine", "neural_content_embedding"),
        str(method.get("method")),
    )


# --------------------------------------------------------------------------- #
# 3. paired_stats — CI brackets the mean, effect size sane, seeded determinism.
# --------------------------------------------------------------------------- #
def test_paired_stats() -> None:
    section("paired_stats (bootstrap CI, Cohen's d, determinism)")

    # Facet consistently LOWER distance than baseline (a real toward-corpus
    # shift). SIGN CONVENTION (round-2): mean_shift = mean(baseline - facet), so
    # a facet nearer the corpus (smaller distance) gives a POSITIVE shift.
    facet = [0.20, 0.22, 0.18, 0.25, 0.19, 0.21, 0.23, 0.17]
    baseline = [0.40, 0.45, 0.38, 0.50, 0.41, 0.44, 0.46, 0.39]

    res = metrics.paired_stats(facet, baseline)
    print(f"  mean_shift = {res['mean_shift']:.4f}  "
          f"CI = [{res['ci_low']:.4f}, {res['ci_high']:.4f}]  "
          f"d = {res['cohens_d']:.3f}  n = {res['n']}")

    # CI must bracket the point estimate.
    check(
        "CI brackets the mean_shift",
        res["ci_low"] <= res["mean_shift"] <= res["ci_high"],
        f"{res['ci_low']:.4f} <= {res['mean_shift']:.4f} <= {res['ci_high']:.4f}",
    )
    # A real, consistent toward-corpus shift should be detected (CI excludes 0).
    # Toward-corpus is POSITIVE now, so the whole CI sits ABOVE 0.
    check(
        "consistent toward-corpus shift -> CI entirely above 0 (positive)",
        res["ci_low"] > 0.0,
        f"ci_low = {res['ci_low']:.4f}",
    )
    # Large, consistent effect -> |d| should be substantial.
    check(
        "large effect -> |cohens_d| > 0.8",
        abs(res["cohens_d"]) > 0.8,
        f"d = {res['cohens_d']:.3f}",
    )
    # Determinism: same inputs -> identical CI (seeded rng(0)).
    res2 = metrics.paired_stats(facet, baseline)
    check(
        "bootstrap is deterministic (seeded)",
        res["ci_low"] == res2["ci_low"] and res["ci_high"] == res2["ci_high"],
        f"[{res2['ci_low']:.6f}, {res2['ci_high']:.6f}]",
    )
    # Required keys present.
    check(
        "returns required keys",
        all(k in res for k in ("mean_shift", "ci_low", "ci_high", "cohens_d")),
        str(sorted(res.keys())),
    )

    # No-effect case: facet == baseline -> mean_shift ~ 0 and d == 0.
    flat = metrics.paired_stats([0.3, 0.3, 0.3], [0.3, 0.3, 0.3])
    check(
        "no-effect case -> mean_shift==0 and d==0",
        abs(flat["mean_shift"]) < 1e-12 and flat["cohens_d"] == 0.0,
        f"shift={flat['mean_shift']}, d={flat['cohens_d']}",
    )

    # Mismatched lengths must raise (paired contract).
    raised = False
    try:
        metrics.paired_stats([0.1, 0.2], [0.1])
    except ValueError:
        raised = True
    check("mismatched-length pairing raises ValueError", raised)


# --------------------------------------------------------------------------- #
# 4. fit_transfer — flat vs decaying vs breakdown, both tiers.
# --------------------------------------------------------------------------- #
def test_fit_transfer() -> None:
    section("fit_transfer (transfer curve)")

    dists = [0.10, 0.20, 0.30, 0.40, 0.50, 0.60, 0.70, 0.80, 0.90]

    # FLAT: style_shift roughly constant as content-distance grows.
    flat_y = [0.30, 0.31, 0.29, 0.30, 0.31, 0.30, 0.29, 0.30, 0.31]
    flat = metrics.fit_transfer(dists, flat_y, tier="full")
    print(f"  flat:     shape={flat['shape']:>9}  slope={flat['slope']:.4f}")
    check(
        "flat curve classified 'flat'",
        flat["shape"] == "flat",
        f"shape={flat['shape']}, slope={flat['slope']:.4f}",
    )

    # DECAYING: style_shift falls steadily but not collapsing to <50% at far end
    # ... actually a steady linear decline from 0.5 to 0.1 DOES drop below 50%,
    # which is (correctly) a breakdown. Use a gentle decline that stays >50%.
    decay_y = [0.40, 0.38, 0.36, 0.34, 0.32, 0.30, 0.28, 0.26, 0.24]
    decay = metrics.fit_transfer(dists, decay_y, tier="full")
    print(f"  decaying: shape={decay['shape']:>9}  slope={decay['slope']:.4f}")
    check(
        "gently-declining curve classified 'decaying'",
        decay["shape"] == "decaying" and decay["slope"] < 0,
        f"shape={decay['shape']}, slope={decay['slope']:.4f}",
    )

    # BREAKDOWN: style holds near, then collapses at the far end (< 50% of near).
    break_y = [0.40, 0.41, 0.39, 0.40, 0.38, 0.20, 0.08, 0.05, 0.03]
    brk = metrics.fit_transfer(dists, break_y, tier="full")
    print(f"  breakdown:shape={brk['shape']:>9}  slope={brk['slope']:.4f}  "
          f"bd={brk['breakdown_distance']}")
    check(
        "collapsing-far curve classified 'breakdown' with a distance",
        brk["shape"] == "breakdown" and brk["breakdown_distance"] is not None,
        f"shape={brk['shape']}, bd={brk['breakdown_distance']}",
    )

    # Envelope keys present (full).
    check(
        "full envelope has required keys",
        all(k in flat for k in ("shape", "slope", "breakdown_distance",
                                "points", "fit")),
        str(sorted(flat.keys())),
    )
    check(
        "full points carry distance+style_shift",
        len(flat["points"]) == len(dists)
        and all({"distance", "style_shift"} <= set(p) for p in flat["points"]),
        f"n_points={len(flat['points'])}",
    )

    # LEAN tier: tertile bins; same envelope; near/mid/far present.
    lean = metrics.fit_transfer(dists, decay_y, tier="lean")
    bins = lean["fit"].get("bins", {})
    print(f"  lean:     shape={lean['shape']:>9}  bins={list(bins.keys())}")
    check(
        "lean returns near/mid/far bins",
        set(bins.keys()) == {"near", "mid", "far"},
        str(list(bins.keys())),
    )
    check(
        "lean envelope matches the shared shape (3 bin points)",
        all(k in lean for k in ("shape", "slope", "breakdown_distance",
                                "points", "fit"))
        and len(lean["points"]) == 3,
        f"n_points={len(lean['points'])}",
    )
    # Lean bin means ordered by distance near<mid<far.
    bd = [bins["near"]["mean_distance"], bins["mid"]["mean_distance"],
          bins["far"]["mean_distance"]]
    check(
        "lean bins ordered near<mid<far by distance",
        bd[0] < bd[1] < bd[2],
        f"{[round(x,3) for x in bd]}",
    )


# --------------------------------------------------------------------------- #
# 5. collapse_rate — block counting on a tiny markdown string.
# --------------------------------------------------------------------------- #
def test_collapse_rate() -> None:
    section("collapse_rate (function->section discretization)")

    # A tiny facet with frontmatter + 7 sections (opening prose 'situate' + 6
    # headed blocks) + a closing epigraph. Expect ~7 blocks -> ratio ~1.0.
    tiny_facet = (
        "---\n"
        "name: test-facet\n"
        "version: 0.1.0\n"
        "lineage: \"a test lineage\"\n"
        "---\n"
        "\n"
        "# Test Facet\n"
        "\n"
        "Opening prose that situates the reader inside the stance. One block.\n"
        "\n"
        "## Stance\n"
        "What this is, affirmative-first. Then what it refuses.\n"
        "\n"
        "## Territory\n"
        "The vocabulary and frameworks, jargon unglossed.\n"
        "\n"
        "## Failure Modes\n"
        "Concrete, in-voice anti-patterns.\n"
        "\n"
        "## Slanted Mirrors\n"
        "Where this sits among neighbors.\n"
        "\n"
        "## Integration\n"
        "How it talks to other facets.\n"
        "\n"
        "---\n"
        "\n"
        "*\"a closing line from the corpus.\"*\n"
    )

    with tempfile.NamedTemporaryFile("w", suffix=".md", delete=False,
                                     encoding="utf-8") as fh:
        fh.write(tiny_facet)
        path = fh.name
    try:
        res = metrics.collapse_rate(path)
    finally:
        os.unlink(path)

    print(f"  blocks={res['blocks']}  functions={res['functions']}  "
          f"ratio={res['ratio']:.3f}")

    # The "# Test Facet" title + opening prose form the 'situate' block, then 6
    # '##' sections => 7 content blocks. We assert the heading-block count.
    check(
        "functions denominator is 7",
        res["functions"] == 7,
        str(res["functions"]),
    )
    check(
        "counts roughly one block per function (6-8 blocks)",
        6 <= res["blocks"] <= 8,
        f"blocks={res['blocks']}",
    )
    check(
        "ratio == blocks/7",
        abs(res["ratio"] - res["blocks"] / 7.0) < 1e-9,
        f"ratio={res['ratio']:.4f}",
    )
    # Frontmatter and epigraph must be excluded: a body-less file -> 0 blocks.
    fm_only = "---\nname: x\nlineage: \"y\"\n---\n"
    with tempfile.NamedTemporaryFile("w", suffix=".md", delete=False,
                                     encoding="utf-8") as fh:
        fh.write(fm_only)
        p2 = fh.name
    try:
        res2 = metrics.collapse_rate(p2)
    finally:
        os.unlink(p2)
    check(
        "frontmatter-only file -> 0 blocks (fm excluded)",
        res2["blocks"] == 0,
        f"blocks={res2['blocks']}",
    )


# --------------------------------------------------------------------------- #
# 6. Integration smoke: a realistic style-shift pipeline end-to-end.
# --------------------------------------------------------------------------- #
def test_integration_pipeline() -> None:
    section("integration smoke (style->paired->transfer)")

    # Simulate a battery: facet outputs match the corpus register; baselines are
    # the flat divergent register. Compute style distances, pair, fit the curve.
    facet_outputs = [
        "Loss came quick. No words—just the gap. Then the cold. Then nothing.",
        "The city emptied. Lights off—one by one. Silence in the street. Gone.",
        "The future broke. No plan—just drift. The clock stopped. We waited.",
    ]
    baseline_outputs = [
        ("It is worth considering that loss, in its many and varied forms, "
         "tends to manifest gradually over an extended period of time."),
        ("One might observe that cities, being complex systems, generally "
         "undergo transitions that unfold across numerous interrelated stages."),
        ("The future, broadly speaking, can be understood as a horizon toward "
         "which present trajectories are, in a general sense, oriented."),
    ]
    # Distances to the corpus style-centroid (lower = closer to corpus voice).
    df = metrics.style_distance(facet_outputs, CORPUS_STYLE)
    db = metrics.style_distance(baseline_outputs, CORPUS_STYLE)
    print(f"  facet dists    = {[round(x,3) for x in df]}")
    print(f"  baseline dists = {[round(x,3) for x in db]}")

    # NOTE: we assert on the AGGREGATE (mean) shift, not per-probe ordering.
    # Per-probe style distance on tiny (~3-passage) samples is noisy by design
    # — the methodology's whole point is that a single probe is not a signal;
    # the paired, baseline-subtracted mean (with a CI, in the real harness) is.
    # The strict per-probe separation is exercised in test_style_distance with
    # maximally-separated fixtures; here we check the harness-level claim.
    check(
        "facet outputs closer to corpus style ON AVERAGE than baselines",
        sum(df) / len(df) < sum(db) / len(db),
        f"mean facet={sum(df)/len(df):.3f} < mean base={sum(db)/len(db):.3f}",
    )

    stats = metrics.paired_stats(df, db)
    # SIGN CONVENTION (round-2): toward-corpus is POSITIVE. With facet distances
    # smaller than baseline distances, mean(baseline - facet) > 0.
    check(
        "paired facet-vs-baseline shift is positive (toward corpus)",
        stats["mean_shift"] > 0,
        f"mean_shift={stats['mean_shift']:.4f}",
    )

    # Build a transfer curve: x = content-distance of each probe from corpus,
    # y = style-shift toward corpus. paired_stats already uses (baseline - facet);
    # the per-probe y here is the SAME convention (baseline_dist - facet_dist, so
    # + = toward corpus), so it lines up with mean_shift's sign.
    content_dists = metrics.content_distance(facet_outputs, CORPUS_STYLE)
    style_shift_toward = [b - f for f, b in zip(df, db)]
    curve = metrics.fit_transfer(content_dists, style_shift_toward, tier="lean")
    check(
        "transfer curve assembles with a valid shape",
        curve["shape"] in ("flat", "decaying", "breakdown"),
        f"shape={curve['shape']}, slope={curve['slope']:.4f}",
    )


# --------------------------------------------------------------------------- #
# 7. REGRESSION — corpus-defines-the-ruler (batch-independence + single-text).
#
# Guards the train/test-leakage bug the review-gate caught: the measurement
# space (vocab, scaling, centroid) must be fit on the CORPUS ONLY, with texts
# projected in. If it isn't, (a) a text's distance depends on its batch-mates,
# and (b) the single-text case degenerates (mean-centering over [1 text + corpus]
# forced the lone text ~anti-parallel to the centroid -> spurious distance 2.0).
# --------------------------------------------------------------------------- #
def test_corpus_defines_ruler() -> None:
    section("regression: corpus-defines-the-ruler (batch-independence)")

    # The exact corpus from the review-gate repro (Fisher / capital-realist).
    fisher_corpus = [
        "Capitalist realism forecloses the very imagination of an alternative.",
        "Hauntology names the lost futures that still press on the present.",
    ]
    on_style = ("The slow cancellation of the future is not a feeling but a "
                "condition.")
    # An off-style text in a totally different register (chatty, list-like).
    off_style = ("So basically there's like a bunch of stuff you can do on the "
                 "weekend, you know, if you want, it's totally up to you!")

    # --- BATCH-INDEPENDENCE: f([A], C) == f([A, B], C)[0] for BOTH axes. ---
    s_solo = metrics.style_distance([on_style], fisher_corpus)[0]
    s_batch = metrics.style_distance([on_style, off_style], fisher_corpus)[0]
    print(f"  style:   solo={s_solo:.6f}  batch[0]={s_batch:.6f}")
    check(
        "STYLE distance is batch-independent (f([A],C)==f([A,B],C)[0])",
        abs(s_solo - s_batch) < 1e-9,
        f"|{s_solo:.9f} - {s_batch:.9f}| = {abs(s_solo - s_batch):.2e}",
    )

    c_solo = metrics.content_distance([on_style], fisher_corpus)[0]
    c_batch = metrics.content_distance([on_style, off_style], fisher_corpus)[0]
    print(f"  content: solo={c_solo:.6f}  batch[0]={c_batch:.6f}")
    check(
        "CONTENT distance is batch-independent (f([A],C)==f([A,B],C)[0])",
        abs(c_solo - c_batch) < 1e-9,
        f"|{c_solo:.9f} - {c_batch:.9f}| = {abs(c_solo - c_batch):.2e}",
    )

    # Adding a third batch-mate must also not move it (stronger independence).
    s_batch3 = metrics.style_distance(
        [on_style, off_style, CONTENT_FAR], fisher_corpus)[0]
    check(
        "STYLE distance stable across different batch compositions",
        abs(s_solo - s_batch3) < 1e-9,
        f"|{s_solo:.9f} - {s_batch3:.9f}| = {abs(s_solo - s_batch3):.2e}",
    )

    # --- SINGLE-TEXT SANITY: finite, well below the cosine max, on<off. ---
    print(f"  single-text style: on_style={s_solo:.6f}  "
          f"off_style={metrics.style_distance([off_style], fisher_corpus)[0]:.6f}")
    check(
        "single-text on-style distance is finite and well below max (< 1.0)",
        0.0 <= s_solo < 1.0,
        f"d(on_style)={s_solo:.6f}",
    )
    s_off_solo = metrics.style_distance([off_style], fisher_corpus)[0]
    check(
        "single-text call: on-style closer than off-style",
        s_solo < s_off_solo,
        f"on={s_solo:.6f} < off={s_off_solo:.6f}",
    )

    # --- THE EXACT REPRO: must NOT be the spurious 2.0 anymore. ---
    repro = metrics.style_distance([on_style], fisher_corpus)
    print(f"  review-gate repro distance = {repro[0]:.6f} (was 2.0)")
    check(
        "review-gate repro no longer returns spurious 2.0",
        repro[0] < 1.5,            # generous: just not pinned to the max
        f"distance={repro[0]:.6f}",
    )

    # --- Method introspection still reports the corpus-only fit. ---
    intro = metrics.style_distance_introspect([on_style], fisher_corpus)
    check(
        "style method reports space fit on corpus only",
        intro["method"].get("space_fit_on") == "corpus_passages_only",
        str(intro["method"].get("space_fit_on")),
    )
    cintro = metrics.content_distance_introspect([on_style], fisher_corpus)
    check(
        "content method reports space fit on corpus only",
        cintro["method"].get("space_fit_on") == "corpus_passages_only",
        str(cintro["method"].get("space_fit_on")),
    )


# --------------------------------------------------------------------------- #
# 8. SIGN CONVENTION — toward-corpus is POSITIVE, everywhere (round-2).
#
# Locks the ONE defined direction: with vals = DISTANCES (lower = closer to the
# corpus centroid), a facet that lands NEARER the centroid than the baseline must
# yield a POSITIVE mean_shift. This is mean(baseline_dist - facet_dist). The
# transfer-curve y-axis uses the same convention, so the headline number and the
# curve agree in sign.
# --------------------------------------------------------------------------- #
def test_sign_convention() -> None:
    section("sign convention: toward-corpus is POSITIVE (round-2)")

    # Facet distances strictly SMALLER than baseline distances on every probe =>
    # facet is nearer the corpus on every probe => unambiguously "toward corpus".
    facet_dist = [0.10, 0.12, 0.08, 0.11, 0.09, 0.13]
    baseline_dist = [0.30, 0.34, 0.28, 0.31, 0.29, 0.35]

    res = metrics.paired_stats(facet_dist, baseline_dist)
    print(f"  facet nearer on every probe -> mean_shift = "
          f"{res['mean_shift']:.4f}  d = {res['cohens_d']:.3f}")

    # THE LOCK: nearer-to-corpus facet => POSITIVE mean_shift.
    check(
        "facet nearer the centroid than baseline -> POSITIVE mean_shift",
        res["mean_shift"] > 0,
        f"mean_shift = {res['mean_shift']:.4f}",
    )
    # And the exact formula: mean(baseline - facet).
    import numpy as _np
    expected = float(_np.mean(_np.array(baseline_dist) - _np.array(facet_dist)))
    check(
        "mean_shift == mean(baseline_dist - facet_dist) exactly",
        abs(res["mean_shift"] - expected) < 1e-12,
        f"{res['mean_shift']:.6f} vs {expected:.6f}",
    )
    # Cohen's d carries the SAME sign (positive = toward corpus).
    check(
        "cohens_d shares the sign (positive = toward corpus)",
        res["cohens_d"] > 0,
        f"d = {res['cohens_d']:.3f}",
    )
    # SYMMETRY: a facet FARTHER from the corpus (away) must be NEGATIVE — the one
    # direction is defined both ways.
    away = metrics.paired_stats(baseline_dist, facet_dist)
    check(
        "facet farther from corpus -> NEGATIVE mean_shift (away)",
        away["mean_shift"] < 0,
        f"mean_shift = {away['mean_shift']:.4f}",
    )

    # The transfer-curve y-axis shares the convention: y = baseline - facet, so a
    # toward-corpus facet gives positive style-shift, and a positive-flat curve
    # reads as robust transfer (not a collapse).
    content_x = [0.1, 0.2, 0.3, 0.4, 0.5, 0.6]
    style_shift_toward = [b - f for f, b in zip(facet_dist, baseline_dist)]
    curve = metrics.fit_transfer(content_x, style_shift_toward, tier="full")
    check(
        "toward-corpus style-shift is positive across the curve",
        all(p["style_shift"] > 0 for p in curve["points"]),
        f"min style_shift = {min(p['style_shift'] for p in curve['points']):.4f}",
    )


# --------------------------------------------------------------------------- #
# 9. VOICE-STRATIFIED CENTROID — corpus_weights (round-2).
#
# The corpus mixes voice-bearing passages with encyclopedic scaffolding. Weighting
# the centroid toward the high-voice passages must MOVE the distances vs a uniform
# centroid (otherwise the stratification does nothing). Also exercises the dict-
# with-`voice_charge` convenience and that default None preserves uniform.
# --------------------------------------------------------------------------- #
def test_voice_stratified_centroid() -> None:
    section("voice-stratified centroid (corpus_weights, round-2)")

    # Corpus: two voice-bearing fragments (the punchy register) + two encyclopedic
    # scaffolding passages (flat exposition). A uniform centroid is diluted by the
    # scaffolding; weighting toward the voice-bearing pair should pull the ruler.
    corpus = [
        "The storm came. It broke the pier—then nothing. No warning.",      # voice
        "Wind first. Then rain—hard, flat, sideways. The boats turned.",     # voice
        ("A storm is a meteorological phenomenon characterized by strong "
         "winds and precipitation, typically associated with low pressure."),  # scaffold
        ("Maritime vessels are watercraft designed for navigation on bodies "
         "of water, and are categorized by hull type and propulsion."),        # scaffold
    ]
    probe = ["The kettle screamed. She killed the flame—then quiet. No fuss."]

    d_uniform = metrics.style_distance(probe, corpus)[0]
    # Weight ONLY the two voice-bearing passages (high=1.0), drop the scaffolding.
    weights = [1.0, 1.0, 0.0, 0.0]
    d_weighted = metrics.style_distance(probe, corpus, corpus_weights=weights)[0]
    print(f"  STYLE: uniform={d_uniform:.4f}  voice-weighted={d_weighted:.4f}")

    # THE LOCK: a voice-stratified centroid changes the distance vs uniform.
    check(
        "voice-weighted centroid changes STYLE distance vs uniform",
        abs(d_uniform - d_weighted) > 1e-6,
        f"|{d_uniform:.6f} - {d_weighted:.6f}| = {abs(d_uniform - d_weighted):.2e}",
    )
    # The punchy probe should land CLOSER once scaffolding stops diluting the
    # ruler.
    check(
        "punchy probe is closer to the voice-weighted centroid than the uniform one",
        d_weighted < d_uniform,
        f"weighted {d_weighted:.4f} < uniform {d_uniform:.4f}",
    )

    # Content axis honors weights too (TF-IDF fallback here). The probe must
    # share topical vocabulary with the corpus for a centroid shift to be visible
    # (a fully-OOV probe pins both at distance 1.0 — uninformative). Use a
    # storm/boat probe and re-weight which passages dominate the topic centroid.
    content_probe = ["The storm broke the boats against the pier in the wind."]
    c_uniform = metrics.content_distance(content_probe, corpus)[0]
    # Weight toward the encyclopedic scaffolding (different topical vocabulary)
    # so the topic centroid moves measurably vs uniform.
    c_weighted = metrics.content_distance(
        content_probe, corpus, corpus_weights=[1.0, 1.0, 0.0, 0.0])[0]
    print(f"  CONTENT: uniform={c_uniform:.4f}  voice-weighted={c_weighted:.4f}")
    check(
        "voice-weighted centroid changes CONTENT distance vs uniform",
        abs(c_uniform - c_weighted) > 1e-6,
        f"|{c_uniform:.6f} - {c_weighted:.6f}|",
    )

    # method records the weighting that ran.
    intro_u = metrics.style_distance_introspect(probe, corpus)
    intro_w = metrics.style_distance_introspect(probe, corpus,
                                                corpus_weights=weights)
    check(
        "method reports centroid_weighting (uniform vs voice_stratified)",
        intro_u["method"].get("centroid_weighting") == "uniform"
        and intro_w["method"].get("centroid_weighting") == "voice_stratified",
        f"uniform={intro_u['method'].get('centroid_weighting')}, "
        f"weighted={intro_w['method'].get('centroid_weighting')}",
    )

    # CONVENIENCE: dict corpus entries carrying voice_charge derive the SAME
    # weights as passing high/low explicitly (high->1.0, low->0.0).
    corpus_dicts = [
        {"text": corpus[0], "voice_charge": "high"},
        {"text": corpus[1], "voice_charge": "high"},
        {"text": corpus[2], "voice_charge": "low"},
        {"text": corpus[3], "voice_charge": "low"},
    ]
    d_dict = metrics.style_distance(probe, corpus_dicts)[0]
    check(
        "dict entries with voice_charge derive the same weighting as explicit weights",
        abs(d_dict - d_weighted) < 1e-9,
        f"dict {d_dict:.6f} vs explicit {d_weighted:.6f}",
    )
    intro_dict = metrics.style_distance_introspect(probe, corpus_dicts)
    check(
        "dict voice_charge path reports voice_stratified weighting",
        intro_dict["method"].get("centroid_weighting") == "voice_stratified",
        str(intro_dict["method"].get("centroid_weighting")),
    )

    # DEFAULT None preserves uniform (and matches a plain-string corpus call).
    check(
        "corpus_weights=None == omitting it (uniform preserved)",
        metrics.style_distance(probe, corpus, corpus_weights=None)[0] == d_uniform,
        "ok",
    )

    # Explicit weight-length mismatch must raise (parallel-to-corpus contract).
    raised = False
    try:
        metrics.style_distance(probe, corpus, corpus_weights=[1.0, 1.0])
    except ValueError:
        raised = True
    check("mismatched corpus_weights length raises ValueError", raised)


# --------------------------------------------------------------------------- #
# 10. NEURAL AUTO-UPGRADE GUARD — method reports the path that actually ran.
#
# The neural backends (StyleDistance/STEL, MiniLM) upgrade automatically when
# importable, else fall back (stylometry / TF-IDF). The deps are NOT installed in
# this venv, so we lock the FALLBACK path + the import-guard logic: the guard
# returns False/None cleanly (no raise), and `method` accurately reports the
# fallback that ran. (The neural branch itself is exercised separately by the
# build's fake-import smoke; here we guarantee the always-on contract.)
# --------------------------------------------------------------------------- #
def test_neural_guard_and_method() -> None:
    section("neural auto-upgrade guard + honest method reporting")

    # Import guard must not raise and (in this venv) reports neural absent.
    st_here = metrics._sentence_transformers_available()
    print(f"  sentence_transformers importable here: {st_here}")
    check(
        "import guard returns a bool without raising",
        isinstance(st_here, bool),
        f"value={st_here}",
    )
    # Model loaders never raise; return None when deps absent.
    if not st_here:
        check(
            "style/content model loaders return None when deps absent (no raise)",
            metrics._load_style_model() is None
            and metrics._load_content_model() is None,
            "both None",
        )

    si = metrics.style_distance_introspect([SIMILAR_STYLE_DIFF_TOPIC], CORPUS_STYLE)
    ci = metrics.content_distance_introspect([CONTENT_NEAR], CORPUS_CONTENT)
    print(f"  STYLE method={si['method']['method']}  "
          f"CONTENT method={ci['method']['method']}")

    # The reported method must match what actually ran given dep availability.
    if st_here:
        check(
            "with deps: style method includes neural_style",
            "neural_style" in str(si["method"]["method"]),
            str(si["method"]["method"]),
        )
        check(
            "with deps: content method is neural_content_embedding",
            ci["method"]["method"] == "neural_content_embedding",
            str(ci["method"]["method"]),
        )
    else:
        check(
            "without deps: style falls back to classical_stylometry (neural flag False)",
            si["method"]["method"] == "classical_stylometry"
            and si["method"]["neural_style_embedding"] is False
            and si["method"]["neural_model_id"] is None,
            str(si["method"]["method"]),
        )
        check(
            "without deps: content falls back to tfidf_cosine",
            ci["method"]["method"] == "tfidf_cosine",
            str(ci["method"]["method"]),
        )


# --------------------------------------------------------------------------- #
# 11. centroid_confound_check — the "ranks Fisher above Sexton" auto-diagnostic.
#
# When the corpus is *about* the voice (commentary/biography PROSE) rather than
# *in* it (the actual VERSE), the content-masked style-centroid measures GENRE,
# not voice: it ranks a wrong-lineage PROSE distractor CLOSER than the corpus's
# own held-out VERSE. We construct BOTH a CONFOUNDED case (this structure) and a
# CLEAN case (held-out in the same register as the corpus, distractor in a
# different one) and lock the boolean + margin sign. Fixtures are designed to
# hold on BOTH the classical-only path and the neural-on path (verified at build
# time), so this test passes regardless of whether sentence-transformers is in
# the venv.
# --------------------------------------------------------------------------- #
def test_centroid_confound_check() -> None:
    section("centroid_confound_check (ranks-Fisher-above-Sexton tripwire)")

    # --- CONFOUNDED: corpus is PROSE *about* a voice; held-out is the VERSE. ---
    # The centroid is built from flowing commentary prose, so it scores terse
    # line-broken verse (the true voice, wrong genre) FARTHER than a wrong-lineage
    # prose distractor that happens to match the corpus GENRE. This is the
    # confessional-poet round-2 failure, reproduced.
    corpus_prose_about = [
        ("In her confessional work the poet returns again and again to the "
         "body, to illness and to the domestic interior, rendering private "
         "suffering in a voice that refuses the consolations of distance."),
        ("The poems are frequently read as autobiography, and indeed the "
         "speaker and the author are difficult to separate, though the craft of "
         "the line belies any sense that this is mere unmediated outpouring."),
        ("Critics have noted that the work, for all its rawness, is "
         "meticulously shaped, the enjambment and the stanza breaks doing "
         "patient structural work beneath the surface of apparent spontaneity."),
        ("Across the collections the recurring images accumulate into a private "
         "mythology, and the reader comes to understand the figures of the "
         "mother, the husband, and the child as fixed stars in a personal "
         "cosmos."),
    ]
    held_out_verse = [
        "My mouth blooms like a cut.\nI'm all bones.\nThe night is a fist.",
        "I am the witch.\nI burn.\nThe fire eats my hands—still I sing.",
    ]
    distractor_prose = [
        ("It is worth considering that the gradual accumulation of capital, "
         "across many interrelated markets, tends to concentrate wealth in ways "
         "that resist any simple corrective through ordinary policy."),
        ("One might observe that economic systems, being subject to numerous "
         "competing pressures, generally evolve along trajectories that are "
         "difficult to anticipate from within the present moment."),
    ]

    conf = metrics.centroid_confound_check(
        held_out_verse, distractor_prose, corpus_prose_about)
    print(f"  CONFOUNDED: held_out={conf['held_out_mean_dist']:.4f}  "
          f"distractor={conf['distractor_mean_dist']:.4f}  "
          f"margin={conf['margin']:.4f}  method={conf['method']['method']}")

    # THE TRIPWIRE: held-out (own voice) is FARTHER than the wrong-lineage
    # distractor => the centroid measures genre not voice => confounded.
    check(
        "confounded corpus flagged confounded=True",
        conf["confounded"] is True,
        f"margin={conf['margin']:.4f}",
    )
    check(
        "confounded case: positive margin (held-out farther than distractor)",
        conf["margin"] > 0.0
        and conf["held_out_mean_dist"] > conf["distractor_mean_dist"],
        f"{conf['held_out_mean_dist']:.4f} > {conf['distractor_mean_dist']:.4f}",
    )
    check(
        "confounded case recommends pairwise fallback",
        conf["recommendation"] == "fall back to pairwise headline",
        conf["recommendation"],
    )

    # --- CLEAN: held-out shares the corpus register; distractor diverges. ---
    style_corpus = [
        "The storm came. It broke the pier—then nothing. No warning. Just water.",
        "Wind first. Then rain—hard, flat, sideways. The boats turned over. Gone.",
        "Cold morning. Grey sea—still as glass. Then the swell. It rose. It fell.",
        "Salt on the rail. The fog lifted—slowly. A gull cried once. Then silence.",
    ]
    held_out_clean = [
        "Night fell. The lamp died—then dark. No sound. Just cold.",
        "She ran. The door slammed—hard. The stairs creaked. Then quiet.",
    ]
    distractor_clean = [
        ("It is worth considering that the gradual unfolding of events, across "
         "many interrelated stages, tends to resist any single summary."),
        ("One might observe that complex systems, being subject to numerous "
         "pressures, generally evolve in ways that are difficult to predict."),
    ]
    clean = metrics.centroid_confound_check(
        held_out_clean, distractor_clean, style_corpus)
    print(f"  CLEAN:      held_out={clean['held_out_mean_dist']:.4f}  "
          f"distractor={clean['distractor_mean_dist']:.4f}  "
          f"margin={clean['margin']:.4f}")

    check(
        "clean corpus flagged confounded=False",
        clean["confounded"] is False,
        f"margin={clean['margin']:.4f}",
    )
    check(
        "clean case: negative margin (own voice closer than distractor)",
        clean["margin"] < 0.0
        and clean["held_out_mean_dist"] < clean["distractor_mean_dist"],
        f"{clean['held_out_mean_dist']:.4f} < {clean['distractor_mean_dist']:.4f}",
    )
    check(
        "clean case recommends style-centroid usable",
        clean["recommendation"] == "style-centroid usable",
        clean["recommendation"],
    )

    # Envelope: required keys + counts + the margin identity.
    check(
        "confound check returns required keys",
        all(k in conf for k in ("confounded", "held_out_mean_dist",
                                "distractor_mean_dist", "margin",
                                "recommendation", "method")),
        str(sorted(conf.keys())),
    )
    check(
        "margin == held_out_mean - distractor_mean exactly",
        abs(conf["margin"]
            - (conf["held_out_mean_dist"] - conf["distractor_mean_dist"]))
        < 1e-12,
        f"margin={conf['margin']:.6f}",
    )
    check(
        "counts match the input population sizes",
        conf["n_held_out"] == len(held_out_verse)
        and conf["n_distractor"] == len(distractor_prose),
        f"n_held_out={conf['n_held_out']}, n_distractor={conf['n_distractor']}",
    )

    # Determinism: same inputs -> identical verdict + numbers (no hidden RNG).
    conf2 = metrics.centroid_confound_check(
        held_out_verse, distractor_prose, corpus_prose_about)
    check(
        "confound check is deterministic (same inputs -> same numbers)",
        conf2["margin"] == conf["margin"]
        and conf2["confounded"] == conf["confounded"],
        f"margin={conf2['margin']:.6f}",
    )

    # Contract guards: empty populations / empty corpus must raise ValueError.
    raised_held = raised_distr = raised_corpus = False
    try:
        metrics.centroid_confound_check([], distractor_prose, corpus_prose_about)
    except ValueError:
        raised_held = True
    try:
        metrics.centroid_confound_check(held_out_verse, [], corpus_prose_about)
    except ValueError:
        raised_distr = True
    try:
        metrics.centroid_confound_check(held_out_verse, distractor_prose, [])
    except ValueError:
        raised_corpus = True
    check(
        "empty held-out / distractor / corpus each raise ValueError",
        raised_held and raised_distr and raised_corpus,
        f"held={raised_held}, distr={raised_distr}, corpus={raised_corpus}",
    )


# --------------------------------------------------------------------------- #
# 12. verbatim_echo — the "hollow tell" (strangeness substrate).
#
# A text that lifts a long contiguous phrase from the corpus should score a HIGH
# echo fraction and a LONG verbatim span; a paraphrase carrying the same ideas in
# different words should score ~0 echo and a span of at most an incidental shared
# word. The function only MEASURES — these checks lock the measurement, not a
# "hollow" threshold (that is the scorer's call). Pure-Python/numpy: deterministic
# regardless of neural availability.
# --------------------------------------------------------------------------- #
def test_verbatim_echo() -> None:
    section("verbatim_echo (hollow-tell / corpus-recitation)")

    corpus = [
        ("The slow cancellation of the future has been accompanied by a "
         "deflation of expectations."),
        ("Capitalist realism is the widespread sense that capitalism is the "
         "only viable system."),
        "There is no alternative, and even to imagine one is now foreclosed.",
    ]
    # HIGH echo: lifts a long verbatim run from the first corpus passage.
    high = ("I would say the slow cancellation of the future has been "
            "accompanied by a deflation of expectations everywhere.")
    # LOW echo: the same ideas, paraphrased — no long shared run.
    low = ("Tomorrow feels foreclosed; our hopes keep shrinking and the system "
           "seems permanent to everyone.")

    res = metrics.verbatim_echo([high, low], corpus, n_lo=4, n_hi=8)
    r_high, r_low = res
    print(f"  HIGH: echo_fraction={r_high['echo_fraction']:.4f}  "
          f"longest_span={r_high['longest_verbatim_span_tokens']}  "
          f"per_n={ {k: round(v,3) for k,v in r_high['per_n'].items()} }")
    print(f"  LOW:  echo_fraction={r_low['echo_fraction']:.4f}  "
          f"longest_span={r_low['longest_verbatim_span_tokens']}")

    # THE TELL: the reciting text echoes far more than the paraphrase.
    check(
        "verbatim-lifting text has higher echo_fraction than paraphrase",
        r_high["echo_fraction"] > r_low["echo_fraction"],
        f"{r_high['echo_fraction']:.4f} > {r_low['echo_fraction']:.4f}",
    )
    check(
        "high-echo text scores a substantial echo_fraction (> 0.3)",
        r_high["echo_fraction"] > 0.3,
        f"echo_fraction={r_high['echo_fraction']:.4f}",
    )
    check(
        "paraphrase echo_fraction is ~0 (no long shared run)",
        r_low["echo_fraction"] < 0.05,
        f"echo_fraction={r_low['echo_fraction']:.4f}",
    )
    # Longest verbatim span: the lift is many tokens; the paraphrase shares at
    # most an incidental single word (< n_lo, so it never enters echo_fraction).
    check(
        "high-echo longest verbatim span is long (>= n_lo)",
        r_high["longest_verbatim_span_tokens"] >= 4,
        f"span={r_high['longest_verbatim_span_tokens']}",
    )
    check(
        "paraphrase longest verbatim span is short (< n_lo)",
        r_low["longest_verbatim_span_tokens"] < 4,
        f"span={r_low['longest_verbatim_span_tokens']}",
    )

    # per_n covers exactly the requested n-range, all fractions in [0,1].
    check(
        "per_n spans exactly n_lo..n_hi",
        set(r_high["per_n"].keys()) == set(range(4, 9)),
        str(sorted(r_high["per_n"].keys())),
    )
    check(
        "all per_n fractions and echo_fraction are in [0,1]",
        all(0.0 <= v <= 1.0 for v in r_high["per_n"].values())
        and 0.0 <= r_high["echo_fraction"] <= 1.0,
        f"echo_fraction={r_high['echo_fraction']:.4f}",
    )
    # Required keys present per text.
    check(
        "each result carries the required keys",
        all(k in r_high for k in ("echo_fraction", "per_n",
                                  "longest_verbatim_span_tokens", "n_tokens")),
        str(sorted(r_high.keys())),
    )

    # A text that IS a corpus passage verbatim echoes ~fully (sanity ceiling).
    exact = metrics.verbatim_echo([corpus[0]], corpus, n_lo=4, n_hi=8)[0]
    print(f"  EXACT corpus passage: echo_fraction={exact['echo_fraction']:.4f}  "
          f"longest_span={exact['longest_verbatim_span_tokens']}")
    check(
        "an exact corpus passage echoes fully (echo_fraction == 1.0)",
        abs(exact["echo_fraction"] - 1.0) < 1e-12,
        f"echo_fraction={exact['echo_fraction']:.4f}",
    )
    check(
        "exact corpus passage longest span == its own token length",
        exact["longest_verbatim_span_tokens"] == exact["n_tokens"],
        f"span={exact['longest_verbatim_span_tokens']} "
        f"n_tokens={exact['n_tokens']}",
    )

    # Configurable n-range: a higher floor than the lift length zeroes the
    # fraction (n-grams longer than any shared run cannot match) but the
    # longest-span metric is NOT capped by n_hi (reports the true long run).
    narrow = metrics.verbatim_echo([high], corpus, n_lo=20, n_hi=25)[0]
    check(
        "n-range is configurable (n_lo above the shared run -> 0 echo_fraction)",
        narrow["echo_fraction"] == 0.0
        and set(narrow["per_n"].keys()) == set(range(20, 26)),
        f"echo_fraction={narrow['echo_fraction']:.4f}",
    )
    check(
        "longest-span metric is NOT capped by n_hi (still reports the long run)",
        narrow["longest_verbatim_span_tokens"]
        == r_high["longest_verbatim_span_tokens"],
        f"span={narrow['longest_verbatim_span_tokens']}",
    )

    # Determinism.
    res2 = metrics.verbatim_echo([high, low], corpus, n_lo=4, n_hi=8)
    check(
        "verbatim_echo is deterministic",
        res2[0]["echo_fraction"] == r_high["echo_fraction"]
        and res2[1]["longest_verbatim_span_tokens"]
        == r_low["longest_verbatim_span_tokens"],
        "ok",
    )

    # Contract guards: empty corpus and a bad n-range raise ValueError.
    raised_corpus = raised_range = False
    try:
        metrics.verbatim_echo([high], [])
    except ValueError:
        raised_corpus = True
    try:
        metrics.verbatim_echo([high], corpus, n_lo=5, n_hi=3)
    except ValueError:
        raised_range = True
    check(
        "empty corpus and inverted n-range each raise ValueError",
        raised_corpus and raised_range,
        f"corpus={raised_corpus}, range={raised_range}",
    )

    # A span shorter than n_lo (single shared word, no qualifying n-gram) yields
    # zero echo but a non-negative span — guards the "absence vs measured-zero"
    # handling for too-short texts.
    tiny = metrics.verbatim_echo(["future"], corpus, n_lo=4, n_hi=8)[0]
    check(
        "a too-short text yields 0 echo_fraction without raising",
        tiny["echo_fraction"] == 0.0 and tiny["n_tokens"] == 1,
        f"echo_fraction={tiny['echo_fraction']:.4f}, n_tokens={tiny['n_tokens']}",
    )


# --------------------------------------------------------------------------- #
# 13. style_weighting_warning — corpus_weights near-inert on the style axis.
#
# corpus_weights moves the content-masked style
# centroid only ~1e-04 (voice_charge varies along content, which the style axis
# masks). We do NOT remove the param (the scorer + the prior tests pass it), but
# when weighting is requested on the STYLE axis the method must carry a warning
# flag — and NO such flag when weights are omitted (uniform) or on the content
# axis (where weighting IS effective).
# --------------------------------------------------------------------------- #
def test_style_weighting_warning() -> None:
    section("style_weighting_warning (corpus_weights near-inert on style)")

    corpus = [
        "The storm came. It broke the pier—then nothing. No warning.",
        "Wind first. Then rain—hard, flat, sideways. The boats turned.",
        ("A storm is a meteorological phenomenon characterized by strong winds "
         "and precipitation, typically associated with low pressure."),
        ("Maritime vessels are watercraft designed for navigation on bodies of "
         "water, and are categorized by hull type and propulsion."),
    ]
    probe = ["The kettle screamed. She killed the flame—then quiet. No fuss."]
    weights = [1.0, 1.0, 0.0, 0.0]

    intro_u = metrics.style_distance_introspect(probe, corpus)
    intro_w = metrics.style_distance_introspect(probe, corpus,
                                                corpus_weights=weights)
    print(f"  uniform has warning: "
          f"{'style_weighting_warning' in intro_u['method']}  "
          f"weighted has warning: "
          f"{'style_weighting_warning' in intro_w['method']}")

    # Weighting requested on the STYLE axis -> a warning flag is present.
    check(
        "style weighting request attaches style_weighting_warning to method",
        "style_weighting_warning" in intro_w["method"]
        and "near-inert" in str(intro_w["method"]["style_weighting_warning"]),
        str(intro_w["method"].get("style_weighting_warning"))[:60],
    )
    # Uniform (no weights) -> NO warning (nothing to warn about).
    check(
        "uniform style call carries NO style_weighting_warning",
        "style_weighting_warning" not in intro_u["method"],
        "absent as expected",
    )
    # The warning is advisory only: it must NOT change the numbers vs a call that
    # introspects the same weighted distance (the param is still honored).
    d_plain = metrics.style_distance(probe, corpus, corpus_weights=weights)[0]
    check(
        "warning is advisory: weighted distance unchanged by introspection",
        abs(intro_w["distances"][0] - d_plain) < 1e-12,
        f"{intro_w['distances'][0]:.6f} == {d_plain:.6f}",
    )
    # The CONTENT axis must NOT carry the style warning (weighting is effective
    # there — the warning is style-axis-specific).
    cintro_w = metrics.content_distance_introspect(
        ["The storm broke the boats against the pier in the wind."],
        corpus, corpus_weights=weights)
    check(
        "content axis does NOT carry the style_weighting_warning",
        "style_weighting_warning" not in cintro_w["method"],
        "absent on content axis as expected",
    )


# --------------------------------------------------------------------------- #
# 14. semantic_echo — the PARAPHRASE tell (the surprise substrate, depth 2).
#
# verbatim_echo is lexical; semantic_echo catches the same MOVE recited in other
# words. It needs the neural content model. When the model is ABSENT, lock the
# honest "unavailable" contract (available=False, no raise). When PRESENT, lock
# the behavioral discrimination: a paraphrase of a corpus move scores a HIGHER
# nearest-corpus cosine than an unrelated line. Empty corpus raises. Guarded so it
# passes on both the core-only and the neural venv.
# --------------------------------------------------------------------------- #
def test_semantic_echo() -> None:
    section("semantic_echo (paraphrase tell, depth-2 surprise substrate)")

    corpus = [
        "Capitalism is the slow cancellation of the future.",
        "There is no time any longer; the present has been foreclosed.",
        "Hauntology is the agency of the virtual, the lost future that lingers.",
    ]

    # Empty corpus must raise (parallel to the other detectors' contract).
    raised = False
    try:
        metrics.semantic_echo(["anything at all here"], [])
    except ValueError:
        raised = True
    check("semantic_echo: empty corpus_passages raises ValueError", raised)

    available = metrics._load_content_model() is not None
    print(f"  neural content model available: {available}")

    if not available:
        # Honest unavailable contract — reported, never hidden, never raised.
        res = metrics.semantic_echo(
            ["the future has been quietly called off"], corpus)
        check(
            "without neural deps: semantic_echo reports available=False (no raise)",
            res[0]["available"] is False
            and res[0]["method"] == "unavailable"
            and res[0]["semantic_echo_max"] is None,
            str(res[0]),
        )
        return

    # With the model: a PARAPHRASE of a corpus move scores a higher nearest-corpus
    # cosine than an UNRELATED line. (Meaning is the axis; surface differs.)
    paraphrase = ["The future keeps being called off; tomorrow never quite arrives."]
    unrelated = ["The recipe calls for two cups of flour and a pinch of salt."]
    r_par = metrics.semantic_echo(paraphrase, corpus)[0]
    r_unr = metrics.semantic_echo(unrelated, corpus)[0]
    print(f"  paraphrase max={r_par['semantic_echo_max']:.3f}  "
          f"unrelated max={r_unr['semantic_echo_max']:.3f}")
    check(
        "paraphrase of a corpus move out-echoes an unrelated line (semantic)",
        r_par["semantic_echo_max"] > r_unr["semantic_echo_max"],
        f"paraphrase {r_par['semantic_echo_max']:.3f} > "
        f"unrelated {r_unr['semantic_echo_max']:.3f}",
    )
    check(
        "available=True + method=neural_content_embedding when the model is present",
        r_par["available"] is True
        and r_par["method"] == "neural_content_embedding",
        str(r_par["method"]),
    )
    check(
        "semantic_echo_max is a cosine in [-1, 1]",
        -1.0 <= r_par["semantic_echo_max"] <= 1.0,
        f"{r_par['semantic_echo_max']:.3f}",
    )


# --------------------------------------------------------------------------- #
# Runner.
# --------------------------------------------------------------------------- #
def main() -> int:
    print("psychomanteum eval — metrics self-test (offline)")
    print(f"python: {sys.version.split()[0]}")
    try:
        import numpy
        import sklearn
        print(f"numpy {numpy.__version__}  scikit-learn {sklearn.__version__}")
    except Exception as e:  # pragma: no cover
        print(f"FATAL: core deps missing: {e}")
        return 2
    try:
        import scipy
        print(f"scipy {scipy.__version__} (optional exp-decay fit available)")
    except Exception:
        print("scipy not installed (optional; linear-only curve fit)")

    tests = [
        test_style_distance,
        test_content_distance,
        test_paired_stats,
        test_fit_transfer,
        test_collapse_rate,
        test_integration_pipeline,
        test_corpus_defines_ruler,
        test_sign_convention,
        test_voice_stratified_centroid,
        test_neural_guard_and_method,
        test_centroid_confound_check,
        test_verbatim_echo,
        test_style_weighting_warning,
        test_semantic_echo,
    ]
    for t in tests:
        try:
            t()
        except Exception:
            section(f"ERROR in {t.__name__}")
            traceback.print_exc()
            check(f"{t.__name__} ran without exception", False, "raised")

    section("SUMMARY")
    passed = sum(1 for _, ok, _ in _RESULTS if ok)
    total = len(_RESULTS)
    for name, ok, _ in _RESULTS:
        if not ok:
            print(f"  FAILED: {name}")
    print(f"\n{passed}/{total} checks passed.")
    return 0 if passed == total else 1


if __name__ == "__main__":
    sys.exit(main())
