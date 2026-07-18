# Codex CLI review log

Persistent record of Claude Code ⇄ Codex CLI reviews for bug fixes in this repo,
so any later Claude Code or Codex session can read the full conversation.

The authoritative workflow rules are in [`../../AGENTS.md`](../../AGENTS.md).
Every Claude Code and Codex CLI session working on bug review must read them
before continuing a discussion.

Convention: one file per reviewed fix, `NN-topic.md`. Each file contains
the append-only Claude↔Codex discussion. Numbering follows the bug numbers in
`../claude-code-investigation.md`.

## Required workflow

1. Claude investigates the bug, explains it with evidence, and proposes a fix.
2. Codex independently inspects the relevant code and tests. It starts from the
   assumption that all claims are unproven and tries to disprove them before
   confirming or refuting each one.
3. If context is insufficient, Codex writes precise clarification questions in
   the same file. Claude answers there; Codex then reassesses the full context.
4. Each Codex response is persisted in the bug file. Chat-only verdicts do not
   count as a completed review.
5. Stop after at most three Claude-message/Codex-response rounds. Finish with
   `AGREED`, or with `UNRESOLVED` plus the exact maintainer decision required.

Agreement must be evidence-based. The three-round limit is not permission to
approve an inadequately supported diagnosis or fix.
