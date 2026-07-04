#!/usr/bin/env python3
"""
eval/harnesses/talkie_server.py — faithful talkie-1930 via llama-server (OpenAI API).

WHY THIS EXISTS. talkie-1930 is a custom-architecture 13B (parameter-free QK-norm,
per-head/per-layer gains, embedding-skip connections, negative-freq_scale RoPE). It
loads FAITHFULLY only in `thomasgauthier/llama.cpp@talkie-1930`, and only on CPU —
the negative-freq_scale RoPE sentinel has no faithful Metal kernel (Metal emits
degenerate `\\x1f` soup; CPU produces correct period prose). ollama's bundled
`talkie` arch has ALSO diverged (it demands learnable QK-norm weight tensors talkie
does not have, and would run it at logit_scale=1.0 instead of the true 256/n_embd).

So talkie is served by:
    llama-server -m <gguf> -ngl 0 --jinja --port 8089
which exposes an OpenAI-compatible endpoint. This adapter routes the CLEAN
(system, user) channel there — the same guarantees as the ollama adapter: a clean
local generation with real sampling params and token logprobs (-> perplexity).

ROUTING. Registers as the "talkie" provider; model strings route via a `talkie:`
prefix (e.g. "talkie:talkie-1930"). `generate._resolve_provider` maps the prefix
here; the adapter strips it (the remainder is the OpenAI `model` id, which
llama-server echoes — it serves whatever model it was launched with). Endpoint is
read from TALKIE_SERVER_URL (default http://127.0.0.1:8089).

CONTRACT. Identical to every other backend:
    _generate_talkie(system, user, model, timeout, params) -> gen._result(...)
optionally AUGMENTED with a compact `gen_meta` (perplexity / token stats) that the
generation driver persists. stdlib-only (urllib) so registration never fails for a
missing dependency; network errors surface as a clean per-call ok=False result.
"""
from __future__ import annotations

import json
import math
import os
import sys
import urllib.error
import urllib.request
from typing import Dict, Optional

# Put eval/ on sys.path so `import generate` resolves however this is launched.
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import generate as gen  # noqa: E402

_PROVIDER = "talkie"
_PREFIX = "talkie:"
_CAPTURE = "talkie-local"


def _endpoint() -> str:
    return os.environ.get("TALKIE_SERVER_URL", "http://127.0.0.1:8089").rstrip("/")


def _strip_prefix(model: str) -> str:
    """`talkie:<id>` -> `<id>` (maxsplit=1)."""
    m = (model or "").strip()
    if m.lower().startswith(_PREFIX):
        return m.split(":", 1)[1]
    return m


def _body_from_params(params: Optional[Dict[str, object]]) -> Dict[str, object]:
    """Map our sampling-param names -> OpenAI/llama-server body keys. Only set given."""
    params = params or {}
    body: Dict[str, object] = {}
    for k in ("temperature", "top_p", "seed", "top_k"):
        if k in params:
            body[k] = params[k]
    # accept either num_predict (ollama's name, used across the harness) or max_tokens
    if "num_predict" in params:
        body["max_tokens"] = params["num_predict"]
    elif "max_tokens" in params:
        body["max_tokens"] = params["max_tokens"]
    return body


def _aggregate_perplexity(content_logprobs) -> Optional[Dict[str, object]]:
    """Compact gen_meta from OpenAI-style choices[0].logprobs.content[].logprob.
    Keeps ONLY aggregates {perplexity, mean_logprob, n_tokens} so files stay small."""
    if not content_logprobs:
        return None
    vals = []
    try:
        for tok in content_logprobs:
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
        pass
    return result


def _generate_talkie(
    system: str,
    user: str,
    model: str,
    timeout: int,
    params: Optional[Dict[str, object]] = None,
) -> Dict[str, object]:
    """Clean local generation via the talkie llama-server. Honors the contract; never raises."""
    real_model = _strip_prefix(model) or "talkie-1930"

    # Empty system => bare-model baseline: omit the system message entirely.
    messages = []
    if (system or "").strip():
        messages.append({"role": "system", "content": system})
    messages.append({"role": "user", "content": user})

    body: Dict[str, object] = {
        "model": real_model,
        "messages": messages,
        "stream": False,
        "logprobs": True,
        "top_logprobs": 1,
    }
    body.update(_body_from_params(params))
    data = json.dumps(body).encode("utf-8")
    req = urllib.request.Request(
        _endpoint() + "/v1/chat/completions",
        data=data,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            payload = json.loads(resp.read().decode("utf-8"))
    except urllib.error.URLError as e:
        return gen._result("", model, _CAPTURE, False,
                           "talkie server unreachable (%s): %s" % (_endpoint(), e), params)
    except Exception as e:
        return gen._result("", model, _CAPTURE, False,
                           "%s: %s" % (type(e).__name__, e), params)

    ch = (payload.get("choices") or [{}])[0]
    text = ((ch.get("message") or {}).get("content") or "").strip()
    if not text:
        return gen._result("", model, _CAPTURE, False,
                           "empty output: talkie server returned no content", params)

    result = gen._result(text, model, _CAPTURE, True, None, params)

    gen_meta: Dict[str, object] = {}
    usage = payload.get("usage") or {}
    if isinstance(usage.get("completion_tokens"), int):
        gen_meta["tokens_out"] = usage["completion_tokens"]
    if isinstance(usage.get("prompt_tokens"), int):
        gen_meta["tokens_in"] = usage["prompt_tokens"]
    if ch.get("finish_reason"):
        gen_meta["finish"] = ch["finish_reason"]
    lp = ch.get("logprobs") or {}
    ppl = _aggregate_perplexity(lp.get("content") if isinstance(lp, dict) else None)
    if ppl:
        gen_meta.update(ppl)
    if gen_meta:
        result["gen_meta"] = gen_meta
    return result


# Register at import (side-effect). Routing is taught in generate._resolve_provider.
gen.register_adapter(_PROVIDER, _generate_talkie)
