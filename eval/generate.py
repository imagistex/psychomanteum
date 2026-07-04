"""
eval/generate.py — the generation primitive of the psychomanteum eval harness.

This is the *anti-circularity, anti-contamination core* of the eval (see
`prompts/eval-methodology.md` and `agents/eval-prober.md`, Step 5). It captures a
REAL generation from a model that is conditioned on ONLY a `(system, user)` pair:

    system = the facet text, verbatim, and nothing else
    user   = the flat probe, e.g. "Describe loss."

NONE of the harness framing — no eval instructions, no "you are being tested," no
sub-agent preamble — may enter that conditioned context. Contamination invalidates
the measurement. That is the whole point: a fresh context steered by the facet
alone, captured verbatim, scored later against held-out corpus passages.

------------------------------------------------------------------------------
DISCOVERED ENVIRONMENT (flags verified by `--help` and a real test run on
2026-05-30, macOS, host-wrapped CLIs)
------------------------------------------------------------------------------

headless-claude-code (DEFAULT):
    claude --bare -p \
           --system-prompt <FACET_TEXT> \
           --output-format json \
           --model <model_alias_or_full> \
           <USER_PROBE>

    - `-p` / `--print`         : non-interactive; print response and exit.
    - `--system-prompt <s>`    : the CLEAN conditioning channel. With this flag
                                 set, claude uses `s` as the session system prompt
                                 INSTEAD of its default system prompt. This is the
                                 facet-as-textual-steering-vector injection point.
                                 (We use --system-prompt, NOT --append-system-prompt:
                                 we want the facet to BE the system, not to ride on
                                 top of the default assistant persona.)
    - `--output-format json`   : structured output. NOTE: in this build it emits a
                                 JSON ARRAY of streamed events (system/init,
                                 assistant, result), not a single object. The clean
                                 assistant text is the `result` field of the element
                                 whose `type == "result"`. We parse that; we fall
                                 back to the `assistant` event's content[].text, and
                                 finally to raw stdout. (Parser handles array, single
                                 object, and plain-text shapes.)
    - `--bare`                 : minimal mode — skips hooks, LSP, plugin sync,
                                 attribution, auto-memory, background prefetches,
                                 keychain reads, and CLAUDE.md auto-discovery. We use
                                 it to MINIMIZE host-wrapper contamination of the
                                 conditioned context.
    - `--model <m>`            : "headless-claude-code" maps to the wrapper default
                                 (we pass no --model); explicit Claude model ids /
                                 aliases (e.g. "opus", "claude-opus-4-8") are passed
                                 through.

    !!! CONTAMINATION CAVEAT (documented per task; recorded in capture_method) !!!
    The host Claude Code wrapper STILL injects its own system prompt even in `--bare`
    headless mode. Empirically, a 2-token user prompt + a ~45-char `--system-prompt`
    produced ~2444 cache-creation input tokens in the result usage — i.e. a large
    hidden system prompt rode along that we did NOT author. So `--system-prompt` does
    NOT give us a perfectly clean (system, user)-only context here; it gives us
    (wrapper_system + facet_system, user). We ACCEPT this contamination for
    preliminary runs and record `capture_method="headless-claude-code"` so it is
    visible downstream and never mistaken for a raw-API capture. A genuinely clean
    context is the future `harnesses/` raw-API direction.

codex (OPTIONAL, multi-model):
    codex exec -m <model> --skip-git-repo-check \
               -o <TMPFILE> \
               <COMBINED_PROMPT>     # see system-channel note below

    - `codex exec`              : run Codex non-interactively.
    - `-o, --output-last-message <FILE>` : write ONLY the final assistant message to
                                 FILE (clean capture; avoids parsing JSONL events).
    - `--skip-git-repo-check`   : allow running outside a git repo / tmp cwd.
    - `-m, --model <m>`         : model selection.
    SYSTEM-CHANNEL NOTE: `codex exec` has NO native `--system-prompt`. We therefore
    fold the facet into the prompt as a leading system block (see _combine_system_user).
    This is WEAKER conditioning than claude's real system channel and is itself a
    contamination source; recorded as capture_method="headless-codex".

gemini (OPTIONAL, multi-model):
    gemini -m <model> -o json -p <COMBINED_PROMPT>

    - `-p, --prompt <s>`        : non-interactive (headless) mode.
    - `-o, --output-format json`: structured output; clean text parsed from the
                                 "response" field (fallbacks handle other shapes).
    - `-m, --model <m>`         : model selection.
    SYSTEM-CHANNEL NOTE: gemini's headless mode also has no clean `--system-prompt`
    flag, so we fold the facet into the prompt the same way. Recorded as
    capture_method="headless-gemini".

------------------------------------------------------------------------------
CONTRACT
------------------------------------------------------------------------------

    generate(system, user, model="headless-claude-code", timeout=180) -> dict

returns:
    {
      "output": str,            # verbatim model text ("" on failure)
      "model": str,             # the model identifier we asked for
      "capture_method": str,    # "headless-claude-code" | "headless-codex" | "headless-gemini"
      "ok": bool,               # True iff a non-empty generation was captured
      "error": str | None,      # human-readable failure reason, else None
    }

This function NEVER raises for an operational failure (timeout, non-zero exit,
empty output, missing CLI) — it returns ok=False with a clear `error`, so the
prober can record the failure without crashing the battery. (It may still raise
on genuine programmer error, e.g. a non-str argument.)
"""

