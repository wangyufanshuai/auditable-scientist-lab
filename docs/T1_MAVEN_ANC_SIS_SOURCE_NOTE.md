# MAVEN ancillary SIS: event-list and source-rights boundary

The official [MAVEN Ancillary Data PDS4 Archive SIS, revision 1.3](https://pds-ppi.igpp.ucla.edu/data/maven-anc/document/maven_sis_anc_20200909.pdf)
is listed in the [PDS document collection](https://pds.nasa.gov/ds-view/pds/viewCollection.jsp?identifier=urn%3Anasa%3Apds%3Amaven.anc%3Adocument),
LIDVID `urn:nasa:pds:maven.anc:document::1.1`. The PDF downloaded from the
official PDS/PPI directory has 1,775,566 bytes and SHA-256
`91295af0366fb13f1a193778de5a558cebdd8c57527e3a66e792bc37bed58572`.
The local copy is ignored and is not redistributed.

Section 2, PDF page 18, explicitly says the mission/science event list "is not
intended to be exhaustive"; it is a reference for unexplained science-data
features. The same page says the ancillary archive excludes some spacecraft
and instrument housekeeping data because of ITAR restrictions, and includes
only engineering data applicable to science processing under a stated
exemption. These are **archive-scope statements**. They do not establish that
any particular unlisted maneuver occurred, or that a specific public product
is restricted. They do establish that zero matching event rows cannot be used
as a completeness proof for the two fixed 2014 NAV arcs.

The PDS archive SIS describes ancillary DRF and event product formats, not the
43-column NAIF SFF `R` record layout. It therefore does not resolve SFF time
scale, frame, units, or numeric-field meaning. The LASP ancillary page points
to separate SFF/SFDF SIS PDFs whose published links returned 404 during this
inspection. SFF numeric values remain inadmissible to the dynamics model.

This is a post-hoc source-interpretation note. It does not change the frozen
event-search protocol, create independent tracking data, or promote the T1
mission Claim beyond `unverified`.
