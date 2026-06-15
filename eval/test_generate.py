#!/usr/bin/env python3
"""
eval/test_generate.py — tests for the generation primitive + driver.

TWO layers:

  1. UNIT TESTS (no `claude` needed; always run). Cover the hardening landed for
     the round-2 generation-loss postmortem:
       - the central claude-stdout parser (stream-json array vs single object vs
         plain-text vs garbage) — the bug the scorer's pairwise path also hit;
       - the atomic-checkpoint + resume-skips-completed-cells logic of
         generation_driver.run_battery (with generate() monkeypatched — NO real
         model call);
       - the timeout HARD-KILL path: a deliberately-hung fake subprocess must make
         the call return ~AT the bound, not long after (proving the kill fired, not 
         just waiting out the child);
       - basic host-lock acquire / release / stale-reclaim.

  2. GUARDED SMOKE TEST (runs ONE real generation iff the `claude` CLI is on PATH;
     else SKIP). Unchanged in spirit from before.

Run:
    python3 eval/test_generate.py            # unit tests (+ smoke if claude present)
    python3 eval/test_generate.py --smoke    # ONLY the real-generation smoke test
    python3 -m unittest eval.test_generate   # unit tests only
"""

import json
import os
import shutil
import sys
import tempfile
import time
import unittest

# Make `import generate` / `import generation_driver` work whether run as
# `python3 eval/test_generate.py` (cwd = repo root) or from inside eval/.
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import generate  # noqa: E402
from generate import generate as run_generate  # noqa: E402
import generation_driver  # noqa: E402


# ============================================================================
# 1a. Central claude-stdout parser (the scorer's pairwise bug, landed centrally)
# ============================================================================

class TestExtractClaudeText(unittest.TestCase):
    def test_stream_json_array_prefers_result_event(self):
        stdout = json.dumps([
            {"type": "system", "subtype": "init"},
            {"type": "assistant",
             "message": {"content": [{"type": "text", "text": "partial..."}]}},
            {"type": "result", "subtype": "success", "result": "the clean answer"},
        ])
        self.assertEqual(generate.extract_claude_text(stdout), "the clean answer")

    def test_stream_json_array_falls_back_to_assistant_blocks(self):
        # No result event => concatenate assistant text blocks in order.
        stdout = json.dumps([
            {"type": "system", "subtype": "init"},
            {"type": "assistant",
             "message": {"content": [{"type": "text", "text": "Hello "},
                                       {"type": "text", "text": "world"}]}},
        ])
        self.assertEqual(generate.extract_claude_text(stdout), "Hello world")

    def test_single_result_object(self):
        stdout = json.dumps({"type": "result", "result": "single-object answer"})
        self.assertEqual(generate.extract_claude_text(stdout), "single-object answer")

    def test_single_object_response_key(self):
        self.assertEqual(
            generate.extract_claude_text(json.dumps({"response": "via response key"})),
            "via response key",
        )

    def test_non_json_returns_none(self):
        # Plain text that isn't JSON => None (caller decides to use raw stdout).
        self.assertIsNone(generate.extract_claude_text("just some plain text, not json"))

    def test_empty_returns_none(self):
        self.assertIsNone(generate.extract_claude_text(""))
        self.assertIsNone(generate.extract_claude_text("   "))

    def test_array_without_text_returns_none(self):
        stdout = json.dumps([{"type": "system", "subtype": "init"},
                             {"type": "result", "subtype": "error"}])
        self.assertIsNone(generate.extract_claude_text(stdout))

    def test_parse_claude_stdout_envelope_ok(self):
        env = generate.parse_claude_stdout(
            json.dumps([{"type": "result", "result": "yo"}]))
        self.assertEqual(env, {"text": "yo", "ok": True, "error": None})

    def test_parse_claude_stdout_envelope_fail(self):
        env = generate.parse_claude_stdout("not json")
        self.assertFalse(env["ok"])
        self.assertEqual(env["text"], "")
        self.assertIsInstance(env["error"], str)


