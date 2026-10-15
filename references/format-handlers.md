# Format handlers

Read this while working on a deck, a workbook, a document, a PDF, a prompt or a
Python file, and for what each handler cannot see. One rule governs every handler:
extraction completeness decides
detection completeness, and every handler names what it cannot see instead of
passing over it in silence.

## markdown

`scripts/extract_markdown.py` is the extractor. Its own `CANNOT_SEE` constant,
copied unchanged:

> "fenced code (three spaces of indent or fewer at the top level, any indent
> inside a list item), an indented code block that follows no list item, and
> front matter, which C140 records"

**Ten more shapes** are kept from counting, since each would otherwise fire on
notation. They split into two different homes,
and a model reporting coverage from this file needs both, since one home means
the text was read and recorded at zero weight and the other means it was never
a weighing surface at all.

Eight are scanner-time masks, applied inside a weighing unit's own text before a
pattern runs, each implemented in `scripts/units.py` and recorded through one of
`general.json`'s own exception ids: an HTML comment (`html-comment-mask`), a
double-backtick code span (`code-mask`), a table with no outer bars
(`markdown-table-pipe`), an HTML entity (`entity-mask`), a wiki link's alias
target (`wiki-alias-mask`), a link target or mailto address carrying a
semicolon (`link-target-mask`), a markdown table row (`markdown-table-mask`) and a
block quote line (`block-quote-mask`). A span in one of these eight is still read and
recorded, and recorded at zero weight is a different thing from never being seen
at all. The closing `-->` of an HTML comment also fires `strict`'s ASCII arrow entry
on its own, which is why the HTML-comment mask exists
instead of leaving that shape to the ASCII-arrow rule alone.

The other two are extraction-time shapes instead of scanner masks, and carry no
exception id: a fence indented under a list item and a four-space code block.
`scripts/extract_markdown.py` classifies both as `kind="code"` units, and every
unit of that kind is built with `weighs=False`, so neither ever reaches the
scanner at all. Both are exactly what the handler's own `CANNOT_SEE` list above
already names, in its own first clause: "an indented code block that follows no
list item" is the four-space shape, and "any indent inside a list item" is the
fenced one.

## txt

`scripts/humanize.py::_extractor` sends a `.txt` file through the same
`extract_markdown.extract_text` call a `.md` file goes through, so a txt file
carries the same `CANNOT_SEE` list above, unchanged. The only difference is
cosmetic: `scripts/humanize.py::_handler_name` names the handler "txt" in the
report's own Cannot see section when the file's own suffix is `.txt`, so the
printed handler name matches the file a reader is holding. A rule's own `formats` field
gates a txt file through its `txt` key and a markdown file through its `markdown` key. Both
shipped rulebooks carry the two keys on some rules, with the same value on every rule that
carries either, so the two formats gate alike.

## prompt

`scripts/extract_prompt.py` is "the markdown extractor with `format` set to
`prompt` and C149's own carve-out added", never a second parser. Its own
`CANNOT_SEE` constant, copied unchanged:

> "whatever sits inside a recorded C149 span: a fenced or four-space block, which
> C140 already exempts in every format regardless of any heading, and a block
> quote that sits under a heading naming an example or directly follows a line
> that introduces one, which this handler exempts on its own, so C149's own spans
> are recorded and reported and never scanned"

> "a settings file or a hook script inside one of the fourteen prompt_globs
> directories, which the glob's own extension keeps out"

C149's own two shapes are
"Few-shot example blocks, quoted target text": a fenced or four-space block is
the first shape, and a block quote directly under an introducing heading or line
is the second. Both are recorded and reported the same way the markdown
shapes above are, at zero weight, never silently dropped.

## code

`scripts/extract_code.py` is the extractor for a Python, JavaScript or TypeScript file. It reads comments
through `tokenize` and docstrings through `ast`, and each comment block,
docstring and prose string becomes a unit of kind `comment`, `docstring` or
`prose_string`. The code around them is no unit, and no rule reads it. Its own
`CANNOT_SEE` constant, copied unchanged, one clause at a time:

> "a lint config written as code, since the standard library parses a config only
> when it is written as data"

> "string literals ast does not class as docstrings and the prose-string rule does
> not admit, since docstrings are read through ast and comments through tokenize"

> "structural tells with no measured band yet, which are reported as numbers with no
> verdict"

> "an implicit concatenation in docstring position, which is never read as a
> docstring"

