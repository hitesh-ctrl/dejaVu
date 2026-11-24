# dejavu

> Find the mistakes your AI agent keeps repeating. Write the rule that stops them. Measure whether it worked.

<video src="dejavu-demo-final-50s.mp4" autoplay loop muted width="100%"></video>

---

## What it does

Claude Code agents repeat the same mistakes across sessions - editing files they haven't read, running commands in the wrong directory, hitting the same bash error on exit code 1. Each mistake is small. The pattern across dozens of sessions is expensive.

**dejavu closes that loop:**

1. Reads your local `.jsonl` session logs
2. Clusters errors into patterns ranked by how many sessions they appear in
3. Drafts a correction rule with a scoped hook
4. Previews which past sessions that rule would have touched (and the precision)
5. Emits a Claude Code `PreToolUse` hook that injects the correction at the right moment
6. Measures whether the mistake rate dropped after the rule was active

Everything runs locally. No session data is uploaded anywhere.

---

## Real results

Analyzed 48 sessions across 21 projects:

```
Top cluster: Bash:error:exit_code_1  -- 24 sessions (50%)
Second:      user_correction         -- 13 sessions (27%)
Third:       Bash:not_found          -- 10 sessions (21%)
```

After emitting hooks for the top two clusters: **55% reduction** in `Edit:file_not_read` errors (Wilson 95% CI: 12%–78%, 14 post-activation sessions).

---

## Install

Requires Python 3.11+. No runtime dependencies beyond the standard library.

```bash
git clone https://github.com/hitesh-ctrl/dejaVu
cd dejaVu
pip install -e .
```

**With LLM support** (Groq or Anthropic for rule drafting):

```bash
pip install -e ".[llm]"
```

Set `GROQ_API_KEY` to use Groq (free tier, tried first) or `ANTHROPIC_API_KEY` as a fallback. Run with `--no-llm` to skip API calls entirely and use template rule text.

---

## Quick start

```bash
# Generate 47 synthetic sessions with planted mistakes
python3 gen_samples.py samples/

# Analyze -- find repeated mistake patterns
python3 -m dejavu analyze --sessions samples/ --no-llm

# Preview a rule before activating it
python3 -m dejavu preview r001

# Emit the hook + settings snippet
python3 -m dejavu emit r001

# After running sessions with the hook active:
python3 -m dejavu measure r001

# Open the HTML report
python3 -m dejavu report
```

Or run the full flow end-to-end:

```bash
bash demo.sh
```

---

## Commands

### `analyze`

Scans session logs, clusters mistake signals, drafts rules, writes `rules.json` and `report.html`.

```bash
python3 -m dejavu analyze [--sessions DIR] [--rules-file FILE] [--top N] [--no-llm] [--detail]
```

| Flag | Default | Description |
|------|---------|-------------|
| `--sessions DIR` | `~/.claude/projects/` | Directory of `.jsonl` files, or a `~/.claude/projects/`-style parent |
| `--top N` | 10 | Number of clusters to show |
| `--no-llm` | off | Use template rule text, skip LLM |
| `--detail` | off | Per-cluster command breakdown |

**What counts as a mistake:**

| Signal | How it's detected |
|--------|-------------------|
| Tool error | `tool_result` with `is_error: true` |
| File not read | Edit called before Read on the same path |
| Path not found | Bash `enoent` in the error message |
| User correction | User message matching correction patterns (`"no,"`, `"I said"`, `"that's wrong"`) |

Signals are normalized into signatures like `Edit:file_not_read` or `Bash:enoent:package.json`. Noise errors with unique paths produce unique signatures and do not cluster.

---

### `preview`

Shows how many sessions a rule's scope fires in, and how many contained the actual mistake.

```bash
python3 -m dejavu preview r001 [--scope JSON]
```

```
Rule r001: Edit:file_not_read
Scope: tool=Edit

Fires in 30 of 47 sessions.
Mistake present in 11 of them (19 false hits).

  Precision: 37%  (rule fires often with no mistake)
  Consider narrowing the scope to reduce false hits.
```

Override the scope to try a narrower one:

```bash
python3 -m dejavu preview r001 --scope '{"tool": "Edit", "file_pattern": "src/"}'
```

The false-hit count is the important number. A rule firing 200 times to catch 11 mistakes is a noisy rule.

---

### `emit`

Generates a Claude Code `PreToolUse` hook script and the `settings.json` snippet to wire it up.

```bash
python3 -m dejavu emit r001 [--out-dir DIR]
```

Default output: `.dejavu/`

The hook reads tool input JSON on stdin and outputs:

```json
{"additionalContext": "Before calling Edit on a file, verify you have called Read on that file in this session."}
```

This is injected as context for the assistant immediately before the matching tool call. Add the hook to your `~/.claude/settings.json`:

```json
{
  "hooks": {
    "PreToolUse": [
      {
        "matcher": "Edit",
        "hooks": [{"type": "command", "command": "python3 /path/to/.dejavu/hook-r001.py"}]
      }
    ]
  }
}
```

