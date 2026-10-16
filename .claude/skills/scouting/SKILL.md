---
name: scouting
description: Use when the user wants a new publisher (institutional research, asset owner, academic) proposed for a tr-learn theme, to sit beside the publishers already archived, and then a docs/backlog link list for the one they pick. Triggers include "what source do you propose for <theme>", "another source like Vanguard/GMO", "backlog list for <publisher>".
---

# Scouting

## Overview

Two turns: a ranked **proposal table**, then, after the user picks, a **backlog link list** in `docs/backlog/`. Nothing is ingested (`add.py` is never run) and nothing is committed without being asked.

## Inputs (natural language)

| Input | Example | Missing |
|---|---|---|
| **Theme** | "how to build a portfolio", "decumulation" | Ask for it; do not start |
| **Sort factors**, in order | "low bias first, then relevance, then free" | Default: relevance to theme → bias (low first) → overlap (low first) |

Ties on the user's factors are broken by the default factors not already used. The reply is in the user's language, column headers included.

## Turn 1: proposal

1. Inventory before proposing: `ls sources/`, `docs/backlog/*.md` headers, grep `themes/` for the theme. Publishers already archived or in backlog are excluded, and named as excluded in one line.
2. Reply = these parts, in this order:
   - **Already covered**: one line per archived or backlogged publisher that touches the theme.
   - **Table**, exactly these columns: `# | Source | Type | <sort factor columns, in the user's order> | What it adds on <theme> | Publisher bias | Overlap | Free material`. Rows sorted by the sort factors. A sort factor that is already a fixed column moves to the front instead of appearing twice.
     - `Publisher bias` = level (low/medium/high) + what the publisher sells or defends ("royalties on RAFI indexes").
     - `Overlap` = level + the archived publisher it repeats.
     - `Free material` = yes / partial / no + what is paywalled.
     - At most 10 rows.
   - **Positioning**: an ASCII map of covered vs. missing.
   - **Recommendation**: one or two picks, each with a reason.
   - The line "links not verified yet", then the question: which one?
3. Popular sources (blogs, individuals) are not institutional: move them to the excluded line.

## Turn 2: backlog file

`docs/backlog/<publisher-slug>.md`, same shape as `docs/backlog/nbim.md`:

1. `# <site>: publications to ingest`
2. Collection paragraph: date, index pages crawled (linked), kept N of M, what was left out.
3. Ingest paragraph: `--publisher <slug>`, institutional (no `--popular`), where the original lives (PDF vs page, `--file` if JS/paywall), the publisher's bias.
4. Caveats as bullets: dead URLs (CLAUDE.md search order: other official URL > third-party copy > Wayback), dates to confirm from the document.
5. Table `| Published | Title | Type | Topic | URL | Status |`, newest first, Status `todo`. Add columns only for what varies per row (e.g. `Author affiliation`).
6. Count line.

Every URL is fetched; title and date come from the page or document itself. Unknown month/day stays out (`YYYY`, `YYYY-MM`). Unverifiable rows are marked unverified in the row, not dropped silently.

## Common mistakes

| Mistake | Fix |
|---|---|
| New column set every time | Use the column list above, verbatim |
| Bias as a bare level | Level + what is sold or defended |
| Ranking with no visible criterion | Sort factors are the first columns |
| Document URLs from memory in turn 1 | Index pages at most, marked unverified |
| Running `add.py` "to save time" | Backlog only; ingest is a later task |
