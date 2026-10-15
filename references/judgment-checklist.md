# The judgment checklist

Read this before the first verdict. It sets out the mechanism a model runs when it
judges a `/humanize report <path>` or `/humanize <path>` pass: the two files that
carry a verdict between a script and a model, the budget that caps how many
questions land on one unit, the three scopes a self-check question runs at, and the
three-pass shape `strict` keeps. `scripts/rulebook.py`, `scripts/selfcheck.py` and
`scripts/reconcile.py` run it.

## The three verdict rules

`skills/humanize/SKILL.md`'s own Judging section states three rules for every
verdict, and this file expands each one.

1. **The sentence is the unit.** A number, a named source or a named system
   protects the sentence it sits in. A shape that recurs across units flags at
   artifact level whatever protects each instance.
2. **Name the fault or leave the line alone.** A flag names the failing question in
   one line. Over-flagging is wrong exactly as under-flagging is.
3. **Under `strict`, no twin means no flag.** A taxonomy flag needs a mirror
   or same-family match, quoted in the finding. `references/twins.md` says where a
   reachable twin lives, and the rule is stated again below.

## The channel: two files beside the artifact, and no model in any script

The whole channel is two files `scripts/reconcile.py` reads and writes, and no
script calls a model.

1. `<path>.humanize-candidates.json`, written by the run. One row per Finding at
   verdict `candidate`, each carrying its `fid`, `rule`, `unit`, `span`, the unit's
   own `text`, and the `question`, `pass_line` and `fire_line` text the rulebook
   carries for that rule at that scope. A `strict` row also carries
   `category`. Rows the five-per-unit cap rotated out this run are not written as
   candidates at all: they move to the file's own top-level `unasked` list, by
   `fid`, `rule`, `unit` and a reason, and coverage below does not ask for a verdict
   on one of them.
2. `<path>.humanize-verdicts.json`, written by the model, under this file. One row
   per candidate `fid`. `scripts/reconcile.py`'s own `_TEXT_FIELDS` names the six
   fields anything downstream reads from a row: `verdict` (one of `pass`, `FIRE` or
   `n-a`), `exception` (an id from the rulebook's own `exceptions` map, only when a
   pass rests on one), `rewrite` (the model's whole-unit replacement,
   only when the model is proposing one), `twin` (the matching example from
   `references/twins.md`, quoted, only for a `strict` taxonomy flag), `meaning` (required beside every rewrite, see
   below) and `risk` (C003's Risk line, what else the change could damage, printed
   under a FIRE left for the human). Nothing else in a row is read. A verdicts file
   also carries `artifact_digest` at its top level, copied unchanged from the
   candidates file it answers, beside the `verdicts` object.

**The meaning line.** A row that carries a `rewrite` carries `meaning`
too. Write the literal `kept` when the rewrite keeps the original's comparison,
population, time window, causal status, definitions, modality, negation and stated
uncertainty, and keeps its terminology and tone in line with the rest of the
document. Otherwise write one sentence naming what changed. `scripts/reconcile.py::accept`
compares the line after trimming the space around it and ignoring case, and applies
the rewrite only when it reads `kept`. Any other line refuses the rewrite, the
original stands, and the report's Rewrites applied section prints the line as the
reason. A row with a rewrite and no line is refused the same way, with "no meaning
line" as the reason. "Kept." with a full stop is refused too, since only the bare
word accepts. The token half of fidelity still runs on every rewrite the line
accepts, as the safety net behind your own reading. A `meaning` on a row with no
rewrite is read by nothing, and so is a `risk` on any row other than a FIRE with
no rewrite.

Two consequences follow from that digest, both load-bearing. `scripts/humanize.py::_stale_reason`
refuses a verdicts file whose digest is missing or does not match the run reading it, and a refused
file has nothing in it judged or applied. And `/humanize report <path>` has to run before
`/humanize <path>` for this reason: a run that writes back changes the artifact and renumbers every
fid, so answering a candidates file that run produced hands your verdicts to fids that no longer
name what they asked about. A refused run writes nothing back, so the fresh candidates file it
leaves is safe to answer, and its refusal says so.

A row can only ever hold what the candidates file gave it a question about. The
`question`, `pass_line` and `fire_line` text in the candidates file is the
authoritative text for that run, read from the shipped rulebook by
`scripts/reconcile.py::_self_check_text`. This checklist's own appendix below is
only an index into that same rulebook, and never a second source of its own.

**The voice block, under `voice: "mine"`.** When a voice profile entry is in force, the
candidates file also carries a top-level `voice` object after `unasked`, which
`scripts/voice.py::rewrite_block` builds from the profile's confirmed entries. It holds
four lists when a confirmed slip entry is in force and three otherwise, since `slips` is
written only then, each list ordered with the entries backed by a recent document first.
`prefer` holds the `diction` and `structure` entries and, under `general`, a `mark` entry
whose silences list is empty, each an object with its `entry` and its `kind`. `licences`
holds the `device` entries as plain text, and it is always empty under `strict`, since
the strict rule overrides a licence whatever the habit. `avoid` holds the `avoid` entries as
plain text. `slips` holds the `slip` entries as plain text. A run with no entry in force
writes no `voice` key. Read the block before you write any `rewrite` for the file, and
follow what each list asks:

- A `prefer` entry of kind `diction` is a word the writer uses, and a rewrite prefers
  it over its synonym.
- A `prefer` entry of kind `structure` is a shape the writer uses, and a rewrite keeps it.
- A `licences` entry is a device the writer uses, so a rewrite may use it, and nothing
  requires it.
- An `avoid` entry is a shape the writer deletes, and it never appears in a rewrite.
- A `prefer` entry of kind `mark` is a glyph the writer uses at a rate of their own, and a
  rewrite keeps the habit.
- A `slips` entry is a form the writer makes by mistake, and a rewrite corrects it to the
  full form and never imitates it.

**The C070 question.** Under `mine`, once a profile entry is in force, the Self-check also asks
`C070-voice-recognized` once per document: "Would the writer recognize the edited draft as their
own voice?" Answer it by reading the edited draft against the lists above. Answer pass when the
preferred words and shapes show where they fit and no avoided shape appears, and FIRE when the
draft reads against them. With no answerable question in the profile the line reads pass by
default. `strict` carries no such question, since the strict
rule stands whatever the habit.

## Coverage: what a missing verdict does

`scripts/humanize.py::run` writes the candidates file on every run that reads the artifact. A run whose artifact cannot be read returns before that write, and `_empty_document`'s own docstring gives the reason, that a question about a file nothing read has no answer a model could give. When no verdicts
file sits beside the artifact yet, the run still completes, at exit code 0, and
every candidate prints with no verdict in the report (`report <path>` is exactly
this run). Once a verdicts file exists, `scripts/reconcile.py::coverage` checks
every candidate `fid` for a usable row, one whose own `verdict` reads `pass`,
`FIRE` or `n-a`. A candidate with no such row FIREs coverage, the whole run then
exits at code 1, and `scripts/humanize.py` names every missing `fid` in the
report's Cannot see section under "coverage failed". This is the first rule of the
detection spine: a coverage step proves every hit was
judged, and an unnamed silence is not proof.

A row the five-per-unit cap rotated out (see below) is not part of this proof: it
already carries verdict `n-a` by the time coverage runs, with no verdicts-file row
needed for it at all.

## The second reader: what it reads, and what it never reads

A post-hoc run on pptx, xlsx or docx, or on a document longer than a page, resolves the
second reader on and writes it a brief at `<path>.humanize-second.json`. The marker's
`second_reader` key and the `--second-reader` run flag override that both ways, and
inline mode never runs one. `scripts/second_reader.py` owns the whole stage and the
report's What ran line prints the resolved state with the rule that decided it.

