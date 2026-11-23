# Session Log Format

Verified by reading real session files from `~/.claude/projects/`.
64 sessions found across 21 project folders. Files that are prefixed `agent-` are subagent sessions.

## File locations

```
~/.claude/projects/<project-slug>/<session-id>.jsonl
~/.claude/projects/<project-slug>/agent-<id>.jsonl  (subagent sessions)
```

Each file is JSONL: one JSON object per line.

## Line types seen

| type | description |
|------|-------------|
| `user` | A user turn (real message, tool result, or compact summary) |
| `assistant` | An assistant turn (text, tool calls, or thinking) |
| `attachment` | Injected context: environment snapshot, deferred tools, hook context, instructions |
| `system` | Hooks output, API errors, compaction boundaries |
| `file-history-snapshot` | Full file tree snapshot. Huge; skip. |
| `file-history-delta` | Incremental file tree delta. Skip. |
| `queue-operation` | Internal queue bookkeeping. Skip. |
| `custom-title` | Session title set by the assistant. |
| `agent-name` | Subagent name. |
| `mode` | Mode change (auto, plan, etc). |
| `tools-used` | Summary of tools used in the turn. |
| `last-prompt` | The last user prompt (used for resume). Skip. |
| `atis-latch` | Internal latching record. Skip. |
| `api-request`, `api-request-shape`, `api-request-blob` | Raw API request records. Skip. |
| `cost-state` | Token cost accounting. |
| `relocated` | Session relocation record. |
| `derived-from` | Session lineage. |
| `bridge-session` | Cloud bridge session link. |
| `pr-link` | Pull request link. |

## Common fields on most lines

```json
{
  "uuid": "...",
  "parentUuid": "... (uuid of previous line, null for first)",
  "timestamp": "2026-09-20T09:00:20.000Z",
  "sessionId": "...",
  "isSidechain": false,
  "cwd": "/work/demo-app",
  "gitBranch": "main",
  "version": "2.1.0",
  "userType": "external",
  "entrypoint": "cli",
  "type": "..."
}
```

`isSidechain: true` on lines from a subagent. Treat subagent sessions separately.

## `user` lines

Three variants, distinguished by `message.content`:

### 1. Real user message

`message.content` is a plain string.

```json
{
  "type": "user",
  "message": {"role": "user", "content": "Fix the list sorting bug"}
}
```

Skip lines where `isCompactSummary: true` - these are auto-generated context summaries, not real messages.

### 2. Tool result

`message.content` is a list whose first block has `type: "tool_result"`.

```json
{
  "type": "user",
  "toolUseResult": {"stdout": "...", "stderr": "...", "interrupted": false},
  "message": {
    "role": "user",
    "content": [{
      "type": "tool_result",
      "tool_use_id": "toolu_...",
      "content": "... output text ...",
      "is_error": true
    }]
  }
}
```

**Error detection:** `is_error: true` on the block is the canonical error flag. It is set for:
- `Read` on a file not yet read before editing ("File has not been read yet")
- File not found ("File does not exist")
- Permission denied by safety check
- User rejected the tool use
- Exit code 1 from Bash (41 out of 42 found in real data had `is_error: true`)
- One case of exit code 1 did NOT have `is_error` - treat "Exit code 1" in content as a secondary signal

The top-level `toolUseResult` field mirrors the result in a structured form for Bash (stdout, stderr, interrupted) and for Write/Edit (filePath, content, structuredPatch).

### 3. Image block

`message.content` is a list with blocks of `type: "image"`. Skip for analysis.

## `assistant` lines

```json
{
  "type": "assistant",
  "isSidechain": false,
  "message": {
    "role": "assistant",
    "stop_reason": "tool_use",
    "content": [...]
  }
}
```

Top-level fields also include: `thinkingDurationMs`, `requestedModel`, `effort`, `perTurnEffort`.

`message.content` is a list of blocks:

| block type | description |
|-----------|-------------|
| `text` | Prose response. Field: `text` (string). |
| `thinking` | Extended thinking. Field: `thinking` (string). |
| `tool_use` | A tool call. Fields: `id`, `name`, `input` (object). |

A single assistant turn can have multiple blocks (e.g. thinking + text + tool_use).

`stop_reason` is `"tool_use"` when the turn ends with a tool call, `"end_turn"` otherwise.

## `attachment` lines

```json
{"type": "attachment", "attachment": {"type": "...", ...}}
```

Attachment subtypes seen:

| subtype | description |
|---------|-------------|
| `environment` | System environment snapshot at session start. Field: `snapshot`. |
| `deferred_tools_delta` | Tool list changes. Fields: `addedNames`, `removedNames`. |
| `instructions` | CLAUDE.md content. Field: `files` (list). |
| `queued_command` | A queued prompt from an agent or hook. Fields: `prompt`, `origin`. |
| `hook_additional_context` | Text injected by a hook rule. Fields: `content`. NOT FOUND in real data yet - no hooks configured. When present, this is how to detect rule delivery for `measure`. |

## `system` lines

| subtype | description |
|---------|-------------|
| `stop_hook_summary` | Fired after each assistant turn. Fields include: `hookAdditionalContext` (hook-injected text if any), `hookInfos` (list of hooks that ran), `hookErrors`, `preventedContinuation`, `stopReason`. |
| `api_error` | LLM API error. Field: `error`. |
| `compact_boundary` | Context compaction happened here. Long sessions may be summarized. |
| `local_command` | A slash command was run. |

Hook delivery is recorded in `system` lines with `subtype: stop_hook_summary` via `hookAdditionalContext` and `hookInfos`. No hooks were configured in the real sessions examined.

## Tool names seen in real logs

`Edit`, `Read`, `Bash`, `Write`, `Grep`, `mcp__ccd_turn__update_plan`, `mcp__ccd_session__*`, `Artifact`, `Agent`, `WebSearch`, and many MCP tools.

## Subagent sessions (agent-*.jsonl)

These files have `agentId` on most lines and no `toolUseResult` on tool result blocks. The `isSidechain` field is `true`. They share `sessionId` with the parent session. Treat them separately unless the goal is to analyze subagent-specific behavior.

## What the synthetic samples do NOT include

- `thinking` blocks (real logs have them when extended thinking is on)
- `attachment` lines with `hook_additional_context` (no hooks configured yet)
- `isCompactSummary: true` lines
- `isSidechain: true` lines
- Image blocks in user messages

## Summary counts (real data)

- 64 session files across 21 project folders
- 15+ qualify as main (non-agent) sessions
- Error signals: `is_error: true` is the primary marker; "Exit code 1" in content is a secondary signal
