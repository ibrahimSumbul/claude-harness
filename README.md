# claude-harness

**English** · [Türkçe](README.tr.md)

**A session-handoff (context-flush) system for Claude Code.** It flushes the running session's
live state to high-fidelity persistent layers — triggered at ~260k tokens, safely ahead of the
~300k long-context degradation zone — then lets you open a clean session and **safely resume**
from exactly where you left off.

> *devir* (Turkish): the handover of a task to whoever comes next.

![devir — who triggers what, and what runs in the background](docs/diagrams/devir-trigger-flow.en.svg)

*At a glance: left — the `/devir-land` branch off Session A for a finished slice; middle — the
manual `/devir` → new session → `/devir-resume` path; right — the automatic L3 hook net.*

---

## Why

A single Claude Code session degrades in answer quality as it grows (~300k tokens). `devir`
catches this **at ~260k**, before entering the degradation zone. "Just open a new session" is
easy to say, but **context is lost**: where you left off, what was tried and failed, which
decisions were made and why. `devir` writes that state to three layers, so the next session
resumes **from where you left off** — not from scratch.

## Architecture — three layers

| Layer | What | Where it lives | Role |
|-------|------|----------------|------|
| **L1** | Global memory (primary) | `~/.claude/projects/<project>/memory/` | Machine-local continuity; auto-recalled into every session |
| **L2** | Git-tracked unique-ID note | `<repo>/.claude/docs/devir-notes/<id>.md` | Durable, cross-machine, team-shareable |
| **L3** | Hook safety net | `~/.claude/hooks/devir-*.py` | Mechanical capture/restore with no model cooperation required (advisory) |

L1 + L2 are written by the **model** (the skill); L3 runs **deterministically** (even if the
model ignores it).

## Components

**Skills** (`disable-model-invocation: true` — user-triggered only). The `SKILL.md` /
`DESIGN.md` files are authored in Turkish (the live, working setup); the summaries below are
in English.

- [`skills/devir/SKILL.md`](skills/devir/SKILL.md) — manual `/devir`: capture live git state →
  write L1+L2 → handoff block → commit closure. Triggered when a **half-done** task approaches
  ~260k. **Key guarantee — promotion gate:** a note is promoted to `open` only if the full
  self-validation checklist passes (goal filled, literal `▶ RESUME` block, non-empty
  tried/failed, decisions, no stray `[TODO]`); otherwise it stays `draft`.
- [`skills/devir-resume/SKILL.md`](skills/devir-resume/SKILL.md) — `/devir-resume`, the "hand-on"
  to `/devir`'s hand-off: in a fresh session, select the right note → staleness (git-drift)
  check (FRESH / SLIGHTLY STALE / STALE) → state what it understood → **get approval** → resume.
  Non-destructive: never deletes, only flips `open → consumed` (reversible). On ambiguity
  (≥2 candidate notes) it **asks** instead of silently choosing.
- [`skills/devir-land/SKILL.md`](skills/devir-land/SKILL.md) — `/devir-land`: land a finished,
  self-contained slice **in the same session**. The pipeline: DONE GATE (test + tsc, verbatim)
  → surgical pathspec staging (never `git add -A/-u`) → trailerless commit → `fetch` +
  rebase-before-push (**no force-push**, retry-once). On conflict, a READ-ONLY Opus supervisor
  subagent classifies it and either auto-applies (SIMPLE, own-files, additive) or escalates for
  approval. **Touches no note or memory** — pure integration; the finished-slice counterpart to
  `/devir`. Rationale: [`skills/devir/DESIGN.md`](skills/devir/DESIGN.md) §7.

**Hooks** (L3, all defensive: every error → exit 0, never breaks the session/compaction):

- [`hooks/devir-autotrigger.py`](hooks/devir-autotrigger.py) — `UserPromptSubmit`: at the
  ~260k token threshold, advises running `/devir` (advisory nudge + refire guard).
- [`hooks/devir-precompact.py`](hooks/devir-precompact.py) — `PreCompact`: just before
  compaction, a mechanical state dump + a git-tracked `draft` note (with redaction).
- [`hooks/devir-sessionstart.py`](hooks/devir-sessionstart.py) — `SessionStart`: on `compact`,
  RESUME auto-inject; on `startup`/`resume`, a status banner.
- [`hooks/devir_common.py`](hooks/devir_common.py) — shared helpers (git, note
  scanning/precedence, redaction, transcript token/file extraction).
- [`hooks/devir_memory.py`](hooks/devir_memory.py) — `flock` + atomic + idempotent upsert into
  the `MEMORY.md` index (parallel-session race protection).

**Tests:** [`hooks/devir_e2e_test.py`](hooks/devir_e2e_test.py) — end-to-end regression
(**43/43**) driving the real hooks with simulated harness payloads in a throwaway git repo.
[`tools/check_doc_sync.py`](tools/check_doc_sync.py) guards constant-, hook-wiring-, and
skill-name drift between code and docs (**14 checks**).

```bash
python3 hooks/devir_e2e_test.py
python3 tools/check_doc_sync.py
```

## Install

This repo is a **snapshot**; the source of truth is your working install at `~/.claude/`.

```bash
# from the repo root
cp -R skills/.   ~/.claude/skills/      # /devir, /devir-resume, /devir-land
cp    hooks/*.py ~/.claude/hooks/       # L3 hook net + shared libs
# then merge the "hooks" block of settings.example.json into ~/.claude/settings.json
python3 ~/.claude/hooks/devir_e2e_test.py   # verify: 43/43
```

Hook wiring lives in [`settings.example.json`](settings.example.json) (`UserPromptSubmit` /
`PreCompact` / `SessionStart`).

> Sync note: changes are made in `~/.claude/`, then copied into this repo and committed.
> (A symlink or one-way sync script could keep them in lockstep in the future.)

## Documentation

The deep docs are currently in Turkish (the operational skills are authored in Turkish, which
is the live, working setup):

- [`docs/workflow.md`](docs/workflow.md) *(Turkish)* — the full workflow: who triggers what and
  when, what runs in the background and why (with diagrams).
- [`docs/fable-comparison.md`](docs/fable-comparison.md) *(Turkish)* — an honest, evidence-based
  comparison of this orchestration approach with Anthropic Fable.
- [`docs/diagrams/`](docs/diagrams/) *(Turkish)* — standalone SVG diagrams + the
  **diagram-update discipline** ([`docs/diagrams/README.md`](docs/diagrams/README.md)).

Türkçe sürüm / Turkish version: **[README.tr.md](README.tr.md)**.
