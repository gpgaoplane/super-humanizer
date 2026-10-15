# Report format

Read this while writing a report or while explaining what a section of one means.
`scripts/report.py` builds the report from a `Context` built entirely from records
already in memory. It reads no file and calls no model. One rule organizes it:
every section prints on every run,
even when it carries nothing, with "none" or "not run" and the reason, because a
section that vanishes when it has nothing to say leaves a reader unable to tell a
clean run from a step that never ran.

A post-hoc run prints the report to the session and writes the same text to
`<path>.humanize-report.md` beside the artifact (`scripts/report.py::REPORT_SUFFIX`).

A retro writes its own report under nine headings of its own, which the last section of this file
describes.

## The eleven sections, in order

`scripts/report.py::SECTIONS` is the ordered list every render walks, and this
file's own headings below are copied from it in the same order.

1. **What ran.** The rulebook name and where it came from, the voice line, which reads
   `Voice: off.` when the marker's `voice` key is false and takes one of the two mine forms below
   otherwise, the second reader on or off with the rule that decided it, the run's scope, and
   one line per rule an overlay changed. The second reader line reads the
   `second_reader.Resolution` the caller computed and passed on
   `Context.second_reader`. This module resolves nothing itself. A `Context` carrying
   no Resolution at all prints the marker's raw setting and says that this run's
   caller resolved none, which is what a caller that never ran the stage gets.

   The mine line has two forms. With no profile it reads `Voice: on (mine), no profile learned
   yet.` and a second sentence, `scripts/voice.py::LEARN_HINT`, which names the learn command,
   so the whole line reads as below, and the same hint joins the cannot-see list after the
   no-profile line.

   > Voice: on (mine), no profile learned yet. Learn it from your own documents: /humanize
   > learn <folder> [--recent NAME ...], which reads a folder of documents you wrote and writes
   > the profile. Nothing runs until you name a folder.

   With a profile read it counts the entries in force by kind, in the order of
   `scripts/voice.py::PROFILE_KINDS` with the kinds at zero left out, and says "1 entry" in the
   singular, as in `Voice: on (mine), 4 entries in force: diction 2, structure 1, avoid 1.` A
   profile with nothing in force reads `Voice: on (mine), 0 entries in force.` Under
   `strict` the second form closes with the clause `, silences and licences off under
   strict`, since the strict rule overrides a mark's silence and a device's licence
   whatever the habit, and the no-profile form takes no clause. A `voice` value other than false
   and `"mine"` warns in the cannot-see list and reads as false.
2. **Configuration in force.** The marker's `protect` list in full, the marker
   keys that differ from the shipped defaults, and the rulebook fields an overlay
   changed.
3. **Findings.** Two counts on the first two lines, always: the total, and
   "N findings over M spans" (printed even at
   "0 findings over 0 spans"). Below that, findings grouped by each rule's
   `class`, each line naming its rule, unit, span when it has one, verdict,
   `category` when the rulebook carries one, the `twin` quoted when a
   taxonomy flag carries one, and whether the second reader raised it.
4. **Self-check.** Every asked entry, printed by
   `scripts/report.py::_self_check_line` as `<id> (<verdict>): "<question>".`, with
   a trailing exception clause on a pass that rests on one, and the ids the
   five-per-unit cap left unasked, listed under their unit.
5. **Density.** The density record per unit (marks, vocab, dense or not), the
   document's own band, and the two sentences every run prints,
   `scripts/report.py::_DENSITY_SENTENCES`, unchanged:

   > Bands describe coverage. They never pick rewrite scope.
   >
   > The band numbers were first measured on slide decks and stay provisional on markdown.

   On an office format the second sentence is `scripts/report.py::OFFICE_BAND_SENTENCE` in its
   place, since the band numbers were measured on slide decks and apply to every office format:

   > The band numbers were first measured on slide decks and stay provisional on this format.

   The density group follows the format, and `scripts/office.py::density_key` decides it. A deck
   prints one group per slide, `- slide 1:`, and one per slide's notes, `- slide 1 notes:`, with
   the notes groups listed after the slides and left out of the band. A workbook prints one group
   per sheet, `- sheet Summary:`, and a hidden sheet's name carries " (hidden)" after it. A PDF
   prints one per page, `- page 3:`. A Word document prints one per unit, `- Unit u0004:`, as a
   markdown file does. A group's label stands alone with no "Unit" before it.

   Under `general` with a profile in force, each silence that fired prints one line after the
   records and before the band, one per rule and entry however many hits it dropped:
   `Voice silence: <rule id> by the <kind> entry "<entry>", so the counts above leave its hits
   out.` The line prints on every route and never under `strict`. The hook prints no such
   line.