> "a comment inside a string, which tokenize reads as the string's own text"

> "a docstring that shares its line with another statement's string, which is read
> as an implicit concatenation, since docstring positions are keyed by line"

> "a file with a lone CR line break, which ast counts as a line end and tokenize does
> not, so its docstrings and strings are not read"

A file adds its own lines after these when the extractor meets one of them: a file
tokenize or ast refuses, a unit whose line ends mix CRLF and LF, an implicit
concatenation in docstring position, and a generated or vendored file skipped under
C146. Five protection rows keep spans out of the scan. C144 records the public API
names, C145 the key and protocol strings, C146 the generated and vendored files, C147
a license header and C148 the strings of a test fixture file.

The write gate scans a Python, JavaScript or TypeScript write at the prose tiers. A post-hoc run
over such a file scans, plans the self-check, writes the candidates file and the report, writes the
rewrites back through each unit's own frame, and runs the project's formatter and tests
once before the write back and once after, restoring the original bytes when either
fails afterwards. On a Python file the formatter is ruff or black and the tests are pytest, and on a
script file the formatter is prettier over the script suffixes and the tests are the package's `npm test`,
with every configured formatter run. A rewritten prose string keeps its quote unless the new text holds more of that quote than of the other, the count rule prettier and ruff share, so a rewrite that adds an apostrophe to a single-quoted string is written with double quotes and passes the check. A script the extractor could not read, because the package is absent, a grammar did not load or a syntax error hid its strings, is announced by the hook as "nothing in this file was read" with the reason, never as scanned.

A JavaScript or TypeScript file (`.js`, `.jsx`, `.mjs`, `.cjs`, `.ts`, `.tsx`, `.mts`, `.cts`) goes through the same extractor by way of
`tree-sitter-language-pack`, imported inside that branch alone, so a Python file never loads it. Line
comments group into blocks, a block comment is one unit whose frame keeps its delimiters and leading
stars, a JSDoc block before a function, class or method declaration, or before a const, let or var whose every declarator takes a function value, is a docstring, and a
template string with no substitution is a prose string. The same five protection rows apply, with
`dist/` and `build/` and the `// Generated by` first line under C146. Its own `SCRIPT_CANNOT_SEE`
constant, copied unchanged, one clause at a time:

- text between JSX tags, which the handler reads as markup
- a JSX attribute's string value, the words of a title, an alt text or an aria-label included, which is kept under C145 as markup and never read as prose
- a template string holding a substitution or read by a tag such as sql or css, the tagged one kept under C145 as a protocol string, and every string literal the prose-string rule does not admit
- an ESLint config in any file other than eslint.config.js, eslint.config.mjs, eslint.config.cjs, .eslintrc.json, .eslintrc, .eslintrc.cjs and .eslintrc.js, such as eslint.config.ts or .eslintrc.yml, and a rule a shared config or a plugin preset turns on, since those seven files are read by a text scan for each rule's own name
- structural tells with no measured band yet, which are reported as numbers with no verdict

A file prints its own line when the package is absent, when a grammar did not load, when the parser
met a syntax error at a named line and read what it could, when the line ends are mixed, and when
C146 skipped it.

## pptx

`scripts/extract_pptx.py::extract` is the extractor for a slide deck. It reads the file through
python-pptx, imported inside that function alone, so a markdown or code run never loads it. Per
slide the units come in one order. A title or center-title placeholder's paragraphs are units of
kind `title`. Every other text frame's paragraphs are `paragraph` units, with a group's shapes in
the group's place. Each table cell's paragraphs are `table_cell` units. A chart's title, its axis
titles, its series names and the categories of its first plot that has any are `label` units, and
so are the text nodes of a SmartArt diagram. The paragraphs of the notes slide are `notes` units.
A blank paragraph is no unit. Its own `CANNOT_SEE` constant, copied unchanged, one clause at a
time:

> "images and any text inside them"

> "alt text on a picture or a shape"

> "the text of a slide layout or master"

> "a chart's data labels and any chart text outside its title, axis titles, series names and
> categories"

> "a comment part"

> "the text a binding template's own dump would exclude, since the run has no template input"

> "an embedded workbook behind a chart"

