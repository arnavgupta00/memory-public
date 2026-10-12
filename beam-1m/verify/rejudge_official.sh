#!/bin/sh
# Level 3: re-judge the 700 published answers with the official BEAM evaluator, pinned commit 3e12035 (gpt-4.1-mini,
# temperature 0). Run from the package root. Needs git, python3 (3.11+), network, and OPENAI_API_KEY in the environment.
# Cost about $2.50; about 15-20 minutes.
#
# The wrapper judgeExpertReview.py (code/ in the full copy, verify/judge-wrapper/ in the public copy) runs the official compute_metrics functions
# unchanged. It refuses to run unless the BEAM checkout is exactly commit 3e12035 with unmodified evaluator files, and it
# logs every judge call.
set -e
[ -n "$OPENAI_API_KEY" ] || { echo "set OPENAI_API_KEY"; exit 1; }
[ -d beam-official ] || git clone https://github.com/mohammadtavakoli78/BEAM.git beam-official
git -C beam-official checkout -q 3e12035532eb85768f1a7cd779832b650c4b2ef9
[ -d .venv-beam ] || { python3 -m venv .venv-beam && .venv-beam/bin/pip install -q -r beam-official/requirements.txt; }
W=code/src/agents/current/src/scripts                                   # full copy
[ -f $W/judgeExpertReview.py ] || W=verify/judge-wrapper/src/agents/current/src/scripts   # public copy
for part in canary-a-part1 canary-a-part2 canary-b remaining-340; do
  mkdir -p rejudge/$part
  EXPERT_REVIEW_JUDGE_OUT=rejudge/$part EXPERT_REVIEW_JUDGE_BUDGET=12 .venv-beam/bin/python $W/judgeExpertReview.py \
    --beam-repo beam-official --beam-root beam-official/chats/1M \
    --cohort data/answers/predictions-as-judged/$part.cohort.json \
    --arm a2=data/answers/predictions-as-judged/$part.predictions.jsonl --baseline-arm a2 \
    --out rejudge/$part/judge.json --max-workers 32
done
python3 verify/compare_rejudge.py rejudge
