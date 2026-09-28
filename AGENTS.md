# Project instructions

- Preserve all source directories under `E:/xuexi`; adapters are read-only by default.
- Do not reset, checkout, delete, rename, or overwrite existing source projects.
- Do not copy code from a source project until its license and revision are recorded.
- Treat synthetic, fixture, and local smoke evidence as engineering evidence only.
- A claim without a verified holdout result must remain `candidate`.
- Every Run must retain input, code/source snapshot, environment, seed, tool versions,
  evidence references, and a replay result.
- LLM output may propose or explain candidates. Deterministic tools and gates own the
  numerical result, dimensional status, evidence level, and final claim status.
- Keep the first release offline-capable. Network access is optional evidence, never a
  hidden dependency of `run` or `replay`.