**Reads.** The brief, which holds the run's own `artifact_digest`, the document's
format, the rulebook's name, a `read` list, the units with their id, kind, surface,
`weighs` flag and text, and an empty `findings` list. Plus the three files that `read`
list names, which the dispatch names by their plugin root paths:
`${CLAUDE_PLUGIN_ROOT}/references/rulebooks/<rulebook>.json`, this checklist at
`${CLAUDE_PLUGIN_ROOT}/references/judgment-checklist.md`, and
`${CLAUDE_PLUGIN_ROOT}/references/twins.md`. The rulebook is there because every rule id in the answer is held
against `book.rules` and one unknown id refuses the whole file. A shared static input is
no leak. Independence is about the first reader's conclusions, and both readers are
entitled to the rules they judge under.

**Never reads.** The main judge's Findings. Its verdicts. Its candidates file. Its
self-check plan, including the order that plan asked its questions in. Two guards hold
that in code. There is no parameter on `second_reader.write_brief` for any of them, and
`rulebook` and `digest`, the two free strings it does take, are checked by value, so a
caller cannot smuggle a findings list through one.

**One channel stays open, and conduct is its only guard.** The brief sits beside the
artifact, so `<path>.humanize-report.md` and `<path>.humanize-candidates.json` are one
read away for anything holding the brief's own path, and both carry the first reader's
findings in full. The brief no longer carries the artifact's own path, which drops the
most direct pointer and closes nothing by itself. The dispatch pastes the brief's JSON,
so the reader is never given the brief's path either, which drops the second pointer.
**Open no file beside the artifact.**
No script enforces this, and nothing here claims a leak has nowhere to land.

The reason is simple. Two nets that see each other
are one net. On one document the main sweep saw every slop sentence and excused
every one, which is why the second reader exists, and a second reader holding the first
reader's verdicts would repeat them back.

**A fresh subagent, never a context fork.** A forked agent carries the main judge's
reasoning whatever the brief withholds, so the independence would be a claim and not a
property. `skills/humanize/SKILL.md`'s own Judging section carries the invocation: the
brief's JSON pasted into the prompt, the three files named by their plugin root paths,
and nothing else. Paste a brief only while its `findings` list is empty. A brief whose
list holds rows has been answered, and pasting it would hand a second reader another
reader's verdicts, so no reader is dispatched for it, and the next run merges it.

**What the second reader writes.** Its own rows, as the `findings` list in its reply,
each holding `rule`, `unit`, `span`, `verdict`, `twin` and `exception`. The session
that dispatched it writes that list into the brief's `findings` key and changes nothing
else in the file, since the reader holds no path to write to. The
verdict is `pass`, `FIRE` or `n-a` and never `candidate`, because the second reader has
already judged and a candidate would demand a verdict from a judge that has run. The
tier and the category come from the rulebook and never from the file. A row naming a
rule the rulebook does not carry, a unit the document does not hold, a span outside its
unit, a verdict outside those three, or a field of the wrong type refuses the whole
file, and the report's Cannot see section names the row and the reason. So does a file
carrying no `findings` key at all, since every brief the run writes carries one and its
absence means something replaced the file. Answer under that key and no other.

**The merge.** `scripts/second_reader.py::merge` runs before reconcile. It appends
every row the second reader wrote after the main judge's rows and marks each one as
raised by the second reader. A row that matches a main judge row is
never dropped. A match is the same rule on the same unit, with the same span or with no
span on either row, since a finding scoped to a whole unit covers every span inside it.
Both rows stay. The main judge's row prints as usual, and the report's Findings section
prints the second reader's row as one line that names its verdict against the main
judge's, as an agreement such as
"- C058 (unit u0003), the second reader agrees: FIRE." or a disagreement such as
"- C058 (unit u0003), the second reader disagrees: it says FIRE where the main judge says pass."
Which verdict wins is left open until real runs show how often the two disagree. So the
pair adds no self-check verdict and no Left for the human row of its own, and the two
rows count as one finding. A row the main judge did not raise prints on its own line,
marked as raised by the second reader. Appending is what keeps every fid the main judge's
own candidates file already handed out, since `records.number` renumbers from `f0001` and
a prefix's order is unaffected by what follows it.

**The brief's own lifecycle.** A run that merges those rows and writes the artifact back
spends the brief and moves it to `<path>.humanize-second.applied-<UTC stamp>.json`, the
same way a spent verdicts file is moved aside, and the next run writes a fresh brief for
the rewritten artifact. A run that refuses a brief moves nothing and leaves it for a
human to read. An unanswered brief is replaced freely, since it is only this run's own
question.

## The five-per-unit cap and the rotation

At most five self-check questions run on any one unit. `scripts/selfcheck.py::CAP` is 5.

**The cap.** A unit can be eligible for more than five self-check entries at once
(a busy paragraph can trip C043, C038, C044, C052, C041, C037 and C047, for
example, `scripts/selfcheck.py::eligible` returning one entry per matching
`self_check` entry regardless of how many times its own generator matched a
Finding). Only five of the eligible entries are asked. The rest are listed by id
under the unit, in the report's Self-check section and its Cannot see section
alike, so a reader can tell a unit that was looked at
carefully from one nothing looked at.