6. **Rewrites applied.** One entry per rewritten unit, the whole unit's own before
   and after text when accepted, or "reverted" with the lost or gained token when
   the fidelity check reverted it, plus `scripts/fidelity.py::CAVEAT` printed
   once at the end, outside every loop, unchanged: "protected-token comparison
   is necessary and insufficient". In the default copy mode an accepted
   rewrite on a deck, a workbook or a Word document lands in the side-by-side copy
   `<stem>.humanized<suffix>` beside the original, and the original is never written. Under
   `office_write: in-place` it lands in the file itself and no copy is written, and the diff the
   run prints reads "after" where a copy's reads "in the copy at <path>". On a PDF an accepted
   rewrite lands in the markdown delivery `<stem>.humanized.md` in both modes, and the PDF is never
   written. A rewrite the writer refused, the copy's or the in-place one, prints "Unit <id>,
   proposed and never applied: <reason>." with its Before and After, and the unit's Left for the
   human entry carries the same reason. A write refused whole, the copy's, the in-place one or a
   PDF delivery's, moves every rewrite of the file to that form with the whole reason, so the
   summary counts none of them as applied. The run prints no diff for a refused rewrite, while
   a markdown write back's refused diff still prints. A comment on a workbook sheet whose own relationships hold
   a threaded comment prints with the in-place writer's threaded reason, quoted in the
   in-place lines of section 8 below.
   Under `voice: "mine"` with a profile file present, a model rewrite that changes more of a
   unit's words than the marker's `refine_cap` key allows, 0.35 by default, is reverted with a
   Cap line. The line prints under the reverted row on a line of its own, apart from the Meaning
   line, which a capped row does not carry, with the Lost and Gained lines under it. The share
   is the words of the original that the rewrite replaced or deleted, plus the words it
   inserted, over the original's word count. A substitution fix is never capped, and a run under
   `voice: off` or under `mine` with no profile file caps nothing. The line reads, with
   `scripts/reconcile.py::cap_refusal` filling the two numbers to three places:

   > Cap: the rewrite changes a share of <share> of the unit's words, over the refine cap of
   > <cap>, so the original stands.

   A run whose rewrite stage was off or skipped prints "None. No unit was rewritten in this run."
7. **Left for the human.** One entry per item C003 raised, each with a "Change:"
   line and a "Risk:" line, C003's own two diagnostic questions.
