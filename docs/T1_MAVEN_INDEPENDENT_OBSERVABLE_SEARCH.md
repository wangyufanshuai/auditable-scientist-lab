# T1 MAVEN independent-observable source search

Source search date: 2026-09-27. This is a source-discovery note, not a data
admission or a scientific validation receipt.

The [PDS MAVEN ROSE raw TNF collection](https://pds.nasa.gov/ds-view/pds/viewCollection.jsp?identifier=urn%3Anasa%3Apds%3Amaven.rose.raw%3Adata.tnf)
is an official raw radiometric tracking collection, LIDVID
`urn:nasa:pds:maven.rose.raw:data.tnf::1.32`, DOI
`10.17189/1517634`. Its catalog describes DSN TRK-2-34 Tracking and
Navigation Files and gives coverage from **2016-02-19** through **2025-11-14**.
The current two NAV short arcs are in the **2014 cruise** interval. Therefore
this cataloged ROSE TNF collection cannot serve as an independent observation
for those two arcs. Do not pair a 2016–2025 radio-science record with a 2014
cruise state or call the current NAV endpoint comparison independent.

The [MAVEN SPICE archive guide](https://naif.jpl.nasa.gov/pub/naif/pds/pds4/maven/maven_spice/document/spiceds_v011.html)
describes the cruise SPK as a **reconstructed trajectory determined by the JPL
Navigation team**. It is the present comparison target, not a raw observation.
The [ROSE archive software interface specification](https://pds-ppi.igpp.ucla.edu/data/maven-rose-raw/document/maven_sis_ROSE-1.7.pdf)
describes TNF and RSR Level-0 files for radio occultation tracking passes and
their processing chain. Its format description does not establish coverage
for the two 2014 cruise arcs.

One targeted search for public 2013–2014 MAVEN cruise DSN range/Doppler
records did not identify an official collection with product-level coverage
for the two fixed arcs. This is a **search result, not proof of nonexistence**.

The author-hosted [MAVEN Navigation Overview](https://drewryanjones.com/assets/conf_paper_2016_no1.pdf)
(Jesick et al., AAS 16-237, PDF SHA-256
`969affe7e6d0c8d0a6cbc4dbcdcc46332d429e5e604f004e5e5f1a946231267c`)
confirms that two-way range, Doppler, and delta-DOR were *acquired* during
cruise. This establishes operational measurements, not public product-level
access to the two frozen arcs. The same source documents solar-radiation-pressure
estimation and approximately weekly desaturation events; see the separate
[conditional sensitivity result](T1_MAVEN_DESAT_SENSITIVITY_RESULT.md).

The official [MAVEN ancillary events collection](https://pds.nasa.gov/ds-view/pds/viewCollection.jsp?identifier=urn%3Anasa%3Apds%3Amaven.anc%3Adata.events)
has an operational-events product spanning both fixed arcs. A preregistered
[inspection](T1_MAVEN_OPS_EVENT_SEARCH_RESULT.md) parsed all 185,321 labeled
records: no desaturation/maneuver keyword record falls inside either 24-hour
arc, although explicit reaction-wheel desaturation records fall nearby. This
is catalog evidence about event timestamps, not proof of a complete maneuver
history, an impulse vector, or an independent tracking observable. The official
[ancillary archive SIS](T1_MAVEN_ANC_SIS_SOURCE_NOTE.md) explicitly says the
event list is not exhaustive; its archive also omits some engineering
housekeeping data. The related
[GNC DRF collection](https://pds.nasa.gov/ds-view/pds/viewCollection.jsp?identifier=urn%3Anasa%3Apds%3Amaven.anc%3Adata.drf.gnc)
begins 2014-11-15 and does not cover the fixed cruise arcs.

An [exploratory NAIF small-forces-file inventory](T1_MAVEN_SFF_EXPLORATORY_RESULT.md)
pins nine nearby reconstructed files. Their raw record timestamps lie around
the recorded desaturations outside the fixed arcs; several filenames repeat
the same records with different production times. The linked format SIS PDFs
currently return HTTP 404, so vector meaning, units, frame, and time scale
are not admitted. This inventory cannot replace a reviewed force history.

The next independent-observable admission gate is to locate an official
radiometric product label or archive inventory whose time coverage includes
the frozen 2014 arcs, then inspect its
data rights, measurement semantics, calibration and station/time models, and
upstream dependence on the NAV SPK. A separately reviewed measurement model
and uncertainty budget are required before using any such records for a
mission-level holdout. If no suitable 2014 record is available, choose a new
future-facing task with a predeclared time split and do not reuse the inspected
2014 endpoints as a holdout.