from __future__ import annotations

import contextlib
import errno
import json
import os
import signal
import shutil
import subprocess
import tempfile
import time
from typing import Dict, Iterator, List, Optional


# --- model -> (capture_method, cli) routing -------------------------------------

# Default headless Claude Code. Any value here (or any unrecognized value that
# looks like a Claude model) routes to the claude CLI.
_CLAUDE_MODEL = "headless-claude-code"
# Values meaning "use the wrapper's DEFAULT model" — emit NO --model flag. Passing
# `--model claude` exits 1 under claude 2.1.168 ("claude" is not a valid model id;
# it is our sentinel for the default). Any value OUTSIDE this set is a real alias/id.
_CLAUDE_DEFAULT_ALIASES = {"headless-claude-code", "claude", "claude-code", "default", ""}


# --- host-level concurrency lock (serialize `claude` across sessions) -----------
#
# WHY (2026-06-02 postmortem): the per-agent sequential bound did NOT stop three
# parallel eval sessions + a build session from all hammering the single shared
# `claude` CLI on the host — ~80min wall vs ~30 est, because the bound only held
# *inside* one agent. The bound must hold at the HOST. This lock serializes every
# real CLI invocation (claude/codex/gemini) across all processes on the machine.
#
# Path: <system temp dir>/psychomanteum-claude-cli.lock  (resolved at runtime via
# tempfile.gettempdir(); on this host that is the user-scoped temp dir). One lock
# for all backends, since they contend on the same machine for the same wrapper.
#
# Semantics:
#   - Exclusive create (O_CREAT|O_EXCL). The holder writes "<pid> <epoch>".
#   - acquire blocks up to LOCK_ACQUIRE_TIMEOUT seconds, polling.
#   - STALE handling: a lock is reclaimed if its PID is dead OR it is older than
#     LOCK_STALE_SECONDS (covers a crash that left the file behind, and the
#     1863s-hang case where the holder is wedged far past any sane call bound).
#   - Best-effort release in a finally; a crash is recovered by stale handling.
#
# This is intentionally a *coarse* lock: correctness (no concurrent hammering)
# over throughput. Generation is meant to run detached and sequential anyway.

_LOCK_NAME = "psychomanteum-claude-cli.lock"
LOCK_ACQUIRE_TIMEOUT = 1800   # max seconds to wait for the lock before giving up
LOCK_STALE_SECONDS = 1200     # a held lock older than this (20 min) is presumed dead
_LOCK_POLL_INTERVAL = 0.5


def _lock_path() -> str:
    """Host-level lockfile path, resolved against the real temp dir at runtime."""
    return os.path.join(tempfile.gettempdir(), _LOCK_NAME)


def _pid_alive(pid: int) -> bool:
    """True if a process with this PID exists (signal 0 probe)."""
    if pid <= 0:
        return False
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        # Exists but owned by another user — treat as alive (don't steal).
        return True
    except OSError:
        return False
    return True


def _read_lock(path: str) -> tuple:
    """Return (pid, epoch) from a lockfile, or (None, None) if unreadable."""
    try:
        with open(path, "r") as fh:
            parts = fh.read().split()
    except (OSError, ValueError):
        return (None, None)
    pid = epoch = None
    if parts:
        try:
            pid = int(parts[0])
        except ValueError:
            pid = None
    if len(parts) > 1:
        try:
            epoch = float(parts[1])
        except ValueError:
            epoch = None
    return (pid, epoch)


