# T1 fixed-date DE440s geometry diagnostic

The optional source is NAIF's unmodified `de440s.bsp` kernel, downloaded from
<https://naif.jpl.nasa.gov/pub/naif/generic_kernels/spk/planets/de440s.bsp>.
NAIF's [checksum list](https://naif.jpl.nasa.gov/pub/naif/generic_kernels/spk/planets/aa_checksums.txt)
records MD5 `3917ee56769db332790c751e2168843d`; this project's downloaded
kernel has SHA-256 `c1c7feeab882263fc493a9d5a5b2ddd71b54826cdf65d8d17a76126b260a49f2`.
The binary is kept outside Git. The adapter refuses any other bytes and never
downloads during evaluation or replay.

NAIF's [rules](https://naif.jpl.nasa.gov/naif/rules.html) say that kernels on
the NAIF server may be downloaded and used by anyone, and that redistribution
of NAIF-distributed kernels is permitted if they have not been modified. The
same page encourages acknowledgement of SPICE/NAIF and the kernel-producing
teams. We cite NAIF/JPL and Park et al., *The JPL Planetary and Lunar
Ephemerides DE440 and DE441*, DOI `10.3847/1538-3881/abd414`, as identified
in the [DE440 technical comments](https://naif.jpl.nasa.gov/pub/naif/generic_kernels/spk/planets/de440_tech-comments.txt).
These terms apply to the NAIF kernel; they do not license unrelated source
projects, images, mission products, or a scientific publication.

The adapter uses optional `spiceypy==8.1.0` with CSPICE N0067. It requests
geometric states (`NONE` aberration) relative to the Sun in the J2000 frame,
using ET seconds computed from Julian Date TDB and returning km and km/s.
No leapsecond kernel or UTC conversion enters this calculation. The two
departure epochs were fixed before evaluation: JD TDB `2460584.5`
(2024-10-01 00:00 TDB) and `2461375.5` (2026-12-01 00:00 TDB). At each date,
the Earth and Mars-barycenter radii set a circular Hohmann time of flight;
the actual Mars-barycenter position at that arrival date is compared with
the ideal opposite-Earth apoapsis position.

DE440s contains Mars **barycenter** (4), not the Mars center (499). This is a
fixed-date geometry comparison against an observation-fitted ephemeris model,
not a propagated spacecraft trajectory, encounter solution, launch window
optimization, independent mission validation, or a holdout test. Its source
is tracked as real ephemeris data, while the mission Claim remains
`unverified`. A Mars-center kernel, spacecraft dynamics, independent task
comparison, and expert review remain open gates.

Run `python scripts/fetch_de440s.py` once to obtain the optional kernel, then
`python scripts/verify_t1_de440s_ephemeris.py --verify` for a local dynamic
rerun. The pinned JSON snapshot and audit can be checked statically without
the 31 MiB kernel, but that does not count as a dynamic replay.
