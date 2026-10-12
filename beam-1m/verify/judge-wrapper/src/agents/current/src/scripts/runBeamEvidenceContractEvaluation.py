from __future__ import annotations

import argparse
from concurrent.futures import ThreadPoolExecutor, as_completed
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
from typing import Any, Callable


SOURCE_COMMIT = "3e12035532eb85768f1a7cd779832b650c4b2ef9"
JUDGE_MODEL = "gpt-4.1-mini"
OFFICIAL_SOURCE_PATHS = (
    "src/evaluation/run_evaluation.py",
    "src/evaluation/compute_metrics.py",
    "src/evaluation/report_results.py",
    "src/prompts.py",
    "src/llm.py",
    "requirements.txt",
)


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load_dotenv(path: Path) -> None:
    if not path.is_file():
        return
    for line in path.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or "=" not in stripped:
            continue
        key, value = stripped.split("=", 1)
        value = value.strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in ("'", '"'):
            value = value[1:-1]
        os.environ.setdefault(key.strip(), value)


def validate_official_repo(repo: Path) -> dict[str, str]:
    commit = subprocess.check_output(
        ["git", "-C", str(repo), "rev-parse", "HEAD"], text=True
    ).strip()
    if commit != SOURCE_COMMIT:
        raise ValueError(f"official BEAM checkout is at {commit}, expected {SOURCE_COMMIT}")
    dirty = subprocess.check_output(
        ["git", "-C", str(repo), "status", "--porcelain", "--", *OFFICIAL_SOURCE_PATHS],
        text=True,
    ).strip()
    if dirty:
        raise ValueError("official BEAM evaluator sources are modified")
    missing = [path for path in OFFICIAL_SOURCE_PATHS if not (repo / path).is_file()]
    if missing:
        raise ValueError(f"official BEAM checkout is missing: {', '.join(missing)}")
    llm_source = (repo / "src/llm.py").read_text(encoding="utf-8")
    if f'model_name="{JUDGE_MODEL}"' not in llm_source or "temperature=0" not in llm_source:
        raise ValueError("official judge model/temperature contract is absent")
    return {path: sha256(repo / path) for path in OFFICIAL_SOURCE_PATHS}


def configure_runtime_copy(repo: Path, scratch: Path) -> None:
    shutil.copytree(repo / "src", scratch / "src")
    config_path = scratch / "src/llms_config.json"
    config = json.loads(config_path.read_text(encoding="utf-8"))
    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        raise ValueError("OPENAI_API_KEY is required")
    config["gpt"]["api_key"] = api_key
    for unused in ("llama", "qwen"):
        config[unused] = {
            "model_url": "https://api.openai.com/v1",
            "model_name": JUDGE_MODEL,
            "api_key": api_key,
        }
    config_path.write_text(json.dumps(config, indent=2), encoding="utf-8")


def load_predictions(path: Path) -> dict[str, str]:
    predictions: dict[str, str] = {}
    for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        if not line.strip():
            continue
        row = json.loads(line)
        question_id = row.get("question_id")
        hypothesis = row.get("hypothesis")
        if not isinstance(question_id, str) or not isinstance(hypothesis, str):
            raise ValueError(f"{path}:{line_number} lacks question_id or hypothesis")
        if question_id in predictions:
            raise ValueError(f"{path}:{line_number} duplicates {question_id}")
        predictions[question_id] = hypothesis
    return predictions


def parse_arm(value: str) -> tuple[str, Path]:
    name, separator, raw_path = value.partition("=")
    if not separator or not name or not raw_path:
        raise argparse.ArgumentTypeError("--arm must be NAME=PREDICTIONS_JSONL")
    if not name.replace("-", "_").isalnum():
        raise argparse.ArgumentTypeError("arm names may contain letters, digits, _ and -")
    return name, Path(raw_path)


def parse_question_id(question_id: str) -> tuple[int, str, int]:
    parts = question_id.split("/")
    if len(parts) != 4 or parts[0] != "beam-1m" or not parts[1].startswith("chat-"):
        raise ValueError(f"invalid BEAM question id: {question_id}")
    return int(parts[1].removeprefix("chat-")), parts[2], int(parts[3])