def _lock_is_stale(path: str) -> bool:
    """A lock is stale if its PID is dead or it is older than LOCK_STALE_SECONDS."""
    pid, epoch = _read_lock(path)
    if pid is not None and not _pid_alive(pid):
        return True
    # Age check: trust the file's own recorded epoch first, fall back to mtime.
    age_ref = epoch
    if age_ref is None:
        try:
            age_ref = os.stat(path).st_mtime
        except OSError:
            return False  # gone; let the create race resolve it
    return (time.time() - age_ref) > LOCK_STALE_SECONDS


@contextlib.contextmanager
def _host_cli_lock(acquire_timeout: float = LOCK_ACQUIRE_TIMEOUT) -> Iterator[bool]:
    """
    Serialize host-wide `claude`/`codex`/`gemini` invocations via an exclusive
    lockfile. Yields True if the lock was acquired (and releases on exit), or
    False if it could not be acquired within acquire_timeout (caller proceeds
    UNLOCKED rather than failing the whole battery — a degraded run beats none).

    Stale locks (dead PID or older than LOCK_STALE_SECONDS) are reclaimed.
    """
    path = _lock_path()
    deadline = time.time() + max(0.0, acquire_timeout)
    held = False
    while True:
        try:
            fd = os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o644)
            try:
                os.write(fd, ("%d %f" % (os.getpid(), time.time())).encode())
            finally:
                os.close(fd)
            held = True
            break
        except FileExistsError:
            if _lock_is_stale(path):
                # Reclaim: remove the stale file and retry immediately.
                try:
                    os.remove(path)
                except OSError:
                    pass
                continue
            if time.time() >= deadline:
                break  # give up; yield False (proceed unlocked)
            time.sleep(_LOCK_POLL_INTERVAL)
        except OSError as e:
            # Unexpected FS error — don't wedge the run; proceed unlocked.
            if e.errno in (errno.EROFS, errno.EACCES, errno.ENOENT):
                break
            time.sleep(_LOCK_POLL_INTERVAL)
            if time.time() >= deadline:
                break
    try:
        yield held
    finally:
        if held:
            try:
                # Only remove if it's still *our* lock (avoid deleting a lock a
                # reclaimer handed to someone else after we were presumed stale).
                pid, _ = _read_lock(path)
                if pid == os.getpid():
                    os.remove(path)
            except OSError:
                pass


# --- hard-kill subprocess runner ------------------------------------------------
#
# WHY (2026-06-02 postmortem): a 180s timeout took 1863s to return under
# contention. subprocess.run(..., timeout=T) raises TimeoutExpired but, on the
# host-wrapped CLI, the wrapper spawns CHILDREN that survive the parent's kill —
# so the call can hang on the still-open pipes of orphaned grandchildren long
# past T. The fix: put the child in its own process GROUP (start_new_session=True)
# and SIGKILL the whole GROUP on timeout, so nothing in the subtree survives to
# hold the pipes open. The call then returns ~at the bound.


class _HardTimeout(Exception):
    """Internal: the child process group was hard-killed at the timeout bound."""


def _run_hardkill(cmd: List[str], timeout: float, input_text: str = "") -> subprocess.CompletedProcess:
    """
    Run `cmd` with a timeout that ACTUALLY kills the whole child process group at
    the bound. Returns a CompletedProcess on normal exit. Raises _HardTimeout if
    the group had to be killed (caller maps this to an ok=False timeout result).

    Mechanism: Popen(start_new_session=True) so the child leads a new process
    group; communicate(timeout) for the happy path; on TimeoutExpired, SIGKILL
    the entire group (os.killpg) and a final short communicate() to reap. POSIX.
    """
    try:
        proc = subprocess.Popen(
            cmd,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            start_new_session=True,   # child is its own process-group leader (POSIX)
        )
    except (OSError, ValueError):
        raise  # genuine invocation failure; caller already catches OSError/ValueError

    def _kill_group() -> None:
        # Kill the whole group so wrapper-spawned grandchildren die too.
        try:
            os.killpg(proc.pid, signal.SIGKILL)
        except (ProcessLookupError, OSError):
            # Fall back to killing just the child if the group call failed.
            try:
                proc.kill()
            except OSError:
                pass

    try:
        out, err = proc.communicate(input=input_text, timeout=timeout)
    except subprocess.TimeoutExpired:
        _kill_group()
        # Reap so we don't leave a zombie; the group is SIGKILL'd so this is fast.
        try:
            out, err = proc.communicate(timeout=10)
        except subprocess.TimeoutExpired:
            out, err = "", ""
        raise _HardTimeout()
    return subprocess.CompletedProcess(cmd, proc.returncode, out, err)


