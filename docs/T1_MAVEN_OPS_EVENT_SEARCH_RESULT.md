# T1 MAVEN operational-event catalog inspection

The [search protocol](T1_MAVEN_OPS_EVENT_SEARCH_PROTOCOL.json) was committed as
`5c1ad36` before opening the events CSV. Its SHA-256 is
`07f7dcc05063d1102835fc1d8549bb776b8c2b6f1ee3dce12f31060e919aee33`.
The [audit](../artifacts/t1-maven-ops-event-search-audit.json) can be rebuilt
from the official [PDS events collection](https://pds.nasa.gov/ds-view/pds/viewCollection.jsp?identifier=urn%3Anasa%3Apds%3Amaven.anc%3Adata.events)
and [operational-events product label](https://pds-ppi.igpp.ucla.edu/data/maven-anc/data/events/ops_events_2013-01-01-00-00-00_2021-11-15-00-00-00.xml).
The product LIDVID is
`urn:nasa:pds:maven.anc:data.events:ops_events_2013-01-01-00-00-00_2021-11-15-00-00-00::1.2`.
The 53,288,544-byte CSV matches the label's MD5
`2968735ba41ef9813878325a656fe9af`; its SHA-256 is
`af9b528afffae7ae7a584030c1a8431f107f80647e2d0635a9f077e70cbbdd73`.
All 185,321 labeled rows were parsed locally. The CSV and label are ignored by
Git pending rights review.

| Fixed 24-hour NAV arc, UTC | All catalog records inside | Desaturation or maneuver keyword records inside | Explicit desaturation start/end records within ±7 days |
|---|---:|---:|---|
| 2014-04-29 23:58:52.815 to 2014-04-30 23:58:52.815 | 2 | 0 | Apr 26 04:00/04:05 and May 3 04:00/04:05 UTC |
| 2014-06-28 23:58:52.816 to 2014-06-29 23:58:52.816 | 0 | 0 | Jun 28 04:00/04:05, Jul 2 17:15/17:20, and Jul 5 04:00/04:05 UTC |

The two records in the first arc are DSN Earth communication-pass events.
The nearby desaturation records explicitly say “Reaction wheel momentum
desaturation event start” or “ended” and come from the Integrated Report.
They are separate timestamped records, not a supplied impulse vector or a
continuous interval estimate. The Jun 28 event ended almost 20 hours before
the second arc began. The [conditional impulse grid](T1_MAVEN_DESAT_SENSITIVITY_RESULT.md)
therefore must **not** be read as an observed impulse in either fixed arc.

An absence of a matching row is evidence about this version of this events
catalog only. It does not prove that no small thrust or unlisted activity
occurred. The product has no event-level inertial delta-v vectors, force
calibration, or independent radiometric measurements for either arc. The
[GNC DRF collection](https://pds.nasa.gov/ds-view/pds/viewCollection.jsp?identifier=urn%3Anasa%3Apds%3Amaven.anc%3Adata.drf.gnc)
starts on 2014-11-15, after both cruise arcs, and the
[ROSE TNF collection](https://pds.nasa.gov/ds-view/pds/viewCollection.jsp?identifier=urn%3Anasa%3Apds%3Amaven.rose.raw%3Adata.tnf)
starts in 2016. Neither collection covers these fixed arcs.

`python scripts/verify_t1_maven_ops_events.py --verify` checks the saved audit
against the label and every CSV row when the official file is present locally.
Core acceptance checks the pinned protocol, saved event inventory, boundaries,
and source fingerprints; on this host it also reruns the full CSV inspection.
The NAV endpoints remain inspected comparison targets, not a scientific
holdout. The mission Claim stays `unverified`.