8. **Cannot see.** The handler's own name, its cannot-see list from the
   extractor's own `CANNOT_SEE` constant, the same text `references/format-handlers.md`
   quotes, and the self-check ids the cap skipped, listed again here by unit. For a deck, a
   workbook, a Word document or a PDF the handler's name is the format, and the file's own lines
   follow the constant, as `references/format-handlers.md` lists them per format. A run that
   wrote a copy or a delivery adds the lines below, and a run that wrote an office file in place
   adds the in-place lines after them. The short name `{kind}` is "copy" for a deck, a workbook or a
   document and "delivery" for a PDF.

   - "the rewrite of <surface> was left for the human: <reason>", one for each rewrite the
     writer refused.
   - When the writer refused every rewrite, "every rewrite this run accepted was refused by the
     {kind} writer, so no side-by-side copy was written beside <path>, since it would hold the
     original's text alone. The original is unchanged, and no answer was spent." A PDF's line says
     "markdown delivery" where this says "side-by-side copy". When the whole write was refused
     for one reason, such as an original that changed on disk, the line reads "no side-by-side
     copy was written beside <path>, because <reason>. The rewrites stay in the report, and the
     original is unchanged."
   - `scripts/humanize.py::COPY_CANDIDATES_LINE`, unchanged, in the place of the line a rewrite of
     the artifact itself prints, since the original keeps the bytes the candidates file records:

     > the candidates file still matches this original, and the answers were spent on the {kind}
     > at {copy}

   - The retired files. "the verdicts file was spent by this run on the {kind} at <copy name>
     and moved to <name>. The original is unchanged, and a run with no verdicts file beside it is
     the ordinary next state." and, when the run merged the second reader's brief, "the second
     reader's brief was spent by this run on the {kind} at <copy name> and moved to <name>. The
     original is unchanged, and the next run writes a fresh brief." The moved files are
     `<path>.humanize-verdicts.applied-<UTC stamp>.json` and
     `<path>.humanize-second.applied-<UTC stamp>.json`.
   - The writer's own lines: a rewrite spread over runs that include a hyperlink, a rewrite that
     split a word across runs, a workbook cell or comment whose rich text runs were flattened, and a
     Word header or footer that Word does not show.

   A run that wrote a deck, a workbook or a Word document in place, under the marker's
   `office_write` key or the run flag `--office-write`, adds these in place of the copy lines
   above, and writes no copy:

   - "the rewrite of <surface> was left for the human: <reason>", one for each rewrite the
     in-place writer refused, which includes a comment on a workbook sheet whose own relationships
     hold a threaded comment, with this reason, `scripts/extract_xlsx.py::THREADED`:

     > the comment sits on a sheet whose relationships hold a threaded comment, whose text Excel
     > shows from its own part, so the legacy text openpyxl reads is never what a reader sees

   - When the in-place writer refused every rewrite, `scripts/humanize.py::IN_PLACE_EVERY_REFUSED_LINE`:

     > every rewrite this run accepted was refused by the in-place writer, so {path} was not
     > written. The file is unchanged, and no answer was spent.

   - When the whole write was refused, such as for an original that changed on disk,
     `scripts/humanize.py::IN_PLACE_REFUSED_LINE`:

     > {path} was not written in place, because {reason}. The rewrites stay in the report, and the
     > file is unchanged.

   - When the temporary file could not be removed after a refusal, the reason ends on
     `scripts/office.py::IN_PLACE_LEFT`:

     > The temporary file {temp} could not be removed and is left beside the original

   - The writer's own lines, which come after the write and before the parts line: the hyperlink
     and split-word lines of a deck and a document, the line for a Word header or footer that Word
     does not show, the flattened line of a workbook, and for a workbook cell written,
     `scripts/extract_xlsx.py::STALE_RESULTS`:

     > formulas that read a rewritten cell show their old result until Excel recalculates, which
     > the file now asks for on open

     A workbook run drops the two side-by-side copy clauses of its handler's list from the report,
     a report run included, since no copy is written. A write of comments and header parts alone
     owes no stale results line.
   - `scripts/office.py::IN_PLACE_PARTS`, last, naming the file, the count of parts replaced, the
     total, which counts the package's zip entries, and their names:

     > {path} was written in place, {count} of {total} package parts replaced ({names}), and every
     > other part is byte for byte what it was

   - In place of the copy's candidates line and retire notes, the markdown branch's. The
     candidates line says the candidates file was written before the rewrite stage ran, so its
     questions belong to the text this run replaced and its recorded digest can never match again,
     and a second report run writes a fresh candidates file for the written file. The retired
     files read "the verdicts file was spent by this run and moved to <name>. The artifact has
     changed, so those answers no longer match its questions. A run with no verdicts file beside
     the artifact is the ordinary next state." and, when the run merged the second reader's brief,
     "the second reader's brief was spent by this run and moved to <name>. The artifact has
     changed, so those findings no longer address it, and the next run writes a fresh brief."

   A PDF under the same mode is never edited in place. Its delivery is written as in
   copy mode, and once it is on disk the run adds `scripts/humanize.py::PDF_NEVER_IN_PLACE_LINE`:

   > the marker asks for in-place writes, and a PDF is never edited in place, so the markdown
   > delivery was written beside it
