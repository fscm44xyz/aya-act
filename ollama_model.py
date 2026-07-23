"""Adapter for a local Ollama server, stdlib only.

make_ollama_model(name) returns a (prompt) -> text function compatible
with runner.run_benchmark. Example:

    from ollama_model import make_ollama_model
    model = make_ollama_model("hf.co/CohereLabs/tiny-aya-global-GGUF:Q4_K_M")
    run_benchmark(model)
"""

import json
import urllib.error
import urllib.request

OLLAMA_URL = "http://localhost:11434/api/chat"


def make_ollama_model(model_name, url=OLLAMA_URL, timeout=120):
    """Build a model function that queries Ollama's chat API.

    timeout is per request (generous: small models on CPU are slow).
    Connection failures are retried once; if the server still cannot be
    reached, a clear error explains that Ollama must be running.
    """

    def model(prompt):
        payload = json.dumps({
            "model": model_name,
            "messages": [{"role": "user", "content": prompt}],
            "stream": False,
            "options": {"temperature": 0},
        }).encode("utf-8")

        last_error = None
        for attempt in range(2):
            request = urllib.request.Request(
                url, data=payload,
                headers={"Content-Type": "application/json"})
            try:
                with urllib.request.urlopen(request, timeout=timeout) as resp:
                    body = json.load(resp)
                break
            except urllib.error.HTTPError as err:
                # Server reachable but rejected the request (e.g. model not
                # pulled) — retrying will not help.
                detail = err.read().decode("utf-8", errors="replace")
                raise RuntimeError(
                    f"Ollama returned HTTP {err.code} for model "
                    f"'{model_name}': {detail}\n"
                    f"If the model is missing, run: ollama pull {model_name}"
                ) from err
            except (urllib.error.URLError, TimeoutError, OSError) as err:
                last_error = err
        else:
            raise RuntimeError(
                f"Could not reach Ollama at {url} after 2 attempts "
                f"({last_error}). Make sure Ollama is running "
                f"(start the Ollama app or run 'ollama serve')."
            ) from last_error

        if "error" in body:
            raise RuntimeError(f"Ollama error: {body['error']}")
        return body["message"]["content"]

    return model
