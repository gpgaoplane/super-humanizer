---
name: humanize
description: Detects AI-style writing in prose, markdown, slide decks, spreadsheets, Word documents, PDFs, source code and prompts, rewrites what a rule can rewrite, and reports what it left for a human with the reason. Use when text reads as AI-written, when a reviewer flags AI slop or canned phrasing, before submitting work drafted with a model, while composing in a repository that carries a .humanize.json marker, or when the user runs /humanize.
---

# Humanize

## Overview

Detect AI-style writing, rewrite what a rule can rewrite, and name what a rule cannot. The
standard is writing quality and never detector evasion. Never claim the output is undetectable.

The register is the whole mechanism. Plain words, one idea per sentence, specific claims, evidence
before conclusions. Removing slop is the humanizing, and no planted roughness substitutes for it.

## What runs

- The Write and Edit hook scans markdown, txt and prompt files in a repository that carries the
  marker. A Python write is scanned too: its comments, docstrings and prose strings run at the
  same tiers, and the message says the code handler scanned it. A JavaScript or TypeScript
  write routes through the same code handler. A write to a deck, a workbook, a Word document or
  a PDF gets one note saying the post-hoc run alone reads that file, and the hook reads nothing
  of it.
- The commit-message hook reads these message forms. A `git commit`
  message comes through one or more `-m` flags, the `--message` forms, or `-F` and `--file` on a
  file that exists, and `-F -` reads its heredoc. A `-m` message may be quoted, a PowerShell
  here-string or the `` `$(cat <<'EOF' ... EOF)` `` form a session writes. `gh pr create`,
  `gh pr edit` and `gh pr merge` are read the same ways. A `bash -c`, `sh -c`, `pwsh -Command` or
  `cmd /c` wrapper around a git or gh call gets a note that its message was not read, and so
  does any other message form.
- `/humanize on`, `/humanize off` and `/humanize protect` set the repository up.
- `/humanize <path>` and `/humanize report <path>` run on a markdown file, a txt file, a
  prompt file or a directory of them. The run extracts, scans, runs the structural pass and the
  density counts, plans the self-check, writes the candidates file, reconciles coverage, runs the
  substitution fixes, checks every rewrite for fidelity, writes the report and writes back what it
  accepted. Under `voice: "mine"` a confirmed profile entry's silences lower its own density count
  in this run under `general`, as they do in the hook, and the Density section names each silence
  that fired.
- `/humanize retro <draft> <final>` works on a markdown, txt or docx draft and final. The run
  aligns the two by bullet and writes a questions file, and a verdicts file beside the draft,
  written under the Retro section of `references/judgment-checklist.md`, is read by the next run,
  which appends one ledger row per divergence, harvests the voice profile from the whole ledger,
  writes it whole and moves the verdicts file aside. `/humanize retro state <kind> <entry>`
  records a stated preference as a confirmed entry at once.
- `/humanize learn <folder> [--recent NAME ...] [--until TEXT]` reads a folder of documents the
  writer wrote and writes one questions file for each. The folder is read in place and nothing
  is written beside it. A verdicts file beside each questions file, written under the Learn
  section of `references/judgment-checklist.md`, is read by the next run, which appends one
  ledger row per trait, harvests the voice profile from the whole ledger, writes it whole and
  moves the verdicts file aside. A trait is a voice trait or a slip, and a confirmed slip is a
  form a rewrite corrects.
- A Python file runs post-hoc too, alone or in a directory. The run scans, plans the self-check,
  writes the candidates file, reconciles coverage, writes the report, and applies the rewrites a
  rule or a verdict can make through each unit's own frame, so a docstring keeps its quotes and
  its indentation. It runs the project's formatter and tests once before any write back and once
  after, and when either fails afterwards it restores the original bytes and the report's
  Validation section says reverted. A JavaScript or TypeScript file routes through the same
  code handler, and the default include globs cover markdown, txt, Python and the script
  suffixes.
