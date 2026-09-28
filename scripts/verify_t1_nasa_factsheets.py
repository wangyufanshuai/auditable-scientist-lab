"""Read-only NASA fact-sheet parameter snapshot and bounded T1 sensitivity audit.

The offline verifier proves consistency of short captured table rows and local
calculations. It cannot reauthenticate the original HTTPS pages or clear their
page-specific usage rights; both remain separate gates.
"""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
from decimal import Decimal
from hashlib import sha256
from html import unescape
import json
from math import pi
from pathlib import Path
import re

from auditable_scientist.tools.numerical import hohmann_baseline


ROOT = Path(__file__).resolve().parents[1]
SNAPSHOT = ROOT / "artifacts/t1-nasa-factsheet-snapshot.json"
AUDIT = ROOT / "artifacts/t1-nasa-factsheet-audit.json"
URLS = {
    "earth": "https://nssdc.gsfc.nasa.gov/planetary/factsheet/earthfact.html",
    "mars": "https://nssdc.gsfc.nasa.gov/planetary/factsheet/marsfact.html",
}
LABELS = {
    "semimajor_axis_million_km": "Semimajor axis (106 km)",
    "sidereal_period_days": "Sidereal orbit period",
}
HEX = re.compile(r"^[a-f0-9]{64}$")


def digest(raw: bytes) -> str:
    return sha256(raw).hexdigest()


def _cell_text(raw: str) -> str:
    return " ".join(unescape(re.sub(r"<[^>]+>", "", raw)).split())


def parse_row(raw: str, label: str, body: str) -> list[str]:
    if body == "earth":
        if "<tr" in raw.lower() or "<th" in raw.lower():
            raise ValueError("Earth fact-sheet orbital row is expected as plain text")
        text = _cell_text(raw)
        match = re.fullmatch(rf"{re.escape(label)}(?: \(days\))?\s+([0-9]+(?:\.[0-9]+)?)", text)
        if match is None:
            raise ValueError(f"Earth fact-sheet row differs: {label}")
        return [match.group(1)]
    if body != "mars":
        raise ValueError(f"unknown fact-sheet body: {body}")
    headers = re.findall(r"<th\b[^>]*>(.*?)</th>", raw, re.I | re.S)
    if len(headers) != 1 or _cell_text(headers[0]) not in (label, f"{label} (days)"):
        raise ValueError(f"Mars fact-sheet row label differs: {label}")
    cells = [_cell_text(item) for item in re.findall(r"<td\b[^>]*>(.*?)</td>", raw, re.I | re.S)]
    if len(cells) != 3 or any(not re.fullmatch(r"[0-9]+(?:\.[0-9]+)?", item) for item in cells):
        raise ValueError(f"Mars fact-sheet comparison cells differ: {label}")
    return cells


def extract_rows(page: bytes, body: str) -> dict[str, dict[str, object]]:
    html = page.decode("utf-8")
    if body == "earth":
        sections = re.findall(r"<h3>Orbital parameters</h3>\s*<pre>(.*?)</pre>", html, re.I | re.S)
        if len(sections) != 1:
            raise ValueError("expected exactly one Earth orbital-parameter section")
        candidates = sections[0].splitlines()
    elif body == "mars":
        candidates = re.findall(r"<tr\b[^>]*>.*?</tr>", html, re.I | re.S)
    else:
        raise ValueError(f"unknown fact-sheet body: {body}")
    result: dict[str, dict[str, object]] = {}
    for key, label in LABELS.items():
        matches = []
        for raw in candidates:
            try:
                values = parse_row(raw, label, body)
            except ValueError:
                continue
            matches.append((raw, values))
        if len(matches) != 1:
            raise ValueError(f"expected exactly one orbital parameter row: {label}")
        raw, values = matches[0]
        result[key] = {"raw_html": raw, "row_sha256": digest(raw.encode("utf-8")), "values": values}
    return result


def capture(earth_html: Path, mars_html: Path) -> dict[str, object]:
    sources = []
    for body, path in (("earth", earth_html), ("mars", mars_html)):
        page = path.read_bytes()
        sources.append({
            "body": body,
            "url": URLS[body],
            "page_sha256": digest(page),
            "page_bytes": len(page),
            "rows": extract_rows(page, body),
            "rights_status": "page-specific-usage-unreviewed",
        })
    snapshot = {
        "schema_version": "t1-nasa-factsheet-snapshot-v1",
        "captured_at": datetime.now(timezone.utc).isoformat(),
        "capture_method": "Read-only HTTPS GET; exact source page bytes were inspected locally, but only two short table rows per page are retained.",
        "sources": sources,
    }
    SNAPSHOT.write_text(json.dumps(snapshot, indent=2, sort_keys=True) + "\n", encoding="utf-8", newline="\n")
    return snapshot