9. **Not applicable.** Every rule in the rulebook whose `formats` field turns it
   off for this document's own format, or "None. Every rule in `<rulebook>`
   applies to the `<format>` format."
10. **Validation.** For a code run, two lines, `formatter: <state> (<scope>)` and
    `tests: <state> (<scope>)`. The state is one of `pass`, `fail`, `not run`,
    `not applicable` and `reverted`. `scripts/validate.py` finds the formatters and
    the tests by convention: `ruff` or `black` from `pyproject.toml`, `prettier` from a
    prettier configuration file or a `prettier` key in `package.json`, `pytest` from a
    pytest configuration, `npm test` from a `test` script in `package.json`, and a bare
    tests or checks folder when neither is configured. Every configured formatter and every
    configured test suite runs, a stage reads `fail` when any command fails and `not run`
    when any did not run, a timed-out command's whole process tree is killed, and each runs
    once before any write back and once after. Every formatter checks the run's own code
    artifacts by name, `ruff format --check --force-exclude <files>`, `black --check <files>`
    and `prettier --check <files>` in batches, never the whole tree, and a formatter with none
    of its file type in the run reads `not applicable`. The run validates once per package
    root its artifacts sit under, the nearest `package.json` or `pyproject.toml` above each,
    and combines the states across roots. The Python tools run under the project's own
    interpreter, prettier comes from the package's own `node_modules/.bin` before the path,
    npm from the path with `CI=1` set, and an absent tool reads `not run`. The interpreter is
    the one in the root's `.venv` folder, else the one the `VIRTUAL_ENV` variable
    names, else the interpreter that runs the plugin. When that interpreter has no
    pytest, the tests stage reads `not run (pytest is not installed for
    <interpreter>)` and the write back stands. A code run executes the project's test
    suite twice, once before and once after the write back, and each run may take up
    to 120 seconds. A stage that was red before any rewrite reads
    `fail (before any rewrite)` and the run applies nothing. A stage that fails
    after the write back reads `reverted`, the original bytes go back on disk, and
    every Rewrites applied row says so. `not run` names its reason, such as no test
    suite found, a timeout, or the rewrite stage being off on this run, and
    `not applicable` means no formatter is configured. The scope names the command
    and the edited units a test file mentions verbatim, which is C145's own literal
    search. A passing suite's scope also carries the test count read from the last
    three lines of pytest's output, or `count not read` when none of them holds one.
    In a repository with a `package.json` the test files read for a mention are every file
    in a `test`, `tests` or `__tests__` folder and every `*.test.*` and `*.spec.*` file,
    and `npm test` carries no count.
    A run over any other format, a deck, a workbook, a Word document and a PDF among them, prints
    the fixed line `scripts/report.py::_VALIDATION_TEXT`, since the formatter and the tests are a
    code run's stages and an office run runs neither:

    > not applicable (no code run). The formatter and the test suite run around a
    > code run's write back.
11. **Limits.** The limits rows, printed in full, plus the uninstall line, the
    four conduct lines, and the disclaimer.

## One line that never prints

- **A protected span the marker's `protect` list masked.** Rewrites applied keeps a line for a
  Finding whose `weight` field reads `"recorded"` instead of `"counted"`, and nothing sets that
  field to `"recorded"`: `protect.apply` and `protect.fill` mask a span before `scan.scan` runs,
  so a masked span raises no Finding at all. The branch prints a line saying so if it is ever
  reached.

## The four conduct lines

Four conduct lines print inside the Limits section, in the report's
own words and never left to a reader to infer. `scripts/report.py::CONDUCT_LINES`
carries exactly these four, unchanged:

1. "It never claims authorship of the text, and it never says the output is
   undetectable or proves human authorship."
2. "It never scores the artifact. It reports findings and leaves the judgment to the reader."
3. "It never infers who or what wrote the input."
4. "It never invents a fact to make a rewrite work. Specificity comes from a
   source, a valid derivation or the author."

## The disclaimer

`scripts/report.py::DISCLAIMER`, printed once inside Limits, unchanged:

> This run covered visible prose defects, chat wrappers, repetition, house style
> and protected-token comparison. It does not claim to have verified every fact.
> It flags a claim that cannot be true on its face, and it never checks a claim
> against a source.

## The limits list

Thirteen rows print in full inside Limits, `scripts/report.py::_LIMITS_ROWS`,
unchanged:

> Managed settings can block plugin hooks entirely through `allowManagedHooksOnly`.
>
> `disableAllHooks` turns every hook off.
>
> Whether workspace trust holds plugin hooks back is undocumented. An interactive session holds settings-file hooks back until the trust dialog is accepted, and a `-p` or SDK session treats the folder as trusted.
>
> A timed-out hook's output is discarded, so the fail-open notice cannot cover a timeout.
>
> The inline gate sees Write and Edit calls only. A shell write is never scanned, and the FileChanged event cannot block it.
>
> A model can run `marker.py` itself, so the marker guard is a speed bump. This report prints the marker's state on every run.
>
> Hook scripts run with the user's full permissions.
>
> Hook output is capped at 10,000 characters, and output over the cap goes to a file with a preview.
>
> Under `strict`, a file written before the plugin was turned on refuses every Edit until a post-hoc run cleans it.
>
> The tests mention in the Validation scope is a literal substring search of the test files for each edited unit's text, so a short unit can match by accident.
>
> A file a project's prettier ignores is never checked, and the formatter stage reads pass for it, as the project's own check would.
>
> Under CI=1, which the validation stage sets for npm test, a jest run that needs a new snapshot fails, so such a package reads fail before any rewrite.
>
> A class list passed through a member call on a helper object, an array, or a cva variant value is read as a prose string, since C145 catches the bare clsx, cn, classNames and cva calls alone.

Plus one more line, `scripts/report.py::_UNINSTALL_LINE`, unchanged:

> The voice profile and the ledger live at `~/.claude/super-humanizer/` and survive an uninstall. The rulebook overlay and the refusal state live in the plugin's data folder, `${CLAUDE_PLUGIN_DATA}`, and do not survive one.

## The retro report, nine sections

`/humanize retro <draft> <final>` prints a report and writes the same text to
`<draft>.humanize-retro-report.md` beside the draft (`scripts/retro.py::REPORT_SUFFIX`). Its
heading list is `scripts/retro.py::SECTIONS`, and `report.section` and
`report._neutralize_headings` take the list a report was rendered under, so a retro heading
forged inside a quoted piece stays in its section. Every section prints on every run, with "None."
and the reason when it has nothing. The nine, in order:

1. **What ran.** The draft and the final with their formats, the rulebook and its sha256, the
   overlay's sha256 or "Overlay: none.", `Voice: mine.` or `Voice: off.` with the line that the
   harvested profile layers on no run until the marker sets mine, the task, the two thresholds,
   the until text or "none, so each side was read whole", and the units dropped on each side.
2. **Alignment.** The pieces and the bullet pieces of each side, the counts of unchanged,
   rewritten, deleted and added, and the rewritten ratios in four bins.
3. **Flag rate.** Each side's raw rate and its comparable rate, in findings per 100 words, with the
   rules set aside named.
4. **Divergences.** One entry for each piece that is not unchanged, with its rid, kind, ratio and
   class, and its Before and After quoted. The class reads `unjudged` until a verdicts file
   answers it.
5. **Ledger.** After a verdicts file is applied, the ids appended, one line for each row the ledger
   already held, and the spent file's new name. Otherwise "None." with the reason.