- A deck, a workbook, a Word document and a PDF run post-hoc too, alone or in a directory. The
  run extracts, scans, plans the self-check, writes the candidates file, reconciles coverage and
  writes the report, as for any other file. A judged run writes what it accepted beside the
  original by default. A deck lands at `<stem>.humanized.pptx`, a workbook at
  `<stem>.humanized.xlsx` and a document at `<stem>.humanized.docx`, each saved through the
  library that read it. The marker key `office_write` set to `in-place`, or the run flag
  `--office-write in-place` for one run, writes the deck, workbook or document itself and leaves
  no copy. The write replaces the changed parts of the package alone and keeps every other part
  byte for byte, through a temporary file beside the original and one rename, so a failure at any
  step leaves the original's bytes as they were. The key takes `copy`, the default, or `in-place`,
  and a value outside the two warns and takes `copy`. A PDF lands at `<stem>.humanized.md`, a
  markdown delivery of its pages' text, in both modes, and is never edited in place. A rewrite the writer cannot place is refused with its reason and stays in the report. No
  formatter or test suite runs on these formats. A PDF is read when it is named directly or when
  the marker adds `**/*.pdf`, and a directory run's summary line counts the PDFs it passed over.
  A file the library cannot read, or whose package is absent, is reported as unread with no
  candidates file and no brief.
- The second reader runs on a post-hoc run over a document longer than a page,
  and on any deck, workbook or Word document whatever its length, so a PDF gets one only when it
  runs longer than a page. The run writes it a brief, you
  dispatch a fresh subagent with the brief pasted into its prompt, you write the findings list it
  answers with into the brief, and the next run merges what it holds. See the Judging section
  below.
- A post-hoc run has no route for a commit message, so the hook above is the one place a commit
  message is read.

### The files a run leaves beside the artifact

| File | Who writes it | What it holds |
|---|---|---|
| `<path>.humanize-report.md` | the run | the whole report, the same text the run printed |
| `<path>.humanize-candidates.json` | the run | one row per finding that needs a verdict, each with its question, and under `voice: "mine"` with a profile entry in force a top-level `voice` block holding the profile's preferred entries, its licences and its avoided shapes for your rewrites, and a `slips` list when a confirmed slip entry is in force, the forms your rewrites correct |
| `<path>.humanize-verdicts.json` | you | the candidates file's own `artifact_digest`, then one row per candidate id, with `verdict` (pass, FIRE or n-a), `exception` when a pass rests on one, `rewrite` when you have one, `meaning` beside every rewrite, `twin` for a `strict` taxonomy flag, and `risk` on a FIRE you leave for the human |
| `<path>.humanize-second.json` | the run asks, and you write the second reader's answer | the document, the rulebook's name, the three files to read and an empty `findings` list, which you fill with the list the second reader answers with. Written only when the second reader resolved on |
| `<stem>.humanized<suffix>` | the run | the side-by-side copy of a deck, a workbook or a Word document, or `<stem>.humanized.md` for a PDF. Written only by a judged run that accepted a rewrite, and by no office run under `office_write: in-place`, which writes the file itself and leaves no copy |

No script calls a model. The run writes the candidates file, you write the verdicts file beside it,
and the next run reads it back. The marker excludes all five from the next run and from the inline
gate, with the retired forms of the verdicts file and the brief, so a copy is never the next run's
input.

A directory run leaves a report and a candidates file beside every deck, workbook and Word
document it reads, and under `second_reader: auto` a brief too. In the default copy mode a judged
run that accepted a rewrite leaves the copy as a fourth file beside the original, and an in-place
run leaves those three alone, since the rewrite went into the file itself. A PDF gets a brief only when it
runs longer than a page. A file the run could not read gets the report alone.

### The order to run them in

