"""Recompute the extensible registry audit and its root acceptance binding."""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path

from auditable_scientist.track_registry import (
    REGISTRY_ROW, canonical_bytes, load_json, safe_file, validate_evidence,
)


ROOT = Path(__file__).resolve().parents[1]
REGISTRY = ROOT / 'docs/TRACK_REGISTRY.json'
SCHEMA = ROOT / 'schemas/track-registry-v1.json'
AUDIT = ROOT / 'artifacts/track-registry-audit.json'
SOURCES = (
    'scripts/verify_track_registry.py', 'src/auditable_scientist/track_registry.py',
    'scripts/sync_optional_acceptance.py',
    'docs/TRACK_REGISTRY.json', 'schemas/track-registry-v1.json',
    'artifacts/portfolio-status.json', 'artifacts/track-portfolio.json',
)


def _load(path: Path) -> dict:
    return load_json(path.read_text(encoding='utf-8'))


def evaluate(*, overrides: dict[str, bytes] | None = None) -> dict:
    overrides = overrides or {}
    registry = _load(REGISTRY)
    schema = _load(SCHEMA)
    result = validate_evidence(registry, ROOT, schema=schema, overrides=overrides)
    sources = []
    for relative in SOURCES:
        path = safe_file(ROOT, relative)
        content = overrides[relative] if relative in overrides else path.read_bytes()
        sources.append({'path': relative, 'sha256': hashlib.sha256(content).hexdigest(), 'bytes': len(content)})
    return {
        'schema_version': 'track-registry-audit-v1',
        'status': 'verified-bounded-track-registry', **result,
        'registry_sha256': hashlib.sha256(REGISTRY.read_bytes()).hexdigest(),
        'schema_sha256': hashlib.sha256(SCHEMA.read_bytes()).hexdigest(),
        'source_files': sources,
        'limitations': [
            'Review fields are authored annotations bound to evidence, not verified rights or human approval.',
            'Required receipt hashes bind bytes, not scientific correctness; domain verifiers remain mandatory.',
            "Only the registry's own root acceptance row is excluded from the canonical root receipt hash.",
            'Registration does not add a runtime tool, dispatch a solver, or pass a scientific gate.',
        ],
    }


def acceptance_row(audit: dict) -> dict:
    return {
        'name': REGISTRY_ROW,
        'command': 'python scripts/verify_track_registry.py --verify',
        'exit_code': 0, 'recorded_at': audit['recorded_at'],
        'input_version': hashlib.sha256(canonical_bytes(audit)).hexdigest(),
        'output_path': 'artifacts/track-registry-audit.json',
    }


def verify_saved(audit: dict | None = None, *, overrides: dict[str, bytes] | None = None,
                 require_projection: bool = True) -> dict:
    saved = audit if audit is not None else _load(AUDIT)
    recorded_at = saved.get('recorded_at')
    if not isinstance(recorded_at, str):
        raise ValueError('track registry audit timestamp is missing')
    parsed = datetime.fromisoformat(recorded_at.replace('Z', '+00:00'))
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise ValueError('track registry audit timestamp must include a timezone')
    comparable = {key: value for key, value in saved.items() if key != 'recorded_at'}
    if canonical_bytes(comparable) != canonical_bytes(evaluate(overrides=overrides)):
        raise ValueError('track registry audit differs from current inputs')
    if require_projection:
        root = _load(ROOT / 'artifacts/acceptance.json')
        rows = [row for row in root['checks'] if row['name'] == REGISTRY_ROW]
        if canonical_bytes(rows) != canonical_bytes([acceptance_row(saved)]):
            raise ValueError('registry root acceptance row differs')
    return saved


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    action = parser.add_mutually_exclusive_group(required=True)
    action.add_argument('--write', action='store_true')
    action.add_argument('--verify', action='store_true')
    args = parser.parse_args()
    if args.write:
        # Explicit generation binds the complete proposed optional projection.
        # Verification/synchronization never takes this regeneration path.
        if __package__:
            from . import sync_optional_acceptance
        else:
            import sync_optional_acceptance
        outputs = sync_optional_acceptance.proposed_outputs()
        proposed = {path.relative_to(ROOT).as_posix(): value.encode('utf-8')
                    for path, value in outputs.items()}
        payload = evaluate(overrides=proposed)
        payload['recorded_at'] = (_load(AUDIT).get('recorded_at') if AUDIT.exists()
                                  else datetime.now(timezone.utc).isoformat())
        rendered = json.dumps(payload, indent=2, sort_keys=True) + '\n'
        if AUDIT.exists() and AUDIT.read_text(encoding='utf-8') != rendered:
            raise ValueError('refusing to overwrite a different registry audit; preserve it before regeneration')
        AUDIT.write_text(rendered, encoding='utf-8', newline='\n')
        result = payload
    else:
        result = verify_saved()
    print(json.dumps({key: result[key] for key in ('status', 'track_count', 'required_receipt_count')}, sort_keys=True))


if __name__ == '__main__':
    main()
