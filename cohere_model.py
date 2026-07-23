"""Adapter for the Cohere Chat API v2, stdlib only.

make_cohere_model(name) returns a (prompt) -> text function compatible
with runner.run_benchmark. Requires the COHERE_API_KEY environment
variable. A 6-10s pause is inserted between calls to respect the strict
trial-tier rate limit; 429 responses trigger exponential backoff.
"""

import json
import os
import random
import time
import urllib.error
import urllib.request

COHERE_URL = "https://api.cohere.com/v2/chat"


def _extract_text(body):
    """Concatenate the text blocks of a v2 chat response.

    v2 shape: {"message": {"content": [{"type": "text", "text": "..."}, ...]}}
    'thinking' blocks (if any) are skipped.
    """
    message = body.get("message", {})
    content = message.get("content", [])
    if isinstance(content, str):
        return content
    parts = []
    for block in content or []:
        if isinstance(block, dict) and block.get("type") == "text":
            parts.append(block.get("text", ""))
    return "".join(parts)


def make_cohere_model(model_name, url=COHERE_URL, timeout=60,
                      min_pause=6.0, max_pause=10.0, max_retries=5):
    """Build a model function that queries Cohere's Chat v2 API.

    The API key is read from COHERE_API_KEY at construction time. Each
    call (except the first) waits min_pause..max_pause seconds before
    sending, to stay under the trial-tier rate limit. On HTTP 429 the
    call backs off exponentially (honoring Retry-After when present) and
    retries up to max_retries times.
    """
    api_key = os.environ.get("COHERE_API_KEY")
    if not api_key:
        raise RuntimeError(
            "COHERE_API_KEY environment variable is not set. Export your "
            "Cohere API key first (get one at dashboard.cohere.com).")

    state = {"first": True}

    def model(prompt):
        # Throttle between calls, but not before the very first one.
        if state["first"]:
            state["first"] = False
        else:
            time.sleep(random.uniform(min_pause, max_pause))

        payload = json.dumps({
            "model": model_name,
            "messages": [{"role": "user", "content": prompt}],
        }).encode("utf-8")

        backoff = 2.0
        last_error = None
        for attempt in range(max_retries):
            request = urllib.request.Request(
                url, data=payload, method="POST",
                headers={
                    "Authorization": f"bearer {api_key}",
                    "Content-Type": "application/json",
                    "Accept": "application/json",
                })
            try:
                with urllib.request.urlopen(request, timeout=timeout) as resp:
                    body = json.load(resp)
                return _extract_text(body)
            except urllib.error.HTTPError as err:
                detail = err.read().decode("utf-8", errors="replace")
                if err.code == 401:
                    raise RuntimeError(
                        "Cohere returned 401 Unauthorized: the key in "
                        "COHERE_API_KEY is invalid or revoked."
                    ) from err
                if err.code == 404:
                    raise RuntimeError(
                        f"Cohere returned 404 for model '{model_name}': the "
                        f"model id is likely wrong. Verify the exact id at "
                        f"docs.cohere.com/docs/models."
                    ) from err
                if err.code == 429:
                    if attempt == max_retries - 1:
                        raise RuntimeError(
                            f"Cohere rate limit (429) still hitting after "
                            f"{max_retries} retries. Trial keys are strict — "
                            f"wait and rerun, or raise the pause."
                        ) from err
                    retry_after = err.headers.get("Retry-After")
                    wait = float(retry_after) if retry_after else backoff
                    time.sleep(wait)
                    backoff *= 2
                    last_error = err
                    continue
                if err.code == 422 and "NO_VALID_RESPONSE_GENERATED" in detail:
                    # Transient: this reasoning model occasionally emits only a
                    # 'thinking' block and no final text, which Cohere reports
                    # as 422 NO_VALID_RESPONSE_GENERATED. Retry with backoff.
                    if attempt == max_retries - 1:
                        raise RuntimeError(
                            f"Cohere kept returning 422 "
                            f"NO_VALID_RESPONSE_GENERATED after {max_retries} "
                            f"retries (model produced no final text): {detail}"
                        ) from err
                    time.sleep(backoff)
                    backoff *= 2
                    last_error = err
                    continue
                raise RuntimeError(
                    f"Cohere returned HTTP {err.code}: {detail}") from err
            except (urllib.error.URLError, TimeoutError, OSError) as err:
                if attempt == max_retries - 1:
                    raise RuntimeError(
                        f"Could not reach Cohere at {url} after "
                        f"{max_retries} attempts ({err})."
                    ) from err
                time.sleep(backoff)
                backoff *= 2
                last_error = err
        raise RuntimeError(f"Cohere call failed: {last_error}")

    return model