def _result(
    output: str,
    model: str,
    capture_method: str,
    ok: bool,
    error: Optional[str],
    params: Optional[Dict[str, object]] = None,
) -> Dict[str, object]:
    """Uniform return shape. (Kept as a helper so every exit path is identical.)

    `params` is a NEW optional key (the sampling-control dict threaded through the
    adapter contract). It is included on EVERY result so the shape is uniform, but
    it is purely additive — existing keys are unchanged and existing callers that
    ignore unknown keys are unaffected. The CLI adapters RECORD params here as a
    no-op (the Meta-wrapped CLIs take no sampling flags); a future API/local
    adapter is free to actually CONSUME params and still report what it used.
    """
    return {
        "output": output,
        "model": model,
        "capture_method": capture_method,
        "ok": ok,
        "error": error,
        "params": params,
    }


def _combine_system_user(system: str, user: str) -> str:
    """
    For CLIs WITHOUT a clean system-prompt channel (codex, gemini), fold the facet
    into a single prompt as a leading system block, then the flat probe.

    This is deliberately minimal framing — it is NOT harness/eval framing (no "you
    are being tested," no scoring instructions). It is the closest available analog
    to a system prompt on a CLI that lacks one. It is still weaker and less clean
    than a real system channel; callers should weigh that via capture_method.
    """
    system = (system or "").strip()
    user = (user or "").strip()
    if not system:
        return user
    return f"{system}\n\n---\n\n{user}"


# --- claude (default) -----------------------------------------------------------

def _extract_claude_text(stdout: str) -> Optional[str]:
    """
    Parse the clean assistant text out of `claude --output-format json` stdout.

    Observed shape in this build: a JSON ARRAY of streamed events:
        [ {type:"system",subtype:"init",...},
          {type:"assistant", message:{content:[{type:"text",text:"..."}]}, ...},
          {type:"result", subtype:"success", result:"<clean text>", ...} ]

    Strategy (most-authoritative first):
      1. result element  -> its "result" string.
      2. assistant element(s) -> concatenated message.content[].text.
      3. single-object shapes -> "result" / "response" / "text".
    Returns None if nothing parseable is found (caller falls back to raw stdout).
    """
    stdout = (stdout or "").strip()
    if not stdout:
        return None

    try:
        data = json.loads(stdout)
    except (ValueError, TypeError):
        # Not JSON (maybe plain text leaked through, or a partial). Let caller
        # decide whether raw stdout is usable.
        return None

    # Shape 1/2: array of events.
    if isinstance(data, list):
        # Prefer the explicit result event.
        for ev in reversed(data):
            if isinstance(ev, dict) and ev.get("type") == "result":
                res = ev.get("result")
                if isinstance(res, str) and res.strip():
                    return res
        # Fall back to assistant text blocks, in order.
        texts: List[str] = []
        for ev in data:
            if isinstance(ev, dict) and ev.get("type") == "assistant":
                msg = ev.get("message") or {}
                for block in (msg.get("content") or []):
                    if isinstance(block, dict) and block.get("type") == "text":
                        t = block.get("text")
                        if isinstance(t, str):
                            texts.append(t)
        if texts:
            joined = "".join(texts).strip()
            if joined:
                return joined
        return None

    # Shape 3: single object.
    if isinstance(data, dict):
        for key in ("result", "response", "text"):
            val = data.get(key)
            if isinstance(val, str) and val.strip():
                return val
        # assistant-style single object
        msg = data.get("message") or {}
        for block in (msg.get("content") or []):
            if isinstance(block, dict) and block.get("type") == "text":
                t = block.get("text")
                if isinstance(t, str) and t.strip():
                    return t
        return None

    return None


# Public, stable name for the ONE central claude-stdout parser. The eval-scorer's
# pairwise judging hits the exact stream-json-vs-single-object bug this solves, so
# it MUST reuse this rather than re-implement (round-2 P1: "land the fix once,
# centrally"). Exposed via `cli.py parse-claude` (see the dispatch entry reported
# to the human) so the scorer can call it through the same JSON-in/JSON-out
# surface as every other compute primitive.
def extract_claude_text(stdout: str) -> Optional[str]:
    """Parse clean assistant text from `claude --output-format json` stdout.

    Robust to BOTH shapes claude emits: a stream-json EVENT ARRAY and a single
    result object (plus assistant-block and plain single-string fallbacks).
    Returns the text, or None if nothing parseable was found. Thin public alias
    of `_extract_claude_text` — one implementation, two names (internal + stable).
    """
    return _extract_claude_text(stdout)