A deck adds its own lines after these when the walk meets one of them: a chart whose API raised,
named by its slide and the exception class, a SmartArt data part that is absent or did not parse,
a table frame holding no table, a count of the text nodes on the slides the walk did not reach, and
a count of the text nodes in the slide layouts and masters it passed over. A deck python-pptx
refuses is reported as unread with the library's message, and an absent python-pptx gives one line
naming the package and the pip line. Neither gets a candidates file or a brief.

The writable rule is set per unit in its frame. A title, a paragraph, a table cell paragraph and a
notes paragraph are writable. A chart string and a SmartArt text node are scanned, counted and
judged, and a rewrite of one is refused with this reason, shared by the deck, workbook and document handlers:

> "read and counted in this version, the rewrite is left for the human"

C142 is the protection row. `extract_pptx` records a slide-number, date or footer placeholder's
paragraphs and every field's text on `document.protected`, and a paragraph of such a placeholder
or one holding a field is a unit that weighs nothing. A field's text has no unit of its own.

In the default copy mode, a post-hoc judged run over a deck writes `<stem>.humanized.pptx` beside it through
`scripts/extract_pptx.py::write_copy`, and the deck itself is never written. A later judged run
that writes a copy builds it from the deck again and replaces the earlier copy whole, so the copy
holds that run's rewrites alone. The writer opens the bytes whose digest the run recorded, so a
deck that changed on disk since the extract refuses the whole copy. Each rewrite goes into its
paragraph's own runs, one line per side of each line break, each line spread over its runs by
`scripts/office.py::distribute` with every cut moved back to a word boundary, and every run
property and break keeps its place. A rewrite is refused, and its paragraph left as it was, for a
unit that is not writable, for a field in the paragraph, for a rewrite with no word, for a control
character other than a tab or a newline, for a lone surrogate or the noncharacters U+FFFE and
U+FFFF, for a newline count that differs from the paragraph's breaks, for text on a line that holds
no run, and for a paragraph that changed since the extract or is gone. The four reasons the module
names as constants read:

> "the paragraph holds a field (a:fld), whose text a rewrite would move or lose"

> "the rewrite empties the paragraph"

> "the paragraph's runs, breaks and fields differ from the ones the extract read, so it changed
> between extract and write"

> "the paragraph the locator names is absent from the deck"

A rewrite spread over runs that include a hyperlink, and a rewrite that split a word across runs,
each put a line under Cannot see. When every rewrite is refused, no copy is written. A rewrite
that holds a character no `a:t` can hold is refused with a reason that names the character and ends
"which cannot be written into an a:t".

Under `office_write: in-place`, which the marker's key or the run flag `--office-write in-place`
sets, the same judged run writes the deck itself and no copy, through
`scripts/extract_pptx.py::write_in_place`. It replaces the changed slide and notes parts alone and
keeps every other zip entry byte for byte, through a temporary file beside the deck that ends in
the deck's suffix and one rename, so a failure at any step leaves the deck's bytes as they were.
The temporary file is flushed and synced to the disk before the rename. A rename refused by a held
handle is tried five times in all, a tenth of a second apart, before the write is refused with the
original, or the temporary file beside it, named as held, and a temporary file the run cannot
remove is named in the reason. The workbook and the document write through the same shape.
The writer names each entry from the package before it reads `.slides`, since python-pptx renames
slide parts in memory when it reads them. It refuses what the copy refuses with the same reasons,
and refuses the whole write when no part holds a written paragraph, with a reason that ends "so
the in-place write could not name the entry to replace". A changed part keeps the original's
declaration and is canonically equal outside the rewritten paragraphs, and the byte identity of
each changed part is printed and never asserted. The writer reads the rebuilt file back through
the extractor and discards it when a unit does not read as its rewrite, and it reads the original
again just before the rename. A written deck owes the report the hyperlink and split-word lines,
then one line naming the parts replaced, `scripts/office.py::IN_PLACE_PARTS`, whose total counts
the package's zip entries, `[Content_Types].xml` and the relationship entries included:

> "{path} was written in place, {count} of {total} package parts replaced ({names}), and every
> other part is byte for byte what it was"

When every rewrite is refused, nothing is written, the deck is unchanged and no answer is spent.

## xlsx

