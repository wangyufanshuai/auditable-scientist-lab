# T1 MAVEN small-forces-file exploratory inventory

The [NAIF MAVEN SFF directory](https://naif.jpl.nasa.gov/pub/naif/MAVEN/misc/sff/)
contains reconstructed small-forces files near both fixed 2014 cruise arcs.
This is a **post-hoc source-discovery check**, not a predeclared scientific
test. The [inventory](T1_MAVEN_SFF_EXPLORATORY_INVENTORY.json) pins the local
directory listing and nine nearby files by SHA-256; the
[audit](../artifacts/t1-maven-sff-exploratory-audit.json) parses every `R`
record's raw timestamp strings and checks their shapes and duplicate content.
The source files remain ignored locally and are not redistributed.

| Nearby reconstructed files | Raw timestamp span in the files | Records | Relation to fixed arc |
|---|---|---:|---|
| `140425_140426` and `140426_140427` | 2014-04-26 03:52:44.540 to 04:04:59.943 | 280 each | Before the 2014-04-29/30 arc |
| `140502_140503` and `140503_140504` | 2014-05-03 03:55:23.989 to 04:05:00.415 | 280 each | After the 2014-04-29/30 arc |
| `140627_140628` and `140628_140630` | 2014-06-28 03:55:12.369 to 04:04:48.522 | 272 each | Before the 2014-06-28/29 arc |
| `140630_140702` and `140702_140704` | 2014-07-02 17:15:03.738 to 18:49:12.469 | 1,001 each | After the 2014-06-28/29 arc |
| `140704_140705` | 2014-07-05 03:59:19.936 to 04:02:14.697 | 80 | After the 2014-06-28/29 arc |

Each of the four file pairs has identical `R` records after removing the
production-time field; the different filenames and hashes do not represent
independent measurements. Notably, `mvn_rec_140628_140630_v03.sff` has a
filename spanning the second arc's date, but its actual records end early on
June 28. The source directory listing contains no reconstructed `.sff` file
with a name directly specifying April 29/30 or June 29. These observations
do **not** prove that the small-force history is complete or that no force
acted in either arc.

The [MAVEN Science Data Center ancillary page](https://lasp.colorado.edu/maven/sdc/public/pages/datasets/ancillary.html)
identifies SFF files and links two SIS documents for their format and fields.
Both linked PDFs returned HTTP 404 during this inspection. Consequently, the
time scale, vector frame, units, and meaning of the SFF numeric columns remain
unverified. The official [ancillary archive SIS](T1_MAVEN_ANC_SIS_SOURCE_NOTE.md)
documents DRF and event products but does not provide the SFF `R` record
layout. This audit does not extract an inertial impulse or admit any SFF
value into orbital propagation. The independent tracking, uncertainty,
scientific-holdout, and mission-validation gates remain open; the Claim stays
`unverified`.

Run `python scripts/verify_t1_maven_sff_inventory.py --verify` to check the
local byte-pinned files, record inventory, and saved audit. This is source
integrity evidence for the inspected files only.