1. `/humanize report <path>`. This asks the questions and changes nothing on disk. It also writes
   `<path>.humanize-second.json` when the second reader resolved on, which the report's What ran
   line says. The learn section's step 1 holds the first-run offer, for a session under
   `voice: "mine"` with no profile.
2. When that brief exists and its `findings` list is empty, dispatch the second reader now, under the
   Judging section below, and write the list it answers with into the brief. It has to finish
   before step 4, because step 4 is what merges its rows.
3. Read `<path>.humanize-candidates.json` and answer every row in
   `<path>.humanize-verdicts.json`, under `references/judgment-checklist.md`. **Copy that
   candidates file's own `artifact_digest` value into the verdicts file, at the top level beside
   `verdicts`.** A verdicts file without it is refused.
4. `/humanize <path>`. This applies your verdicts, merges the second reader's rows, rewrites and
   writes back. On a deck, a workbook or a Word document it writes the copy beside the original
   in place of writing back, unless `office_write` reads `in-place` or the run passes
   `--office-write in-place`, when it writes the rewrites into the file itself, and on a PDF it
   writes the markdown delivery in both modes. A later judged run that writes a copy or a delivery
   builds it from the original again and replaces the earlier one whole, so it holds that run's
   rewrites alone.

The verdicts file therefore looks like this:

```json
{"artifact_digest": "<copied from the candidates file, unchanged>",
 "verdicts": {"f0003": {"verdict": "FIRE", "exception": null, "rewrite": "...", "twin": "",
                        "meaning": "kept", "risk": ""}}}
```

**Every rewrite carries a meaning line.** Write `kept` when the rewrite says what the original
said, with the same comparison, population, time window, cause, definitions, modality, negation
and stated doubt. Otherwise write one sentence naming what changed. The run applies a rewrite only
when its line reads `kept`, and prints your sentence where it lists the rewrite as reverted. The
token check still runs after it. `risk` is the Risk line the report prints under a FIRE you leave
for the human, naming what else the change it asks for could damage.

**Run `report` first, and never answer a candidates file from a run that wrote back.** A candidate is
addressed by an id stamped by position over one reading of the file under one rulebook. Anything
that moves between the asking and the answering hands the same id to a different finding, so your
answer about one rule would be recorded against another. The digest you copy is what proves the two
match, and it covers six things: the artifact's bytes, the shipped rulebook file's bytes, the
overlay file's bytes, the format, the marker's protect list, and under `voice: "mine"` the voice
profile file's bytes, so a profile changed between the asking and the answering refuses the file.
A run refuses a verdicts file whose digest does not match. A refused run rewrites nothing and has
already written a fresh candidates file, so its refusal says to answer that file and apply.

A run with no verdicts file beside the artifact completes anyway, and every candidate then prints
with no verdict. That is what step 1 above is. A run whose verdicts file leaves any candidate
unanswered rewrites nothing, keeps the file where it is, and names the candidates to answer, so
answer them in the same file and run again.

**A successful apply spends its verdicts file and moves it aside**, to
`<path>.humanize-verdicts.applied-<UTC stamp>.json`, and the report says so. The apply rewrote the
artifact, so those answers no longer match its questions, and leaving the file in place would make
every later run refuse it. To judge the rewritten artifact, go back to step 1. A refused run moves
nothing, so the file stays where it is for you to fix. In the default copy mode, on a deck, a workbook, a Word document or a
PDF the apply wrote the copy or the delivery and left the original as it was. The verdicts file
is still moved aside, the report says the original is unchanged, and the candidates file still
matches that original. On a deck, a workbook or a Word document written in place the artifact
changed, so the verdicts file and the brief move aside with the notes a markdown write back
carries, which say the artifact has changed and the answers no longer match its questions, and the
candidates file's recorded digest can never match again. A second `report` run writes a fresh
candidates file for the written file.

### The retro, run, answer, run again

`<draft>` is the plugin's output and `<final>` the version the user finished with. A retro learns
from the difference, and these four files sit beside the draft.