def parse_claude_stdout(stdout: str) -> Dict[str, object]:
    """JSON-in/JSON-out wrapper for the central parser, for `cli.py parse-claude`.

    Returns {"text": <parsed str or "">, "ok": <bool>, "error": <str|None>} so a
    Bash caller (the scorer's pairwise path) gets a uniform envelope and never has
    to know the parser returns None. ok=False with text="" means "no parseable
    assistant text" — the caller decides whether to fall back to raw stdout.
    """
    text = _extract_claude_text(stdout)
    if text is None or not text.strip():
        return {"text": "", "ok": False, "error": "no parseable assistant text in claude stdout"}
    return {"text": text, "ok": True, "error": None}


# --- judgment-JSON extraction (the scorer's INNER parse) ------------------------
#
# WHY (2026-06-08, round-3 cohort): the eval-scorer hand-rolled a brace-counter to
# pull a `{accuracy:..., reason:"..."}` judgment object out of a judge's prose-
# wrapped reply. A naive counter breaks when a string VALUE contains an apostrophe
# (mis-tracked as a quote) or a `{`/`}`/`[`/`]` (counted as structure). One valid
# judgment was dropped this round and recovered only by an ad-hoc field-regex.
# Fix once, centrally: a string-AWARE matcher (only the JSON double-quote toggles
# string state; everything inside a string — apostrophes, braces, brackets — is
# skipped), exposed via `cli.py extract-json` so the scorer stops improvising.

def extract_json_object(text: str) -> Dict[str, object]:
    """Extract the first balanced top-level ``{...}`` JSON object from a text blob.

    String-aware: only the JSON string delimiter ``"`` toggles in-string state, so
    apostrophes, braces, and brackets that appear INSIDE a string value cannot
    break the brace match (the round-3 scorer bug). Returns
    ``{"obj": dict|None, "ok": bool, "error": str|None}`` plus ``"via"`` noting the
    parse path. Falls back to ``ast.literal_eval`` for a Python-dict-shaped blob
    (single-quoted), so a judge that emits a dict literal instead of strict JSON
    still parses. Never raises on bad input — returns ok=False with a reason.
    """
    if not isinstance(text, str):
        return {"obj": None, "ok": False, "error": "input is not a string"}
    start = text.find("{")
    if start < 0:
        return {"obj": None, "ok": False, "error": "no JSON object found (no '{')"}
    depth = 0
    in_str = False
    esc = False
    for i in range(start, len(text)):
        c = text[i]
        if in_str:
            if esc:
                esc = False
            elif c == "\\":
                esc = True
            elif c == '"':
                in_str = False
            continue
        if c == '"':
            in_str = True
        elif c == "{":
            depth += 1
        elif c == "}":
            depth -= 1
            if depth == 0:
                blob = text[start:i + 1]
                try:
                    return {"obj": json.loads(blob), "ok": True, "error": None, "via": "json"}
                except (ValueError, TypeError):
                    try:
                        import ast
                        obj = ast.literal_eval(blob)
                    except (ValueError, SyntaxError, MemoryError, RecursionError):
                        obj = None
                    if isinstance(obj, dict):
                        return {"obj": obj, "ok": True, "error": None, "via": "ast"}
                    return {"obj": None, "ok": False,
                            "error": "balanced object found but not parseable as JSON or a dict literal"}
    return {"obj": None, "ok": False, "error": "no balanced JSON object (unbalanced braces)"}