# ============================================================================
# 1b. Hard-kill timeout — a hung child must return ~AT the bound, not long after
# ============================================================================

class TestHardKillTimeout(unittest.TestCase):
    def test_run_hardkill_returns_at_bound_for_hung_child(self):
        # A child that sleeps far longer than the timeout.
        # _run_hardkill must SIGKILL the process group and return
        # at ~the bound.
        cmd = [sys.executable, "-c", "import time; time.sleep(60)"]
        t0 = time.time()
        with self.assertRaises(generate._HardTimeout):
            generate._run_hardkill(cmd, timeout=1.0, input_text="")
        elapsed = time.time() - t0
        # Generous ceiling (reap window is 10s) but FAR below the 60s sleep —
        # proves the kill actually fired rather than the call waiting out the child.
        self.assertLess(elapsed, 15.0,
                        "hard-kill timeout took %.1fs; should return ~at the 1s bound" % elapsed)

    def test_run_hardkill_normal_exit_returns_completedprocess(self):
        cmd = [sys.executable, "-c", "print('hi', end='')"]
        cp = generate._run_hardkill(cmd, timeout=10.0, input_text="")
        self.assertEqual(cp.returncode, 0)
        self.assertEqual(cp.stdout, "hi")

    def test_generate_claude_timeout_returns_ok_false(self):
        # End-to-end through _generate_claude: point the `claude` lookup at a fake
        # hung executable and assert generate() returns ok=False quickly (not a
        # raise, not a 60s hang). Uses the public generate() entry.
        hung = _make_hung_fake_cli()
        try:
            orig_which = generate.shutil.which
            generate.shutil.which = lambda name: hung if name == "claude" else orig_which(name)
            t0 = time.time()
            res = run_generate("sys", "Describe loss.", model="headless-claude-code", timeout=1)
            elapsed = time.time() - t0
        finally:
            generate.shutil.which = orig_which
            os.remove(hung)
        self.assertFalse(res["ok"])
        self.assertIn("timeout", (res["error"] or "").lower())
        self.assertLess(elapsed, 15.0, "generate() hung %.1fs past a 1s timeout" % elapsed)


def _make_hung_fake_cli() -> str:
    """Write an executable shim that sleeps forever, return its path."""
    fd, path = tempfile.mkstemp(prefix="fake_hung_claude_", suffix=".py")
    os.write(fd, b"import time\nwhile True:\n    time.sleep(3600)\n")
    os.close(fd)
    # Wrap as a tiny shell launcher so shutil.which-style direct exec works.
    sh_fd, sh_path = tempfile.mkstemp(prefix="fake_hung_claude_", suffix=".sh")
    os.write(sh_fd, ("#!/bin/sh\nexec %s %s\n" % (sys.executable, path)).encode())
    os.close(sh_fd)
    os.chmod(sh_path, 0o755)
    return sh_path


# ============================================================================
# 1c. Host-level concurrency lock — acquire / release / stale reclaim
# ============================================================================

