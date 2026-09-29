# T5 PBS visual review boundary

The optional [visual-review receipt](../artifacts/t5-pbs-visual-review-audit.json)
records an agent-authored, read-only inspection of all three pages of the
rights-declared PBS PDF. The observations are bound to the PDF SHA-256 and to
the local `pdftoppm` render identity; rendered images are not redistributed.

The review records two extraction leads for later human/source-owner review: a
visible `Sort By ...` string inside the page-2 safety box that may be export UI
residue, and chemical subscripts/separator differences between the page-3
render and text extraction. It also notes that material cards have not yet
been structured. These observations do not resolve the source, create a
machine-readable recipe, or authorize laboratory work.

`python scripts/verify_t5_pbs_visual_review.py --verify` checks the committed
receipt and its hash-bound contract without requiring the excluded PDF. Passing
means only that the authored review record is internally consistent. The
complete visual omission review, independent procedure validation, biosafety
review, human acceptance, execution, and scientific Claim remain open.
