#!/usr/bin/env python3
"""
eval/harnesses/ollama.py — local open-weight generation adapter (Ollama).

WHY THIS EXISTS. The CLI adapters (claude/codex/gemini) run behind vendor
wrappers that inject hidden system context — the verified `contamination_caveat`
("Meta-wrapper system prompt injected even under --bare") that forces every CLI
capture to be RELATIVE-ONLY. The cross-model steerability study needs a CLEAN
(system, user) channel. Local models via Ollama give exactly that, plus two
things the CLIs cannot: real sampling control (temperature/seed/...) and token
logprobs (which revive the perplexity signal).

ROUTING. Registers itself as the "ollama" provider at import time (see
harnesses/__init__.py, imported best-effort by generate.py). Model strings route
here via an `ollama:` prefix, e.g.
    "ollama:qwen2.5:7b-instruct"
    "ollama:hf.co/thomasgauthier/talkie-1930-13b-it-GGUF:Q4_K_M"
`generate._resolve_provider` maps the prefix to this provider; the adapter strips
it (maxsplit=1, since real Ollama tags themselves contain colons) to recover the
underlying tag.

CONTRACT. Identical to the CLI backends:
    _generate_ollama(system, user, model, timeout, params) -> result dict
where `result` is `gen._result(...)`'s uniform shape, optionally AUGMENTED with a
compact `gen_meta` (perplexity / mean_logprob / token stats) that the generation
driver persists when present. The `ollama` python client is imported LAZILY so a
missing dependency yields a clean per-call error instead of breaking registration
(the CLI adapters must keep working on a machine with no ollama installed).
"""
from __future__ import annotations

import math
import os
import sys
from typing import Dict, Optional

# Put eval/ on sys.path so `import generate` resolves however this is launched
# (mirrors generation_driver.py's bootstrap).
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import generate as gen  # noqa: E402

_PROVIDER = "ollama"
_PREFIX = "ollama:"
_CAPTURE = "ollama-local"


def _strip_prefix(model: str) -> str:
    """`ollama:<tag>` -> `<tag>` (maxsplit=1; tags contain colons like `:Q4_K_M`)."""
    m = (model or "").strip()
    if m.lower().startswith(_PREFIX):
        return m.split(":", 1)[1]
    return m


def _options_from_params(params: Optional[Dict[str, object]]) -> Dict[str, object]:
    """Map our sampling-param names -> Ollama `options` keys. Only set what's given."""
    params = params or {}
    opts: Dict[str, object] = {}
    if "temperature" in params:
        opts["temperature"] = params["temperature"]
    if "top_p" in params:
        opts["top_p"] = params["top_p"]
    if "top_k" in params:
        opts["top_k"] = params["top_k"]
    if "seed" in params:
        opts["seed"] = params["seed"]
    # accept either max_tokens (our name) or num_predict (Ollama's)
    if "num_predict" in params:
        opts["num_predict"] = params["num_predict"]
    elif "max_tokens" in params:
        opts["num_predict"] = params["max_tokens"]
    # num_ctx: Ollama DEFAULTS to 2048 and SILENTLY TRUNCATES longer prompts (the
    # facet system prompt can exceed it). Always set it explicitly so a big facet is
    # never quietly dropped — the corruption is invisible otherwise.
    if "num_ctx" in params:
        opts["num_ctx"] = params["num_ctx"]
    return opts


def _aggregate_perplexity(logprobs) -> Optional[Dict[str, object]]:
    """Compact gen_meta from a logprobs payload. Best-effort + shape-tolerant.

    Ollama returns a list of per-token entries, each carrying the chosen token's
    logprob (natural log). We keep ONLY aggregate stats (never the full array) so
    generations.json stays small: {perplexity, mean_logprob, n_tokens}. Returns
    None if no usable logprobs are present.
    """
    if not logprobs:
        return None
    vals = []
    try:
        for tok in logprobs:
            lp = tok.get("logprob") if isinstance(tok, dict) else getattr(tok, "logprob", None)
            if isinstance(lp, (int, float)) and not math.isinf(lp) and not math.isnan(lp):
                vals.append(float(lp))
    except TypeError:
        return None
    if not vals:
        return None
    mean_lp = sum(vals) / len(vals)
    result = {"mean_logprob": round(mean_lp, 4), "n_tokens": len(vals)}
    try:
        result["perplexity"] = round(math.exp(-mean_lp), 4)
    except OverflowError:
        pass  # absurd logprob magnitude (mean_lp < ~-709); skip ppl, keep the rest
    return result


