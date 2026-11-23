# Build brief: rulescope (working name)

Paste this into Claude Code in an empty repo, and put `gen_samples.py` in the repo root. Build in phases. Stop after each phase and show me the output before continuing.

## What this is

A local command line tool that reads Claude Code session logs, finds mistakes the agent repeats, drafts a scoped rule for each one, previews which past sessions that rule would have touched, and later checks whether the mistake rate dropped.

Context: this is a follow-up project for Mirrors (runmirrors.com), a startup that helps teams fix recurring AI agent mistakes with scoped rules instead of ever-growing prompts. Their loop is: find repeated mistakes, write a scoped rule, preview which past conversations it would hit, deliver it at the matching step, compare outcomes with and without it. This tool is a small honest version of that loop on real data. It is not a copy of their product, and the README must not claim to match their internals.

## Hard rules

- Everything runs locally. Never upload session logs anywhere. The only network call allowed is to an LLM API for naming clusters and drafting rule text, and the user must be able to turn that off (`--no-llm` falls back to simple template text).
- Redact by default before anything goes to an LLM or into a report: home directory paths, emails, anything that looks like an API key or token.
- Never commit real session logs. The repo ships with a small synthetic sample set in `samples/` for tests and the demo.
- No em dashes anywhere in docs or README. Plain, short sentences.
- Do not invent the transcript format. Phase 0 is to look at real files.

## Phase 0: inspect the data

Claude Code writes session logs as JSONL files, usually under `~/.claude/projects/<project-folder>/<session-id>.jsonl`. Check that this is true on this machine. Open several real files and write `FORMAT.md` describing what you actually see: line types, where user text, assistant text, tool calls and tool results live, how errors are marked, what timestamps exist. Count how many sessions are available. If there are fewer than 15, say so and tell me.

### Starting hints from a redacted structure sample of one real session (verify, do not trust)

- Each line is one JSON object with a `type`. Seen: `user`, `assistant`, `attachment`, `system`, `file-history-snapshot`, `queue-operation`, `custom-title`, `agent-name`, `mode`, `tools-used`. Skip the ones you don't need. `file-history-snapshot` lines are huge and useless here.
- Common fields on conversation lines: `uuid`, `parentUuid`, `timestamp`, `sessionId`, `cwd`, `gitBranch`, `isSidechain` (true for subagent work, treat it separately), `version`.
- Assistant lines: `message.content` is a list of blocks with `type` of `thinking`, `text` or `tool_use`. A `tool_use` block has `id`, `name` (for example `Edit`, `Bash`, `Read`) and `input`.
- Tool results come back as `type: user` lines whose `message.content` is a list containing a block with `type: tool_result`, a `tool_use_id` that matches the call, and `content` that is either a string or a list of text blocks. Some also carry a top-level `toolUseResult`.
- A real user message has `message.content` as a plain string. Lines with `isCompactSummary: true` are auto-generated summaries, not real user messages, so do not count them as corrections.
- `system` lines with `subtype: compact_boundary` mean the session was compacted. Long sessions may have been summarized.
- `attachment` lines with `attachment.type` of `hook_additional_context` show text a hook injected. This is useful: it means the logs record when an injected rule fired, so `measure` can count how often each rule was delivered.
- NOT yet confirmed: how a failed tool call is marked. The sample did not include one. Search real files for failed results (look for `is_error`, error text, nonzero exit codes in Bash output) and document the real marker in FORMAT.md before writing the detector.

## Test data (provided)

`gen_samples.py` is provided next to this brief. Copy it into the repo and run `python gen_samples.py samples/`. It writes 47 synthetic sessions in the same shape as the real logs, plus `ground_truth.json` with the exact planted answers:

- "edit without reading first": 11 of 47 sessions (9 in the first 25, 2 in the last 22)
- "tests run from the wrong folder": 8 of 47
- "user corrects the agent": 6 of 47
- A rule scoped to "before any Edit" fires in 30 sessions and 11 of them had the mistake (so the preview must show 30 hits and 11 true, 19 false)
- Rule activation after session index 24, so `measure` should show 9 of 25 before and 2 of 22 after

