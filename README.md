# dejavu

A local CLI tool that reads Claude Code session logs, finds mistakes the agent
repeats, drafts a scoped rule for each one, previews which past sessions that
rule would have touched, and later checks whether the mistake rate dropped.

This project is a small honest version of the loop that
[Mirrors](https://runmirrors.com) uses to fix recurring AI agent mistakes with
scoped rules: find repeated mistakes, write a scoped rule, preview which past
conversations it would hit, deliver it at the matching step, compare outcomes
with and without it. This tool is not a copy of their product.

Everything runs locally. No session data is uploaded anywhere. The only network
call is an optional LLM API call for drafting rule text (disable with
`--no-llm`).

---

## 60-second demo (synthetic samples)

```bash
# 1. Generate 47 synthetic sessions with planted mistakes
python3 gen_samples.py samples/

# 2. Analyze
python3 -m dejavu analyze --sessions samples/ --no-llm

# 3. Preview the top rule
python3 -m dejavu preview r001

# 4. Narrow the scope and preview again
python3 -m dejavu preview r001 --scope '{"tool": "Edit", "file_pattern": "src/"}'

# 5. Emit the hook
python3 -m dejavu emit r001

# 6. Measure (needs sessions after activation -- not applicable here since
#    all samples predate the activation timestamp)
python3 -m dejavu measure r001
```

Expected output from step 2:

```
Top mistake clusters:

  r001  Edit:file_not_read        11 sessions
       fires in 30 sessions, mistake in 11 (19 false hits)

  r002  Bash:enoent:package.json   8 sessions
       fires in 47 sessions, mistake in 8 (39 false hits)

  r003  user_correction            6 sessions
```

Or run everything at once:

```bash
bash demo.sh
```

---

## Install

```bash
# Minimal (no LLM support)
pip install -e .

# With LLM support (Claude API for rule drafting)
pip install -e ".[llm]"
```

Requires Python 3.11+. No runtime dependencies beyond the standard library.
`anthropic` is optional (only needed for `--no-llm` to be omitted).

---

## Usage

### analyze

Loads sessions, clusters mistake signals, drafts rules, writes `rules.json`
and `report.html`.

```bash
python3 -m dejavu analyze [--sessions DIR] [--rules-file FILE] [--top N] [--no-llm]
```

- `--sessions DIR`: directory containing `.jsonl` session files, or a
  `~/.claude/projects/`-style directory with project subdirectories.
  Default: `~/.claude/projects/`.
- `--no-llm`: use template rule text, skip the LLM API call.

### preview

Shows how many sessions a rule's scope would fire in, and how many had the
actual mistake.

```bash
python3 -m dejavu preview r001 [--scope JSON]
```

- `--scope JSON`: override the saved scope to try a narrower one, e.g.
  `'{"tool": "Edit", "file_pattern": "src/"}'`.

The false-hit count is the important number. A rule firing 200 times to catch
11 mistakes is a bad rule.

### emit

Generates a Claude Code PreToolUse hook script, a `settings.json` snippet to
wire it up, and a `CLAUDE.md` fallback snippet.

```bash
python3 -m dejavu emit r001 [--out-dir DIR]
```

Default output dir: `.dejavu/`.

The hook script reads tool input JSON on stdin and outputs:
```json
{"additionalContext": "rule text here"}
```

This is the correct format for PreToolUse hooks in Claude Code. The
`additionalContext` field injects text as context for the assistant before the
tool call runs. Plain stdout injection only works for `UserPromptSubmit` and
`SessionStart` events, not `PreToolUse`.

To install the hook, follow the instructions in the generated
`settings-snippet-r001.txt` file.

### measure

Compares mistake rate before and after the rule was activated.

```bash
python3 -m dejavu measure r001 [--sessions DIR]
```

Prints counts, rates, and 95% confidence intervals (Wilson score). Prints a
warning when the sample is small.

---

## How mistake detection works

Three signals are detected:

1. **Tool error**: a `tool_result` with `is_error: true`. Covers file-not-found,
   permission denied, Edit on unread file, Bash nonzero exit.

2. **Retry after failure**: implicit. When the same session has an error
   followed by a corrected call, both are captured by the error signal.

3. **User correction**: a user message matching patterns like "no,", "I said",
   "that's wrong", etc.

Signals are normalized into signatures like `Edit:file_not_read` or
`Bash:enoent:package.json`. Noise errors with unique paths (like
`ls missing-dir-5`) produce unique signatures and do not cluster.

---

## Hook delivery and the measure command

When you run `emit`, the rule's `activated_at` timestamp is written to
`rules.json`. The `measure` command uses this timestamp to split sessions into
before/after groups and compare mistake rates.

If you configured the hook in `settings.json`, future sessions will record hook
activations in `system` lines with `subtype: stop_hook_summary` via the
`hookAdditionalContext` field. The `measure` command currently uses the
timestamp split rather than hook-activation records.

---

## Real results (from my own sessions)

Analyzed 48 sessions across 21 projects. No private content.

```
Top cluster: Bash:error:exit_code_1  -- 24 sessions (50%)
Second:      user_correction         -- 13 sessions (27%)
Third:       Bash:not_found          -- 10 sessions (21%)
```

---

## Honest limits

- Before/after is observational. Old sessions cannot be replayed with the rule
  on. Session timing may be unrelated to the rule.
- Mistake detection is heuristic. It misses errors that do not produce
  `is_error: true` or user correction messages. It may flag false positives
  (expected `git diff` exits, linter errors, etc.).
- Thresholds and patterns were tuned on a small synthetic set of 47 sessions.
- The rule delivery hook was verified to output valid `additionalContext` JSON
  on one machine (macOS, Python 3.11+). Live injection was verified by running
  the hook script with sample stdin and confirming the output. End-to-end
  injection in a live Claude Code session was not verified.
- Confidence intervals are Wilson score intervals. They are wide with small N.
  The small-sample warning fires at <20 sessions.

---

## Project structure

```
dejavu/        core library
  parser.py       load .jsonl session files into an event model
  detector.py     find mistake signals
  store.py        rule storage (rules.json)
  preview.py      scope matching across sessions
  emitter.py      generate hook scripts and settings snippets
  measure.py      before/after comparison
  report.py       static HTML report
  llm.py          optional LLM rule drafting
  redact.py       PII redaction before LLM/report
  cli.py          argparse CLI
samples/          synthetic test sessions (generated, not real logs)
tests/            automated tests asserting exact ground-truth numbers
demo-repo/        a small app for live demonstrations
demo.sh           end-to-end demo script
FORMAT.md         documented session log format (Phase 0)
```

---

## Running tests

```bash
python3 gen_samples.py samples/   # generate samples if not already done
python3 -m pytest tests/ -v
```

All 8 tests assert exact numbers from `ground_truth.json`.
