"""Expert review 2026-09-27: pinned official BEAM evaluator with attempt logging and a spend guard.

Same observation wrapper as judgeJevDownstream.LoggedJudge, except that message-list prompts
(used by the official event-ordering LLM alignment) are passed through unchanged instead of being
rejected. Prompts, judge model, temperature and scoring are untouched.
Usage: EXPERT_REVIEW_JUDGE_OUT=<dir> EXPERT_REVIEW_JUDGE_BUDGET=<usd> python judgeExpertReview.py <runner args>
"""
from pathlib import Path
import hashlib
import json
import os
import time
import uuid

import judgeJevDownstream as logged

logged.OUT = Path(os.environ["EXPERT_REVIEW_JUDGE_OUT"]).resolve()
logged.OUT.mkdir(parents=True, exist_ok=True)
BUDGET = float(os.environ.get("EXPERT_REVIEW_JUDGE_BUDGET", "1.0"))


def _serialize(prompt):
    if isinstance(prompt, str):
        return prompt
    return json.dumps(prompt, sort_keys=True, ensure_ascii=False)


class ReviewJudge(logged.LoggedJudge):
    def __init__(self, model):
        super().__init__(model, budget=BUDGET)

    def invoke(self, prompt, **kwargs):
        text = _serialize(prompt)
        reserve = ((len(text.encode()) + 1024) * .4 + 65536 * 1.6) / 1e6
        attempt = str(uuid.uuid4())
        with self.lock:
            if self.blocked or self.spent + self.reserved + reserve > self.budget:
                raise RuntimeError("Judge budget/unknown usage requires review")
            self.reserved += reserve
            self.record({"event": "dispatch", "attempt": attempt, "prompt": prompt,
                         "input_sha256": hashlib.sha256(text.encode()).hexdigest(),
                         "reserved_usd": reserve, "model": "gpt-4.1-mini"})
        start = time.monotonic()
        try:
            response = self.model.invoke(prompt, **kwargs)
        except Exception as error:
            with self.lock:
                self.reserved -= reserve
                self.blocked = True
                self.record({"event": "failure", "attempt": attempt,
                             "error_type": type(error).__name__, "usage": None, "cost_usd": None})
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


if __name__ == "__main__":
    logged.LoggedJudge = ReviewJudge
    logged.runner.configure_runtime_copy = logged.configure
    logged.runner.main()