def _generate_claude(
    system: str,
    user: str,
    model: str,
    timeout: int,
    params: Optional[Dict[str, object]] = None,
) -> Dict[str, object]:
    capture_method = "headless-claude-code"

    # `params` is RECORDED for provenance but is a NO-OP here: the Meta-wrapped
    # `claude` CLI exposes no sampling flags, so we do not invent any. The contract
    # carries it so a future raw-API/local adapter can actually consume it.
    exe = shutil.which("claude")
    if not exe:
        return _result("", model, capture_method, False, "model unavailable: 'claude' CLI not found on PATH", params)

    # Build the invocation. The facet rides the CLEAN --system-prompt channel; the
    # flat probe is the positional prompt. --bare minimizes wrapper contamination;
    # --output-format json gives us a parseable result envelope.
    cmd = [
        exe,
        "--bare",
        "-p",
        "--system-prompt", system,
        "--output-format", "json",
    ]
    # Default model => emit NO --model (see _CLAUDE_DEFAULT_ALIASES). Any other value
    # is an explicit Claude model alias/id, passed through. Guards the 2.1.168
    # `--model claude`-exits-1 bug surfaced 2026-06-07 (the invalid-model error was
    # masked by the startup version banner in the stderr tail).
    if model and model.strip().lower() not in _CLAUDE_DEFAULT_ALIASES:
        cmd += ["--model", model]
    cmd.append(user)

    try:
        # Host-level lock serializes this CLI call against every other session;
        # _run_hardkill guarantees the whole child group dies at the bound.
        with _host_cli_lock():
            proc = _run_hardkill(cmd, timeout=timeout, input_text="")
    except _HardTimeout:
        return _result("", model, capture_method, False, "timeout after %ds invoking claude (process group hard-killed)" % timeout, params)
    except (OSError, ValueError) as e:
        return _result("", model, capture_method, False, "failed to invoke claude: %s" % e, params)

    if proc.returncode != 0:
        # Host launcher banners go to STDERR; surface a trimmed tail for diagnosis.
        err_tail = (proc.stderr or "").strip().splitlines()[-3:]
        return _result(
            "",
            model,
            capture_method,
            False,
            "claude exited %d: %s" % (proc.returncode, " | ".join(err_tail) or "(no stderr)"),
            params,
        )

    text = _extract_claude_text(proc.stdout)
    if text is None:
        # JSON didn't parse / had no text. Last resort: raw stdout if it's non-empty
        # (the wrapper writes clean JSON to stdout and banners to stderr, so raw
        # stdout that fails to parse is unusual — but better to capture than drop).
        raw = (proc.stdout or "").strip()
        if raw:
            return _result(raw, model, capture_method, True, None, params)
        return _result("", model, capture_method, False, "empty output: no result/assistant text in claude JSON and stdout empty", params)

    if not text.strip():
        return _result("", model, capture_method, False, "empty output: claude returned an empty result string", params)

    return _result(text, model, capture_method, True, None, params)


# --- codex (optional) -----------------------------------------------------------

def _generate_codex(
    system: str,
    user: str,
    model: str,
    timeout: int,
    params: Optional[Dict[str, object]] = None,
) -> Dict[str, object]:
    capture_method = "headless-codex"

    # `params` is RECORDED for provenance but a NO-OP here (see _generate_claude).
    exe = shutil.which("codex")
    if not exe:
        return _result("", model, capture_method, False, "model unavailable: 'codex' CLI not found on PATH", params)

    prompt = _combine_system_user(system, user)

    # `-o/--output-last-message <FILE>` writes ONLY the final assistant message to a
    # temp file — a clean capture without parsing JSONL events.
    tmp_fd, tmp_path = tempfile.mkstemp(prefix="psychomanteum_codex_", suffix=".txt")
    os.close(tmp_fd)
    try:
        cmd = [exe, "exec", "--skip-git-repo-check", "-o", tmp_path]
        # codex has no documented "default" sentinel; only pass -m for a concrete model.
        if model and model not in ("codex", "headless-codex"):
            cmd += ["-m", model]
        cmd.append(prompt)

        try:
            with _host_cli_lock():
                proc = _run_hardkill(cmd, timeout=timeout, input_text="")
        except _HardTimeout:
            return _result("", model, capture_method, False, "timeout after %ds invoking codex (process group hard-killed)" % timeout, params)
        except (OSError, ValueError) as e:
            return _result("", model, capture_method, False, "failed to invoke codex: %s" % e, params)

        # Prefer the last-message file (cleanest). Fall back to stdout.
        text = ""
        try:
            with open(tmp_path, "r") as fh:
                text = fh.read().strip()
        except OSError:
            text = ""

        if proc.returncode != 0 and not text:
            err_tail = (proc.stderr or "").strip().splitlines()[-3:]
            return _result(
                "",
                model,
                capture_method,
                False,
                "codex exited %d: %s" % (proc.returncode, " | ".join(err_tail) or "(no stderr)"),
                params,
            )

        if not text:
            text = (proc.stdout or "").strip()

        if not text:
            return _result("", model, capture_method, False, "empty output: codex produced no final message", params)

        return _result(text, model, capture_method, True, None, params)
    finally:
        try:
            os.remove(tmp_path)
        except OSError:
            pass


# --- gemini (optional) ----------------------------------------------------------