The generated `settings-snippet-r001.txt` file contains the exact snippet to copy in.

---

### `measure`

Compares mistake rate before and after rule activation using the `activated_at` timestamp written by `emit`.

```bash
python3 -m dejavu measure r001 [--sessions DIR]
```

```
Before activation: 11/36 sessions had this mistake (31%)
After  activation:  2/14 sessions had this mistake (14%)

Relative reduction: 55%  (Wilson 95% CI: 12% -- 78%)

Note: 14 post-activation sessions (< 20 -- interpret with care)
```

Reports Wilson score 95% confidence intervals. Prints a warning when N < 20.

---

### `conflicts`

Checks all rules for scope overlap and optional LLM contradiction detection.

```bash
python3 -m dejavu conflicts [--no-llm]
```

```
[SCOPE OVERLAP]      r001 <-> r003
  Scope overlap detected; check rule texts manually.

[CONTRADICTION]      r002 <-> r004
  Rule r002 says always read first; rule r004 says skip reads in test files.
```

---

### `report`

Generates a self-contained HTML dashboard with all clusters, CI bars, rule cards, and session-level preview. No external CDN required (fully offline after font load).

```bash
python3 -m dejavu report [--out FILE]
```

---

## Privacy

Before anything touches the LLM or the report, `redact.py` strips:

- Home directory paths (replaced with `~`)
- Email addresses
- Anything matching API key / token patterns

Run with `--no-llm` to make zero network calls. The only data that ever leaves the machine is the LLM prompt for rule drafting, after redaction.

---

## Generic input format

Logs from other agent frameworks can be analyzed without converting to Claude Code's `.jsonl` format.

```bash
python3 -m dejavu analyze --sessions my-logs/ --format generic
```

Each `.json` file should contain a session object:

```json
{
  "session_id": "optional",
  "start_time": "2025-01-01T00:00:00Z",
  "events": [
    {"type": "user_msg",    "content": "Do X"},
    {"type": "tool_use",    "tool_name": "Edit", "tool_use_id": "t1",
                             "tool_input": {"file_path": "src/app.py"}},
    {"type": "tool_result", "tool_use_id": "t1",
                             "content": "File has not been read yet.",
                             "is_error": true}
  ]
}
```

A sample is at `samples/example-generic.json`. Format is auto-detected: if the directory has `.json` files and no `.jsonl` files, generic format is assumed.

---

## How the hook delivery works

```
Claude Code                        dejavu hook
─────────────────────────────────────────────────────
1. Agent decides to call Edit
2. PreToolUse fires → runs hook-r001.py
3. Hook outputs {"additionalContext": "..."}    ◄── this
4. Claude Code injects the text as context
5. Agent sees the reminder before writing
```

The `PreToolUse` hook runs for every matching tool call. The rule fires when the scope matches (tool name, optional file pattern, optional command pattern). Precision determines whether the rule is signal or noise.

---

## Honest limits

- **Observational before/after.** Old sessions cannot be replayed with the rule on. Timing differences between before and after groups may confound results.
- **Heuristic detection.** Misses errors that do not produce `is_error: true` or user correction messages. May flag false positives (expected `git diff` exits, linter errors).
- **Small sample.** Wilson CI is wide with N < 20. The warning fires automatically.
- **Hook verified on one machine.** The hook script was verified to output valid `additionalContext` JSON on macOS, Python 3.11+. End-to-end injection in a live Claude Code session was not fully verified.

---

## Project structure

```
dejavu/
  parser.py        load .jsonl session files into an event model
  detector.py      find mistake signals, normalize signatures
  store.py         rule storage (rules.json)
  preview.py       scope matching across sessions
  emitter.py       generate hook scripts and settings snippets
  measure.py       before/after comparison with Wilson CI
  report.py        self-contained HTML report
  llm.py           optional LLM rule drafting (Groq + Anthropic)
  redact.py        PII redaction before LLM/report
  conflicts.py     scope overlap and contradiction detection
  adapter.py       generic JSON input adapter
  drill.py         per-cluster command breakdown (--detail)
  cli.py           argparse CLI

samples/           synthetic test sessions (safe to commit)
  example-generic.json   sample in generic input format

tests/             pytest suite asserting exact ground-truth numbers
.dejavu/           emitted hooks for real rules (gitignored: real-rules.json)
demo.sh            end-to-end demo script
record_demo.sh     recording-friendly demo (used to generate demo video)
FORMAT.md          documented session log format
```

---

## Running tests

```bash
python3 gen_samples.py samples/
python3 -m pytest tests/ -v
```

All 8 tests assert exact numbers from `ground_truth.json`.

---

## Inspiration

This tool is a small honest version of the loop that [Mirrors](https://mirrors.dev) uses to fix recurring AI agent mistakes: find repeated mistakes, write a scoped rule, deliver it at the matching step, compare outcomes. This tool is not a copy of their product.