**The rotation.** `scripts/selfcheck.py::_rotate` picks the five: the eligible
entries are read in the rulebook's own order, the unit's own index in the
document's list of weighing units sets where the five-entry window starts (`start
= index % n`, `n` the number of eligible entries), and the window wraps. So the
same five entries are never the ones a busy document keeps skipping, and the
choice is deterministic given the same document and the same rulebook, which is
what makes it testable.

**What happens to a rotated entry.** `scripts/reconcile.py::write_candidates` never
writes a rotated-out Finding as a candidate. It sets that Finding's own `verdict`
to `n-a` and its `exception` to `"rotated out of this unit's budget"`
(`reconcile.ROTATED_OUT_REASON`), then records it under the candidates file's
`unasked` list by `fid`, `rule` and `unit`. Coverage never asks a verdict for it.
The report still prints its id under its unit, in both the Self-check section and
the Cannot see section, so the unasked ones have a home exactly as the asked ones
do.

## The three scopes

Every self-check entry in a rulebook's `self_check` object sits in exactly one of
three lists.

- **`per_unit`.** The entry has a generator, a regex the unit's own text is checked
  against, or the name of another rule whose own Finding already sits on this
  unit, or a `phrases` list, a literal case-insensitive substring match with no
  `generator` key at all (`scripts/selfcheck.py::_entry_matches`). Six
  per-unit entries in each book carry `phrases`
  this way. A third generator shape names unit kinds, such as `unit kind: comment,
  docstring`, and matches every unit of those kinds. `C095-dropped-article` and
  `C139-senior-engineer` use it. `C130-bullet-body` uses a regex for a bullet line, and
  its rule's formats keep it to commit bodies. A generator can also be a list of
  these shapes, and the entry is then eligible where any one of them matches.
  `C014-source-remark` carries five literal phrases, such as
  `not provided`, each matched in any case.
  `C113-imperative-title` carries one with three alternatives. The first is every
  heading and every slide title. The second is a unit that is one sentence of at
  most eight words whose first word is one of fifteen imperative verbs, such as
  `Unlock`, `Boost` or `Streamline`, with the capital. The third is a unit holding a
  title-shaped line, a line of at most eight words that opens on a capital or a digit
  and ends on no sentence mark, which is how a plain-text deck dump reads a slide
  title. An alternative can carry its own scope, a mapping of `form`, one of these
  shapes, and `off`, the document formats and unit kinds it is skipped on, while the
  rule and its other alternatives stay on there. C113's third alternative is one, off
  on `pptx`, `xlsx` and `docx`, where a slide title and a bullet are units of their
  own, so a short bullet is never asked as a title. A PDF page is one unit of many
  lines, as a deck dump's slide is, so the line still reads its titles. Under
  `strict`, `C154-say-out-loud`, `C053-vague-declarative` and `C044-sounds-deep`
  carry a regex any unit holding a word matches, so all three are eligible on every
  weighing unit and take three of the five slots the cap gives each unit. Their
  `formats` turn all three off on a comment, a docstring and a prose string, so the
  slots of a code unit go to the code register's own questions. Under `general`,
  `C044-sounds-deep` keeps its own pattern hits. An entry runs only on a unit its
  generator or its phrase list matched, subject to the five-per-unit cap above.

  **A unit row the planner raises.** An entry made eligible by its own generator, on
  a unit where its rule raised no Finding, has no Finding of its own to carry a
  question. `scripts/reconcile.py::unit_findings` raises one: the rule id, the
  unit, a null `span` and verdict `candidate`. The candidates file writes it as a unit
  row with the unit's own `text`, the same shape a pattern candidate has, so you answer
  it by its `fid` like any other. `C014-source-remark`, `C113-imperative-title`,
  `C154-say-out-loud`, `C053-vague-declarative` under `strict`,
  `C095-dropped-article` and
  `C139-senior-engineer` reach you this way, and so does `C044-sounds-deep` under
  `strict` on a unit its own patterns missed, since an entry with a generator of
  its own is asked where the generator says. A phrase-list entry whose rule runs a
  pattern on the unit gets no unit row. `C130-bullet-body` does too once a commit
  body unit reaches a post-hoc run. No post-hoc route produces one today, so the commit
  hook's own candidate line is C130's live home. The cap and the
  rotation treat these rows as they treat a pattern row, so one the cap left out moves
  to the `unasked` list. An entry whose generator reads another rule's hits is left
  alone.

  **A deck's speaker notes.** On a pptx run, `scripts/structure.py::notes_caveat`
  reads each slide's notes against the slide's own body for C080's three qualifiers,
  "preliminary", "pilot" and "n =", each a whole word in any case. A notes unit
  holding one the body lacks gets a candidate with its span on the qualifier, and
  `C080-notes-caveat`, whose generator is C080's own hits, asks of it: "Does the
  qualifier in the speaker notes caveat a claim the slide body makes, so the slide
  presents that claim without its caveat?" A qualifier the slide shows too raises
  nothing, and so does a deck with no notes.
- **`per_document`.** The entry runs once on the whole document, with no cap. Every
  one of them is asked on every run, with two exceptions
  (`scripts/selfcheck.py::plan_questions`). An entry whose `needs` key reads `voice` is
  asked only when a voice profile is in force under `mine`, a profile holding no avoid entry
  included, which is `C070-voice-recognized`. An entry whose generator names unit
  kinds is asked only on a document holding a weighing unit of one of them, so
  `C125-restates-next-line` is asked on a Python file with a comment and never on
  a markdown file. Any other generator on a per-document entry is read by nothing.
  Under `mine` each confirmed avoid entry adds one more per-document line, id
  `mine-avoid-<n>`, asking "Does the text use "<phrase>", which the voice profile avoids?"
  with the pass line "the phrase is absent". It runs under both rulebooks, with no cap and no
  place in a unit's rotation.
- **Both scopes.** An entry is never asked where its own rule's `formats` field
  turns the rule off, for the document's format or for the unit's kind, the same
  gate the scanner applies to the rule's patterns. So `C031-light-verb` is not
  asked on a Python file, since `C031` is off for code prose.
- **`per_rewrite`.** The list is present and empty in both rulebooks. Its two questions, `C002-semantic-fidelity` and `C067-drift-inward`, compare a
  rewrite with its own original, and you answer both through the `meaning` line of
  every verdicts row that carries a rewrite, described under the channel above. No
  candidate row asks them. `C002-semantic-fidelity` asks "Does the rewrite change the
  comparison, population, time window, causal status, definitions, modality, negation
  or stated uncertainty from the original?" and `C067-drift-inward` asks "does the
  tool's own rewrite drift in terminology or tone from the rest of the document?". A
  rewrite that passes both reads `kept`. A rewrite that fails either gets one sentence
  naming what changed, and the run refuses it.

The count of entries in each book and scope heads its list in the Appendix below,
read from the two shipped rulebook files.

## The pass and FIRE line

Every exception's wording requires text evidence
and a printed pass line. That rule is scoped to an **exception**, and it never
promises that every FIRE prints a canned line back on its own.
`scripts/report.py::_self_check_line`
is what the report actually prints for one self-check entry, and it prints exactly
this, whatever the verdict:

```
<id> (<verdict>): "<question>".
```

and, only when the verdict is `pass` **and** the row named an `exception` id, one
more clause is appended:

```
, resting on exception <exception id>: <the rulebook's own pass_line for that id>
```

Two things follow from reading the code instead of assuming a shape.

- **A FIRE prints no separate canned line.** The rulebook's own `fire_line` field
  for a rule (for example C058's `"FIRE: the passive construction hides an actor
  the text can support naming"`) is guidance the candidates file hands the model
  while it is judging, so the model knows what firing this rule is supposed to
  mean. It is not echoed back into the report. If your reasoning for a FIRE needs
  to survive into the record, it belongs in the `risk` field of a FIRE you leave
  for the human, which Left for the human prints as that item's Risk line.
- **An `exception` id has to be a real key in the rulebook's own `exceptions`
  map**, or `book.exceptions.get(exception_id, {}).get("pass_line", "")` reads back
  empty and the printed clause names an exception with no text after it. This
  differs by book, so check the one the run is judging under. `general` ships
  thirteen: `quote-mask`, `code-mask`, `url-mask`, `markdown-table-pipe`,
  `markdown-table-mask`, `block-quote-mask`, `html-comment-mask`, `entity-mask`,
  `wiki-alias-mask`, `link-target-mask`, `C079`, `C090` and `C091`. `strict` ships
  the same twelve masking and
  document-title exceptions minus `C090`: its own wording reads "clears its flag
  under `general`", so no other rulebook carries it, and `strict.json`
  ships no such key. Never write an exception id you invented for the occasion.

## The three-pass shape under `strict`

Under `strict` the judgment pass runs in three passes. Pass A
covers five checks on marks and shapes, pass B covers the taxonomy with the nearest twin
quoted, and pass C covers the writing-style checklist, where the per-document rows run.

- **Pass A, five checks on marks and shapes.**
  - Punctuation marks, `C018`, at `block`. An exact rule that FIREs on sight and needs no
    judgment.
  - Contrast shapes, `C041` and `C042`, at self-check, with real patterns and per_unit
    candidates.
  - Passive voice, `C058`, at self-check. One pattern and the live entry
    `C058-passive-voice`. It is a judgment call every time and never a regex tier.
  - Imperative headings and slogans, both `C113`. `C113` carries no pattern. Its entry is
    eligible on every heading and slide title, on a unit that is one short imperative
    sentence, and on a markdown, txt, prompt or PDF unit holding a title-shaped line, so the
    planner raises a `C113` unit row there with the unit's own text. Answer it as an
    imperative heading on a heading or a title, and as a slogan on a slogan.

  Name the check from this list. A rule's `category` value names its family, and two of
  these checks share `C113`.
