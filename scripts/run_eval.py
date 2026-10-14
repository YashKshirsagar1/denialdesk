"""
Eval runner for the DiagnosisAgent.
Usage:
  python scripts/run_eval.py --mock
  python scripts/run_eval.py --mock --output data/eval_results.json
"""
import argparse
import asyncio
import json
import os
import sys
from datetime import datetime, timezone
from types import SimpleNamespace

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from denialdesk.agents.diagnosis_agent import DiagnosisAgent
from denialdesk.llm.base import LLMMessage, LLMProvider, LLMResponse


# ---------------------------------------------------------------------------
# Mock LLM — returns the rule-based result wrapped as JSON so the agent
# goes through the full parse path without hitting the real API.
# ---------------------------------------------------------------------------

class MockLLMProvider(LLMProvider):
    async def complete(
        self,
        messages: list[LLMMessage],
        system: str | None = None,
        max_tokens: int = 2048,
    ) -> LLMResponse:
        return LLMResponse(content="{}", input_tokens=0, output_tokens=0, model="mock")

    async def complete_json(
        self,
        messages: list[LLMMessage],
        system: str | None = None,
        max_tokens: int = 2048,
    ) -> dict:
        # Return an empty dict so the agent falls back to rule-based values.
        # This tests the full pipeline without requiring any API key.
        return {}


# ---------------------------------------------------------------------------
# Case-like object that satisfies DiagnosisAgent.diagnose()
# ---------------------------------------------------------------------------

def _build_case(entry: dict) -> SimpleNamespace:
    denial_date_str = entry["denial_date"]
    filing_deadline_str = entry["filing_deadline"]

    def parse_dt(s: str) -> datetime:
        return datetime.fromisoformat(s).replace(tzinfo=timezone.utc)

    case = SimpleNamespace(
        id=entry["id"],
        carc=entry["carc"],
        rarc=entry.get("rarc", ""),
        cpt_hcpcs=entry.get("cpt", ""),
        icd10=",".join(entry.get("icd10", [])),
        billed_amt=float(entry["billed_amt"]),
        allowed_amt=float(entry.get("allowed_amt", 0)),
        payer=entry["payer"],
        denial_date=parse_dt(denial_date_str),
        filing_deadline=parse_dt(filing_deadline_str),
        state="ingested",
    )
    return case


# ---------------------------------------------------------------------------
# Eval logic
# ---------------------------------------------------------------------------

async def run_eval(eval_cases: list[dict], use_mock: bool) -> list[dict]:
    provider = MockLLMProvider() if use_mock else _get_real_provider()
    agent = DiagnosisAgent(llm_provider=provider, model_version="mock" if use_mock else "claude-sonnet-4-6")

    results = []
    for entry in eval_cases:
        case = _build_case(entry)
        diagnosis = await agent.diagnose(case)

        score_lo, score_hi = entry["expected_score_range"]
        score_in_range = score_lo <= diagnosis.winnability_score <= score_hi
        root_cause_match = diagnosis.root_cause == entry["expected_root_cause"]
        winnable_pred = diagnosis.winnability_score >= 0.5
        winnable_match = winnable_pred == entry["expected_winnable"]

        results.append({
            "id": entry["id"],
            "carc": entry["carc"],
            "expected_root_cause": entry["expected_root_cause"],
            "predicted_root_cause": diagnosis.root_cause,
            "root_cause_match": root_cause_match,
            "expected_winnable": entry["expected_winnable"],
            "predicted_winnable": winnable_pred,
            "winnable_match": winnable_match,
            "expected_score_range": entry["expected_score_range"],
            "predicted_score": round(diagnosis.winnability_score, 3),
            "score_in_range": score_in_range,
            "notes": entry.get("notes", ""),
        })

    return results


def _get_real_provider():
    from denialdesk.llm import get_llm_provider
    return get_llm_provider()


def print_summary(results: list[dict]) -> None:
    n = len(results)
    root_correct = sum(1 for r in results if r["root_cause_match"])
    winnable_correct = sum(1 for r in results if r["winnable_match"])
    score_correct = sum(1 for r in results if r["score_in_range"])

    print("\n" + "=" * 60)
    print("DenialDesk Diagnosis Agent — Eval Results")
    print("=" * 60)
    print(f"Total cases:             {n}")
    print(f"Root cause accuracy:     {root_correct}/{n} ({root_correct/n*100:.1f}%)")
    print(f"Winnable accuracy:       {winnable_correct}/{n} ({winnable_correct/n*100:.1f}%)")
    print(f"Score-in-range accuracy: {score_correct}/{n} ({score_correct/n*100:.1f}%)")

    # Per-CARC breakdown
    by_carc: dict[str, dict] = {}
    for r in results:
        carc = r["carc"]
        if carc not in by_carc:
            by_carc[carc] = {"total": 0, "root_correct": 0, "winnable_correct": 0}
        by_carc[carc]["total"] += 1
        if r["root_cause_match"]:
            by_carc[carc]["root_correct"] += 1
        if r["winnable_match"]:
            by_carc[carc]["winnable_correct"] += 1

    print("\nPer-CARC root cause accuracy:")
    print(f"  {'CARC':<8} {'Cases':<8} {'Root%':<10} {'Win%'}")
    print(f"  {'-'*8} {'-'*8} {'-'*10} {'-'*8}")
    for carc, stats in sorted(by_carc.items()):
        t = stats["total"]
        rp = stats["root_correct"] / t * 100
        wp = stats["winnable_correct"] / t * 100
        print(f"  {carc:<8} {t:<8} {rp:<10.1f} {wp:.1f}")

    print()
    # Show failures
    failures = [r for r in results if not r["root_cause_match"]]
    if failures:
        print(f"Root cause mismatches ({len(failures)}):")
        for r in failures:
            print(f"  {r['id']}: expected={r['expected_root_cause']}, got={r['predicted_root_cause']}")
    else:
        print("No root cause mismatches.")
    print("=" * 60)


def main() -> None:
    parser = argparse.ArgumentParser(description="Run DenialDesk diagnosis eval")
    parser.add_argument("--mock", action="store_true", help="Use mock LLM (no API key required)")
    parser.add_argument("--output", default=None, help="Write results JSON to this path")
    args = parser.parse_args()

    eval_path = os.path.join(os.path.dirname(__file__), "..", "data", "eval_cases.json")
    with open(eval_path) as f:
        eval_cases = json.load(f)

    results = asyncio.run(run_eval(eval_cases, use_mock=args.mock))
    print_summary(results)

    if args.output:
        os.makedirs(os.path.dirname(os.path.abspath(args.output)), exist_ok=True)
        payload = {
            "run_at": datetime.now(timezone.utc).isoformat(),
            "mock": args.mock,
            "count": len(results),
            "results": results,
        }
        with open(args.output, "w") as f:
            json.dump(payload, f, indent=2)
        print(f"Results written to {args.output}")


if __name__ == "__main__":
    main()
