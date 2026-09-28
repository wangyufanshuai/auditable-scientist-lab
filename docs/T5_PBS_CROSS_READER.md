# T5: independent full-document text coverage check

This optional audit uses local Poppler `pdftotext` 26.02.0 as a second reader
for the pinned three-page [PBS source](T5_PBS_SOURCE_RESULT.md). It records
the SHA-256 of every extracted page and every ordered line without storing
the protocol text. Each of the 11 existing citation anchors is located in
the second extraction; the citation, abstract, materials, and safety sections
and all six numbered step labels must also appear in their declared pages.
An exact page-text hash gate catches omissions outside those named markers.
Per-page ASCII token overlap with `pypdf` must exceed 94%; the observed
overlap and both readers' unmatched token counts are recorded so the known
line-joining and chemical-glyph differences remain visible.

Run `python scripts/verify_t5_pbs_cross_reader.py --verify` with the pinned
local PDF and Poppler executable. The
[audit](../artifacts/t5-pbs-cross-reader-audit.json) includes three negative
controls: dropping the safety heading, a numbered step label, and a
non-anchor title line must each fail. The PDF and Poppler binary are not
redistributed. The executable hash and version identify this particular
local extractor; its shared-library dependency tree and binary-distribution
license have not been independently audited. Poppler's
[project](https://poppler.freedesktop.org/) identifies its upstream source;
the `pdftotext` [source notice](https://fossies.org/linux/poppler/utils/pdftotext.cc)
states that Poppler changes to that file are GPL version 2 or later.

The source PDF itself declares a Creative Commons Attribution License
without a version. The current
[protocols.io terms](https://www.protocols.io/terms) (effective 2026-01-27,
checked 2026-09-28) also say user-generated
content is CC-BY, while their overview limits use of site Content in an
offline environment. How those statements apply to redistribution or a
future product needs rights review. This project retains only hashes,
locations, short citation anchors, and review flags. Cross-reader agreement
checks extracted text coverage, not complete semantic or visual coverage,
experimental reproducibility, or biosafety. The Claim stays `unverified`,
human review remains required, and execution remains forbidden.
