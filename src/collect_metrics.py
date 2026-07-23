#!/usr/bin/env python3
"""
collect_metrics.py -- aggregate the proposal's decision-gate metrics for a run.

Reads artifacts/<run>/manifest.json (+ verification.json if present) and emits
artifacts/<run>/metrics.json plus a short Markdown table, quantifying:

  * Correctness  -- did the agent-generated code compile & run? did SNES converge?
                    observed order of accuracy; finest-grid error.
  * Efficiency   -- wall-clock per stage; code-gen LLM response loops & tool calls;
                    an approximate count of LLM (Argo) completions.
  * Human effort -- lines of solver code hand-written by a human (0: it was generated);
                    size of the human-written problem specification.

Stdlib only. Run with any Python:
  python3 src/collect_metrics.py [--run run-YYYYmmdd-HHMMSS]
"""
import os
import sys
import json
import argparse

HERE = os.path.dirname(os.path.abspath(__file__))
PROJECT = os.path.dirname(HERE)
ARTIFACTS = os.path.join(PROJECT, "artifacts")


def latest_run():
    p = os.path.join(ARTIFACTS, "LATEST")
    if os.path.isfile(p):
        return open(p).read().strip()
    runs = sorted(d for d in os.listdir(ARTIFACTS) if d.startswith("run-"))
    return runs[-1] if runs else sys.exit("no runs found")


def load(path):
    return json.load(open(path)) if os.path.isfile(path) else {}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--run", default=None)
    args = ap.parse_args()
    run_id = args.run or latest_run()
    run_dir = os.path.join(ARTIFACTS, run_id)
    man = load(os.path.join(run_dir, "manifest.json"))
    ver = load(os.path.join(run_dir, "verification.json"))
    stages = man.get("stages", {})

    cg = stages.get("codegen", {})
    code_path = os.path.join(run_dir, "grad_shafranov.c")
    code_lines = sum(1 for _ in open(code_path)) if os.path.isfile(code_path) else 0
    out_path = os.path.join(run_dir, "codegen_output.txt")
    run_output = open(out_path).read() if os.path.isfile(out_path) else ""
    compiled_and_ran = bool(code_lines) and ("error" not in run_output.lower()
                                             or "Max-norm" in run_output)

    # approximate number of Argo LLM completions: model(1) + na(1) + codegen loops
    codegen_loops = cg.get("response_loops")
    llm_completions = 2 + (codegen_loops or 0)
    total_seconds = sum(v.get("seconds", 0) or 0 for v in stages.values())

    orders = ver.get("observed_order_maxnorm") or []
    finest_err = None
    if ver.get("max_norm_error"):
        errs = [e for e in ver["max_norm_error"] if e]
        finest_err = errs[-1] if errs else None

    metrics = {
        "run": run_id,
        "model": man.get("model"),
        "correctness": {
            "model_name": stages.get("model", {}).get("name"),
            "code_generated": bool(code_lines),
            "code_lines": code_lines,
            "compiled_and_ran": compiled_and_ran,
            "snes_converged_reason": _grep(run_output, "ConvergedReason"),
            "observed_order_maxnorm": orders,
            "finest_grid_maxnorm_error": finest_err,
            "verification_sizes": ver.get("sizes"),
        },
        "efficiency": {
            "wallclock_seconds_total": round(total_seconds, 1),
            "wallclock_by_stage": {k: v.get("seconds") for k, v in stages.items()},
            "codegen_response_loops": codegen_loops,
            "codegen_tool_calls": cg.get("tool_cnt"),
            "approx_llm_completions": llm_completions,
        },
        "human_effort": {
            "solver_lines_handwritten": 0,
            "solver_lines_agent_generated": code_lines,
            "human_science_spec_chars": len(man.get("science_spec", "")),
            "human_codegen_spec_chars": len(man.get("codegen_spec", "")),
        },
    }
    with open(os.path.join(run_dir, "metrics.json"), "w") as f:
        json.dump(metrics, f, indent=2)

    md = _markdown(metrics)
    with open(os.path.join(run_dir, "metrics.md"), "w") as f:
        f.write(md)
    print(md)
    print("[metrics] wrote %s/metrics.json and metrics.md" % run_dir)


def _grep(text, key):
    for line in text.splitlines():
        if key in line:
            return line.strip()
    return None


def _markdown(m):
    c, e, h = m["correctness"], m["efficiency"], m["human_effort"]
    order = ", ".join("%.2f" % p for p in (c["observed_order_maxnorm"] or [])) or "n/a"
    return (
        "## Decision-gate metrics -- run %s (model %s)\n\n" % (m["run"], m["model"]) +
        "| Dimension | Metric | Value |\n|---|---|---|\n" +
        "| Correctness | PDE model identified | %s |\n" % c["model_name"] +
        "| Correctness | agent code compiled & ran | %s |\n" % c["compiled_and_ran"] +
        "| Correctness | SNES converged | %s |\n" % (c["snes_converged_reason"] or "n/a") +
        "| Correctness | observed order of accuracy | %s |\n" % order +
        "| Correctness | finest-grid max-norm error | %s |\n" % c["finest_grid_maxnorm_error"] +
        "| Efficiency | total wall-clock (s) | %s |\n" % e["wallclock_seconds_total"] +
        "| Efficiency | code-gen LLM loops / tool calls | %s / %s |\n" % (
            e["codegen_response_loops"], e["codegen_tool_calls"]) +
        "| Efficiency | approx. LLM completions | %s |\n" % e["approx_llm_completions"] +
        "| Human effort | solver lines hand-written | %s |\n" % h["solver_lines_handwritten"] +
        "| Human effort | solver lines agent-generated | %s |\n" % h["solver_lines_agent_generated"] +
        "| Human effort | problem-spec size (chars) | %s |\n" % (
            h["human_science_spec_chars"] + h["human_codegen_spec_chars"]))


if __name__ == "__main__":
    main()
