# T1 MAVEN conditional solar-radiation-pressure sensitivity protocol

This protocol fixes a bounded SRP response grid **before computing its
endpoints**. It reuses the already inspected MAVEN NAV initial states and the
precommitted Sun + Earth-Moon/Mars-barycenter force model. The NAV endpoints
are not a new or independent scientific holdout. The four effective
area-to-mass ratios in the [machine-readable protocol](T1_MAVEN_SRP_SENSITIVITY_PROTOCOL.json)
are generic scenario values, not inferred spacecraft properties. They will
not be fitted or ranked by agreement with the NAV endpoints.

NASA's [solar irradiance page](https://earth.gsfc.nasa.gov/climate/projects/solar-irradiance/science)
states a SORCE-derived total solar irradiance around 1361 W/m² and explicitly
notes solar-cycle variation. [IAU 2012 Resolution B2](https://syrte.obspm.fr/IAU_resolutions/Res_IAU2012_B2.pdf)
defines the astronomical unit as exactly 149,597,870,700 m. The
[MAVEN navigation overview](https://drewryanjones.com/assets/conf_paper_2016_no1.pdf)
says the mission used a set of flat plates with specular and diffuse
coefficients and generally estimated an overall SRP scale factor. Its
mission-calibrated plate, attitude, coefficient, and uncertainty histories
are not available in this protocol.

For each J2000 Sun-relative state, the extra acceleration is
`(1361 W/m² / c) × (AU/r)^2 × A_eff/m` in the outward radial direction, then
converted from m/s² to km/s². `A_eff/m` is an intentionally lumped parameter.
The model omits attitude, shadowing, thermal recoil, and spacecraft-specific
optical behavior. RK4 at 600 and 300 seconds will compute the difference from
the zero-coefficient baseline over each frozen 24-hour arc. The numerical
gates and evaluation budget are fixed in JSON. Report every scenario,
including failed gates, without tuning a coefficient to either known NAV
endpoint.

Only conditional model sensitivity can pass. A small or large response cannot
validate the spacecraft trajectory, establish actual SRP magnitude, or close
the independent-observation, maneuver-history, uncertainty, and review gates.
The T1 mission Claim stays `unverified`.