- **Pass B, the taxonomy with the nearest twin quoted.** Four categories, read from
  `strict.json`'s own `category` field.

  | Category | Rule | Reachable in this build |
  |---|---|---|
  | awkward phrasing | `C154-say-out-loud` | Yes. No pattern of its own, and a generator eligible on every weighing unit, so the planner raises a unit row on each one |
  | flowery language | `C046-three-shapes`, `C044-sounds-deep`, `C047-ing-rider`, `C054-metaphor-no-link` | Yes, each ships real patterns and a live per_unit entry, and `C044-sounds-deep` as a unit row on every weighing unit its patterns miss |
  | vague wording | `C065-restatable-portable` (per_document, asked on every run) and `C053` (below) | Yes. `C065` on every run, and `C053-vague-declarative` as a unit row on every weighing unit |
  | unnecessary words | `C028-standalone-look` | Yes, real patterns and a live per_unit entry |

  `C053` under `strict` ships a per_unit entry, `C053-vague-declarative`, asking
  `general`'s own question, `Does it name anything specific?`, on every weighing unit.
  `C053` carries no pattern, so the planner raises a `C053` unit row on each unit, and your
  verdict travels by that row's `fid` like any other candidate. Address the row by its
  `fid` and never by the entry id. A verdicts row keyed `C053-vague-declarative` matches no
  Finding, so `scripts/reconcile.py::apply_verdicts` discards it and Cannot see names it as
  an id this run raised no finding for.

  A taxonomy candidate passes or FIREs the way any other self-check entry does, and a FIRE
  also carries a `twin` in the verdicts row: the example from `references/twins.md` the
  flagged text mirrors, quoted. The rule, restated exactly: **no twin, no flag.** A
  taxonomy candidate with no twin you can quote does not fire, whatever the regex under it
  found.
- **Pass C, the Writing Style checklist.** Every `per_document` entry in the book
  runs here (title takeaway or label, title punctuation shape, terminology and
  tone drift), asked once per document with no cap and no rotation, the same list
  `plan.per_document` hands back in full for the run. C070 is held back when no profile is in
  force, and the avoid lines join the list under `mine`.

## Worked example: two candidate rows, start to finish

A fully reproducible worked run, `general` rulebook. Write `notes.md` with exactly
these two paragraphs:

```
The analyst finished the numbers on Monday, and the report was filed late anyway.

Every reviewer on the pilot team signed off before the release shipped.
```

Both lines are real triggers, checked directly against the shipped rulebook
instead of invented: the first is a passive construction whose actor the sentence
itself names, the analyst (C058), the second is a quantifier the sentence itself
backs with a named set (C037). `/humanize report notes.md` writes `notes.md.humanize-candidates.json`
carrying, among its 20 rows, these two real unit-scoped ones (the top-level
`artifact`, `artifact_digest`, `rulebook` and `generated` fields are left out
here, since the digest and the timestamp are run-specific):

```json
{
  "fid": "f0001",
  "rule": "C058",
  "unit": "u0001",
  "span": [59, 68],
  "text": "The analyst finished the numbers on Monday, and the report was filed late anyway.",
  "question": "Is the actor unknown or genuinely unimportant here, or does the text support naming one?",
  "pass_line": "the actor is unknown or genuinely doesn't matter, or the sentence simply describes a state",
  "fire_line": "FIRE: the passive construction hides an actor the text can support naming"
}
```

```json
{
  "fid": "f0002",
  "rule": "C037",
  "unit": "u0002",
  "span": [0, 5],
  "text": "Every reviewer on the pilot team signed off before the release shipped.",
  "question": "is the quantifier backed by a named, specific set the text supports, or is it a lazy extreme with nothing behind it?",
  "pass_line": "a quantifier backed by a named set, judged on text evidence, passes",
  "fire_line": "FIRE: \"every\", \"always\", \"never\" or another lazy extreme names no real set"
}
```

The model reads the candidates file, judges each row, and writes
`notes.md.humanize-verdicts.json`, copying the candidates file's own
`artifact_digest` across unchanged:

```json
{
  "artifact_digest": "<copied unchanged from the candidates file>",
  "verdicts": {
    "f0001": {"verdict": "FIRE", "exception": null, "rewrite": "", "twin": "",
              "meaning": "", "risk": "the active form puts the filing on the analyst, which a reader should confirm first"},
    "f0002": {"verdict": "pass", "exception": null, "rewrite": "", "twin": "",
              "meaning": "", "risk": ""}
  }
}
```

`f0001` carries no rewrite, so its `meaning` is empty, and its `risk` is the line
Left for the human prints under it. A row that did carry a rewrite would need
`meaning` as well, `kept` or the one sentence naming what changed.

`f0001` FIREs: the sentence names the analyst who finished the numbers, so the
text supports naming who filed the report, and the passive hides that actor,
which is the entry's own fire line. A sentence that named no actor at all, such
as "The report was filed late, and no one followed up on it afterward", would
pass on the entry's own pass line instead, because an unknown actor is a pass. `f0002` passes on the
self-check entry's own criterion, no exception needed: "every reviewer on the
pilot team" names a real, specific set the sentence itself states.

**The Self-check section never prints a fid.**
`scripts/humanize.py::_joined` copies `verdict` and `exception` onto the
rulebook's own self-check entry, and `_self_check_line` prints that entry's own
`id`, never the fid that named it in the two channel files. Applying the verdicts
above to a real run of this exact document prints, verbatim:

```
Unit u0001:
- C058-passive-voice (FIRE): "Is the actor unknown or genuinely unimportant here, or does the text support naming one?".
Unit u0002:
- C037-lazy-extreme (pass): "is the quantifier backed by a named, specific set the text supports, or is it a lazy extreme with nothing behind it?".
```

Neither `f0001` nor `f0002` appears anywhere in that output. A fid is what
Cannot see names on a coverage failure, and what Left for the human addresses
each item by. The Self-check section is addressed by self-check entry id and
unit alone, so do not go looking for a fid there.

**The exception clause, shown by its own shape and not by a claim about which
real candidate would use it.** When a verdicts row also names a real
`exceptions` map id, `_self_check_line` appends one more clause. Applying
`{"verdict": "pass", "exception": "quote-mask"}` to any entry, whatever rule it
names, prints:

```
..., resting on exception quote-mask: quoted material, recorded and weighing nothing.
```

`scripts/scan.py::_masked_text` already applies a pattern entry's own
`exceptions` list before that pattern runs, so a `per_unit` candidate that
reached you at all already survived every mask its own pattern names, `f0002`
above included. Citing a masking exception at verdict time makes sense for a
`per_document` question, which has no pattern and no scan-time mask of its own,
or for a shape a pattern's own exceptions list did not cover.

**These two rows are the unit-scoped half of a complete answer, and this worked
run answers only them on purpose, to keep the two printed lines above readable.**
The real candidates file for this exact document carries 20 rows: `f0001` and
`f0002` above, plus 18 more `per_document` rows the same way "A candidate that
names no unit" below describes. The run is voice off, and the Appendix lists two
`general` per-document entries a markdown run with voice off never asks, C125 and C070. A
verdicts file answering only `f0001` and
`f0002`, applied for real, does not clear coverage. `scripts/reconcile.py::coverage`
finds the 18 `per_document` fids still at verdict `candidate`, the run exits at
code 1, and Cannot see prints, verbatim from a real run:

```
- coverage failed. 18 candidates carry no usable verdict in the verdicts file: f0012, f0013, f0014, f0015, f0016, f0017, f0018, f0019, f0020, f0021, f0022, f0023, f0024, f0025, f0026, f0027, f0028, f0029
```

The Self-check section prints the two lines already shown above, then a
`Document:` heading carrying all 18 `per_document` self-check entry ids at
`(no verdict)` (`C031-light-verb`, `C033-you-can` and the sixteen more the
Appendix lists), the same self-check entry ids the appendix names and never the
`f0012`-to-`f0029` fids Cannot see prints above. A verdicts file has to answer
every candidate the run raises, and answering only the ones a worked example
shows for readability is exactly what coverage catches. Coverage never grades
an answer as good enough. It only checks that one exists.