Write automated tests that assert these exact numbers. If the real failure marker differs from the generator's assumption (`is_error: true` on the tool_result block), fix `Session.tool_result()` in the generator, not the tests, so the samples stay realistic. Never commit real logs.

## Phase 1: the core loop

1. **Parse** every session into a simple internal model: session id, start time, ordered events (user message, assistant message, tool call, tool result).
2. **Detect mistake signals.** Start with cheap, deterministic signals and only use an LLM after:
   - a tool result marked as an error
   - the same tool call retried with small changes right after a failure
   - a user message that corrects the agent ("no", "that's wrong", "I said", "don't", "stop"), or an interruption
3. **Normalize each signal into a signature**, for example `Bash:npm test:ENOENT package.json` or `Edit:file not read first`. Group identical or near-identical signatures into clusters.
4. **Report** the top clusters as: "signature, seen in K of N sessions, example session ids". Counts are by session, not by event.
5. **Draft a rule** for each top cluster: plain rule text plus a scope. A scope is a matcher on the upcoming step, such as tool name plus a command pattern, or a keyword in the user request. The LLM drafts the text and a proposed scope. The scope must be machine checkable, not prose.
6. **Preview the rule.** Run the scope matcher over every stored session and report: steps and sessions where the rule would have fired, and how many of those actually had the mistake. Example: "would fire in 30 sessions, mistake present in 11 of them." Showing the false hits is the important part. A rule that fires 200 times to catch 11 mistakes is a bad rule, and the tool should say so.
7. **Deliver the rule at the matching step.** Generate a Claude Code hook (check the current Claude Code docs for the exact hook mechanism and whether a PreToolUse hook can add context for the next step) that injects the rule text only when the scope matches. Also generate a plain CLAUDE.md snippet as the fallback. Do not guess at hook syntax. Read the docs and tell me what you verified.
8. **Measure.** Record when a rule was activated. Later, compare mistake rate (sessions with the mistake / sessions) before and after activation. Show the counts and a confidence interval. Print a clear warning when the sample is small. Label this as an observed before and after comparison, not a controlled test, because old sessions cannot be replayed with the rule on.

Deliverables for phase 1: a CLI (`analyze`, `preview <rule-id>`, `emit <rule-id>`, `measure <rule-id>`), a static HTML report generated from the analysis, tests on the synthetic samples, and a README.

## Demo support (build at the end of phase 1)

I will record a 70 second demo video. Make it easy and reliable:

- A tiny `demo-repo/` with a task that reliably triggers the "edit without reading first" mistake, plus a scripted prompt I can paste, so the live before/after run behaves the same on every take.
- A `demo.sh` that runs the whole flow in order: `analyze`, show the too-broad first rule and its preview (many hits, few real mistakes), narrow the scope, preview again, `emit` the hook.
- Readable terminal output: short lines, the counts in plain words ("fires in 30 sessions, mistake in 11"), no noise.

## Phase 2: only after phase 1 works and I have approved it

- A generic input adapter for a simple JSON format (a list of messages, tool calls and tool results) so logs from other agent frameworks can be analyzed.
- A rule conflict check: given two or more rules, flag pairs whose scopes overlap and whose text contradicts. Use the LLM for the contradiction judgment and show its reasoning.
- A single shareable report file with no external dependencies.

## README must include

- A 60 second demo using the synthetic samples, with exact commands.
- The honest limits: before and after is observational; mistake detection is heuristic and will miss things; thresholds were tuned on a small set of sessions; the rule delivery hook was tested on one machine.
- One real result from my own sessions, written as numbers only, with no private content.

## Definition of done for phase 1

- `analyze` runs on my real sessions and on the samples without errors.
- The top cluster has a rule whose preview shows both hits and false hits.
- The emitted hook fires in a live Claude Code session on the matching step and not on others. Show me how you verified that.
- Tests pass. README demo commands work from a clean clone.

Ask me before making any decision that changes scope. Keep the code small and readable. Prefer Python.
