# Project agent instructions

## Claude Code ↔ Codex CLI — bug-review protocol

The **single authoritative, strict** protocol for how the two AI agents on this
repository discuss and agree on bug fixes. Both agents MUST read it before
starting or continuing any review, and follow it exactly.

- **Claude** — Claude Code (Anthropic). Runs the session, investigates bugs,
  proposes and (after agreement) implements fixes + tests.
- **Codex** — Codex CLI (OpenAI), invoked non-interactively via `codex exec`
  from Claude's shell, as the independent reviewer.

Both agents are **collaborators seeking one common, correct solution** — not
adversaries. Codex reviews skeptically (to find real problems), but the shared
goal is the best fix, and **both** must actively help find it.

---

## 1. The workflow (exactly these steps)

1. **Claude** analyzes the bug, works out a **rough proposed solution**, and
   writes both (bug + proposal) into the bug's `.md` file. **Claude does NOT
   change code yet.**
2. **Claude calls Codex**, telling it which `.md` file to read, that it's a bug,
   and to work by this protocol.
3. **Codex** independently analyzes Claude's findings, **reads the actual code**,
   and confirms for itself whether it is a real bug and whether the proposed
   solution is good. It writes **all** its findings into the **same** `.md` file.
4. **Codex calls Claude**, saying it has written its opinion into that `.md`.
5. **Claude** re-reads the `.md`; if it disagrees, it writes its own findings and
   the reasons its view is better/worse into the `.md`, and notifies Codex.
6. **Codex** re-reads, analyzes Claude's latest message, writes its findings into
   the `.md`, and calls Claude.
7. Steps 5–6 repeat for **up to ~3 iterations total**, until Claude and Codex
   reach a **common solution**.
8. **Only once they agree on a common solution** does Claude begin changing the
   actual **code** files (never the `.md` protocol log) and testing the fix.

**Nuance rule:** when the remaining difference is only a nuance (two roughly
equivalent solutions), **both agents must say so explicitly and accept either** —
do not deadlock or bikeshed over equivalent choices. Converge and pick one.

**The agents resolve things themselves.** For ordinary technical decisions —
including substantive ones and normal tradeoffs (algorithm choice, error handling,
a dependency version bump, refactors, unit contracts) — the two agents research
the pros/cons of **both their own and the other's** proposal and reach a common
solution on their own. Do NOT ask the maintainer for these.

**Escalate to the maintainer ONLY** for a decision that would **significantly
affect the whole project** — e.g. changing the architecture or product behavior,
adding/removing a major dependency, or a change with broad user-visible impact —
**or** a genuine substantive deadlock that survives ~3 iterations. Record it as
`UNRESOLVED` with the exact decision required. When in doubt between escalating
and deciding, **decide** and record the rationale.

## 2. One file per bug, append-only

- All discussion of a bug lives in **one Markdown file**:
  `docs/codex-review/NN-topic.md`, `NN` = the bug number in
  `docs/claude-code-investigation.md` (single numbering — no parallel schemes,
  numbering owned by that investigation doc).
- **Append-only:** never rewrite or delete an earlier message; add a new one below.

## 3. Message format

```
### MSG-<n> — <FROM> → <TO> — <UTC timestamp>
- Bug: <file>:<line> — <one-line description>   (the bug location AND the fix file)
- Fix under review: <file(s) that will change>
- Status: <one of section 4>
- Notify: @<other-agent> — read this file, review the newest message, reply here.

<body: analysis / evidence / findings / rebuttal / verdict>
```
`<n>` increments monotonically across the whole file regardless of sender.

## 4. Status vocabulary (single, canonical)

| Status | Meaning | Set by |
|--------|---------|--------|
| `NEEDS_REVIEW` | Claude proposed the bug+fix; Codex must review. | Claude |
| `CLARIFY` | Reviewer lacks material context; asks precise questions (no verdict yet). | Codex |
| `CHANGES_REQUIRED` | Reviewer found problems; itemized, with evidence + a concrete alternative. | Codex |
| `AGREED` | Both agents have converged on one common solution. | either |
| `UNRESOLVED` | After ~3 iterations a *substantive* disagreement remains for the maintainer. | either |

