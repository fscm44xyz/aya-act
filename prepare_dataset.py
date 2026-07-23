"""Convert teacher_core.jsonl into a chat fine-tuning JSONL (train.jsonl).

Target format — Cohere chat fine-tuning (the shape Aya / Command models
expect). Each line is one conversation:

  {"messages": [{"role": "User",    "content": <input>},
                {"role": "Chatbot", "content": <output>}]}

  input  = the full planning prompt (tool schemas + output protocol +
           the user request) — exactly what the model sees at inference.
  output = the verifier-approved completion (the JSON plan).

Roles follow Cohere's convention: System / User / Chatbot (capitalized;
Cohere uses "Chatbot", not "assistant"). If instead you fine-tune the Aya
open weights via HuggingFace/transformers, flip ROLE_USER / ROLE_ASSISTANT
to "user" / "assistant" below — that is the only change needed.

--split-system moves the fixed instructions (tools + protocol) into a
System turn and leaves only the request in the User turn; some setups
generalize better that way. Default keeps the whole prompt as the User
turn, matching a plain (input -> output) pair.

Usage:
  python prepare_dataset.py --in teacher_core.jsonl --out train.jsonl
  python prepare_dataset.py --split-system
"""

import argparse
import json

# Cohere chat roles. For HF/transformers Aya fine-tuning use "user"/"assistant".
ROLE_SYSTEM = "System"
ROLE_USER = "User"
ROLE_ASSISTANT = "Chatbot"

REQUEST_MARKER = "USER REQUEST:"


def to_chat_example(record, split_system=False):
    """Turn one teacher record into a {'messages': [...]} chat example."""
    prompt = record["prompt_completo"]
    output = record["respuesta_valida"]
    if split_system:
        head, _, request = prompt.rpartition(REQUEST_MARKER)
        messages = [
            {"role": ROLE_SYSTEM, "content": head.strip()},
            {"role": ROLE_USER, "content": request.strip()},
            {"role": ROLE_ASSISTANT, "content": output},
        ]
    else:
        messages = [
            {"role": ROLE_USER, "content": prompt},
            {"role": ROLE_ASSISTANT, "content": output},
        ]
    return {"messages": messages}


def convert(in_path, out_path, split_system=False):
    n = 0
    with open(in_path, encoding="utf-8") as fin, \
            open(out_path, "w", encoding="utf-8") as fout:
        for line in fin:
            line = line.strip()
            if not line:
                continue
            example = to_chat_example(json.loads(line), split_system)
            fout.write(json.dumps(example, ensure_ascii=False) + "\n")
            n += 1
    shape = "system-split (3 turns)" if split_system else "single-user (2 turns)"
    print(f"Wrote {n} examples to {out_path} [{shape}]")
    return n


def main():
    parser = argparse.ArgumentParser(description="Prepare chat fine-tuning JSONL.")
    parser.add_argument("--in", dest="in_path", default="teacher_core.jsonl")
    parser.add_argument("--out", dest="out_path", default="train.jsonl")
    parser.add_argument("--split-system", action="store_true",
                        help="emit a System turn (tools+protocol) + User turn "
                             "(request only) instead of one User turn")
    args = parser.parse_args()
    convert(args.in_path, args.out_path, args.split_system)


if __name__ == "__main__":
    main()