| File | Who writes it | What it holds |
|---|---|---|
| `<draft>.humanize-retro.json` | the run | one question per divergence, the digests to copy, and on a stale run a last key `superseded` |
| `<draft>.humanize-retro-verdicts.json` | you | under the Retro section of `references/judgment-checklist.md`, the questions file's `retro_digest` copied across, then one row per `rid` with `class`, `rule`, `entry`, `kind` and `note` |
| `<draft>.humanize-retro-verdicts.applied-<UTC stamp>.json` | the run | the spent verdicts file, moved aside |
| `<draft>.humanize-retro-report.md` | the run | the retro report |

The marker keeps all four out of the next run and the inline gate with `**/*.humanize-retro*.json`
and `**/*.humanize-retro-report.md`, which match the spent form too.

1. Run `/humanize retro <draft> <final>`. It writes the questions file and the report and appends
   nothing.
2. Answer the questions file in the verdicts file under the Retro section of
   `references/judgment-checklist.md`, with `retro_digest` copied across.
3. Run the same retro again. It appends the ledger, harvests the profile and moves the verdicts
   file aside. A refused file stays beside the draft with the ledger unchanged and its reason in
   Cannot see, and the run exits 1. A stale one names the half of the digest that moved and
   leaves a fresh questions file to answer.
4. `/humanize retro state <kind> <entry>` records a stated preference without a draft, the kind
   one of diction, mark, device, structure and avoid. A kind outside the five exits 2, and a
   ledger or profile the disk refuses exits 1.

### The learn command, run, answer, run again

`<folder>` holds documents the writer wrote themselves. The first three files below sit under
`~/.claude/super-humanizer/learn/<document digest>/`, one folder for each document, and the
last two sit one level up under `~/.claude/super-humanizer/learn/`.

| File | Who writes it | What it holds |
|---|---|---|
| `questions.json` | the run | one document's units, its candidates and slips, the entries already known, the five kind lines and the `learn_digest` to copy |
| `verdicts.json` | you | under the Learn section of `references/judgment-checklist.md`, the questions file's `learn_digest` copied across, then a `traits` list |
| `verdicts.applied-<UTC stamp>.json` | the run | the spent verdicts file, moved aside |
| `recent.json` | the run | the digests of the documents the user named recent, written when `--recent` is given |
| `learn-report.md` | the run | the learn report |

1. Under `voice: "mine"` with no profile, offer `/humanize learn` with a folder before any
   rewrite, and run nothing until the user names one.
2. With no `--recent`, ask the user which of the documents are recent before the run, and pass
   their answer as `--recent` names. A name is a file's name in the folder, matched exactly.
3. Run `/humanize learn <folder>`. It writes the questions files and the report and appends
   nothing.
4. Answer each questions file in a `verdicts.json` beside it, under the Learn section of
   `references/judgment-checklist.md`, with `learn_digest` copied across.
5. Run the same command again. It appends the ledger, harvests the profile and moves each spent
   file aside. A refused file stays where it is with the ledger unchanged and its reason in
   Cannot see, and the run exits 1. A stale one is refused with a line naming the half of the digest that moved, or saying it
   cannot be named when no questions file records the digest the file copied, and a fresh
   questions file is left to answer.

## The two modes

| Mode | When it runs | What happens |
|---|---|---|
| post-hoc | the user runs `/humanize <path>` | the full pipeline over an existing artifact, ending in a rewrite and a report. Text and code are rewritten in place. A deck, a workbook and a Word document go to a copy beside the original by default and into the file itself under `office_write: in-place`, and a PDF goes to a delivery beside the original in both modes |
| inline | a repository carries `.humanize.json` | the Write and Edit hook scans markdown, txt, prompt-file, Python, JavaScript and TypeScript writes as they happen. Compose in register from the first draft, because retrofitting a finished file is what a blocked write costs. A deck, a workbook, a Word document or a PDF write gets one note and is never read |

## Text pasted with no file