**One caution this worked run does not show.** The entries whose generator names unit
kinds carry no pattern of their own on the units they ask about: `C095-dropped-article`
and `C139-senior-engineer` carry no pattern of their own on the units they ask about,
so the planner raises a unit row for each, and each reaches the candidates file with
the unit's own text. `C130-bullet-body`, whose generator is a bullet line, takes the
same path once a commit body unit reaches a post-hoc run. No post-hoc route produces
one today, so the commit hook's own candidate line is its live home.

## A candidate that names no unit: the per_document shape

Every `general` run over a markdown file with voice off raises 18 more candidates than the
two above, one per `per_document` self-check entry it asks. Under `mine` with a profile in force
it raises one more for C070 and one for each confirmed avoid entry. This shape looks
different enough from the two worked rows that it needs its own line. A real row,
read off a
markdown file through `humanize.run(path, rewrite=False)`:

```json
{
  "fid": "f0016",
  "rule": "C031-light-verb",
  "unit": "document",
  "span": null,
  "text": "",
  "question": "Does a light verb plus a nominalization here hide a plain verb?",
  "pass_line": "the nominalization names a thing the sentence needs",
  "fire_line": "FIRE: write the plain verb"
}
```

Three things mark it as document-scoped instead of unit-scoped. `unit` reads
`"document"`, never a unit id. `span` is `null`. `text` is empty, since no single
unit's text is what the question is about, and `rule` carries the self-check
entry's own id (`C031-light-verb`) instead of the bare rule id (`C031`) a
unit-scoped row carries. It still needs a verdict the same way any other
candidate does, and it still prints under a `Document:` heading in the Self-check
section instead of under a `Unit <id>:` one, using the same
`<id> (<verdict>): "<question>"` line shape.

## The retro: one file beside the draft, and the classes

`/humanize retro <draft> <final>` compares the plugin's draft with the human's final of it
and asks one question per divergence. `scripts/retro.py` runs it. The run writes the questions file, and you
write one file beside the draft in answer. No script calls a model.

1. `<draft>.humanize-retro.json`, written by the run. Each row of its `divergences` list
   carries the `rid`, the change the alignment found under its own `kind`, the `ratio`, the
   `before` and `after` texts of one bullet piece each, and the `hits`, the ids of the rules
   whose findings sit on the draft piece. Its `classes` object holds the six classes below,
   each with the same line.
2. `<draft>.humanize-retro-verdicts.json`, written by you under this section. It is one JSON
   object with two keys. `retro_digest` is copied unchanged from the questions file. `verdicts`
   maps the `rid` of every divergence to one row.

A row holds five fields, and the run reads nothing else in it. Each of `rule`, `entry`,
`kind` and `note` is a string or null.

- `class` names one of the six classes below. A row with no class counts as unanswered.
- `entry` names, on a voice verdict, the word, mark, phrase or shape the edit shows, written
  as the profile should hold it.
- `kind` names, on a voice verdict, one of the five kinds below. This field is the voice
  entry's kind and has nothing to do with the questions file's `kind`.
- `rule` names, on a slop verdict, the id of the rule the draft piece broke, as the rulebook
  in force holds it. The divergence's `hits` list the rules the run found on the piece, and a
  rule the rulebook does not hold refuses the whole file.
- `note` is one sentence on what the edit shows, and on an artifact conflict it holds the
  evidence. It enters the ledger row as its `note`, an empty string when you write none.

The six classes, each with the line the questions file carries:

- `calibration`. The final moved a score or a judgment of degree, and the wording followed the
  new level.
- `scope or standard`. The final judged against another standard or over another scope than the
  draft did.
- `evidence selection`. The final supports the point with other evidence, an example added or
  cut.
- `voice`. The final says what the draft said in the writer's own words, a habit the profile
  can learn.
- `slop`. The draft carried an AI tell a rule names and the final removed it, so the row names
  the rule.
- `artifact conflict`. The edit contradicts what the artifact under review shows, and an edit
  being made does not make it correct, so the row carries the evidence.

The five kinds a voice verdict names:

- `diction`, a word or phrase the writer prefers.
- `mark`, a punctuation mark the writer uses on purpose.
- `device`, a sentence device the writer uses on purpose, which the rewrite stage reads as a
  licence.
- `structure`, a shape of sentence or paragraph the writer prefers.
- `avoid`, a shape the writer deletes, which a voice verdict on a deleted divergence names. Once
  confirmed, the entry is the `mine-avoid-<n>` self-check line, which you answer pass when the
  phrase is absent.

An example of the file, with the digest left for you to copy:

```
{
 "retro_digest": "<the retro_digest of the questions file>",
 "verdicts": {
  "r0004": {"class": "voice", "rule": null, "entry": "next to", "kind": "diction",
            "note": "The writer says next to where the draft said beside."},
  "r0006": {"class": "slop", "rule": "C018", "entry": null, "kind": null,
            "note": "The final drops the em dash and splits the clause."}
 }
}
```

What the run does with the file, in this order:

1. The shape is read first. A file that holds no JSON object, a row that is no object, a
   class outside the six, a kind outside the five, a rule outside the rulebook, or a field of
   another type refuses the whole file with the `rid` and the field named.
2. The digest comes next, and it has two halves. The alignment half covers the two files,
   the until text and the alignment's own constants, which decide every `rid`. The rulebook
   half covers the rulebook file and its overlay. A file with no `retro_digest` is refused
   whole. A file whose digest differs from the run's is refused whole with a line naming the
   half that moved, and the run writes a fresh questions file beside the draft to answer.
3. Coverage runs over every divergence. A divergence with no row, a row with no class, and a
   voice row with no entry or no kind leave the file unanswered, so the run names each such
   `rid`, appends nothing and exits 1. A `rid` naming no divergence is named and passed over.
4. An answered file appends one ledger row per divergence, the report's Ledger section lists
   the ids, and the file moves to `<draft>.humanize-retro-verdicts.applied-<UTC stamp>.json`.
   The ledger refuses a row it already holds, so a second apply of the same file appends
   nothing. After the append the run harvests the voice profile from the whole ledger, writes
   it whole and audits promotions, which the report's Profile and Promotions sections show.

A refused file stays where it is and the ledger stays as it was, so you fix the same file
and run the retro again.

## The learn command: documents the writer wrote, and the traits they show

`/humanize learn <folder> [--recent NAME ...] [--until TEXT]` reads documents the writer wrote
themselves and asks what each one shows of their voice and their slips. `scripts/learn.py`
runs it. The run
writes one questions file for each document, and you write one file beside it in answer. No
script calls a model. Both files live under `~/.claude/super-humanizer/learn/<document digest>/`.
The folder named `learn` is `scripts/learn.py::FOLDER`, and the folder above it is the home the
profile and the ledger share.

1. `questions.json`, written by the run. Its keys are `task`, `document`, `format`,
   `content_digest`, `learn_digest`, `rulebook_digest`, `overlay_digest`, `recent`, `family`,
   `units`, `candidates`, `slips`, `known`, `kinds` and `instructions`. Each of `units` holds
   the `id` a trait cites, the `surface`, the `text`, the `sentences` count and the `layout`
   flag. Each of `candidates` holds an `id`, a `name`, a `value`, a `direction`, a `floor`, a
   `corpus` count and the `units` where the candidate shows. Each of `slips` holds an `id`, a
   `form`, a `count` and its `units`.
2. `verdicts.json`, written by you under this section. It is one JSON object with two keys.
   `learn_digest` is copied unchanged from the questions file. `traits` is a list.

A trait holds six fields, and the run reads nothing else in it.

