# T1 archived MAVEN spacecraft-state source

The [MAVEN PDS4 SPICE archive](https://naif.jpl.nasa.gov/pub/naif/pds/pds4/maven/maven_spice/document/spiceds_v011.html)
contains a JPL Navigation team reconstructed cruise and Mars orbit insertion
spacecraft trajectory. This optional source probe uses the exact [cruise SPK](https://naif.jpl.nasa.gov/pub/naif/pds/pds4/maven/maven_spice/spice_kernels/spk/maven_cru_rec_131118_140923_v1.bsp)
`maven_cru_rec_131118_140923_v1.bsp`, PDS LIDVID
`urn:nasa:pds:maven.spice:spice_kernels:spk_maven_cru_rec_131118_140923_v1.bsp::1.0`.
Its [product label](https://naif.jpl.nasa.gov/pub/naif/pds/pds4/maven/maven_spice/spice_kernels/spk/maven_cru_rec_131118_140923_v1.xml)
states 4,797,440 bytes, MD5 `8d7c55ef3bb935ad487c529f5be5343d`, and
UTC coverage 2013-11-18 19:20:42 through 2014-09-23 11:58:53. The locally
downloaded binary also has SHA-256
`07c76dfc2a1f66a54b4dd74105b2a5a70d72192813abee3659a74d4d21988dc5`.
It remains Git-ignored. `scripts/fetch_maven_cruise.py` verifies all three
byte-level constraints before admitting it.

The probe loads that SPK first, then the checksum-pinned MAR099s and DE440s
kernels. The latter two provide the planetary and Mars-center chain; body
`-202` supplies the MAVEN spacecraft trajectory. The MAVEN SPK itself also
contains planetary segments, so load order is part of the contract. Its
`-202` segments are J2000 SPK type 1, centered on the Sun (`10`) during the
sampled cruise point and on Mars barycenter (`4`) at the two sampled approach
points. The SPICE chain from spacecraft to Mars center is checked against
explicit spacecraft-minus-center state subtraction. All states are geometric
(`NONE`), J2000, km and km/s. Times are numeric TDB seconds past J2000
(JD TDB 2451545.0), with no UTC conversion or leapsecond kernel in the probe.

The three sample ETs are `446904000`, `464616000`, and `464702400` seconds.
They were chosen **after inspecting** the archive and segment transition, so
they are exploratory checks, not a holdout. A source match demonstrates that
the archived reconstructed spacecraft trajectory can be read with a bounded,
replayable coordinate contract. It does not independently propagate the
spacecraft, validate any force or maneuver model, compare independent NAV
solutions, verify Hohmann transfer performance, or establish encounter
accuracy. The NAV SPK and planetary kernels may share upstream models; they
must not be counted as independent ephemeris confirmations. The mission Claim
remains `unverified`.

[NAIF rules](https://naif.jpl.nasa.gov/naif/rules.html) permit download and use
of NAIF-hosted kernels and redistribution of unmodified kernels. We do not
redistribute the binary. [NAIF's credit guidance](https://naif.jpl.nasa.gov/naif/credit.html)
asks users to credit ancillary-data providers, and [PDS citation guidance](https://pds.nasa.gov/datastandards/citing/)
recommends product LIDVIDs with the bundle or collection citation. This audit
records the product identifier and rights source; publication still needs a
formal citation and domain expert review.

Run `python scripts/fetch_maven_cruise.py --verify`, then
`python scripts/verify_t1_maven_source.py --verify` for dynamic recomputation.
The committed small snapshot can also be checked without the binary, but
static checking alone cannot authenticate a fresh SPK evaluation. The next
scientific step is a preregistered, independent spacecraft propagation and
MAVEN NAV comparison with a declared maneuver and force model, numerical
tolerances, holdout dates, and uncertainty budget.
