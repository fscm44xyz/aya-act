"""Adapter for a locally fine-tuned tiny-aya LoRA checkpoint.

make_local_model(base_model_id, adapter_path) returns a (prompt) -> text
function compatible with runner.run_benchmark. The base model is loaded
ONCE in 4-bit (same QLoRA config as train.py), the LoRA adapter is attached
on top with peft, and the tokenizer is loaded FROM adapter_path so it
carries the exact chat template saved during training.

Requires a CUDA GPU and:
    pip install "trl[peft]" bitsandbytes transformers datasets accelerate
"""

import torch
from peft import PeftModel
from transformers import AutoModelForCausalLM, AutoTokenizer, BitsAndBytesConfig


def make_local_model(base_model_id, adapter_path, max_new_tokens=512):
    """Load base + LoRA adapter once; return a (prompt) -> text function."""
    bnb_config = BitsAndBytesConfig(
        load_in_4bit=True,
        bnb_4bit_compute_dtype=torch.float16,
        bnb_4bit_use_double_quant=True,
        bnb_4bit_quant_type="nf4",
    )

    base = AutoModelForCausalLM.from_pretrained(
        base_model_id,
        attn_implementation="sdpa",
        dtype=torch.float16,
        quantization_config=bnb_config,
        device_map="auto",
    )
    model = PeftModel.from_pretrained(base, adapter_path)
    model.eval()

    # Tokenizer from the adapter dir: it holds the training chat template.
    tokenizer = AutoTokenizer.from_pretrained(adapter_path)
    pad_id = tokenizer.pad_token_id
    if pad_id is None:
        pad_id = tokenizer.eos_token_id

    def model_fn(prompt):
        # Render the single user turn with the chat template (adds Aya turn
        # tokens + the generation prompt), then tokenize WITHOUT re-adding
        # special tokens — the template already inserted them, so this avoids
        # a spurious leading BOS. Passing input_ids + attention_mask
        # explicitly keeps generate() robust.
        text = tokenizer.apply_chat_template(
            [{"role": "user", "content": prompt}],
            add_generation_prompt=True,
            tokenize=False,
        )
        inputs = tokenizer(
            text,
            return_tensors="pt",
            add_special_tokens=False,
        ).to(model.device)

        with torch.no_grad():
            outputs = model.generate(
                input_ids=inputs["input_ids"],
                attention_mask=inputs["attention_mask"],
                max_new_tokens=max_new_tokens,
                do_sample=False,
                pad_token_id=pad_id,
            )

        new_tokens = outputs[0][inputs["input_ids"].shape[-1]:]
        return tokenizer.decode(new_tokens, skip_special_tokens=True)

    return model_fn