When the user pastes text into the conversation and names no file, judge it right there. This is
the one case where you judge without the scripts, since they have no file to read. Read the text
against `references/register-prose.md` and `references/judgment-checklist.md`, and name each
pattern it carries with the words that carry it, so the user can check every finding. Cite a rule
id only from the Appendix rows of `references/judgment-checklist.md` for the rulebook in force,
`general` when no marker sits above the session. Any rewrite you offer follows the Rewriting
section below, so it adds no fact, number or name the text does not give. Then offer the full
run: saved to a `.md` or `.txt` file, `/humanize report <path>` gives the whole report. Never
answer with the offer alone, and never say who or what wrote the text.

## Commands

Run each command's invocation with the Bash tool. It starts `sh`, which Git Bash supplies
on Windows and every macOS and Linux shell has.

| Command | What it does |
|---|---|
| `/humanize on` | write `.humanize.json` in the repository root through `scripts/marker.py`, invoked as `sh "${CLAUDE_PLUGIN_ROOT}/hooks/run-python.sh" "${CLAUDE_PLUGIN_ROOT}/scripts/marker.py" on` |
| `/humanize off` | remove it, invoked as `sh "${CLAUDE_PLUGIN_ROOT}/hooks/run-python.sh" "${CLAUDE_PLUGIN_ROOT}/scripts/marker.py" off` |
| `/humanize <path>` | run the full pipeline on that path, detect, rewrite and report, invoked as `sh "${CLAUDE_PLUGIN_ROOT}/hooks/run-python.sh" "${CLAUDE_PLUGIN_ROOT}/scripts/humanize.py" "<path>"`. `run <path>` is the same command. Add `--office-write in-place` or `--office-write copy` to override the marker's `office_write` key for that run |
| `/humanize report <path>` | the same run with the rewrite stage off, detect and report only, invoked as `sh "${CLAUDE_PLUGIN_ROOT}/hooks/run-python.sh" "${CLAUDE_PLUGIN_ROOT}/scripts/humanize.py" report "<path>"` |
| `/humanize retro <draft> <final> [--task NAME] [--until TEXT]` | align a draft with the user's final and write the questions file and the report, or apply the verdicts file beside the draft, harvest the profile and write `voice-profile.json`, invoked as `sh "${CLAUDE_PLUGIN_ROOT}/hooks/run-python.sh" "${CLAUDE_PLUGIN_ROOT}/scripts/humanize.py" retro "<draft>" "<final>"`. `--task` defaults to the sha256 of the draft's bytes. Its exit code is 1 on any refusal |
| `/humanize retro state <kind> <entry>` | append one stated ledger row and rewrite the profile, invoked as `sh "${CLAUDE_PLUGIN_ROOT}/hooks/run-python.sh" "${CLAUDE_PLUGIN_ROOT}/scripts/humanize.py" retro state <kind> "<entry>"` |
| `/humanize learn <folder> [--recent NAME ...] [--until TEXT]` | read a folder of the user's own documents in place and write a questions file for each, or apply the verdicts files beside them, harvest the profile and write `voice-profile.json`, invoked as `sh "${CLAUDE_PLUGIN_ROOT}/hooks/run-python.sh" "${CLAUDE_PLUGIN_ROOT}/scripts/humanize.py" learn "<folder>"`. `--recent` names the documents written recently by file name, and `--until` cuts each document at the first heading that holds the text. Its exit code is 1 on any refusal |
| `/humanize protect <pattern>` | add a pattern whose matched spans are recorded and weigh nothing, invoked as `sh "${CLAUDE_PLUGIN_ROOT}/hooks/run-python.sh" "${CLAUDE_PLUGIN_ROOT}/scripts/marker.py" protect "<pattern>"` |

Never write `.humanize.json` or a `.overlay.json` file through Write or Edit. The hook refuses
both. `scripts/marker.py` is the only writer of the marker. The user edits an overlay by hand.