- `entry` is a non-empty string, the word, mark, phrase, shape or form written as the profile
  should hold it.
- `kind` is one of the five kinds below. `avoid` is refused, since no sample teaches a shape
  the writer deleted.
- `class` is `voice` or `slip` and equals the kind's class, `slip` for a trait of kind `slip`
  and `voice` for every other.
- `units` is a non-empty list of unit ids. Each may carry a `/sNNN` suffix that names one
  sentence of that unit, from 1 up to its `sentences` count, in a three-digit suffix, `/s001`
  for the first sentence and never `/s1`. A unit with a count of 0 takes no
  suffix.
- `candidate` is null, an id that the questions file's `candidates` or `slips` hold, a rule id
  that the general rulebook holds, in the bare form the `candidates` rows carry, `C037`
  and never `C037-lazy-extremes`, or a word row's id.
- `note` is null or one sentence.

Null and the empty string both read as absent on `candidate` and `note`. A key the shape does
not name is ignored. Any other value refuses the whole file, naming the trait's index counted
from one and the field.

Decide first whether a trait is a slip or a voice trait. A slip is a form a dictionary or a
grammar would mark wrong and the writer would accept correcting, and a voice trait is a choice
a careful writer could make on purpose. A lowercase i opening a sentence, a missing article,
"tho" for "though" and a space before a full stop are slips, and so is chat shorthand such as "tbh". A casual word, a one-word
fragment after a full sentence, a colon before the point, a long sentence and an aside in
brackets are voice.

The five kinds a trait names, each with the line the questions file's `kinds` carries:

- `diction`. A word or a phrase the writer reaches for, which a rewrite keeps.
- `mark`. A punctuation mark the writer uses at a rate of their own, its glyph as the entry,
  which a rewrite keeps.
- `device`. A move the writer makes on purpose, such as a one-word fragment after a full
  sentence, which a rewrite may use.
- `structure`. A shape the writer gives a sentence, a paragraph or a list, which a rewrite
  keeps.
- `slip`. A form the writer makes by mistake, such as a lowercase i, which a rewrite corrects
  to the full form.

`avoid` belongs to the retro, and no sample teaches it. A `diction` entry is the bare word or
phrase, as short as it can be, and a `mark` entry is the glyph itself, since the held-out check
reads a diction entry by presence and a mark entry by its candidate's direction and floor.

The `candidates` and `slips` rows are advice the script counted. A count or mark row at its
floor, a rule row with its count, a recurring word row and a slip row are each a candidate.
Confirm or reject each one from the units it cites, and add what only reading finds. A count or
mark row carries its `direction` and `floor`, and its `corpus` count says how many of the
folder's tasks reach that floor. A trait that confirms a candidate names it in `candidate`. The
corpus counts, the rule counts, the recurring words and the `known` list are advice that can
change between the asking and the applying.

The `known` list holds the entry and the kind of every entry the ledger already holds. A trait
the `known` list already names is written with that exact entry text and kind, so one habit
never becomes two entries. The harvest joins rows by their kind and their entry text, case
aside, so write one habit with the same entry text in every file you answer, and a slip that
confirms a `slips` row takes the row's `form` as its entry. A first run answers many files
while `known` is empty in each, so the same text matters most there.

A rejected candidate gets no trait. A document that shows nothing gets an empty `traits` list,
and the run moves the file aside and appends nothing.

The recent list at `learn/recent.json` is the writer's own word on which documents are recent.
The questions file's `recent` says whether this document is on it. It is advice. It changes no entry's state. It orders the voice block's lists and names the
entries resting on older documents alone in the reports.

An example of the file, with the digest left for you to copy:

```
{
 "learn_digest": "<copied unchanged from the questions file>",
 "traits": [
  {"entry": "honestly", "kind": "diction", "class": "voice",
   "units": ["u0002/s002", "u0012/s001"], "candidate": "wcdb011f8fbe1",
   "note": "The writer opens an aside with it in both places."},
  {"entry": "'", "kind": "mark", "class": "voice",
   "units": ["u0005/s001", "u0012/s001"], "candidate": "c18", "note": null},
  {"entry": "lowercase i", "kind": "slip", "class": "slip",
   "units": ["u0002/s001", "u0005/s001"], "candidate": "p01", "note": null},
  {"entry": "a one-word fragment after a full sentence", "kind": "device", "class": "voice",
   "units": ["u0013/s003"], "candidate": null, "note": null}
 ]
}
```

What the run does with the file, in this order:

1. The shape is read first. A file that holds no JSON object, a trait that is no object, a kind
   outside the five, a class that disagrees with its kind, an entry with no text, a `units`
   list with no unit id and a field of another type refuse the whole file with the trait's index
   and the field named.
2. The digest comes second, and it has two halves. The content half covers the document's
   units, their sentence counts, its count and mark rows and its slips. The rulebook half covers
   the rulebook file and its overlay. A file with no `learn_digest` is refused whole. A file
   whose digest differs from the run's is refused whole as stale with a line naming the half
   that moved, or saying it cannot be named when no questions file records the digest the file
   copied, and the run writes a fresh questions file to answer.
3. The units and the candidate are resolved against the questions file. A unit the file does not
   hold, a suffix past the unit's `sentences` count and a `candidate` that no row, no rule of the
   general rulebook and no word row's shape names refuse the whole file. A word row's id is `w`
   and twelve hex characters, and it resolves by that shape even when the recurring list has
   moved.
4. The run appends one ledger row per trait, with an id derived from its content, so the same
   trait named twice refuses as held and a new trait on the same document appends.
5. The run harvests the profile whole from the whole ledger with the recent list read, and
   the spent file moves to `verdicts.applied-<UTC stamp>.json`.

A refused file stays where it is and the ledger stays as it was. Fix the same file and run the
learn command again.

## Appendix: every self-check id, by book and scope

Every id below is copied from `references/rulebooks/general.json` and
`references/rulebooks/strict.json`.

#### general

##### general / per_unit (44)

