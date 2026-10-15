# Register: code

Read this while rewriting comments, docstrings, prose strings or commit messages. The
register is a senior engineer's on the codebase at hand: plain words, a comment that
says why, a docstring that states the contract, and nothing a reader has to decode.
This file grounds each of those properties in a rule the code handler ships, and closes
with the questions `C139-senior-engineer` asks of every comment and docstring.

Code prose runs `general`'s prose rules at their own tiers, with the rows that are off for
the technical register left out. `C024`, `C025`, `C030`, `C031`,
`C032`, `C037` and `C052` are off for code prose, and `C040` is off for comments and
docstrings. Under `strict` the same rules run, and the AI-style punctuation marks block.
In code prose the mark rules fire on typographic marks alone, so an em dash in a comment
is a mark and an ASCII arrow such as `->` is notation.

## Plain words in comments

A comment is prose a maintainer reads beside the code, so the prose rules that stay on
apply to it as they apply to a paragraph. The vocabulary lists are off here because a
technical word is often the precise one. A plain word is still the target, and a word
that only sounds weighty is still cut.

## A comment says why

`C125-restates-next-line` asks `Does any comment say what the line after it already
says, where a reader needs why?` of every file that holds a comment. The line
"Increment the retry count by one." above `retries += 1` adds nothing the code does not
say. "Count the retry before the sleep, so the backoff reads the attempt that just
failed." says why the line sits where it does. The second of `C139`'s questions asks the
same thing of every comment and docstring.

## A docstring states the contract

A docstring says what a function takes, what it returns and what it raises, in the
terms a caller needs. `C126` (`Example usage` blocks) asks whether an example shows a
use the signature leaves unclear: "Example usage: parse_rows(open(path))" repeats the
signature, and "Returns one dict per row, keyed by the header line." states the
contract. `C095-dropped-article` asks of every docstring and commit body whether the
text drops the articles a sentence needs or leans on an abbreviation the reader must
decode.

## No narration of a prior version

The history of the code lives in version control, and a comment describes the code as
it stands. `C093` warns on edit-history phrases in comments and docstrings. "The lookup
now uses a set and replaces the old loop over every item." narrates a change. "A set
keeps the lookup fast when the list holds thousands of ids." says why the code is what
it is today.

## No asserted guarantee without a test

A comment that promises a property the code does not show is a claim nobody checked.
`C094-shown-property` asks `does the comment state a property the code visibly has?`
of every comment carrying a guarantee word. "Thread safe, so callers never need a
lock." asserts the property. "Takes the module lock before it appends, which
test_parallel_append checks." names the mechanism and the test behind it.

## No `Note:` labels

A label that announces the next sentence gives the reader one more thing to skip.
`C123-label` asks whether the label marks a warning the reader would otherwise miss.
"Note: the cache is cleared on every call." carries the label. "The cache is cleared on
every call, so each caller reads fresh data." says the same thing and adds the reason.

## No `This ensures`

`C124` counts `This ensures` at density in comments and docstrings, the same family as
`C152`'s bare `ensure` in prose. "This ensures the cache stays warm between calls."
opens on the phrase. "Warming the cache here saves a second read on the next call."
names the effect directly.

## No file header with author and date

Version control records who wrote a file and when. `C127-file-header` asks whether a
header's author and date belong there. "Author: Dana Reyes, 2024-03-01" repeats what
the history holds, and "Parsers for the three export formats the billing service
writes." is the description, which belongs in the module docstring. A license header is
protected under `C147` and weighs nothing, so a header such as "Copyright 2024 Example
Corp. Licensed under the MIT License." is left exactly as it is.

## Commit messages

A commit subject is imperative and short by convention, and the body says why the
change was made. `C095` warns on a body line that opens on a past participle with no
verb after it: "Added retry for timeouts." is a fragment, and "The worker retries a
request that times out, up to three times." is a sentence. `C096` asks whether a message
names what changed: "Tidy the export module while preserving all existing behavior"
assures the reader about process, and "Quote every CSV field that holds a comma" names
the change. `C130-bullet-body` asks whether a bullet body adds what the subject leaves
out. `C021` counts an emoji in the subject, at block under `strict`.

## What a rewrite leaves alone

Five protection rows keep text out of every rewrite. `C144` keeps public API names, so
a rewrite that drops one reverts. `C145` keeps key and protocol strings, and on a script object-key strings, JSX attribute values, tagged templates and class-list arguments as well, `C146` skips
generated and vendored files, `C147` keeps license headers and `C148` keeps test
fixture data. A rewrite touches the words of a comment, a docstring or a prose string,
and the code around it keeps every byte.

## The senior-engineer questions

`C139-senior-engineer` asks four questions of every comment and docstring:

`Does the abstraction fit the problem or the template? Does the comment say why or
what? Is the defensive code at a boundary? Would a senior engineer on this codebase
have written it this way?`

"Check that the value is not None before using it." restates a guard a reader can see.
"Retry once, since the upstream cache answers 503 for a few seconds after a deploy."
names the boundary and the reason, which is what the last question looks for.
