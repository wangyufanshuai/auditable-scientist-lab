# T1 MAVEN offline short-arc Run

- Run: `run-t1-maven-8bd3e76cea54eb4e`
- Arc count: `2`
- Endpoint position errors (km): `[0.535836911089304, 0.2848350571145478]`
- Wrong-sign gravity rejected: `True`
- Mission Claim: `unverified`
- Result hash: `90bae80c56701ab57123aee99d0de81fe06c0ca1ee46a31704b3050688cf6452`

Replay propagates saved NAV initial states with the Sun-only RK4 model; it does not query SPICE. The source is a reconstructed mission solution, not independent flight truth. No full force/maneuver model, scientific holdout, encounter or mission validation is established.