class TestHostLock(unittest.TestCase):
    def setUp(self):
        # Redirect the lock into an isolated temp dir so tests never touch a real
        # host lock and never collide with each other.
        self._tmp = tempfile.mkdtemp(prefix="psy_lock_test_")
        self._orig_gettempdir = generate.tempfile.gettempdir
        generate.tempfile.gettempdir = lambda: self._tmp

    def tearDown(self):
        generate.tempfile.gettempdir = self._orig_gettempdir
        shutil.rmtree(self._tmp, ignore_errors=True)

    def test_acquire_creates_and_release_removes(self):
        path = generate._lock_path()
        self.assertFalse(os.path.exists(path))
        with generate._host_cli_lock() as held:
            self.assertTrue(held)
            self.assertTrue(os.path.exists(path))
            pid, epoch = generate._read_lock(path)
            self.assertEqual(pid, os.getpid())
            self.assertIsNotNone(epoch)
        self.assertFalse(os.path.exists(path), "lock not released on context exit")

    def test_contended_lock_times_out_and_proceeds_unlocked(self):
        # Simulate another LIVE holder (this very PID is alive), fresh timestamp =>
        # not stale. A short acquire_timeout must expire and yield held=False
        # (degraded-but-proceeds), NOT hang or raise.
        path = generate._lock_path()
        with open(path, "w") as fh:
            fh.write("%d %f" % (os.getpid(), time.time()))
        t0 = time.time()
        with generate._host_cli_lock(acquire_timeout=0.3) as held:
            self.assertFalse(held)
        elapsed = time.time() - t0
        self.assertLess(elapsed, 5.0)
        # The pre-existing (not-ours-to-remove) lock must survive our give-up.
        self.assertTrue(os.path.exists(path))
        os.remove(path)

    def test_stale_lock_by_dead_pid_is_reclaimed(self):
        path = generate._lock_path()
        dead_pid = _find_dead_pid()
        with open(path, "w") as fh:
            fh.write("%d %f" % (dead_pid, time.time()))
        # Dead PID => stale => reclaimed immediately, we acquire.
        with generate._host_cli_lock(acquire_timeout=0.5) as held:
            self.assertTrue(held, "stale (dead-PID) lock should have been reclaimed")
            pid, _ = generate._read_lock(path)
            self.assertEqual(pid, os.getpid())

    def test_stale_lock_by_age_is_reclaimed(self):
        path = generate._lock_path()
        old = time.time() - (generate.LOCK_STALE_SECONDS + 60)
        # Live PID but ancient timestamp => stale by age (the 1863s-hang case).
        with open(path, "w") as fh:
            fh.write("%d %f" % (os.getpid(), old))
        self.assertTrue(generate._lock_is_stale(path))
        with generate._host_cli_lock(acquire_timeout=0.5) as held:
            self.assertTrue(held, "age-stale lock should have been reclaimed")


def _find_dead_pid() -> int:
    """Return a PID that is (almost certainly) not alive."""
    for candidate in range(999999, 990000, -1):
        if not generate._pid_alive(candidate):
            return candidate
    return 999999


# ============================================================================
# 1d. generation_driver — atomic checkpoint + resume-skips-completed-cells
# ============================================================================