`scripts/extract_xlsx.py::extract` is the extractor for a workbook. It reads the file through
openpyxl, imported inside that function and inside `write_copy` and `write_in_place` alone, and
loads it twice, once for the formulas and once
for the values Excel cached for them. Per worksheet, in the workbook's own order, the units come in
one order. The sheet's name is a `label` unit and never a title. A typed string cell is a
`table_cell` unit, and so is the cached string of a formula cell, whose surface ends in "(formula
result)". A typed string is a value of type str that does not start with an equals sign, and its
text is the value stripped. A number, a date, a boolean, a blank string and an error value typed
with no formula are no unit. A cell comment is a `notes` unit. Each header and footer part that
holds text is a `label` unit, and so is a chart title and an axis title. A hidden sheet's surfaces
carry " (hidden)" after its name. Its own `CANNOT_SEE` constant, copied unchanged, one clause at a
time:

> "formula-built cell text when no cached value is stored"

> "a chart's series names and category labels, which reference cells the walk already reads as
> cells"

> "chart text outside the chart XML openpyxl reads, such as data labels and drawing text boxes"

> "a data validation's prompt and error text"

> "a comment's author"

> "a threaded comment as Excel shows it, since openpyxl reads the legacy comment written beside
> it, and that comment's placeholder paragraph is read as the comment's prose"

> "an image and any text inside it"

> "a pivot table's captions"

> "the side-by-side copy's own gap, since openpyxl writes formulas without their cached values, so
> a run on the copy sees none of the formula-built text and Excel recalculates on open"

> "the side-by-side copy's own losses, since openpyxl's save drops images when Pillow is absent,
> drawing shapes and text boxes, data validation and conditional formatting extensions,
> sparklines and slicers, and resets the size and place of each comment box"

A workbook adds its own lines after these when the walk meets one of them: each distinct warning
openpyxl raised while loading, a chartsheet, which holds a chart alone and so is named and not
read, a count of formula cells that carry no cached value, a count of formula cells whose cached
result is an error value, and a count of string cells that start with an equals sign and so are no
unit. An absent openpyxl and a workbook it refuses are reported as unread, as for a deck.

The writable rule is set per unit in its frame. A typed cell, a comment and a header or footer
part are writable. A formula cell's cached string, a sheet name and chart text are scanned,
counted and judged, and a rewrite of one is refused with the shared reason quoted under pptx.

C143 is the protection row. `extract_xlsx` records a machine key, a cell string with two or more
bars and no spaced bar, on `document.protected`, and the unit weighs nothing. It reads a formula's
cached string for a key too, and it records each formula's own text, which no unit holds.

In the default copy mode, a post-hoc judged run over a workbook writes `<stem>.humanized.xlsx` beside it through
`scripts/extract_xlsx.py::write_copy`, and the workbook itself is never written. A later judged run
that writes a copy builds it from the workbook again and replaces the earlier copy whole, so the
copy holds that run's rewrites alone. A typed cell is written with the padding the extract stripped
kept around the rewrite. A comment and a header or footer part are written whole, and a header or
footer part must keep the same field codes in the same order. A rewrite is refused for a unit that
is not writable, for a rewrite with no word, for a control character other than a tab, a line feed
or a carriage return, for a lone surrogate or the noncharacters U+FFFE and U+FFFF, for a rewrite
that starts with an equals sign, for one that is an error value, for a changed header code, and for
a cell, comment or sheet that changed since the extract or is gone. Two of the reasons are
constants:

> "the rewrite starts with an equals sign, which a workbook cell reads as a formula"

> "the sheet, cell or comment the locator names is absent from the workbook"

A rich text cell a rewrite touches is written as plain text, and a line under Cannot see says its
runs were flattened in the written file. The copy asks Excel to recalculate on open, because openpyxl
writes formulas without their cached values. When every rewrite is refused, no copy is written. A
rewrite that holds a character no cell, comment or header can hold is refused with a reason that
names the character and ends "which cannot be written into" and the cell, the comment or the header
or footer part.

Under `office_write: in-place` the same judged run writes the workbook itself and no copy, through
`scripts/extract_xlsx.py::write_in_place`. Each changed entry is edited through lxml on its raw
bytes and every other entry is byte for byte what it was, every cached value included, through a
temporary file beside the workbook that ends in its suffix and one rename. lxml is imported by name
inside that function alone, with every helper taking the `etree` module as an argument, since
openpyxl holds no tree and its own one-sheet writer re-types every string cell and drops a
header and footer. An absent lxml refuses the write with the package named. A typed cell is written
into the sheet part. A shared string cell takes a new string appended to the shared strings part,
`uniqueCount` raised and `count` left, so a string two cells share keeps the other cell. An inline
string cell's `is` becomes one `t`. A comment's `text` element becomes one `t` in the comments part
the sheet's own relationships name, a relative target read from the sheet part's folder. A header
or footer part is written by replacing the unit's text once inside its own raw segment of the
node's text, so every font, size, color and field code keeps its place and no space is added
after a size code. The workbook part takes `fullCalcOnLoad="1"` in three states: set on a `calcPr`
that lacks it, a `calcPr` inserted in the schema order openpyxl carries when the part has none, and
the part left byte for byte when the flag already reads 1.

