#!/usr/bin/env python3
"""Generate synthetic Claude Code style session logs with planted mistakes.

Usage: python gen_samples.py [out_dir]   (default: samples/)

Writes N session .jsonl files plus ground_truth.json with the exact planted counts,
so tests can assert exact answers.

The line shapes follow the structure seen in real Claude Code logs (user / assistant /
attachment / system / file-history-snapshot lines, tool_use blocks in assistant messages,
tool_result blocks in user messages). ASSUMPTION to verify in Phase 0: failed tool results
are marked with "is_error": true on the tool_result block. If real logs differ, change
Session.tool_result() below and nothing else.
"""
import json, os, random, sys, uuid
from datetime import datetime, timedelta

N = 47
SEED = 7
OUT = sys.argv[1] if len(sys.argv) > 1 else "samples"
START = datetime(2026, 9, 20, 9, 0, 0)

# Planted mistakes. Counts are exact. Index ranges split sessions into an early block
# (before the rule) and a late block (after the rule) so `measure` has something to show.
EARLY = range(0, 25)    # sessions 0..24
LATE = range(25, 47)    # sessions 25..46
rng = random.Random(SEED)

def pick(pool, k):
    return set(rng.sample(sorted(pool), k))

# A: Edit on a file that was never Read. 9 early + 2 late = 11 of 47. The rule recorded as
#    activated after session index 24, so the rate drops from 9/25 to 2/22.
A = pick(EARLY, 9) | pick(LATE, 2)
# B: tests run from the wrong folder. 8 sessions spread across both blocks.
B = pick(EARLY, 4) | pick(LATE, 4)
# C: user corrects the agent ("no, I said ..."). 6 sessions.
C = pick(range(N), 6)
# Sessions that use Edit at all (the scope "before an Edit" fires here). A subset of these
# is the mistake sessions A. Total 30, so a rule scoped to "any Edit" fires in 30 sessions
# but only 11 had the mistake: the false hits the tool must report.
EDIT_SESSIONS = set(A) | pick(set(range(N)) - A, 19)

def ts(base, step):
    return (base + timedelta(seconds=20 * step)).strftime("%Y-%m-%dT%H:%M:%S.000Z")

class Session:
    def __init__(self, idx):
        self.idx = idx
        self.sid = str(uuid.UUID(int=rng.getrandbits(128)))
        self.base = START + timedelta(days=idx * 1.3, minutes=rng.randint(0, 300))
        self.step = 0
        self.parent = None
        self.lines = []
        self.cwd = "/work/demo-app"

    def _common(self):
        return {"parentUuid": self.parent, "isSidechain": False, "userType": "external",
                "entrypoint": "cli", "cwd": self.cwd, "sessionId": self.sid,
                "version": "2.1.0", "gitBranch": "main"}

    def _add(self, obj):
        u = str(uuid.UUID(int=rng.getrandbits(128)))
        obj["uuid"] = u
        obj["timestamp"] = ts(self.base, self.step)
        self.step += 1
        self.parent = u
        self.lines.append(obj)
        return u

    def user_text(self, text):
        o = self._common()
        o.update({"type": "user", "message": {"role": "user", "content": text}})
        self._add(o)

    def assistant_text(self, text):
        o = self._common()
        o.update({"type": "assistant", "message": {"role": "assistant", "content": [{"type": "text", "text": text}], "stop_reason": "end_turn"}})
        self._add(o)

    def tool_use(self, name, inp):
        tid = "toolu_" + "".join(rng.choice("abcdef0123456789") for _ in range(24))
        o = self._common()
        o.update({"type": "assistant", "message": {"role": "assistant", "content": [{"type": "tool_use", "id": tid, "name": name, "input": inp}], "stop_reason": "tool_use"}})
        self._add(o)
        return tid

    def tool_result(self, tid, text, is_error=False):
        block = {"type": "tool_result", "tool_use_id": tid, "content": text}
        if is_error:
            block["is_error"] = True
        o = self._common()
        o.update({"type": "user", "message": {"role": "user", "content": [block]}})
        self._add(o)

    def noise_lines(self):
        # Line types a parser must skip without crashing.
        self.lines.append({"type": "file-history-snapshot", "messageId": "m", "snapshot": {"trackedFileBackups": {}}, "isSnapshotUpdate": False})
        self.lines.append({"type": "queue-operation", "operation": "enqueue", "sessionId": self.sid})