6. **Profile.** After an apply, the head "The rows were appended, and the profile was harvested
   from the N rows the ledger holds and written whole: E entries, C confirmed and W at watch.",
   or "No row was appended" in its place when the file was applied before,
   one line for each entry whose state changed with its evidence ("new at watch", "watch to
   confirmed") or "No entry changed state.", one "- Dropped:" line for each entry the file held
   that the harvest does not, and one "- Left out:" line for each entry an avoid entry outranked
   or a ledger row the harvest passed over, a row whose class and kind disagree among them, and
   one for a recent list under the home the harvest could not read. A profile the disk refused prints "could not be
   written, so it stays as it was", and the run exits 1.
7. **Promotions.** The head with the rows read, one line for each rule that
   `scripts/voice.py::PROMOTE_AT` or more slop rows name, saying the tier it argues, that it "is
   already there at" a tier, that it "is held by" the design that holds its tier, or that it "is
   absent from the strict rulebook", one line for each template hit naming the row and the
   reference file, and one line for each earlier row carrying a promotion. Otherwise "None." with
   the reason.
8. **Cannot see.** The handlers' own cannot-see lines and the configuration warnings, then the
   refusal lines of a verdicts file (`retro.NOTHING_ALIGNED`, `UNUSABLE`, `NO_DIGEST`,
   `STALE_LINES`, `FRESH_QUESTIONS`, `MISSING`, `UNKNOWN` and `LEDGER_REFUSED`), the lines of a
   profile or a ledger the disk refused (`PROFILE_REFUSED` and `LEDGER_UNREAD`), one line for each
   malformed ledger line by its number, the unread reference file line, and under another
   rulebook the general book's own warnings, since the silences are always measured under it.
9. **Limits.** The sentences of `scripts/retro.py::LIMITS`.

The questions file `<draft>.humanize-retro.json` carries the digests the verdicts file copies. A
stale run adds a last key, `superseded`, holding the pair a refused verdicts file was answered
under. `/humanize retro state <kind> <entry>` writes no report file. It prints Ledger, Profile,
Promotions and Cannot see to the console under the title "# Retro state", with its loader's
warnings in Cannot see.

## The learn report, ten sections

`/humanize learn <folder>` prints a report and writes the same text to
`learn/learn-report.md` under the home, `~/.claude/super-humanizer/` by default
(`scripts/learn.py::REPORT_NAME` under `scripts/learn.py::FOLDER`). Its heading list is `scripts/learn.py::SECTIONS`. Every section
prints on every run, with "None." or "none" and the reason when it has nothing. The report
prints the documents' file names, since the folder is the user's own. The ten, in order:

1. **What ran.** The folder, the rulebook and its sha256, the overlay's sha256 or "Overlay:
   none.", the recent names given or "none given", the until text or "none, so each document
   was read whole", and the thresholds `GROUP_AT`, `LAYOUT_AT`, `RECUR_IN` and `RECUR_CAP`.
2. **Documents.** The count read by format, each skipped file with its reason, and per document
   whether the until cut applied, a PDF with no page opening on the text reading "no heading
   unit, the cut was not applied".
3. **Tasks.** The count, each family by member count and the Jaccard range it joined at, or the
   join through a document the ledger holds and this folder lacks when no pair of its members
   reaches the threshold, the equal texts read once with the member read, and the highest
   Jaccard between two documents of different tasks, so a near miss at the threshold is visible.
4. **Recency.** The documents the recent list names, the count it does not, whether this run
   rewrote the list, and the line that the list is the user's own word and how to change it.
5. **Candidates.** Per task the counts and marks at their floors with their directions, the
   rules, the slip forms, and then the recurring words offered, each as numbers.
6. **Ledger.** The ids appended per document, each row refused as held with its kind and entry,
   the documents the ledger holds rows for apart from the documents waiting on a verdicts file,
   the count of documents the ledger holds rows for that sit outside the folder, and the
   documents refused as held under another task id.
7. **Profile.** The profile step's lines as the retro prints them, or the line that no step ran.
8. **Older only.** Each entry in force whose sample rows cite no document of the recent list. An
   entry with no recency reading is left out.
9. **Cannot see.** Every loader warning, the refusal of a stale or unusable verdicts file with
   the half or the trait named, one line counting the documents the ledger holds and this
   folder lacks whose questions file under the home will not read back, the formats the walk
   refused, and the layout units by count.
10. **Limits.** The sentences of `scripts/learn.py::LIMITS`.

The questions file carries the digest the verdicts file copies. A verdicts file the run refuses
stays where it is, a fresh questions file is written beside it, and the run exits 1.
