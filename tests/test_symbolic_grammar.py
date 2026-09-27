"""The bounded grammar must enumerate safely and select using training rows only."""

from pathlib import Path

from auditable_scientist.benchmark import hohmann as benchmark


ROOT = Path(__file__).resolve().parents[1]


def test_grammar_enumerates_ten_unique_expressions_without_baseline(monkeypatch) -> None:
    cases = benchmark.load_hohmann_dataset(ROOT / "examples/hohmann/dataset.json")
    specs = benchmark.bounded_candidate_specs()
    assert len(specs) == len({item.candidate_id for item in specs}) == 10
    assert len({item.expression for item in specs}) == 10
    monkeypatch.setattr(benchmark, "hohmann_baseline", lambda *args: (_ for _ in ()).throw(AssertionError("baseline called")))
    assert all(item.evaluator(cases[0]) > 0 for item in specs)
    assert specs[0].candidate_id == "tof-semimajor-pi-v2"


def test_holdout_change_does_not_select_a_different_candidate() -> None:
    config = benchmark.load_hohmann_config(ROOT / "examples/hohmann/run.json")
    cases = benchmark.load_hohmann_dataset(ROOT / "examples/hohmann/dataset.json")
    original = benchmark.run_hohmann_experiment(config, cases)
    assert original.grammar_version == benchmark.GRAMMAR_VERSION
    altered = [case.model_copy(update={"target_tof_days": case.target_tof_days + 100}) if case.split == "holdout" else case for case in cases]
    changed = benchmark.run_hohmann_experiment(config, altered)
    assert original.selected_candidate_id == changed.selected_candidate_id == "tof-semimajor-pi-v2"
    assert original.gate.passed and not changed.gate.passed
    assert original.candidate_order == changed.candidate_order


def test_correct_grammar_candidate_matches_separate_baseline() -> None:
    case = benchmark.load_hohmann_dataset(ROOT / "examples/hohmann/dataset.json")[0]
    predicted = benchmark.bounded_candidate_specs()[0].evaluator(case)
    reference = benchmark.hohmann_baseline(case.r1_km, case.r2_km, case.mu_km3_s2).time_of_flight_days
    assert abs(predicted - reference) < 1e-10