class TestGenerationDriverCheckpointResume(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.mkdtemp(prefix="psy_gen_driver_")
        # Minimal battery: 2 probes.
        self.battery_path = os.path.join(self._tmp, "battery.json")
        with open(self.battery_path, "w") as fh:
            json.dump({
                "probes": [
                    {"id": "anchor-loss", "source": "anchor", "field": None,
                     "keyword": "loss", "prompt": "Describe loss.",
                     "content_distance": 0.4},
                    {"id": "x-foo", "source": "cross-domain", "field": "x",
                     "keyword": "foo", "prompt": "Describe foo.",
                     "content_distance": 0.8},
                ],
                "battery_summary": {"anchor": 1, "cross_domain": 1},
            }, fh)
        self.facet_path = os.path.join(self._tmp, "facet.md")
        with open(self.facet_path, "w") as fh:
            fh.write("FACET TEXT")
        self.distractor_path = os.path.join(self._tmp, "distractor.md")
        with open(self.distractor_path, "w") as fh:
            fh.write("DISTRACTOR TEXT")
        self.out_path = os.path.join(self._tmp, "generations.json")

        # Monkeypatch the model call: NO real claude. Count calls and record what
        # (system, user) each call saw, so we can assert resume skips.
        self.calls = []
        self._orig_generate = generation_driver.gen.generate

        def fake_generate(system, user, model="headless-claude-code", timeout=300):
            self.calls.append((system[:12], user, model))
            return {"output": "OUT for %s" % user, "model": model,
                    "capture_method": "headless-claude-code", "ok": True, "error": None}

        generation_driver.gen.generate = fake_generate
        self._fake_generate = fake_generate

    def tearDown(self):
        generation_driver.gen.generate = self._orig_generate
        shutil.rmtree(self._tmp, ignore_errors=True)

    def test_full_run_then_resume_skips_everything(self):
        meta = {"facet_name": "test", "tier": "lean"}
        s1 = generation_driver.run_battery(
            self.battery_path, self.facet_path, self.distractor_path,
            self.out_path, manifest_meta=dict(meta), model="m1", timeout=5)
        # 2 probes x 3 conditions = 6 cells, all completed, none skipped.
        self.assertEqual(s1["total"], 6)
        self.assertEqual(s1["completed"], 6)
        self.assertEqual(s1["skipped"], 0)
        self.assertEqual(len(self.calls), 6)
        self.assertTrue(os.path.exists(self.out_path))

        # File is valid JSON with all 6 cells stamped with model m1.
        with open(self.out_path) as fh:
            man = json.load(fh)
        self.assertEqual(len(man["probes"]), 2)
        for p in man["probes"]:
            self.assertEqual(set(p["generations"].keys()), {"facet", "baseline", "distractor"})
            for cond, cell in p["generations"].items():
                self.assertEqual(cell["model"], "m1")
                self.assertTrue(cell["output"])

        # RESUME on the SAME model => every cell is reused, ZERO new model calls.
        self.calls.clear()
        s2 = generation_driver.run_battery(
            self.battery_path, self.facet_path, self.distractor_path,
            self.out_path, manifest_meta=dict(meta), model="m1", timeout=5)
        self.assertEqual(s2["completed"], 0)
        self.assertEqual(s2["skipped"], 6)
        self.assertEqual(len(self.calls), 0, "resume re-called the model on completed cells")

    def test_resume_after_partial_loss(self):
        # Simulate a crash mid-run: pre-seed generations.json with only the first
        # probe's 3 cells (as the atomic checkpoint would have left it), then run.
        partial = {
            "probes": [
                {"id": "anchor-loss", "source": "anchor", "field": None,
                 "keyword": "loss", "prompt": "Describe loss.", "content_distance": 0.4,
                 "generations": {
                     c: {"system": "empty" if c == "baseline" else c,
                         "output": "prior", "ok": True, "model": "m1"}
                     for c in ("facet", "baseline", "distractor")}},
            ],
        }
        with open(self.out_path, "w") as fh:
            json.dump(partial, fh)

        s = generation_driver.run_battery(
            self.battery_path, self.facet_path, self.distractor_path,
            self.out_path, manifest_meta={"facet_name": "t"}, model="m1", timeout=5)
        # Probe 1 (3 cells) skipped; probe 2 (3 cells) freshly generated.
        self.assertEqual(s["skipped"], 3)
        self.assertEqual(s["completed"], 3)
        # Only probe-2 prompts were sent to the model.
        users = {u for (_s, u, _m) in self.calls}
        self.assertEqual(users, {"Describe foo."})

    def test_model_change_invalidates_prior_cells(self):
        # Cells captured on m1 must NOT be reused for an m2 run (battery on one
        # model is not comparable to another — the model is part of the cell key).
        generation_driver.run_battery(
            self.battery_path, self.facet_path, self.distractor_path,
            self.out_path, manifest_meta={"facet_name": "t"}, model="m1", timeout=5)
        self.calls.clear()
        s = generation_driver.run_battery(
            self.battery_path, self.facet_path, self.distractor_path,
            self.out_path, manifest_meta={"facet_name": "t"}, model="m2", timeout=5)
        self.assertEqual(s["skipped"], 0, "m1 cells were wrongly reused for an m2 run")
        self.assertEqual(s["completed"], 6)
        self.assertEqual(len(self.calls), 6)

    def test_atomic_write_leaves_no_tmp_and_valid_json(self):
        generation_driver.run_battery(
            self.battery_path, self.facet_path, self.distractor_path,
            self.out_path, manifest_meta={"facet_name": "t"}, model="m1", timeout=5)
        # No leftover temp files in the output dir.
        leftovers = [f for f in os.listdir(self._tmp) if ".tmp." in f]
        self.assertEqual(leftovers, [], "atomic write left temp files behind: %r" % leftovers)
        # Output parses.
        with open(self.out_path) as fh:
            json.load(fh)

    def test_failed_cell_recorded_and_not_treated_as_done(self):
        # A failing generate() must record ok=False and NOT count the cell as done
        # (so a later resume retries it).
        def failing(system, user, model="headless-claude-code", timeout=300):
            return {"output": "", "model": model, "capture_method": "headless-claude-code",
                    "ok": False, "error": "boom"}
        generation_driver.gen.generate = failing
        s = generation_driver.run_battery(
            self.battery_path, self.facet_path, self.distractor_path,
            self.out_path, manifest_meta={"facet_name": "t"}, model="m1", timeout=5)
        self.assertEqual(s["failed"], 6)
        self.assertEqual(s["completed"], 0)
        with open(self.out_path) as fh:
            man = json.load(fh)
        # The failed cells exist but are not "done" — a resume would retry them.
        cell = man["probes"][0]["generations"]["facet"]
        self.assertFalse(cell["ok"])
        self.assertFalse(generation_driver._cell_done(cell))


# ============================================================================
# 2. GUARDED real-generation smoke test (only with `claude` on PATH)
# ============================================================================

PIRATE_SYSTEM = "You are a pirate. Speak only as a pirate."
PIRATE_USER = "Describe the sea."


def smoke_main() -> int:
    if shutil.which("claude") is None:
        print("SKIP: claude CLI not found")
        return 0

    print("== psychomanteum eval/generate smoke test ==")
    print("model:  headless-claude-code (default)")
    print("system: %r" % PIRATE_SYSTEM)
    print("user:   %r" % PIRATE_USER)
    print("(invoking a real generation; this may take a few seconds...)\n")

    result = run_generate(PIRATE_SYSTEM, PIRATE_USER, model="headless-claude-code", timeout=180)

    print("---- captured output (verbatim) ----")
    print(result.get("output") or "(empty)")
    print("---- end output ----\n")

    view = dict(result)
    out = view.get("output") or ""
    if len(out) > 400:
        view["output"] = out[:400] + ("... [+%d chars]" % (len(out) - 400))
    print("---- parsed result dict ----")
    print(json.dumps(view, indent=2, ensure_ascii=False))
    print("---- end dict ----")

    ok = bool(result.get("ok"))
    looks_piratey = any(
        token in out.lower()
        for token in ("ahoy", "matey", "arr", "ye ", " ye", "yer ", "scurvy", "aye", "'tis", "sailin", "landlubber")
    )
    print("\nok=%s   conditioning-appears-applied=%s" % (ok, looks_piratey))
    if ok and not looks_piratey:
        print("note: generation succeeded but no obvious pirate markers detected — "
              "inspect the verbatim output above to judge conditioning.")
    return 0 if ok else 1


if __name__ == "__main__":
    if "--smoke" in sys.argv:
        sys.exit(smoke_main())
    # Default: run the unit tests (always — no claude needed), THEN the guarded
    # smoke test as a bonus signal (SKIP if no claude).
    print("== unit tests (no claude required) ==")
    suite = unittest.TestLoader().loadTestsFromModule(sys.modules[__name__])
    result = unittest.TextTestRunner(verbosity=2).run(suite)
    print("\n== guarded real-generation smoke test ==")
    smoke_rc = smoke_main()
    sys.exit(0 if result.wasSuccessful() else 1)