## What the scripts own, and what you own

The scripts are deterministic and run without a model. Do not redo their work by eye.

| Stage | Owner |
|---|---|
| extract, scan, density, reconcile | `scripts/`, standard library only |
| judge | you, under `references/judgment-checklist.md` |
| retro: align, append the ledger, harvest the profile, audit promotions | `scripts/`, standard library only |
| retro: classify each divergence and name a voice entry | you, under the Retro section of `references/judgment-checklist.md` |
| rewrite | `scripts/fixes.py` for substitutions, you for everything harder |
| report | `scripts/`, in the shape `references/report-format.md` fixes |

## Judging

Read `references/judgment-checklist.md` before the first verdict.

The scan hands over two kinds of finding. A **hit** is an exact rule and needs no verdict. A
**candidate** needs one, and reconcile fails the run when a candidate has none. Answer every
candidate with pass, FIRE or n-a, one printed line each.

Three rules govern every verdict.

1. **The sentence is the unit.** A number, a named source or a named system protects the sentence
   it sits in. A shape that recurs across units flags at artifact level whatever protects each
   instance.
2. **Name the fault or leave the line alone.** A flag names the failing question in one line.
   Over-flagging is wrong exactly as under-flagging is.
3. **Under `strict`, no twin means no flag.** A taxonomy flag needs a mirror or same-family
   match from `references/twins.md`. Quote the twin in the finding.

Ask at most five questions of any one unit and list the ids of the ones skipped. Questions with no
generator run once per document. Under `voice: "mine"` with a profile entry in force, C070's
voice question and one line per confirmed avoid entry also run once per document, under
`strict` the avoid lines alone, and none of them takes a unit's place. On an office file the rulebook sets the candidates file's size,
and a 25-slide deck can give tens of rows under `general` and thousands under `strict`, since
every weighing unit is asked C154 and C053 there.

### The second reader

A post-hoc run on a document longer than a page, and on any deck, workbook or Word document,
writes `<path>.humanize-second.json`, the second reader's brief. The report's What ran line says whether the second reader resolved on and which
rule decided it.

1. The second reader is a **fresh subagent with no context fork**. Dispatch it with the brief's JSON
   pasted into its prompt, and name the three files the brief's own `read` list names by their
   plugin root paths: `${CLAUDE_PLUGIN_ROOT}/references/rulebooks/<rulebook>.json`, the rulebook it
   will be held to, then `${CLAUDE_PLUGIN_ROOT}/references/judgment-checklist.md` and
   `${CLAUDE_PLUGIN_ROOT}/references/twins.md`. Hand it nothing beyond those. A forked agent carries
   the first reader's reasoning, and the whole value of this pass is that it has none of it.
2. **It never receives the main judge's findings, its verdicts, its candidates file or its
   questions.** Two nets that see each other are one net. The
   brief the run writes holds the document, the rulebook's name, the `read` list and an empty
   `findings` list, and that is the whole of what the second reader is handed.
3. **It is never given the brief's path, and it never opens a file beside the artifact.**
   `<path>.humanize-report.md` and `<path>.humanize-candidates.json` sit next to the brief and hold
   the first reader's findings in full, so reading either one collapses the two nets as surely as
   forking would. Pasting the brief keeps its path out of the prompt. The rest is conduct and no
   script can enforce it, so say it in the dispatch.
4. It answers with its own `findings` list in its reply, one row per finding it raises, each with
   `rule`, `unit`, `span`, `verdict` (pass, FIRE or n-a), `twin` under `strict` and
   `exception` when a pass rests on one. The session that dispatched it writes that list into the
   brief's `findings` key and changes nothing else in the file. The next run merges those rows
   before reconcile and the report marks every one the main judge did not raise.
5. Paste a brief only while its `findings` list is empty. A brief whose list holds rows has been
   answered, and pasting it would hand a second reader another reader's verdicts, so dispatch no
   reader for it. The run leaves a filled brief as it is, and the next run merges it.

