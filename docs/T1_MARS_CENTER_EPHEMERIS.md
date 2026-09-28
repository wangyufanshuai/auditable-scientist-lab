# T1 fixed-date Mars-center geometry diagnostic

This optional audit combines two unmodified NAIF/JPL SPK kernels. Planetary
states come from [DE440s](https://naif.jpl.nasa.gov/pub/naif/generic_kernels/spk/planets/de440s.bsp)
(official MD5 `3917ee56769db332790c751e2168843d`, local SHA-256
`c1c7feeab882263fc493a9d5a5b2ddd71b54826cdf65d8d17a76126b260a49f2`).
The Mars mass-center offset relative to Mars barycenter comes from
[MAR099s](https://naif.jpl.nasa.gov/pub/naif/generic_kernels/spk/satellites/mar099s.bsp)
(official [MD5](https://naif.jpl.nasa.gov/pub/naif/generic_kernels/spk/satellites/aa_checksums.txt)
`fd7302dfbaa0c63ce85b1e98923ee6a1`, local SHA-256
`997dc93ba640e476da7a494d2237dcdeb145e528db37be8ccee588c615e4e1ff`).
Both binaries stay outside Git. The read-only adapter refuses different bytes.

NAIF's [satellite SPK guide](https://naif.jpl.nasa.gov/pub/naif/generic_kernels/spk/satellites/AAREADME_Satellite_SPKs)
identifies Mars center as body 499 and explains its state is relative to the
Mars system barycenter (4). The [MAR099s technical comments](https://naif.jpl.nasa.gov/pub/naif/generic_kernels/spk/satellites/mar099s.cmt)
state that its short kernel includes bodies 401, 402 and 499 from 1995 through
2049 and overlapping planetary bodies from DE440. We load MAR099s first and
DE440s second, giving DE440s precedence for planetary states; the direct
`MARS`-relative-`SUN` SPICE chain is checked against the explicit sum of
DE440s barycenter and MAR099s 499/4 states. The two departure Earth and Mars
barycenter states must also equal the earlier DE440s snapshot exactly.

The dates remain JD TDB `2460584.5` and `2461375.5`. For each, the ideal
circular Hohmann time is recomputed using Earth and Mars **center** departure
radii. The Mars center and barycenter position gaps are compared at the same
ideal arrival epoch and to the same ideal target point. J2000, geometric
(`NONE`) states use km and km/s; ET is derived from JD TDB, with no UTC or
leapsecond conversion. The resulting center/barycenter separation is under
0.2 m at both arrivals, while the ideal-position gaps remain tens of millions
of kilometers. These scales are diagnostic, not a preregistered holdout test.

[NAIF's rules](https://naif.jpl.nasa.gov/naif/rules.html) permit download and
use of NAIF server kernels and redistribution of unmodified NAIF-distributed
kernels; this project does not redistribute either binary. These rules do not
establish rights in unrelated mission products or scientific validity. The
two kernels both incorporate DE440 planetary information, so they are not
independent planetary ephemeris confirmations. No spacecraft is propagated,
no encounter or launch window is solved, and no mission trajectory is
validated. The mission Claim stays `unverified`; spacecraft dynamics,
independent mission comparison, and expert review remain open.

Run `python scripts/fetch_mar099s.py` once, then
`python scripts/verify_t1_mars_center_ephemeris.py --verify` for a dynamic
offline recheck with the already pinned DE440s kernel and `spiceypy==8.1.0`.
The small JSON snapshot and audit can be checked statically without either
binary, but static checking does not count as a dynamic kernel rerun.