def _extract_gemini_text(stdout: str) -> Optional[str]:
    """Parse clean text from `gemini -o json` stdout; tolerate multiple shapes."""
    stdout = (stdout or "").strip()
    if not stdout:
        return None
    try:
        data = json.loads(stdout)
    except (ValueError, TypeError):
        return None
    if isinstance(data, dict):
        for key in ("response", "result", "text", "output"):
            val = data.get(key)
            if isinstance(val, str) and val.strip():
                return val
    if isinstance(data, list):
        # stream-json-like array; collect any string-valued response/text fields.
        chunks: List[str] = []
        for ev in data:
            if isinstance(ev, dict):
                for key in ("response", "text"):
                    v = ev.get(key)
                    if isinstance(v, str):
                        chunks.append(v)
        if chunks:
            joined = "".join(chunks).strip()
            if joined:
                return joined
    return None


def _generate_gemini(
    system: str,
    user: str,
    model: str,
    timeout: int,
    params: Optional[Dict[str, object]] = None,
) -> Dict[str, object]:
    capture_method = "headless-gemini"

    # `params` is RECORDED for provenance but a NO-OP here (see _generate_claude).
    exe = shutil.which("gemini")
    if not exe:
        return _result("", model, capture_method, False, "model unavailable: 'gemini' CLI not found on PATH", params)

    prompt = _combine_system_user(system, user)

    cmd = [exe, "-o", "json"]
    if model and model not in ("gemini", "headless-gemini"):
        cmd += ["-m", model]
    cmd += ["-p", prompt]

    try:
        with _host_cli_lock():
            proc = _run_hardkill(cmd, timeout=timeout, input_text="")
    except _HardTimeout:
        return _result("", model, capture_method, False, "timeout after %ds invoking gemini (process group hard-killed)" % timeout, params)
    except (OSError, ValueError) as e:
        return _result("", model, capture_method, False, "failed to invoke gemini: %s" % e, params)

    if proc.returncode != 0:
        err_tail = (proc.stderr or "").strip().splitlines()[-3:]
        return _result(
            "",
            model,
            capture_method,
            False,
            "gemini exited %d: %s" % (proc.returncode, " | ".join(err_tail) or "(no stderr)"),
            params,
        )

    text = _extract_gemini_text(proc.stdout)
    if text is None:
        raw = (proc.stdout or "").strip()
        if raw:
            return _result(raw, model, capture_method, True, None, params)
        return _result("", model, capture_method, False, "empty output: gemini returned no parseable text and stdout empty", params)

    if not text.strip():
        return _result("", model, capture_method, False, "empty output: gemini returned an empty response", params)

    return _result(text, model, capture_method, True, None, params)


# --- adapter registry -----------------------------------------------------------
#
# Generalizes the old hardcoded if/elif dispatch (claude/codex/gemini) into a small
# open registry so a FUTURE provider (hosted API, local Ollama/HF) can be added
# WITHOUT editing generate()'s dispatch — it just calls register_adapter(...) at
# import time. The routing behavior is UNCHANGED: the resolver below reproduces the
# exact mapping the if/elif encoded.
#
# Adapter contract (every registered callable obeys this signature and return shape):
#     (system: str, user: str, model: str, timeout: int,
#      params: dict | None) -> dict          # the SAME dict _result(...) builds
#
# The three existing backends already match this contract (each now takes `params`),
# so they are registered directly — no wrappers.

# provider key -> adapter callable
_ADAPTERS: Dict[str, object] = {
    "claude": _generate_claude,
    "codex": _generate_codex,
    "gemini": _generate_gemini,
}


def register_adapter(provider: str, fn) -> None:
    """Register (or override) the adapter callable for a provider key.

    PUBLIC extension hook: a future provider (raw Anthropic API, local Ollama/HF,
    etc.) registers itself here — no edit to generate()'s dispatch is needed. `fn`
    MUST honor the adapter contract:

        fn(system: str, user: str, model: str, timeout: int,
           params: dict | None) -> dict   # same shape as _result(...)

    To make a NEW provider routable by model-string, ALSO teach `_resolve_provider`
    (or pass a model string that already resolves to `provider`). Registering an
    adapter under a brand-new key that the resolver never returns is harmless but
    unreachable via model-string routing until the resolver knows about it.

    Raises TypeError if `provider` is not a non-empty str or `fn` is not callable.
    """
    if not isinstance(provider, str) or not provider.strip():
        raise TypeError("register_adapter(provider, fn): provider must be a non-empty str")
    if not callable(fn):
        raise TypeError("register_adapter(provider, fn): fn must be callable")
    _ADAPTERS[provider.strip().lower()] = fn