def _generate_ollama(
    system: str,
    user: str,
    model: str,
    timeout: int,
    params: Optional[Dict[str, object]] = None,
) -> Dict[str, object]:
    """Clean local generation via Ollama. Honors the adapter contract; never raises."""
    real_model = _strip_prefix(model)

    # Lazy import: a missing `ollama` client must not break registration or the
    # CLI adapters — surface it as an operational error on THIS call only.
    try:
        import ollama
    except Exception as e:  # ImportError / partial install
        return gen._result("", model, _CAPTURE, False,
                           "ollama python client not installed: %s" % e, params)

    # Empty system => bare-model baseline: omit the system message entirely.
    messages = []
    if (system or "").strip():
        messages.append({"role": "system", "content": system})
    messages.append({"role": "user", "content": user})

    # Keep `params` AS THE CALLER PASSED IT (None stays None) so it is recorded
    # faithfully on the result: the driver persists it, and a default (None) run
    # must resume against cells stamped with None — recording {} instead breaks
    # _params_match({} , None) and reruns would never reuse cached cells.
    _p = params or {}
    want_logprobs = bool(_p.get("logprobs", True))   # capture by default for local
    top_n = _p.get("top_logprobs", 0)
    options = _options_from_params(params)

    def _chat(with_logprobs: bool):
        client = ollama.Client(timeout=timeout)
        kwargs = dict(model=real_model, messages=messages, options=options, stream=False)
        # Thinking-model control (e.g. gemma): pass `think` ONLY when the caller set
        # it, so default behavior is unchanged for every existing call. think=False
        # routes a thinking model's reasoning out of the way so `content` fills
        # directly; think=True keeps it and we capture the reasoning below.
        if "think" in _p:
            kwargs["think"] = _p["think"]
        if with_logprobs:
            # Only pass the logprobs kwargs when we actually want them, so the
            # retry path can OMIT them entirely — recovering even on a client/server
            # that rejects the logprobs field itself (e.g. an older ollama-python
            # that raises TypeError on the unknown kwarg).
            kwargs["logprobs"] = True
            if top_n:
                kwargs["top_logprobs"] = top_n
        return client.chat(**kwargs)

    try:
        resp = _chat(want_logprobs)
    except Exception as e_first:
        # A logprobs-unsupported server must NOT fail the whole generation: retry
        # once without logprobs before giving up.
        if want_logprobs:
            try:
                resp = _chat(False)
                want_logprobs = False
            except Exception as e:
                return gen._result("", model, _CAPTURE, False,
                                   "%s: %s" % (type(e).__name__, e), params)
        else:
            return gen._result("", model, _CAPTURE, False,
                               "%s: %s" % (type(e_first).__name__, e_first), params)

    # Pull fields shape-tolerantly (ChatResponse is a pydantic model).
    data = resp.model_dump() if hasattr(resp, "model_dump") else dict(resp)
    text = ((data.get("message") or {}).get("content") or "").strip()
    if not text:
        return gen._result("", model, _CAPTURE, False,
                           "empty output: ollama returned no message content", params)

    result = gen._result(text, model, _CAPTURE, True, None, params)

    # Optional compact generation metadata (driver persists it when present).
    gen_meta: Dict[str, object] = {}
    for k_out, k_in in (("tokens_out", "eval_count"), ("tokens_in", "prompt_eval_count")):
        v = data.get(k_in)
        if isinstance(v, int):
            gen_meta[k_out] = v
    ec, ed = data.get("eval_count"), data.get("eval_duration")
    if isinstance(ec, int) and isinstance(ed, (int, float)) and ed:
        gen_meta["tok_per_s"] = round(ec / (ed / 1e9), 1)  # eval_duration is ns
    if data.get("done_reason"):
        gen_meta["finish"] = data["done_reason"]
    # logprobs may live at top level or under message, depending on version.
    lp_payload = data.get("logprobs") or (data.get("message") or {}).get("logprobs")
    ppl = _aggregate_perplexity(lp_payload)
    if ppl:
        gen_meta.update(ppl)
    # Thinking-model reasoning (present only when a model like gemma actually thinks
    # and `think` was not disabled). Capture it so the model's deliberation — part of
    # its authoring "journey" — is preserved rather than silently dropped.
    thinking = (data.get("message") or {}).get("thinking")
    if isinstance(thinking, str) and thinking.strip():
        gen_meta["thinking"] = thinking
        gen_meta["thinking_chars"] = len(thinking)
    if gen_meta:
        result["gen_meta"] = gen_meta
    return result


# Register at import (side-effect). Routing is taught in generate._resolve_provider.
gen.register_adapter(_PROVIDER, _generate_ollama)