FILES = ["src/app.ts", "src/utils/format.ts", "src/api/client.ts", "src/components/List.tsx", "README.md"]

def build(idx):
    s = Session(idx)
    s.noise_lines()
    s.user_text(rng.choice(["Add input validation to the form", "Refactor the API client error handling", "Fix the list sorting bug", "Update the README setup steps", "Rename the format helper"]))
    s.assistant_text("I'll start by looking at the relevant files.")
    f = rng.choice(FILES)

    if idx in EDIT_SESSIONS:
        if idx in A:
            # MISTAKE A: edit without reading first, tool errors, then the agent reads and retries.
            t = s.tool_use("Edit", {"file_path": f, "old_string": "foo", "new_string": "bar", "replace_all": False})
            s.tool_result(t, "File has not been read yet. Read it first before writing to it.", is_error=True)
            t = s.tool_use("Read", {"file_path": f})
            s.tool_result(t, "1\tconst foo = 1;\n2\texport default foo;")
            t = s.tool_use("Edit", {"file_path": f, "old_string": "foo", "new_string": "bar", "replace_all": False})
            s.tool_result(t, "The file has been updated successfully.")
        else:
            t = s.tool_use("Read", {"file_path": f})
            s.tool_result(t, "1\tconst foo = 1;\n2\texport default foo;")
            t = s.tool_use("Edit", {"file_path": f, "old_string": "foo", "new_string": "bar", "replace_all": False})
            s.tool_result(t, "The file has been updated successfully.")
    else:
        t = s.tool_use("Read", {"file_path": f})
        s.tool_result(t, "1\tconst foo = 1;")
        t = s.tool_use("Grep", {"pattern": "TODO"})
        s.tool_result(t, "No matches found")  # not an error, just noise

    if idx in B:
        # MISTAKE B: tests from the wrong folder, error, cd, retry.
        s.cwd = "/work"
        t = s.tool_use("Bash", {"command": "npm test"})
        s.tool_result(t, "npm ERR! enoent Could not read package.json: Error: ENOENT: no such file or directory", is_error=True)
        t = s.tool_use("Bash", {"command": "cd demo-app && npm test"})
        s.tool_result(t, "Tests: 12 passed, 12 total")
        s.cwd = "/work/demo-app"
    else:
        t = s.tool_use("Bash", {"command": "npm test"})
        s.tool_result(t, "Tests: 12 passed, 12 total")

    if idx in C:
        # MISTAKE C: user corrects the agent.
        s.user_text("no, I said use the existing helper, don't create a new file")
        s.assistant_text("Understood, I'll reuse the existing helper instead.")

    # One-off unrelated error in some sessions (noise that should NOT form a big cluster).
    if rng.random() < 0.25:
        t = s.tool_use("Bash", {"command": "ls missing-dir-%d" % idx})
        s.tool_result(t, "ls: cannot access 'missing-dir-%d': No such file or directory" % idx, is_error=True)

    s.assistant_text("Done.")
    return s

def main():
    os.makedirs(OUT, exist_ok=True)
    sessions = [build(i) for i in range(N)]
    for s in sessions:
        with open(os.path.join(OUT, f"{s.sid}.jsonl"), "w") as fh:
            for line in s.lines:
                fh.write(json.dumps(line) + "\n")
    order = [s.sid for s in sessions]
    truth = {
        "total_sessions": N,
        "mistakes": {
            "edit_without_read": {"sessions": len(A), "early": len(A & set(EARLY)), "late": len(A & set(LATE))},
            "tests_wrong_folder": {"sessions": len(B)},
            "user_correction": {"sessions": len(C)},
        },
        "scope_before_edit": {"sessions_where_rule_fires": len(EDIT_SESSIONS), "sessions_with_mistake": len(A)},
        "rule_activation_after_session_index": 24,
        "early_block_sessions": len(EARLY), "late_block_sessions": len(LATE),
        "session_order_oldest_first": order,
    }
    with open(os.path.join(OUT, "ground_truth.json"), "w") as fh:
        json.dump(truth, fh, indent=2)
    print(json.dumps({k: v for k, v in truth.items() if k != "session_order_oldest_first"}, indent=2))

if __name__ == "__main__":
    main()
