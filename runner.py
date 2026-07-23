"""Benchmark runner: prompts a model on every scenario, verifies, reports.

A "model" is any function (prompt: str) -> str. A DUMMY model with
hardcoded responses is included so the verifier can be exercised without
calling any API: most dummy answers are correct (some wrapped in noisy
prose/fences to exercise tolerant parsing) and three are deliberately
wrong to show failure detection in the report.

Usage:  python runner.py [--model OLLAMA_NAME] [--langs es,pt,hi] [--csv results.csv]
Without --model the built-in dummy is used (no API calls).
Example: python runner.py --model hf.co/CohereLabs/tiny-aya-global-GGUF:Q4_K_M
"""

import argparse
import csv
import json

import scenarios
import tools
import verifier

REQUEST_MARKER = "USER REQUEST:"


# ----------------------------------------------------------------------
# Prompt construction
# ----------------------------------------------------------------------

def build_prompt(scenario):
    # PROMPT FROZEN as of 2026-07-22: benchmark results depend on this exact
    # wording. Do not edit without invalidating previous result CSVs.
    tool_specs = {name: tools.tool_schema(name) for name in scenario["tools"]}
    return f"""You are an agent that plans tool calls. You do not execute anything;
you respond with JSON only, no extra text.

AVAILABLE TOOLS:
{json.dumps(tool_specs, indent=2, ensure_ascii=False)}

OUTPUT PROTOCOL:
1. DEFAULT: respond with a JSON array of calls in execution order, even if
   there is only one call:
   [{{"tool": "<name>", "args": {{"<param>": <value>, ...}}}}, ...]
2. To pass a field from the RESULT of an earlier step as an argument, write
   the string "$N.field", where N is the 1-based step number, e.g. "$1.id".
   "$N.field" may ONLY reference a step that comes BEFORE the call using it.
   If a value is given literally in the request, use the literal value.
3. ONLY if the request contains a condition ("if X ... otherwise ..."),
   respond instead with a branches object covering every branch:
   {{"setup": [<calls always run first>],
     "branches": [{{"condition": {{"field": "$N.field", "op": ">", "value": 100}},
                    "calls": [...]}},
                   {{"condition": "else", "calls": [...]}}]}}
   Supported ops: > < >= <= == !=
   Never use this shape for a request without a condition.
4. If NO available tool can satisfy the request, respond with exactly:
   {{"error": "no tool available"}}

{REQUEST_MARKER} {scenario["request"]}"""


# ----------------------------------------------------------------------
# Dummy model
# ----------------------------------------------------------------------

def _concrete(value):
    """Turn a ground-truth arg value into a concrete model answer value."""
    if isinstance(value, dict) and "contains" in value:
        needles = value["contains"]
        if isinstance(needles, str):
            needles = [needles]
        return "The " + " ".join(needles) + " (auto-generated message)."
    return value


def _calls_from_expected(expected_calls):
    return [{"tool": c["tool"],
             "args": {k: _concrete(v) for k, v in c.get("args", {}).items()}}
            for c in expected_calls]


def perfect_response(scenario):
    """Serialize the ground truth as a valid model answer."""
    expected = scenario["expected"]
    if scenario["type"] == "rejection":
        return json.dumps(expected, ensure_ascii=False)
    if scenario["type"] == "conditional":
        answer = {
            "setup": _calls_from_expected(expected.get("setup", [])),
            "branches": [{"condition": b["condition"],
                          "calls": _calls_from_expected(b["calls"])}
                         for b in expected["branches"]],
        }
        return json.dumps(answer, ensure_ascii=False)
    return json.dumps(_calls_from_expected(expected), ensure_ascii=False)


def _build_dummy_responses():
    """request text -> hardcoded response, keyed by the scenario request."""
    all_scenarios = scenarios.get_scenarios(list(scenarios.VALIDATION_SCENARIOS))
    responses = {sc["request"]: perfect_response(sc) for sc in all_scenarios}
    by_id = {sc["id"]: sc for sc in all_scenarios}

    # Noisy but correct: exercises tolerant JSON extraction.
    responses[by_id["chain_01"]["request"]] = (
        "Sure! Here is my plan:\n```json\n"
        + perfect_response(by_id["chain_01"])
        + "\n```\nLet me know if you need anything else.")
    responses[by_id["one_shot_03"]["request"]] = (
        "I'll schedule it right away.\n\n"
        + perfect_response(by_id["one_shot_03"]))

    # Deliberate failure 1: raw value instead of a reference ($1.id).
    responses[by_id["chain_02"]["request"]] = json.dumps([
        {"tool": "find_customer", "args": {"name": "Maria Lopez"}},
        {"tool": "open_ticket",
         "args": {"customer_id": "CUST-123", "severity": "low",
                  "description": "billing question"}},
    ])
    # Deliberate failure 2: answers a rejection scenario with a tool call.
    responses[by_id["reject_01"]["request"]] = json.dumps([
        {"tool": "find_customer", "args": {"name": "John Smith"}},
    ])
    # Deliberate failure 3: conditional missing the else branch.
    responses[by_id["cond_04"]["request"]] = json.dumps({
        "setup": [{"tool": "get_balance", "args": {"account_id": "ACC-77"}}],
        "branches": [
            {"condition": {"field": "$1.balance", "op": "<", "value": 100},
             "calls": [{"tool": "open_ticket",
                        "args": {"customer_id": "C-77", "severity": "high",
                                 "description": "low balance alert"}}]},
        ],
    })
    return responses


