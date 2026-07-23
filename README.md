# aya-act

Core of a multi-step **agency benchmark** for small language models, plus a
teacher-model pipeline that turns the benchmark into verified fine-tuning data.

A *scenario* is (1) a set of tools with a schema, (2) a natural-language user
request, and (3) the expected correct call sequence (ground truth). A model
receives tools + request and answers with a JSON plan; a verifier compares the
plan against the ground truth and decides pass/fail automatically — no humans.

## Capabilities covered

Each scenario carries a type label:

- `one_shot` — a single call, no dependencies.
- `data_chain` — an argument references an earlier result via `"$N.field"`
  (the field of step N's result, 1-based).
- `rejection` — no available tool fits; the only correct answer is
  `{"error": "no tool available"}`.
- `conditional` — the request branches (`if X then A else B`); the ground truth
  encodes every branch with its condition.

## Modules

| File | Purpose |
|------|---------|
| `tools.py` | Pool of ~10 enterprise tools with schema + `side_effect` flag. |
| `scenarios.py` | Hand-written scenarios (20 core, English) + slots for `es`/`pt`/`hi` validation sets. |
| `verifier.py` | `verificar(escenario, respuesta) -> {pasa, fallos}`. Tolerant JSON extraction, strict logic: order, references (incl. dangling), arg values **and schema types**, rejection, branches, and a benign-superset policy (`pasos_extra`). |
| `runner.py` | Runs all scenarios through a model `(prompt) -> text`, prints a per-type table, dumps a CSV. Includes a hardcoded dummy model. |
| `ollama_model.py` | Adapter for a local Ollama server (stdlib only). |
| `cohere_model.py` | Adapter for the Cohere Chat v2 API (stdlib only; key from `COHERE_API_KEY`). |
| `teacher_generate.py` | Teacher mode: sample a strong model up to *k* times per scenario, keep the first verifier-approved completion, dump a JSONL dataset. |
| `prepare_dataset.py` | Convert the teacher dataset into a chat fine-tuning JSONL (`train.jsonl`). |
| `tests/` | Verifier unit tests (one per failure mode). |

## Usage

```bash
# Run the benchmark with the dummy model (no API)
python runner.py

# Benchmark a real model
python runner.py --provider ollama --model <name>
python runner.py --provider cohere --model north-mini-code-1-0 --csv baseline.csv

# Generate verified training data with a teacher model
python teacher_generate.py --provider cohere --model north-mini-code-1-0 --k 4 --out teacher_core.jsonl

# Convert to a chat fine-tuning JSONL
python prepare_dataset.py --in teacher_core.jsonl --out train.jsonl

# Tests
python -m unittest discover -s tests
```

The Cohere adapter reads the API key from the `COHERE_API_KEY` environment
variable — no key is ever stored in the repo.

## Data format

`train.jsonl` uses Cohere's chat fine-tuning shape (one conversation per line):

```json
{"messages": [{"role": "User", "content": "<full prompt>"}, {"role": "Chatbot", "content": "<verified JSON plan>"}]}
```

Roles are constants in `prepare_dataset.py`; switch to `user`/`assistant` for
HuggingFace/transformers fine-tuning of the Aya open weights.
