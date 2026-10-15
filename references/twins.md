# Twins

A twin is the example a `strict` taxonomy flag rests on: a past instance of the shape a
candidate now matches, quoted in the finding's `twin` field. The field stays empty under
`general`. The field enforces one rule: **no twin, no flag.** A taxonomy
candidate under `strict` with no twin to quote does not fire, whatever the candidate regex
under it found.

## The general bank

`general` carries no taxonomy pass, so `Finding.twin` never populates under it.
What follows is not a twin in that technical sense. It is an illustrative bank of
already-shipped flagged and clean pairs, one per rule, gathered here from
`references/rulebooks/general.json`'s own `examples` field so a reader has one
place to see a spread of what the rulebook already catches and how a clean
rewrite reads. Every pair below is copied unchanged from this project's own
rulebook file, written for this project, and none comes from another project or
from Wikipedia.

| Rule | Name | Flagged | Clean |
|---|---|---|---|
| C007 | Chat-wrapper closed list | "I hope this helps. Tell me if the table needs another column." | ""Here is an example:" opens the README section about the chatbot, and it stays." |
| C011 | Chatbot markup tokens | "The trust was founded in 1961【12†L40-44】." | "The trust was founded in 1961, and the sources sit in the appendix [1]." |
| C016 | Knowledge-limit disclaimers and guesses | "Up to my last training update, the site listed four regions." | "As of March 2025, the site listed four regions." |
| C018 | AI-style punctuation marks and the widened mark set | "The parser rejects a bad date; it exits 2 and writes nothing." | "The parser rejects a bad date, exits 2 and writes nothing." |
| C024 | Merged AI vocabulary list | "The report delves into the pivotal shift and showcases a robust result." | "The report explains the change in cost and shows the result." |
| C025 | Stiff synonyms and inflated verbs | "The report was authored by the finance team." | "The finance team wrote the report." |
| C028 | Staged run-up openers and throat-clearing phrases | "Let's dive in." | "The next section covers the cost table." |
| C030 | Wordiness filler pairs | "In order to reach the site, take the ferry." | "To reach the site, take the ferry." |
| C031 | Light verb plus nominalization | "The committee made a decision on the vendor." | "The committee decided on the vendor." |
| C032 | Business-jargon pairs, split by sense | "We will circle back to the invoice next week." | "We will return to the invoice next week." |
| C035 | Stacked-qualifier hedges | "The change could potentially raise the cost." | "The change may raise the cost." |
| C040 | Abstract metaphor nouns in technical prose | "The endgame for the migration is a flywheel of weekly releases." | "The migration ends when the weekly release runs without a manual step." |
| C046 | Inflated significance and sales language | "The bridge plays a vital role in the region's history." | "The bridge carried little traffic." |
| C150 | Empty superlatives | "This parser is the best of the three we tried." | "This parser read 40 of 40 files, and the other two failed on 6." |
| C152 | Bare "ensure" | "Ensure the file is closed before the run." | "Close the file before the run." |


## The strict twins

Each `strict` taxonomy category carries two twins, written for this project. A FIRE quotes
the twin whose shape the flagged text mirrors, or one of the same family. A candidate that
mirrors none of them passes.

| Category | Rules | Twin | The same point, plainly |
|---|---|---|---|
| awkward phrasing | `C154` | "The tool achieves the provision of faster exports to the user base." | "The tool exports faster." |
| awkward phrasing | `C154` | "Upon the completion of the upload, the file becomes available for opening." | "Once the upload finishes, you can open the file." |
| flowery language | `C044`, `C046`, `C047`, `C054` | "This release marks a pivotal milestone in our ongoing journey toward excellence." | "This release adds offline mode." |
| flowery language | `C044`, `C046`, `C047`, `C054` | "The dashboard serves as a beacon of clarity in a sea of data." | "The dashboard shows the three numbers the team checks each day." |
| vague wording | `C053`, `C065` | "This represents a significant step forward for the project." | "This cuts the build from nine minutes to four." |
| vague wording | `C053`, `C065` | "The new process improves things across the board." | "The new process removes two manual approvals." |
| unnecessary words | `C028` | "It is worth noting that the cache is cleared on restart." | "The cache is cleared on restart." |
| unnecessary words | `C028` | "Let's take a closer look at the results." | "The results follow." |

`SKILL.md`'s own Judging section sends a taxonomy question to this file for a mirror or a
same-family match. Under `strict` that match is one of the twins above. Under `general` the
taxonomy pass does not run, and the bank above illustrates the rules.