Every rule id in the answer has to come from the rulebook file the `read` list names, because a row
naming a rule that rulebook does not carry refuses the whole file, and so does a unit the document
does not hold, a span outside its unit or a verdict of `candidate`. The report says which row and
why. Do not take a rule id off a reference file: `references/judgment-checklist.md` names rules from
both rulebooks, and `C154` sits in its taxonomy table while `general` does not carry it.

A second reader row on a rule, unit and span the main judge also raised is kept beside the main
row, and the report says whether the two verdicts agree. The run never overwrites a brief that
carries an answer, so one answer is enough. A run that applies
those rows and rewrites the artifact spends the brief and moves it to
`<path>.humanize-second.applied-<UTC stamp>.json`, and the next run writes a fresh brief for the
rewritten artifact. A run that wrote a copy or a delivery spends the brief the same way, and the
report says the original is unchanged. A deck, a workbook or a Word document whose rewrites went
into the file itself spends the brief with the note that the artifact has changed. A run that refuses a brief moves nothing, and the report says what was wrong
with it.

## Rewriting

Read `references/register-prose.md` for prose, or `references/register-code.md` for comments,
docstrings, prose strings and commit messages.

| Rule | Why |
|---|---|
| rewrite the whole unit, never the changed sentence | a paste-ready fix is the whole unit of pasting |
| never invent a fact, a number, an agent or a mechanism | specificity comes from a source, a valid derivation or the author |
| put a figure or a detail the author has not given in a bracketed slot, such as "[minutes saved]", in a rewrite and in any example beside it | a sample figure reads as a fact once the reply is copied |
| offer a Change instruction wherever a rule cannot write the sentence | a substitution that breaks the frame is worse than an instruction |
| never emit an AI-style punctuation mark unless a learned voice profile shows the habit | whatever a gate masks, the draft drifts toward |
| under `voice: "mine"`, read the candidates file's `voice` block before every rewrite | it holds the writer's own habits, and `references/judgment-checklist.md` says what each of its lists asks of a rewrite |
| behavior must not change, in code | a cleanup that could change behavior is reported and never applied |

After a code rewrite, run the project's formatter and its existing tests. Revert and report
anything that fails either. A deck, a workbook, a Word document or a PDF run runs neither, and
its Validation section reads as the fixed line.

## What this skill never does

State these in the report. They are not inferences to leave to the reader.

1. Never claim authorship of the text, and never call the output undetectable or proof of human
   authorship.
2. Never score the artifact.
3. Never infer who or what wrote the input.
4. Never invent a fact to make a rewrite work.
5. Never run `retro state` for an entry you inferred. A stated preference is the user's own
   command, and a judge's inference goes in a voice verdict.

## Reference files

At the plugin root, reached through `${CLAUDE_PLUGIN_ROOT}`.

| File | Read it when |
|---|---|
| `references/judgment-checklist.md` | before judging. The questions, their scope and the cap, the Retro section's six classes and the Learn section's slip-or-voice line |
| `references/twins.md` | judging a taxonomy category under `strict` |
| `references/register-prose.md` | rewriting prose, or composing in inline mode |
| `references/register-code.md` | rewriting comments, docstrings, prose strings or commit messages |
| `references/report-format.md` | writing the report, or explaining what a section means |
| `references/format-handlers.md` | working on a deck, a workbook, a document, a PDF, a prompt, a Python file or a JavaScript or TypeScript file, and for what each handler cannot see |
| `references/rulebooks/*.json`, `references/lexicons.json` | data the scripts read. Do not load unless debugging a rule |

## Limits to state, never hide

The inline gate sees Write and Edit calls only, so a file written by a shell command is never
scanned. A hook that passes its timeout is cancelled with its output discarded, so a write that
lands with no message at all was not scanned. Every handler lists what it cannot see, and that
list belongs in the report whether or not anything was found.