def score_from_result(ability: str, result: dict[str, Any]) -> float:
    field = "tau_norm" if ability == "event_ordering" else "llm_judge_score"
    score = result.get(field)
    if not isinstance(score, (int, float)):
        raise ValueError(f"official result for {ability} lacks {field}")
    return float(score)


def mean(values: list[float]) -> float:
    return sum(values) / len(values) if values else 0.0


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Score paired BEAM evidence-contract arms with the exact pinned evaluator."
    )
    parser.add_argument("--beam-repo", type=Path, required=True)
    parser.add_argument("--beam-root", type=Path, required=True)
    parser.add_argument("--cohort", type=Path, required=True)
    parser.add_argument("--arm", type=parse_arm, action="append", required=True)
    parser.add_argument("--baseline-arm", default="baseline")
    parser.add_argument("--fixed-predictions", type=Path)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--max-workers", type=int, default=20)
    args = parser.parse_args()

    if args.max_workers < 1:
        raise ValueError("--max-workers must be positive")
    project_root = Path(__file__).resolve().parents[5]
    load_dotenv(project_root / ".env")
    repo = args.beam_repo.resolve()
    beam_root = args.beam_root.resolve()
    cohort_path = args.cohort.resolve()
    source_hashes = validate_official_repo(repo)
    cohort = json.loads(cohort_path.read_text(encoding="utf-8"))
    question_ids = cohort.get("question_ids")
    inherited_ids = set(cohort.get("inherited_fixed_question_ids", []))
    if (
        not isinstance(question_ids, list)
        or not question_ids
        or not all(isinstance(item, str) for item in question_ids)
        or len(set(question_ids)) != len(question_ids)
    ):
        raise ValueError("cohort must contain unique non-empty question_ids")
    if not inherited_ids.issubset(set(question_ids)):
        raise ValueError("inherited fixed IDs must be inside the cohort")

    arm_specs = args.arm
    arm_names = [name for name, _path in arm_specs]
    if len(set(arm_names)) != len(arm_names):
        raise ValueError("arm names must be unique")
    if args.baseline_arm not in arm_names:
        raise ValueError("--baseline-arm must name one supplied --arm")
    fixed_path = args.fixed_predictions.resolve() if args.fixed_predictions else None
    fixed = load_predictions(fixed_path) if fixed_path else {}
    arms: dict[str, dict[str, str]] = {}
    arm_sources: dict[str, dict[str, str]] = {}
    for name, path_value in arm_specs:
        path = path_value.resolve()
        source = load_predictions(path)
        resolved: dict[str, str] = {}
        for question_id in question_ids:
            answer = source.get(question_id)
            if answer is None and question_id in inherited_ids:
                answer = fixed.get(question_id)
            if answer is None:
                raise ValueError(f"arm {name} is missing active cohort question {question_id}")
            resolved[question_id] = answer
        arms[name] = resolved
        arm_sources[name] = {"path": str(path), "sha256": sha256(path)}

    args.out.parent.mkdir(parents=True, exist_ok=True)
    execution: dict[str, Any] = {
        "schema_version": 1,
        "benchmark": "BEAM",
        "tier": "1M",
        "cohort": cohort.get("name"),
        "cohort_path": str(cohort_path),
        "cohort_sha256": sha256(cohort_path),
        "official_source_commit": SOURCE_COMMIT,
        "official_source_hashes": source_hashes,
        "judge_model": JUDGE_MODEL,
        "judge_temperature": 0,
        "official_scoring": {
            "event_ordering": "tau_norm",
            "other_abilities": "llm_judge_score",
        },
        "baseline_arm": args.baseline_arm,
        "arms": arm_sources,
        "fixed_predictions": None if fixed_path is None else {
            "path": str(fixed_path), "sha256": sha256(fixed_path)
        },
        "questions": len(question_ids),
        "status": "running",
        "rows": [],
    }
    args.out.write_text(json.dumps(execution, indent=2) + "\n", encoding="utf-8")

    with tempfile.TemporaryDirectory(prefix="beam-evidence-contract-official-") as temporary:
        scratch = Path(temporary)
        configure_runtime_copy(repo, scratch)
        sys.path.insert(0, str(scratch))
        from src.evaluation.compute_metrics import (  # type: ignore[import-not-found]
            evaluate_abstention,
            evaluate_contradiction_resolution,
            evaluate_event_ordering,
            evaluate_information_extraction,
            evaluate_instruction_following,
            evaluate_knowledge_update,
            evaluate_multi_session_reasoning,
            evaluate_preference_following,
            evaluate_summarization,
            evaluate_temporal_reasoning,
            initialize_models,
        )
        from src.llm import gpt_llm  # type: ignore[import-not-found]

        evaluators: dict[str, Callable[..., dict[str, Any]]] = {
            "abstention": evaluate_abstention,
            "contradiction_resolution": evaluate_contradiction_resolution,
            "event_ordering": evaluate_event_ordering,
            "information_extraction": evaluate_information_extraction,
            "instruction_following": evaluate_instruction_following,
            "knowledge_update": evaluate_knowledge_update,
            "multi_session_reasoning": evaluate_multi_session_reasoning,
            "preference_following": evaluate_preference_following,
            "summarization": evaluate_summarization,
            "temporal_reasoning": evaluate_temporal_reasoning,
        }
        initialize_models()

        def evaluate(arm: str, question_id: str) -> dict[str, Any]:
            conversation_id, ability, one_based_index = parse_question_id(question_id)
            evaluator = evaluators.get(ability)
            if evaluator is None:
                raise ValueError(f"unsupported BEAM ability: {ability}")
            probe_path = beam_root / str(conversation_id) / "probing_questions/probing_questions.json"
            probes = json.loads(probe_path.read_text(encoding="utf-8"))
            probe = probes[ability][one_based_index - 1]
            result = evaluator(
                rubric=probe["rubric"],
                llm_response=arms[arm][question_id],
                probing_question=probe["question"],
                model=gpt_llm,
            )
            return {
                "arm": arm,
                "question_id": question_id,
                "ability": ability,
                "score": score_from_result(ability, result),
                "official_result": result,
            }

        tasks = [(arm, question_id) for question_id in question_ids for arm in arms]
        rows: list[dict[str, Any]] = []
        with ThreadPoolExecutor(max_workers=args.max_workers) as executor:
            futures = {
                executor.submit(evaluate, arm, question_id): (arm, question_id)
                for arm, question_id in tasks
            }
            for future in as_completed(futures):
                row = future.result()
                rows.append(row)
                execution["rows"] = sorted(
                    rows, key=lambda item: (item["question_id"], item["arm"])
                )
                args.out.write_text(json.dumps(execution, indent=2) + "\n", encoding="utf-8")

    rows = execution["rows"]
    arm_summary: dict[str, Any] = {}
    for arm in arms:
        arm_rows = [row for row in rows if row["arm"] == arm]
        ability_names = sorted({row["ability"] for row in arm_rows})
        arm_summary[arm] = {
            "questions": len(arm_rows),
            "mean_score": mean([row["score"] for row in arm_rows]),
            "abilities": {
                ability: mean([
                    row["score"] for row in arm_rows if row["ability"] == ability
                ])
                for ability in ability_names
            },
        }
    baseline_scores = {
        row["question_id"]: row["score"]
        for row in rows if row["arm"] == args.baseline_arm
    }
    paired: dict[str, Any] = {}
    for arm in arms:
        if arm == args.baseline_arm:
            continue
        deltas = [
            row["score"] - baseline_scores[row["question_id"]]
            for row in rows if row["arm"] == arm
        ]
        paired[arm] = {
            "wins": sum(delta > 0 for delta in deltas),
            "losses": sum(delta < 0 for delta in deltas),
            "ties": sum(delta == 0 for delta in deltas),
            "mean_delta": mean(deltas),
        }
    execution["aggregate"] = {"arms": arm_summary, "paired_vs_baseline": paired}
    execution["status"] = "completed"
    args.out.write_text(json.dumps(execution, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(execution["aggregate"], indent=2))


if __name__ == "__main__":
    main()