_DUMMY_RESPONSES = None


def dummy_model(prompt):
    """Hardcoded model: looks up the response by the request line."""
    global _DUMMY_RESPONSES
    if _DUMMY_RESPONSES is None:
        _DUMMY_RESPONSES = _build_dummy_responses()
    request = prompt.rsplit(REQUEST_MARKER, 1)[-1].strip()
    return _DUMMY_RESPONSES.get(request, "I don't know what to do.")


# ----------------------------------------------------------------------
# Runner
# ----------------------------------------------------------------------

def run_benchmark(model_fn, scenario_list=None, csv_path="results.csv"):
    """Run every scenario through model_fn, print a per-type table,
    dump one CSV row per attempt. Returns the list of result dicts."""
    scenario_list = scenario_list or scenarios.get_scenarios()
    results = []
    for sc in scenario_list:
        response = model_fn(build_prompt(sc))
        verdict = verifier.verificar(sc, response)
        results.append({"scenario": sc, "response": response, **verdict})

    _print_table(results)
    _write_csv(results, csv_path)
    print(f"\nCSV written to {csv_path}")
    return results


def _print_table(results):
    by_type = {}
    for r in results:
        by_type.setdefault(r["scenario"]["type"], []).append(r)

    header = f"{'type':<14}{'passed':>8}{'total':>8}{'rate':>8}"
    print(header)
    print("-" * len(header))
    total_pass = 0
    for stype in sorted(by_type):
        rows = by_type[stype]
        passed = sum(r["pasa"] for r in rows)
        total_pass += passed
        print(f"{stype:<14}{passed:>8}{len(rows):>8}{passed / len(rows):>8.0%}")
    print("-" * len(header))
    print(f"{'TOTAL':<14}{total_pass:>8}{len(results):>8}"
          f"{total_pass / len(results):>8.0%}")

    failed = [r for r in results if not r["pasa"]]
    if failed:
        print("\nFailures:")
        for r in failed:
            codes = ", ".join(sorted({f['codigo'] for f in r["fallos"]}))
            print(f"  {r['scenario']['id']:<14} {codes}")


def _write_csv(results, path):
    with open(path, "w", newline="", encoding="utf-8") as fh:
        writer = csv.writer(fh)
        writer.writerow(["scenario_id", "type", "pasa", "fallos", "detalles",
                         "respuesta_modelo"])
        for r in results:
            writer.writerow([
                r["scenario"]["id"],
                r["scenario"]["type"],
                int(r["pasa"]),
                ";".join(f["codigo"] for f in r["fallos"]),
                ";".join(f["detalle"] for f in r["fallos"]),
                r["response"],
            ])


def main():
    parser = argparse.ArgumentParser(description="Run the agency benchmark.")
    parser.add_argument("--model", default="",
                        help="model name; omit to use the built-in dummy")
    parser.add_argument("--provider", default="ollama",
                        choices=["ollama", "cohere"],
                        help="provider for --model (default ollama)")
    parser.add_argument("--langs", default="",
                        help="comma-separated validation languages (es,pt,hi)")
    parser.add_argument("--csv", default="results.csv", help="output CSV path")
    args = parser.parse_args()
    langs = [l for l in args.langs.split(",") if l]

    if args.model:
        if args.provider == "cohere":
            from cohere_model import make_cohere_model
            model_fn = make_cohere_model(args.model)
        else:
            from ollama_model import make_ollama_model
            model_fn = make_ollama_model(args.model)
        print(f"Running against {args.provider} model: {args.model}\n")
    else:
        model_fn = dummy_model
    run_benchmark(model_fn, scenarios.get_scenarios(langs), args.csv)


if __name__ == "__main__":
    main()