The in-place write refuses what the copy refuses through the one `_check_unit`, with the same
reasons. It adds a cell stored with another type, with this reason, whose type is named:

> "the cell is stored with the type {type}, and the in-place write rewrites a shared string or an
> inline string alone"

and a cell stored as a shared string whose workbook names no shared strings part the package
holds, with its own reason:

> "the workbook lists no shared strings part for a cell stored as a shared string"

The changed reason covers a cell whose raw string no longer reads as the unit's text, and a header
segment that no longer reads as the unit once its codes are taken out or that holds the text twice,
so the whole of the changed reason reads:

> "the text differs from the one the extract read, so the workbook changed between extract and
> write"

A header rewrite that holds a code or opens on a digit or a space right after a size code is
refused alone with:

> "the rewrite would read as a header code or as part of the one before it, so the header's codes
> would change"

A comment on a sheet whose own relationships hold a threaded comment is refused, and a comment on
another sheet of the same workbook is written. The clause under Cannot see on a threaded comment
stays, since the extract still reads the legacy comment. The reason reads:

> "the comment sits on a sheet whose relationships hold a threaded comment, whose text Excel shows
> from its own part, so the legacy text openpyxl reads is never what a reader sees"

A comment or a rich cell a rewrite touches owes the flattened line, `extract_xlsx.FLATTENED`, which
opens "the rewrite of" and the unit's surface and ends:

> "was written as plain text, so the rich text runs of its {kind} were flattened"

A written cell alone owes the stale results line and sets the recalculation flag, and a write of
comments and header parts alone owes neither and leaves the flag as it was:

> "formulas that read a rewritten cell show their old result until Excel recalculates, which the
> file now asks for on open"

That line comes before the line naming the parts replaced, `office.IN_PLACE_PARTS`, quoted under
pptx. The two side-by-side copy clauses of the Cannot see list above describe a copy that no
in-place run writes, so an in-place run drops both from its report, a report run included, and a
copy run prints them whole. When every rewrite is refused, nothing is written.

## docx

`scripts/extract_docx.py::extract` is the extractor for a Word document. It reads the file through
python-docx, imported inside that function and inside `write_copy` and `write_in_place` alone. The body is walked in
document order, so paragraphs and tables come as they sit, and a table's cells and nested tables
come row by row. A body paragraph is a `heading` for a style named Title or starting Heading, a
`list_item` for numbering or a style starting List, a `caption` for a Caption style, and a
`paragraph` otherwise. Every paragraph in a table cell is a `table_cell` unit. Then come the
headers and footers of each section, the default, first page and even page ones, each paragraph a
`label` unit. A header or footer linked to the previous section is passed over. The footnotes and
endnotes parts follow, each note paragraph a `notes` unit, and last the alt text of every drawing,
each a `label` unit. A paragraph's text is read at the `w:t` level, with a tab, a line break and a
hyphen rendered as the separators they stand for, and a paragraph with no text is no unit. Its own
`CANNOT_SEE` constant, copied unchanged, one clause at a time:

> "a text box or a shape's text"

> "a content control's text"

> "text inside a tracked deletion"

> "a comment part"

> "SmartArt"

> "a field's instruction text, which is read through its last result alone"

> "a hyperlink's target"

> "an image and any text inside it"

> "footnote and endnote text, which is read and counted and never rewritten in this version"

A document adds its own lines after these when the walk meets one of them: a footnotes or endnotes
part that could not be parsed, a note whose `w:id` is missing or not a whole number, a count of
tracked changes whose text was passed over, and a count of the `w:t` nodes in the parts the walk
reads that it did not reach. python-docx raises no warning to list. A part with no `w:body` and a
file python-docx refuses are reported as unread, and so is an absent python-docx.