Use `AGREED` (never both `AGREE` and `AGREED`).

## 5. Hand-off / notification (each agent calls the other)

- **Claude → Codex:** Claude writes its message into the bug `.md`, then runs
  `codex exec` (see §6) with a prompt that names the file and says "review the
  newest message and reply in this file". Claude runs it in the background; the
  task-completion notification is Codex's "call me when done".
- **Codex → Claude:** Codex **appends its `### MSG-n` block directly into the same
  bug `.md`** (writing to the `.md` is REQUIRED — that is how it negotiates), then
  ends its run. Claude is notified and reads the file.

The bug `.md` is the single source of truth; verdicts only in transient shell
output do not count as a completed review.

## 6. Invocation + safety mechanism

- **Codex must be able to read the repo and write the review `.md`.** In this
  environment its sandbox helper (bubblewrap) fails on network-namespace setup
  (`bwrap: loopback: Failed RTM_NEWADDR`) under both `--sandbox read-only` and
  `--sandbox workspace-write`, which blocks Codex's file reads/writes. The mode
  that works is **`codex exec --dangerously-bypass-approvals-and-sandbox
  --skip-git-repo-check`** (no OS sandbox → real file read/write). The prompt
  tells Codex to modify **ONLY** the current bug's `.md` — nothing else.
- **Codex must NOT change code** (or any file other than the bug `.md`) during a
  review. Code changes happen only at step 8, by Claude, after `AGREED`.
- **Claude's guardrail — change attribution by time boundary (no git commits):**
  1. **Before** each Codex run, Claude snapshots the boundary:
     `SNAP=$(git stash create)` (whole-tree hash, no commit/branch/index change) +
     a manifest `git ls-files -co --exclude-standard | sort | xargs -r sha256sum`
     (catches new/untracked files `stash create` misses).
  2. **After** the run, `git diff --name-only "$SNAP"` + manifest diff must list
     **only** the bug `.md` (it *will* show as changed — that is the one expected
     change, since the snapshot covers the whole tree).
  3. Anything else the snapshot **isolates** — its purpose is control/clarity,
     **not blind reversion**. Codex's stray edit may be a good idea: Claude reads
     it, understands why, and either **adopts it deliberately** (if sound and the
     discussion is `AGREED`) or **reverts** it (`git checkout "$SNAP" -- <path>`
     keeps Claude's edits; `rm`/`git clean -fd` for a new file) and asks Codex to
     re-propose it as a `.md` patch. Codex's edits must never merge *silently*.
  - Claude freezes its own code edits while a review is in flight, so the post-run
    delta is unambiguously Codex's.
- Git commits/pushes/branch switches are the **maintainer's**; agents never commit
  or change branches.

## 7. Review quality (both agents)

- Adversarial-but-collaborative: Codex assumes every claim/diagnosis/unit
  assumption/severity/fix is unproven and tries to disprove it against the real
  code/tests/docs; it confirms what survives and cites the evidence. Claude does
  not defend reflexively — if Codex is right, adopt it; if wrong, rebut with
  evidence. The goal is the best common solution.
- **Pin units explicitly per field** — no `<1`/`>10` magnitude heuristics
  (yfinance: rate/margin/growth are fractions, `debtToEquity` is percent-of-ratio,
  `dividendYield` is already percent — bugs #1/#2/#14).
- **Quantify severity impact** before assigning the marker.
- Prefer **behavior-preserving** edits; correct only the broken edge.
- After agreement, every fix ships with a **focused test + a full regression pass**
  (`.venv/bin/python tests/test_*.py`), recorded in the `.md`.
- **Verify units/schemas against live data** (yfinance/etc.) when relevant —
  network is available here.

## 8. Definition of done

A bug is done when: the bug `.md` ends with an `AGREED` message (or `UNRESOLVED`
handed to the maintainer); the agreed code fix + tests are implemented and the
full regression passes; and `docs/claude-code-investigation.md` records the
outcome in its "Status ispravki" section.
