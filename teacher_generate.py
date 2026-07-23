"""Teacher mode: sample a strong model to build a verifier-approved dataset.

For each scenario, sample the model up to k times (pacing handled by the
model adapter's own rate-limit pauses). After each sample, run the
verifier and keep the FIRST completion that passes (pasa=True — non-fatal
codes such as pasos_extra / envoltura_incorrecta are, by definition, still
a pass). Scenarios where no sample passes within k tries are recorded as
"sin_dato" for manual review.

Output (JSONL, one line per scenario that produced data):
  {escenario_id, tipo, idioma, prompt_completo, respuesta_valida, intentos_usados}
The prompt_completo is exactly what the model saw (schemas + protocol +
request); respuesta_valida is the raw completion that passed.

Usage:
  python teacher_generate.py --provider cohere --model north-mini-code-1-0 \
      --k 4 --out teacher_core.jsonl
"""

import argparse
import json

import runner
import scenarios
import verifier


def generate_dataset(model_fn, scenario_list, k, jsonl_path,
                     default_lang="en"):
    """Sample model_fn up to k times per scenario; write passing samples.

    Returns a summary dict. Model/HTTP errors on a single sample are
    treated as a failed attempt (logged, not fatal) so one bad scenario
    cannot abort the whole run.
    """
    con_dato, sin_dato = [], []
    total_attempts = 0

    with open(jsonl_path, "w", encoding="utf-8") as fh:
        for sc in scenario_list:
            prompt = runner.build_prompt(sc)
            idioma = sc.get("idioma", default_lang)
            valid, used = None, 0

            for attempt in range(1, k + 1):
                used = attempt
                try:
                    response = model_fn(prompt)
                except Exception as err:  # transient API/model failure
                    print(f"  [ERR ] {sc['id']:<14} attempt {attempt}/{k}: {err}")
                    continue
                if verifier.verificar(sc, response)["pasa"]:
                    valid = response
                    break

            total_attempts += used
            if valid is not None:
                fh.write(json.dumps({
                    "escenario_id": sc["id"],
                    "tipo": sc["type"],
                    "idioma": idioma,
                    "prompt_completo": prompt,
                    "respuesta_valida": valid,
                    "intentos_usados": used,
                }, ensure_ascii=False) + "\n")
                con_dato.append(sc["id"])
                print(f"  [OK  ] {sc['id']:<14} valid on attempt {used}/{k}")
            else:
                sin_dato.append(sc["id"])
                print(f"  [MISS] {sc['id']:<14} no valid sample in {k} attempts")

    n = len(scenario_list)
    summary = {
        "con_dato": con_dato,
        "sin_dato": sin_dato,
        "avg_attempts": total_attempts / n if n else 0.0,
    }

    # Record sin_dato separately for manual review.
    if sin_dato:
        review_path = jsonl_path + ".sin_dato.json"
        with open(review_path, "w", encoding="utf-8") as rf:
            json.dump(sin_dato, rf, ensure_ascii=False, indent=2)

    print("\n=== Teacher summary ===")
    print(f"scenarios with data  : {len(con_dato)}/{n}")
    print(f"scenarios sin_dato   : {len(sin_dato)}/{n}"
          + (f" -> {sin_dato} (see {jsonl_path}.sin_dato.json)"
             if sin_dato else ""))
    print(f"avg attempts/scenario: {summary['avg_attempts']:.2f}")
    print(f"JSONL written to {jsonl_path}")
    return summary


def main():
    parser = argparse.ArgumentParser(description="Teacher-model dataset generator.")
    parser.add_argument("--model", required=True, help="model name / id")
    parser.add_argument("--provider", default="cohere",
                        choices=["ollama", "cohere"])
    parser.add_argument("--k", type=int, default=4,
                        help="max samples per scenario (default 4)")
    parser.add_argument("--out", default="teacher_core.jsonl",
                        help="output JSONL path")
    parser.add_argument("--langs", default="",
                        help="validation languages to include (es,pt,hi)")
    args = parser.parse_args()

    if args.provider == "cohere":
        from cohere_model import make_cohere_model
        model_fn = make_cohere_model(args.model)
    else:
        from ollama_model import make_ollama_model
        model_fn = make_ollama_model(args.model)

    langs = [l for l in args.langs.split(",") if l]
    print(f"Teacher: {args.provider}:{args.model}, k={args.k}\n")
    generate_dataset(model_fn, scenarios.get_scenarios(langs), args.k, args.out)


if __name__ == "__main__":
    main()