def _resolve_provider(model: str) -> str:
    """Map a model-string to a provider key, preserving the EXACT old routing.

    Old if/elif (verbatim behavior):
      - "codex"  -> codex
      - "gemini" -> gemini
      - everything else (default sentinel, "claude"/"claude-code"/"", explicit
        Claude model ids/aliases like "opus"/"claude-opus-4-8") -> claude

    Note the per-backend "default" sentinels are handled INSIDE each adapter (codex
    skips -m for {"codex","headless-codex"}; gemini for {"gemini","headless-gemini"};
    claude skips --model for _CLAUDE_DEFAULT_ALIASES). The resolver only chooses the
    PROVIDER; sentinel-to-default-model handling stays where it always was.
    """
    key = (model or "").strip().lower()
    if key == "codex" or key == "headless-codex":
        return "codex"
    if key == "gemini" or key == "headless-gemini":
        return "gemini"
    # Local open-weight models route via an `ollama:` prefix (e.g.
    # "ollama:qwen2.5:7b-instruct"). The ollama adapter strips the prefix to
    # recover the real tag. Registered out-of-tree (eval/harnesses/ollama.py).
    if key == "ollama" or key.startswith("ollama:"):
        return "ollama"
    # talkie-1930 served by a faithful llama-server (OpenAI API). Custom arch that
    # loads only in thomasgauthier/llama.cpp@talkie-1930 on CPU; routed via a
    # `talkie:` prefix. Registered out-of-tree (eval/harnesses/talkie_server.py).
    if key == "talkie" or key.startswith("talkie:"):
        return "talkie"
    # Raw Anthropic API — the un-deferred API adapter: a CLEAN (system, user)
    # channel for frontier Claude weights (vs the contaminated `claude` CLI).
    # Routed via an `anthropic:` prefix, e.g. "anthropic:claude-fable-5".
    # Registered out-of-tree (eval/harnesses/anthropic_api.py).
    if key == "anthropic" or key.startswith("anthropic:"):
        return "anthropic"
    # Default + "claude"/"claude-code"/"" + explicit Claude ids/aliases -> claude.
    return "claude"


# --- public entry point ---------------------------------------------------------

def generate(
    system: str,
    user: str,
    model: str = "headless-claude-code",
    timeout: int = 180,
    params: Optional[Dict[str, object]] = None,
) -> Dict[str, object]:
    """
    Capture a real, fresh, facet-conditioned generation on the clean (system, user)
    pair. See module docstring for the full contract and contamination caveats.

    Routing (via the adapter registry; see register_adapter / _resolve_provider):
      - "headless-claude-code" (default) or a Claude model id/alias -> headless claude
      - "codex"  -> headless codex   (if installed)
      - "gemini" -> headless gemini  (if installed)
    Future providers register an adapter and (if model-string routable) extend the
    resolver — no edit to this dispatch.

    `params` is an OPTIONAL sampling-control dict threaded through to the adapter and
    recorded on the result (result["params"]). It is a NO-OP for the CLI adapters
    (the Meta-wrapped CLIs take no sampling flags); the contract carries it for a
    future API/local adapter that will consume it. Omitting it preserves today's
    behavior exactly.

    Returns the result dict; never raises on operational failure (returns ok=False).
    """
    if not isinstance(system, str) or not isinstance(user, str):
        # Genuine programmer error — surface it rather than silently coercing.
        raise TypeError("generate(system, user, ...) requires str system and str user")

    m = (model or "").strip() or "headless-claude-code"

    provider = _resolve_provider(m)
    adapter = _ADAPTERS.get(provider)
    if adapter is None:
        # Only reachable if a resolver returns a key with no registered adapter
        # (e.g. someone extended the resolver but forgot register_adapter). Fail
        # operationally — same no-raise contract as every other failure path.
        return _result(
            "", m, "unknown",
            False,
            "no adapter registered for provider %r (model %r)" % (provider, m),
            params,
        )
    return adapter(system, user, m, timeout, params)


# --- optional out-of-tree adapters ----------------------------------------------
#
# Register optional local/API adapters (eval/harnesses/) via import side-effect.
# BEST-EFFORT: a missing optional dependency must never break the core CLI
# adapters above, so any failure here is swallowed. eval/ is on sys.path[0] in
# this codebase (cli.py / generation_driver bootstrap), so the bare import
# resolves; each adapter imports its heavy dep lazily so registration won't fail.
try:
    import harnesses as _harnesses  # noqa: F401
except Exception:
    pass
