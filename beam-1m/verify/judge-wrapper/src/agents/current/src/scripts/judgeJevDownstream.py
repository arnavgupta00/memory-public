"""Observe and budget the existing official evaluator without changing its prompts/scoring."""
from pathlib import Path
import hashlib
import json
import threading
import time
import uuid
import sys

import runBeamEvidenceContractEvaluation as runner

ROOT = Path(__file__).resolve().parents[5]
OUT = ROOT / "runs/jev-downstream12-20260921"


class LoggedJudge:
    def __init__(self, model, budget=3.0):
        self.model = model
        self.budget = budget
        self.spent = 0.0
        self.reserved = 0.0
        self.blocked = False
        self.lock = threading.Lock()
        self.journal = OUT / "judge-attempts.jsonl"
        if self.journal.exists():
            raise RuntimeError("Judge ledger exists; explicit partial-run recovery required")
        if model.model_name != "gpt-4.1-mini" or model.temperature != 0:
            raise RuntimeError("Unexpected official judge configuration")
        # No invisible transport retries. No prompt, sampling, or output-limit changes.
        model.root_client.max_retries = 0

    def record(self, row):
        with self.journal.open("a") as f:
            f.write(json.dumps({"time": time.time(), **row}) + "\n")

    def invoke(self, prompt, **kwargs):
        if not isinstance(prompt, str):
            raise RuntimeError("This frozen cohort should use rubric text prompts only")
        # Bytes upper-bound text tokens; 65,536 is deliberately above the model's
        # maximum output capacity. This is a spend reservation, not an output cap.
        reserve = ((len(prompt.encode()) + 1024) * .4 + 65536 * 1.6) / 1e6
        attempt = str(uuid.uuid4())
        with self.lock:
            if self.blocked or self.spent + self.reserved + reserve > self.budget:
                raise RuntimeError("Judge budget/unknown usage requires review")
            self.reserved += reserve
            self.record({"event": "dispatch", "attempt": attempt, "prompt": prompt,
                         "input_sha256": hashlib.sha256(prompt.encode()).hexdigest(),
                         "reserved_usd": reserve, "model": "gpt-4.1-mini"})
        start = time.monotonic()
        try:
            response = self.model.invoke(prompt, **kwargs)
        except Exception as error:
            with self.lock:
                self.reserved -= reserve
                self.blocked = True
                self.record({"event": "failure", "attempt": attempt,
                             "error_type": type(error).__name__, "usage": None,
                             "cost_usd": None})
            raise
        usage = response.usage_metadata
        cost = None if not usage else (usage["input_tokens"] * .4 + usage["output_tokens"] * 1.6) / 1e6
        with self.lock:
            self.reserved -= reserve
            if cost is None:
                self.blocked = True
            else:
                self.spent += cost
            self.record({"event": "response", "attempt": attempt,
                         "response": response.model_dump(mode="json"), "usage": usage,
                         "cost_usd": cost, "elapsed_seconds": time.monotonic() - start})
        if cost is None:
            raise RuntimeError("Official judge response has unknown usage")
        if response.response_metadata.get("finish_reason") != "stop":
            raise RuntimeError("Incomplete judge response; not a valid quality score")
        return response


configure_original = runner.configure_runtime_copy


def configure(repo, scratch):
    configure_original(repo, scratch)
    sys.path.insert(0, str(scratch))
    from src import llm
    llm.gpt_llm = LoggedJudge(llm.gpt_llm)


if __name__ == "__main__":
    runner.configure_runtime_copy = configure
    runner.main()
