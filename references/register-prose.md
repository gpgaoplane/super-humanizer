# Register: prose

Read this while rewriting prose, or while composing in inline mode. The register
is the whole mechanism (`skills/humanize/SKILL.md`'s own Overview): `plain words,
one idea per sentence, specific claims, evidence before conclusions`. Removing
slop is the humanizing, and no planted roughness substitutes for it. This file
grounds each of those four properties in rules already shipped, and closes with
what each rulebook's own `target_corpus` names as the standard it reads toward.

## Plain words

A plain word replaces a stiff one, and a filler phrase is cut instead of kept and
softened. This is `C039-plain-word-substitution`'s own question: `Is the flagged
word protected industry terminology the text relies on, for example "margin
expansion" for investors, or is it one the plain-word dictionary replaces?`
`C030` (wordiness filler pairs) and `C031` (light verb plus a nominalization) ship
every pattern as a `change` fix, never `final`, so a run offers the instruction
and leaves the rewrite for the human: "In order to reach the site, take the
ferry." becomes "To reach the site, take the ferry." (`C030`), and "The
committee made a decision on the vendor." becomes "The committee decided on the
vendor." (`C031`), and both name the plain-word target to write toward instead
of a substitution the run already made. `C024` and `C025` cover the merged AI
vocabulary and the stiff-synonym list itself: "The report delves into the pivotal
shift and showcases a robust result." becomes "The report explains the change in
cost and shows the result." A plain word is not always the shorter one. `C039`'s
own question protects a term of art the text relies on, the same way `C040` asks
whether a noun is "a term of art here, as `surface` is in `API surface`... or is
it a metaphor?"

## One idea per sentence

The sentence is the judgment unit for exactly this reason: one
sentence carries one claim, and a shape recurring across several sentences is a
document-level pattern instead of one sentence's own fault. Two rules test for
this directly. `C036-two-intensifiers` asks `does the unit carry two or more
counted intensifiers?`, since a sentence stacking intensifiers is usually
carrying more claims than it states plainly. `C050-scaffolding-shape` asks
whether a setup sentence, a landing phrase or a paired judgment shape "carry a
real point, or only the shape", since a scaffolded sentence often exists to delay
the one idea instead of to hold a second one. `C077` (bullets, headers and small
tables where prose reads better) asks the same question one level up, over a
structure standing in for a sentence: `would prose read better? would one or two
sentences carry this without loss?`

## Specific claims

A specific claim names a system, a number or a source. `C046-three-shapes` asks
whether a sentence is `debate framing, a low-importance preamble, or belaboring
how much something is conserved` instead of a claim the text supports, and its
own shipped example is exact: "The bridge plays a vital role in the region's
history." names nothing, and its clean twin, "The bridge carried little
traffic.", names a fact. `C053-vague-declarative` asks the shortest version of
the same test: `Does it name anything specific?` It runs once per document under
`general` and on every unit under `strict`, where the same words also reach a
model through `C048-unattributed-authority`, whose own question reads "Does it name
anything specific? (vague wording under strict)". `references/twins.md`
holds the twins a `C053` flag needs under `strict`. `C065-restatable-portable`
widens the general question to a whole document: `What does
it tell the reader to do or know? Could it sit unchanged in another project's
docs?`, the strict style's vague-wording test: could the same words sit unchanged
in another artifact?

## Evidence before conclusions

A conclusion earns its place with the evidence already in the text instead of a
hedge standing in for evidence the writer never had. `C016-date-and-availability`
tests exactly this seam: `Does the sentence carry a date or a source-availability
claim the text supports, or is it the model's own guess?`, with "Up to my last
training update, the site listed four regions." on one side and "As of March
2025, the site listed four regions." on the other. `C035` (stacked-qualifier
hedges) keeps a single, real hedge and cuts the pile: "The change could
potentially raise the cost." becomes "The change may raise the cost." The hedge
lexicon itself, the fidelity check's own list of protected words, is `may, might, could, some, preliminary, associated with, suggests,
appears, approximately`: a real hedge from that list, backed by the sentence's own
uncertainty, is not what any of these rules removes. `C066-balanced-conclusion`
closes the loop at document scope: `does the text weigh every side because the
subject has sides, or by habit, and does it cover every angle because the reader
needs each one?` A conclusion balanced by habit is a conclusion with no evidence
behind the balance.

## What each rulebook's `target_corpus` points at

Each rulebook points at a target corpus, the writing it reads toward.

`general`'s own `target_corpus`:

> Plain-language guidance for a general reader: the Federal plain language guides, the
> Google developer documentation style guide and the Microsoft Writing Style Guide, read
> as the register target and never as shippable text. Those guides use em dashes and
> semicolons in good writing, which is why most marks are counted here and never removed
> by the tool. The em dash in prose and the arrow inside a sentence are the two
> exceptions, and each gets a warn with an instruction to rewrite the sentence.

`strict`'s own `target_corpus`:

> The strict style, carried by the rules, questions and twins in this rulebook.

Read as a register target and never as shippable text is the operative phrase for
`general`: the guides above use em dashes and semicolons themselves, which is
exactly why `general` counts most marks instead of treating one as automatically
wrong, and why `plain words` above is a register to write toward and never an
absolute ban on any one mark.
