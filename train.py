"""SFT (QLoRA) for CohereLabs/tiny-aya-global on MY agency dataset.

Unlike the official tool-calling script, this trains the model to emit MY
JSON protocol (an array of {"tool","args"} calls, a {"setup","branches"}
object, or {"error": "no tool available"}) — NOT Cohere's <tool_call> XML.

My dataset (train.jsonl) is already in Cohere chat shape, where each User
message contains the tool schemas AND the output protocol inline, and the
Chatbot message is the target JSON. We therefore do NOT use the template's
tools= mechanism: with no tools passed, the Aya template just wraps my
content in its turn tokens (<|USER_TOKEN|>, <|START_RESPONSE|>, ...), which
is exactly what keeps training consistent with the benchmark/verifier.

Install (PyTorch 2.8 + CUDA 12.8 assumed already present — do NOT reinstall torch):
    pip install "trl[peft]" bitsandbytes transformers datasets accelerate
"""

import torch
from datasets import load_dataset
from peft import LoraConfig, PeftModel
from transformers import AutoModelForCausalLM, AutoTokenizer, BitsAndBytesConfig

from trl import SFTConfig, SFTTrainer

MODEL_ID = "CohereLabs/tiny-aya-global"
DATA_FILE = "train.jsonl"
OUTPUT_DIR = "tiny-aya-agent-v1"
CHAT_TEMPLATE_PATH = "/workspace/trl/examples/scripts/tiny_aya_chat_template.jinja"


def make_bnb_config():
    """QLoRA 4-bit config (identical to the official script)."""
    return BitsAndBytesConfig(
        load_in_4bit=True,
        bnb_4bit_compute_dtype=torch.float16,
        bnb_4bit_use_double_quant=True,
        bnb_4bit_quant_type="nf4",
    )


def create_conversation(sample):
    """Map one {"messages": [User, Chatbot]} row to prompt/completion.

    Roles are lowercased to user/assistant (what the Aya template expects).
    No tools are attached: my content already carries schemas + protocol,
    and the target is my raw JSON string. Giving prompt and completion
    separately makes SFTTrainer mask the prompt and train on the JSON only.
    """
    user_msg = next(m for m in sample["messages"] if m["role"] == "User")
    asst_msg = next(m for m in sample["messages"] if m["role"] == "Chatbot")
    return {
        "prompt": [{"role": "user", "content": user_msg["content"]}],
        "completion": [{"role": "assistant", "content": asst_msg["content"]}],
    }


def main():
    # --- Data: MY local dataset, converted to prompt/completion ---
    dataset = load_dataset("json", data_files=DATA_FILE, split="train")
    dataset = dataset.map(create_conversation, remove_columns=dataset.column_names)
    # Tiny 20-example end-to-end validation run: train on all, no eval split.

    # --- Model: 4-bit QLoRA (unchanged from official) ---
    model = AutoModelForCausalLM.from_pretrained(
        MODEL_ID,
        attn_implementation="sdpa",
        dtype=torch.float16,
        quantization_config=make_bnb_config(),
    )

    peft_config = LoraConfig(
        r=32,
        lora_alpha=32,
        target_modules=["q_proj", "k_proj", "v_proj", "o_proj",
                        "gate_proj", "up_proj", "down_proj"],
    )

    training_args = SFTConfig(
        output_dir=OUTPUT_DIR,
        per_device_train_batch_size=1,
        gradient_accumulation_steps=4,
        chat_template_path=CHAT_TEMPLATE_PATH,
        warmup_steps=5,
        learning_rate=2e-4,
        optim="paged_adamw_8bit",
        # Test-run adjustments:
        num_train_epochs=3,        # was a single step
        max_length=2048,           # my prompts carry the full protocol
        logging_steps=1,           # see the loss every step
        report_to="none",          # no trackio / hub
        push_to_hub=False,
        # use_liger_kernel / activation_offloading dropped (fragile extra deps).
    )

    trainer = SFTTrainer(
        model=model,
        args=training_args,
        train_dataset=dataset,
        peft_config=peft_config,
    )
    trainer.train()
    trainer.save_model(OUTPUT_DIR)  # saves adapter + tokenizer (with template)

    # --- Sanity inference: one training prompt, end to end ---
    # Reload the tokenizer from OUTPUT_DIR so it carries the exact chat
    # template used in training, then reattach the adapter to the base model.
    tokenizer = AutoTokenizer.from_pretrained(OUTPUT_DIR)
    base = AutoModelForCausalLM.from_pretrained(
        MODEL_ID,
        attn_implementation="sdpa",
        dtype=torch.float16,
        quantization_config=make_bnb_config(),
        device_map="auto",
    )
    infer_model = PeftModel.from_pretrained(base, OUTPUT_DIR)
    infer_model.eval()

    raw = load_dataset("json", data_files=DATA_FILE, split="train")[0]
    user_msg = next(m for m in raw["messages"] if m["role"] == "User")
    prompt_ids = tokenizer.apply_chat_template(
        [{"role": "user", "content": user_msg["content"]}],
        add_generation_prompt=True,
        return_tensors="pt",
    ).to("cuda")

    with torch.no_grad():
        out = infer_model.generate(
            prompt_ids, max_new_tokens=256, do_sample=False,
            pad_token_id=tokenizer.eos_token_id,
        )
    generated = tokenizer.decode(out[0][prompt_ids.shape[-1]:],
                                 skip_special_tokens=True)

    print("\n================ SANITY INFERENCE ================")
    print("USER REQUEST (tail):",
          user_msg["content"].rsplit("USER REQUEST:", 1)[-1].strip())
    print("--- MODEL OUTPUT ---")
    print(generated)
    print("--- EXPECTED (train target) ---")
    print(next(m for m in raw["messages"] if m["role"] == "Chatbot")["content"])
    print("==================================================")


if __name__ == "__main__":
    main()