def verify_snapshot(snapshot: dict[str, object]) -> dict[str, object]:
    if snapshot.get("schema_version") != "t1-nasa-factsheet-snapshot-v1":
        raise ValueError("fact-sheet snapshot schema differs")
    sources = snapshot.get("sources")
    if not isinstance(sources, list) or [item.get("body") for item in sources] != ["earth", "mars"]:
        raise ValueError("fact-sheet source set differs")
    for source in sources:
        body = source["body"]
        if (source.get("url") != URLS[body]
                or source.get("rights_status") != "page-specific-usage-unreviewed"
                or not isinstance(source.get("page_bytes"), int) or source["page_bytes"] <= 0
                or not HEX.fullmatch(str(source.get("page_sha256", "")))
                or set(source.get("rows", {})) != set(LABELS)):
            raise ValueError(f"fact-sheet source identity, rights, or page metadata differs: {body}")
        for key, label in LABELS.items():
            row = source["rows"][key]
            raw = row["raw_html"]
            if digest(raw.encode("utf-8")) != row["row_sha256"] or parse_row(raw, label, body) != row["values"]:
                raise ValueError(f"fact-sheet row bytes or values differ: {body}/{key}")
            if len(row["values"]) != (1 if body == "earth" else 3):
                raise ValueError(f"fact-sheet comparison column count differs: {body}/{key}")

    earth, mars = sources
    earth_axis = Decimal(earth["rows"]["semimajor_axis_million_km"]["values"][0])
    mars_axis = Decimal(mars["rows"]["semimajor_axis_million_km"]["values"][0])
    earth_period = Decimal(earth["rows"]["sidereal_period_days"]["values"][0])
    mars_period = Decimal(mars["rows"]["sidereal_period_days"]["values"][0])
    if (str(earth_axis) != mars["rows"]["semimajor_axis_million_km"]["values"][1]
            or str(earth_period) != mars["rows"]["sidereal_period_days"]["values"][1]):
        raise ValueError("Earth columns differ between the two fact sheets")
    if not (100 < earth_axis < 200 and 200 < mars_axis < 300
            and 300 < earth_period < 400 and 600 < mars_period < 800):
        raise ValueError("fact-sheet orbital values are outside the declared sanity bounds")

    dataset = json.loads((ROOT / "examples/hohmann/dataset.json").read_text(encoding="utf-8"))
    baseline = dataset["cases"][0]
    mu = baseline["mu_km3_s2"]
    source_result = hohmann_baseline(float(earth_axis * 1_000_000), float(mars_axis * 1_000_000), mu)
    fixture_result = hohmann_baseline(baseline["r1_km"], baseline["r2_km"], mu)
    implied_mu_earth = 4 * pi * pi * source_result.r1_km**3 / (float(earth_period) * 86400)**2
    implied_mu_mars = 4 * pi * pi * source_result.r2_km**3 / (float(mars_period) * 86400)**2
    relative_mu_differences = {
        "earth": (implied_mu_earth - mu) / mu,
        "mars": (implied_mu_mars - mu) / mu,
    }
    if any(abs(value) > 0.001 for value in relative_mu_differences.values()):
        raise ValueError("rounded fact-sheet periods and axes fail the predeclared 0.1% Kepler check")
    return {
        "schema_version": "t1-nasa-factsheet-audit-v1",
        "status": "verified-offline-snapshot-only",
        "snapshot_sha256": digest(SNAPSHOT.read_bytes()),
        "script_sha256": digest(Path(__file__).read_bytes()),
        "benchmark_source_sha256": digest(ROOT.joinpath("src/auditable_scientist/tools/numerical.py").read_bytes()),
        "source_page_sha256": {item["body"]: item["page_sha256"] for item in sources},
        "source_urls": URLS,
        "source_rights_status": "unreviewed-page-specific",
        "full_page_bytes_committed": False,
        "offline_origin_authentication": False,
        "real_data_claim": False,
        "scientific_validation_claim": False,
        "rounded_axes_million_km": {"earth": str(earth_axis), "mars": str(mars_axis)},
        "sidereal_period_days": {"earth": str(earth_period), "mars": str(mars_period)},
        "kepler_relative_mu_difference": relative_mu_differences,
        "solar_mu_km3_s2_from_synthetic_fixture": mu,
        "fact_sheet_parameter_hohmann_days": source_result.time_of_flight_days,
        "synthetic_fixture_hohmann_days": fixture_result.time_of_flight_days,
        "parameter_sensitivity_days": source_result.time_of_flight_days - fixture_result.time_of_flight_days,
        "limits": [
            "Rows and calculations replay offline; the full original pages were not archived or reauthenticated offline.",
            "Fact-sheet rounded mean elements do not define a mission trajectory or validate transfer accuracy.",
            "Page-specific source rights, independent ephemeris comparison, and human scientific review remain open.",
        ],
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("mode", choices=("capture", "verify"))
    parser.add_argument("--earth-html", type=Path)
    parser.add_argument("--mars-html", type=Path)
    parser.add_argument("--write-audit", action="store_true")
    args = parser.parse_args()
    if args.mode == "capture":
        if args.earth_html is None or args.mars_html is None:
            parser.error("capture requires --earth-html and --mars-html")
        snapshot = capture(args.earth_html, args.mars_html)
        print(json.dumps({"snapshot": str(SNAPSHOT), "sources": len(snapshot["sources"])}))
        return
    snapshot = json.loads(SNAPSHOT.read_text(encoding="utf-8"))
    audit = verify_snapshot(snapshot)
    if args.write_audit:
        AUDIT.write_text(json.dumps(audit, indent=2, sort_keys=True) + "\n", encoding="utf-8", newline="\n")
    elif audit != json.loads(AUDIT.read_text(encoding="utf-8")):
        raise ValueError("committed fact-sheet audit differs from offline recomputation")
    print(json.dumps({"status": audit["status"], "parameter_sensitivity_days": audit["parameter_sensitivity_days"]}))


if __name__ == "__main__":
    main()