| id | rule | question |
|---|---|---|
| `C011-plus-n` | `C011` | `Does the "+N" suffix name a count the text supports, or is it a chatbot's own citation-count marker?` |
| `C016-date-and-availability` | `C016` | `Does the sentence carry a date or a source-availability claim the text supports, or is it the model's own guess?` |
| `C024-sense-qualified` | `C024` | `Does the entry carry the sense its qualifier names, for example "tapestry (figurative)" or "harness, not a test harness"?` |
| `C027-relation-holds` | `C027` | `Does the connector state a relation that holds between the adjacent propositions?` |
| `C028-standalone-look` | `C028` | `Does "Look," stand alone and line-initial before a routine claim, or does it sit inside a casual sentence?` |
| `C029-t03-recap` | `C029` | `Does the signpost help a reader navigate, or does it only announce what the next sentence says?` |
| `C034-what-to-do` | `C034` | `Does the sentence say what to do, or that something is generally done?` |
| `C040-term-of-art` | `C040` | `Is the noun a term of art here, as "surface" is in "API surface" and "harness" is in "test harness", or is it a metaphor?` |
| `C046-three-shapes` | `C046` | `Is this debate framing, a low-importance preamble, or belaboring how much something is conserved, rather than a claim the text supports?` |
| `C049-closer-shapes` | `C049` | `Does the last unit end on a concrete sentence the draft already carries, or on a dramatic fragment, a restatement or a stock send-off?` |
| `C036-two-intensifiers` | `C036` | `does the unit carry two or more counted intensifiers?` |
| `C037-lazy-extreme` | `C037` | `is the quantifier backed by a named, specific set the text supports, or is it a lazy extreme with nothing behind it?` |
| `C038-tutorial-voice` | `C038` | `does the text name the convention or cite where the fix is standard?` |
| `C041-three-poisons` | `C041` | `Three poisons: did anyone make the judgment the first half denies, are the two halves the same thing in two registers, does deleting the contrast lose nothing? Any yes fires. Question 1 on text evidence only, default FIRE` |
| `C042-fragment-triplet` | `C042` | `Three poisons: did anyone make the judgment the first half denies, are the two halves the same thing in two registers, does deleting the contrast lose nothing? Any yes fires.` |
| `C043-unstated-objection` | `C043` | `does the phrase argue against an unstated objection, and is the option one a reader would actually weigh?` |
| `C044-sounds-deep` | `C044` | `"If it sounds like a pull-quote, rewrite it" (5.C8). "Would you say it out loud?" is the awkward-phrasing test, and an aphorism passes it` |
| `C047-ing-rider` | `C047` | `is the -ing rider, the copula-avoidance form, or the stand-in for "is", "was" or "began" attached to a claim or a named source with nothing behind it?` |
| `C048-unattributed-authority` | `C048` | `are the outlets named and what they said stated?` |
| `C050-scaffolding-shape` | `C050` | `does the sentence use a named scaffolding shape, a setup sentence, a landing phrase, a participial reframe, a thesis-first opener, or one of the paired or chiasmus judgment shapes, to carry a real point, or only the shape?` |
| `C051-colon-reveal` | `C051` | `"If the point is clear, delete the aside." Is the span before the colon a complete clause? Does the colon replace a relation the sentence should state?` |
| `C052-false-agency` | `C052` | `does an abstract noun act as the subject of an agentive verb, with no real actor named?` |
| `C054-metaphor-no-link` | `C054` | `does the vehicle share a property with the tenor? has the reader seen this comparison a hundred times?` |
| `C055-self-question-answer` | `C055` | `does a question sentence get answered at once by a sentence that just repeats its key noun?` |
| `C056-invented-example` | `C056` | `does "imagine", "say a", "suppose", "for instance, a customer might" or "picture a" introduce an invented case where a real one would do?` |
| `C058-passive-voice` | `C058` | `Is the actor unknown or genuinely unimportant here, or does the text support naming one?` |
| `C060-forced-triad` | `C060` | `Each retained item has a clear role; no quota for list length.` |
| `C073-parallel-gerund-bullets` | `C073` | `do the five parallel bullets each carry a distinct point, or only the shared gerund-opening template?` |
| `C075-bold-label-list` | `C075` | `does every list item open on a bold label with nothing more than the label itself?` |
| `C076-heading-repeated` | `C076` | `does the first sentence under the heading only restate it, or treat the heading as a proper-noun subject, before any real content?` |
| `C077-table` | `C077` | `would prose read better? would one or two sentences carry this without loss?` |
| `C113-imperative-title` | `C113` | `does the title or heading read as an imperative command or a slogan?` |
| `C155-checkmark-shape` | `C155` | `does the list mark every item, or does the mark carry information?` |
| `C039-plain-word-substitution` | `C039` | `Is the flagged word protected industry terminology the text relies on, for example "margin expansion" for investors, or is it one the plain-word dictionary replaces?` |
| `C094-shown-property` | `C094` | `does the comment state a property the code visibly has?` |
| `C095-dropped-article` | `C095` | `Does the text drop the articles a sentence needs, as in "Parser rejects bad date", or lean on an abbreviation the reader must decode?` |
| `C096-names-the-change` | `C096` | `does the message name what changed, or does it assure the reader about process?` |
| `C123-label` | `C123` | `Does the label mark a warning the reader would otherwise miss, or does it only announce the sentence after it?` |
| `C126-example-block` | `C126` | `Does the example show a use the signature and the prose leave unclear, or is it a template block every function carries?` |
| `C127-file-header` | `C127` | `Does the header name an author and a date that version control already records, with a description the module docstring should carry?` |
| `C130-bullet-body` | `C130` | `Do the body's bullets add what the subject leaves out, or do they restate it?` |
| `C139-senior-engineer` | `C139` | `Does the abstraction fit the problem or the template? Does the comment say why or what? Is the defensive code at a boundary? Would a senior engineer on this codebase have written it this way?` |
| `C014-source-remark` | `C014` | `is the sentence addressed to the document's reader about the reader's decision, or to the requester about the writer's inputs?` |
| `C080-notes-caveat` | `C080` | `Does the qualifier in the speaker notes caveat a claim the slide body makes, so the slide presents that claim without its caveat?` |

##### general / per_document (20)

| id | rule | question |
|---|---|---|
| `C031-light-verb` | `C031` | `Does a light verb plus a nominalization here hide a plain verb?` |
| `C033-you-can` | `C033` | `Does the sentence work without the "you can" opener?` |
| `C015-requester-remark` | `C015` | `is this sentence addressed to the person who asked for the text?` |
| `C017-answer-shaped` | `C017` | `does the answer show an answer-shaped habit, such as an unrequested option list, defining known terms, blanket caveats, or refusal-style disagreement, rather than the requested content?` |
| `C045-mannered-prompt` | `C045` | `does metaphor or flourish stand in for a direct statement here?` |
| `C053-vague-declarative` | `C053` | `Does it name anything specific?` |
| `C061-wordy-indirect` | `C061` | `is the sentence wordy and indirect where a direct one would serve the same content?` |
| `C062-coined-label` | `C062` | `does a coined or unexplained jargon label appear where the industry uses a plain, standard term?` |
| `C063-next-action` | `C063` | `does the reader know their next action, and does each paragraph or slide perform a clear function? "can you swap paragraphs 2 and 4 without breaking it?"` |
| `C064-cross-unit-consistency` | `C064` | `is a number, a name or a unit used two ways in this document?` |
| `C065-restatable-portable` | `C065` | `What does it tell the reader to do or know? Could it sit unchanged in another project's docs?` |
| `C066-balanced-conclusion` | `C066` | `does the text weigh every side because the subject has sides, or by habit, and does it cover every angle because the reader needs each one?` |
| `C067-drift-outward` | `C067` | `does terminology or tone drift across the deck for the same thing?` |
| `C071-length-calibration` | `C071` | `does the written deliverable pad with filler sections, redundant summaries or boilerplate?` |
| `C074-neat-takeaway` | `C074` | `does every section end on a neat takeaway, or does the same callout follow every section?` |
| `C077-bullets-headings` | `C077` | `would prose read better? would one or two sentences carry this without loss?` |
| `C078-heading-category` | `C078` | `does this heading say what is under it, or only name a category?` |
| `C057-hedge-claim-pull` | `C057` | `does any sentence in this document carry a hedge whose claim pulls in the opposite direction?` |
| `C125-restates-next-line` | `C125` | `Does any comment say what the line after it already says, where a reader needs why?` |
| `C070-voice-recognized` | `C070` | `Would the writer recognize the edited draft as their own voice?` |

##### general / per_rewrite (0)

Empty. The meaning line answers both questions this list held. See
"The three scopes" above.

#### strict

##### strict / per_unit (44)