The writable rule is set per unit in its frame. A body paragraph, a table cell paragraph and a
header or footer paragraph are writable. A note and an alt text are scanned, counted and judged,
and a rewrite of one is refused with the shared reason quoted under pptx. A paragraph whose frame
names a blocking element is refused too, with the element named. The blocking elements include a
drawing, a note or comment reference, a field's parts, a hyphen element, a tracked change and a
content control.

C141 is the protection row. `extract_docx` records a paragraph styled Quote, Intense Quote or Block
Text as quoted material and one styled Bibliography as a citation on `document.protected`, and the
unit weighs nothing.

In the default copy mode, a post-hoc judged run over a document writes `<stem>.humanized.docx` beside it through
`scripts/extract_docx.py::write_copy`, and the document itself is never written. A later judged run
that writes a copy builds it from the document again and replaces the earlier copy whole, so the
copy holds that run's rewrites alone. A paragraph is found through its locator, the part and the
index of its `w:p` among every `w:p` of that part. The rewrite is split at its tabs and line breaks
into one segment per side of each separator, and each segment is spread over the `w:t` nodes of its
own segment by `scripts/office.py::distribute`, with every cut moved back to a word boundary. Each
node's text is set directly with `xml:space="preserve"`, and `Run.text` is never called, so every
run property, hyperlink and other element keeps its place. A rewrite is refused for a note or an
alt text, for a blocking element, for a rewrite with no word, for a control character other than a
tab or a newline, for a lone surrogate or the noncharacters U+FFFE and U+FFFF, for tabs and line
breaks that differ in count or order from the paragraph's separators, for text on a side of a
separator that holds no `w:t`, for a paragraph that changed since the extract, and for a locator
that names no paragraph or a linked header. Three reasons are constants:

> "the rewrite empties the paragraph"

> "the paragraph the locator names is absent from the document"

> "the rewrite's tabs and line breaks come in another order than the paragraph's separators"

A written rewrite can owe the report a line under Cannot see, which opens "the rewrite of" and the
unit's surface. A rewrite spread over runs that include a hyperlink adds this ending:

> "was spread over runs that include a hyperlink, so the words under the link may have moved with
> the rewrite"

A rewrite in a first page or even page header or footer that Word does not show adds this ending,
where the setting is the section's different first page (`w:titlePg`) or the settings' different
odd and even pages (`w:evenAndOddHeaders`):

> "was written into a header or footer that Word shows only when {setting} is on, and this
> document leaves it off"

A rewrite that split a word across runs adds the line shared with the deck and the workbook. When
every rewrite is refused, no copy is written. A rewrite that holds a character no `w:t` can hold is
refused with a reason that names the character and ends "which cannot be written into a w:t".

Under `office_write: in-place` the same judged run writes the document itself and no copy, through
`scripts/extract_docx.py::write_in_place`. It writes each rewrite into the paragraph's own `w:t`
nodes through the same refusals and the same segment-by-segment spread, and replaces the document
part, or the header or footer part a paragraph lives in, alone. Every other zip entry is byte for
byte what it was, through a temporary file beside the document that ends in its suffix and one
rename. The part is found among the package's parts through the written paragraph's root, so no
header part is created, and the write refuses the whole when no part holds a written paragraph,
with a reason that ends "so the in-place write could not name the entry to replace". The changed
part keeps the original's declaration and is canonically equal outside the rewritten paragraphs,
with the byte identity of the part printed and never asserted. It is not byte for byte the original
even with the old text put back, since each written `w:t` takes `xml:space`. A rewrite with fewer
characters than its segment has `w:t` nodes leaves one run empty, its properties kept, and the
split-word line names the paragraph. The owed lines of a written document come after the rename and
before the line naming the parts replaced, `office.IN_PLACE_PARTS`, quoted under pptx, whose total
counts the package's zip entries. When every rewrite is refused, nothing is written.

## pdf

`scripts/extract_pdf.py::extract` is the extractor for a PDF. It reads the file through pypdf,
imported inside that function and inside `write_markdown` alone. Plain extraction gives no
paragraph boundary inside a page, so the page is the unit. A page that holds a text layer is one
`paragraph` unit with the surface "page N", the locator page N and block 0, and a frame that says
`pdf_page` and writable. A page whose stripped text runs under 20 characters and that holds at
least one image is image-only, and a page with no text and no image is empty. Each of those is
named by its number in one line and is no unit, since the build runs no OCR. The 20 is
`scripts/extract_pdf.py::IMAGE_ONLY_MAX_CHARS`. Its own `CANNOT_SEE` constant, copied unchanged,
one clause at a time:

> "reading order not verified, since a two-column text layer can come out interleaved"

> "paragraph boundaries inside a page, which plain extraction does not give, so the page is the
> unit"

> "an image-only or scanned page, which is reported and skipped with no OCR"

> "annotations and form field values"

> "running headers and footers, which the text layer mixes into the page"

> "text inside an image"

A PDF adds its own lines after these when the read meets one of them: an image-only page with its
character count and image count, an empty page, a page whose images could not be counted, a page
whose text pypdf could not extract, a page whose lone surrogate characters were read as U+FFFD,
and a count of the warnings pypdf logged while it read the file, which are held back from stderr.
Four lines are constants:

> "the file is encrypted, so no page of it was read"

> "the file is encrypted with a cipher pypdf reads only through another package, so no page of it
> was read: {error}"

> "the file holds no page"

> "pypdf logged {count} warnings while reading the file"

A file with an owner password alone opens with the empty password and is read. A PDF that yields
no unit, because every page is image-only or empty, the file is encrypted or holds no page, or
pypdf is absent, is reported as unread. It gets no candidates file, no brief and no delivery. A
file pypdf cannot read is reported as unread with the library's message.

Every page unit is writable, since the delivery holds the rewritten text of any page. The PDF
extractor records no span on `document.protected`.

A PDF is read when it is named directly or when the marker adds `**/*.pdf` to its include list,
because no default glob carries it. A directory run's summary line names the count of PDFs it
passed over.

A post-hoc judged run over a PDF writes `<stem>.humanized.md` beside it through
`scripts/extract_pdf.py::write_markdown`, and the PDF itself is never written. A later judged run
that writes a delivery builds it from the PDF again and replaces the earlier delivery whole, so the
delivery holds that run's rewrites alone. The writer reads the PDF again from the bytes whose
digest the run recorded. The delivery opens with a title line that names the PDF and a line saying
each page's text is verbatim as pypdf read it. Then comes "## Page N" and the page's text, with the
rewrite applied where one was accepted, for each page that holds a text layer, and one sentence for
each page the walk skipped, in page order. The file is written only when at least one rewrite
applied. A rewrite is refused for a rewrite with no word, for a lone surrogate, which UTF-8 cannot
hold, and for a page that changed since the extract or is gone. Two reasons are constants:

> "the rewrite empties the page"

> "the page the locator names is absent from the file"

Under `office_write: in-place` a PDF is still never edited. The delivery is written
as before, and the run adds one line to Cannot see once the delivery is on disk,
`scripts/humanize.py::PDF_NEVER_IN_PLACE_LINE`:

> "the marker asks for in-place writes, and a PDF is never edited in place, so the markdown
> delivery was written beside it"

## retro

`/humanize retro <draft> <final>` reads two files in the formats `scripts/retro.py::FORMATS`
names, markdown, txt and docx. A markdown or txt file goes through `extract_markdown` and a Word
file through the docx handler above, so each side carries its handler's own cannot-see list. Any
other suffix is refused with the three named. A deck, a workbook or a PDF is a side-by-side copy or
a delivery in this version, so none is a final of the writer's own.

The extractors stay as they are, and the retro cuts each unit into pieces after extraction. A
line opening on a list marker is a piece with the marker stripped, a line indented by two spaces
continues the piece before it, and any other non-blank line is a piece of its own. A Word
paragraph is one piece with its marker stripped. The alignment pairs the pieces of the two sides,
so a draft whose body holds no bullet reads no divergence. A Word side its library cannot read
refuses the retro whole with the missing-package or floor line the handler prints.

The flag rate reads each side through its own handler with every mask intact. The comparable
number sets aside each rule whose `formats` field turns it off for the other side's format,
reading the `markdown`, `txt` or `docx` key of the rule, and the report names the rules set aside.

## The inline gate, across every format

`scripts/gate_write.py` sees Write and Edit tool calls only. A file written by a
shell command is never scanned, and the FileChanged event carries no power to
block. This is printed in every report's own Limits section. A Write or Edit to a
deck, a workbook, a document or a PDF is answered with one note,
`scripts/gate_write.py::ROUTE_NOTES`, which reads as follows, and the hook reads
nothing of the file:

> "this file is read by the post-hoc run alone, so this write was not scanned"