| id | rule | question |
|---|---|---|
| `C011-plus-n` | `C011` | `Does the "+N" suffix name a count the text supports, or is it a chatbot's own citation-count marker?` |
| `C016-date-and-availability` | `C016` | `Does the sentence carry a date or a source-availability claim the text supports, or is it the model's own guess?` |
| `C024-sense-qualified` | `C024` | `Does the entry carry the sense its qualifier names, for example "tapestry (figurative)" or "harness, not a test harness"?` |
| `C027-relation-holds` | `C027` | `Does the connector state a relation that holds between the adjacent propositions?` |
| `C029-t03-recap` | `C029` | `Does the signpost help a reader navigate, or does it only announce what the next sentence says?` |
| `C046-three-shapes` | `C046` | `Is this debate framing, a low-importance preamble, or belaboring how much something is conserved, rather than a claim the text supports?` |
| `C049-closer-shapes` | `C049` | `Does the last unit end on a concrete sentence the draft already carries, or on a dramatic fragment, a restatement or a stock send-off?` |
| `C036-two-intensifiers` | `C036` | `does the unit carry two or more counted intensifiers?` |
| `C037-lazy-extreme` | `C037` | `is the quantifier backed by a named, specific set the text supports, or is it a lazy extreme with nothing behind it?` |
| `C041-three-poisons` | `C041` | `Three poisons: did anyone make the judgment the first half denies, are the two halves the same thing in two registers, does deleting the contrast lose nothing? Any yes fires. Question 1 on text evidence only, default FIRE` |
| `C042-fragment-triplet` | `C042` | `Three poisons: did anyone make the judgment the first half denies, are the two halves the same thing in two registers, does deleting the contrast lose nothing? Any yes fires.` |
| `C043-unstated-objection` | `C043` | `does the phrase argue against an unstated objection, and is the option one a reader would actually weigh?` |
| `C044-sounds-deep` | `C044` | `"If it sounds like a pull-quote, rewrite it" (5.C8). "Would you say it out loud?" is the awkward-phrasing test, and an aphorism passes it` |
| `C047-ing-rider` | `C047` | `is the -ing rider, the copula-avoidance form, or the stand-in for "is", "was" or "began" attached to a claim or a named source with nothing behind it?` |
| `C048-unattributed-authority` | `C048` | `Does it name anything specific? (vague wording under strict)` |
| `C051-colon-reveal` | `C051` | `"If the point is clear, delete the aside." Is the span before the colon a complete clause? Does the colon replace a relation the sentence should state?` |
| `C054-metaphor-no-link` | `C054` | `does the vehicle share a property with the tenor? has the reader seen this comparison a hundred times?` |
| `C075-bold-label-list` | `C075` | `does every list item open on a bold label with nothing more than the label itself?` |
| `C076-heading-repeated` | `C076` | `does the first sentence under the heading only restate it, or treat the heading as a proper-noun subject, before any real content?` |
| `C113-imperative-title` | `C113` | `does the title or heading read as an imperative command or a slogan?` |
| `C154-say-out-loud` | `C154` | `Would you say it out loud?` |
| `C053-vague-declarative` | `C053` | `Does it name anything specific?` |
| `C155-checkmark-shape` | `C155` | `does the list mark every item, or does the mark carry information?` |
| `C058-passive-voice` | `C058` | `Is the actor unknown or genuinely unimportant here, or does the text support naming one?` |
| `C094-shown-property` | `C094` | `does the comment state a property the code visibly has?` |
| `C095-dropped-article` | `C095` | `Does the text drop the articles a sentence needs, as in "Parser rejects bad date", or lean on an abbreviation the reader must decode?` |
| `C123-label` | `C123` | `Does the label mark a warning the reader would otherwise miss, or does it only announce the sentence after it?` |
| `C126-example-block` | `C126` | `Does the example show a use the signature and the prose leave unclear, or is it a template block every function carries?` |
| `C127-file-header` | `C127` | `Does the header name an author and a date that version control already records, with a description the module docstring should carry?` |
| `C130-bullet-body` | `C130` | `Do the body's bullets add what the subject leaves out, or do they restate it?` |
| `C139-senior-engineer` | `C139` | `Does the abstraction fit the problem or the template? Does the comment say why or what? Is the defensive code at a boundary? Would a senior engineer on this codebase have written it this way?` |
| `C014-source-remark` | `C014` | `is the sentence addressed to the document's reader about the reader's decision, or to the requester about the writer's inputs?` |
| `C080-notes-caveat` | `C080` | `Does the qualifier in the speaker notes caveat a claim the slide body makes, so the slide presents that claim without its caveat?` |
| `C028-standalone-look` | `C028` | `Does "Look," stand alone and line-initial before a routine claim, or does it sit inside a casual sentence?` |
| `C034-what-to-do` | `C034` | `Does the sentence say what to do, or that something is generally done?` |
| `C040-term-of-art` | `C040` | `Is the noun a term of art here, as "surface" is in "API surface" and "harness" is in "test harness", or is it a metaphor?` |
| `C038-tutorial-voice` | `C038` | `does the text name the convention or cite where the fix is standard?` |
| `C050-scaffolding-shape` | `C050` | `does the sentence use a named scaffolding shape, a setup sentence, a landing phrase, a participial reframe, a thesis-first opener, or one of the paired or chiasmus judgment shapes, to carry a real point, or only the shape?` |
| `C052-false-agency` | `C052` | `does an abstract noun act as the subject of an agentive verb, with no real actor named?` |
| `C055-self-question-answer` | `C055` | `does a question sentence get answered at once by a sentence that just repeats its key noun?` |
| `C056-invented-example` | `C056` | `does "imagine", "say a", "suppose", "for instance, a customer might" or "picture a" introduce an invented case where a real one would do?` |
| `C073-parallel-gerund-bullets` | `C073` | `do the five parallel bullets each carry a distinct point, or only the shared gerund-opening template?` |
| `C039-plain-word-substitution` | `C039` | `Is the flagged word protected industry terminology the text relies on, for example "margin expansion" for investors, or is it one the plain-word dictionary replaces?` |
| `C096-names-the-change` | `C096` | `does the message name what changed, or does it assure the reader about process?` |

##### strict / per_document (17)

| id | rule | question |
|---|---|---|
| `C031-light-verb` | `C031` | `Does a light verb plus a nominalization here hide a plain verb?` |
| `C033-you-can` | `C033` | `Does the sentence work without the "you can" opener?` |
| `C015-requester-remark` | `C015` | `is this sentence addressed to the person who asked for the text?` |
| `C045-mannered-prompt` | `C045` | `does metaphor or flourish stand in for a direct statement here?` |
| `C061-wordy-indirect` | `C061` | `is the sentence wordy and indirect where a direct one would serve the same content?` |
| `C062-coined-label` | `C062` | `does a coined or unexplained jargon label appear where the industry uses a plain, standard term?` |
| `C064-cross-unit-consistency` | `C064` | `is a number, a name or a unit used two ways in this document?` |
| `C065-restatable-portable` | `C065` | `What does it tell the reader to do or know? Could it sit unchanged in another project's docs?` |
| `C067-drift-outward` | `C067` | `does terminology or tone drift across the deck for the same thing?` |
| `C071-length-calibration` | `C071` | `does the written deliverable pad with filler sections, redundant summaries or boilerplate?` |
| `C078-heading-category` | `C078` | `does this heading say what is under it, or only name a category?` |
| `C066-balanced-conclusion` | `C066` | `does the text weigh every side because the subject has sides, or by habit, and does it cover every angle because the reader needs each one?` |
| `C074-neat-takeaway` | `C074` | `does every section end on a neat takeaway, or does the same callout follow every section?` |
| `C017-answer-shaped` | `C017` | `does the answer show an answer-shaped habit, such as an unrequested option list, defining known terms, blanket caveats, or refusal-style disagreement, rather than the requested content?` |
| `C125-restates-next-line` | `C125` | `Does any comment say what the line after it already says, where a reader needs why?` |
| `C063-next-action` | `C063` | `does the reader know their next action, and does each paragraph or slide perform a clear function? "can you swap paragraphs 2 and 4 without breaking it?"` |
| `C057-hedge-claim-pull` | `C057` | `does any sentence in this document carry a hedge whose claim pulls in the opposite direction?` |

##### strict / per_rewrite (0)

Empty. The meaning line answers both questions this list held. See
"The three scopes" above.
