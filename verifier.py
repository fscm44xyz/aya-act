"""Automatic verifier: compares a model response against scenario ground truth.

Entry point: verificar(escenario, respuesta_modelo) -> {"pasa": bool,
"fallos": [{"codigo": str, "detalle": str}]}.

Failure codes
-------------
orden_incorrecto        right calls, wrong order
referencia_no_resuelta  raw/literal value where a "$N.field" reference was
                        required, or a dangling reference ("referencia
                        colgante"): $N points at a step that does not exist
                        before it in the model's own response
herramienta_inexistente called a tool not available in the scenario
args_incorrectos        wrong argument names, values, wrong reference, or a
                        value whose JSON type does not match the tool schema
                        (e.g. a number where the schema declares "string")
rama_faltante           conditional: an expected branch is missing
no_rechazo              rejection scenario not answered with the rejection object
-- additional codes --
formato_invalido        no JSON could be extracted, or wrong top-level shape
rechazo_indebido        rejected although an available tool could satisfy the request
longitud_incorrecta     wrong number of calls
rama_sobrante           conditional: model produced an extra, unexpected branch
envoltura_incorrecta    NON-FATAL: linear plan wrapped in a setup/branches
                        structure; the calls are unwrapped and verified normally
pasos_extra             NON-FATAL: all required ground-truth calls are present
                        in valid order, plus one or more EXTRA read-only calls
                        (a defensible superset that causes no undue effects)
paso_extra_con_efecto   extra, unrequested call to a side-effecting tool
                        (transfer, notify, ...) — a real undue effect, fatal

Superset policy
---------------
A plan is accepted (with a non-fatal pasos_extra) when the ground-truth
calls appear as an ordered subsequence and every additional call is
read-only. An additional call to a side-effecting tool is fatal
(paso_extra_con_efecto). Ordering, arguments, references, rejection and
branch logic are NOT relaxed by this policy.

Parsing is format-tolerant (JSON embedded in prose, code fences, multiple
top-level objects); verification logic is strict.
"""

import json
import re

from tools import SIDE_EFFECT_TOOLS, TOOLS

REJECTION_ERROR = "no tool available"

# Codes recorded in `fallos` but which do not, on their own, fail the attempt.
NON_FATAL_CODES = {"envoltura_incorrecta", "pasos_extra"}

_REFERENCE_RE = re.compile(r"^\$(\d+)\.([A-Za-z_]\w*)$")
_CONDITION_STR_RE = re.compile(r"^(\S+)\s*(>=|<=|==|!=|=|>|<)\s*(.+)$")


# ----------------------------------------------------------------------
# Tolerant JSON extraction
# ----------------------------------------------------------------------

def extract_json(text):
    """Extract JSON value(s) from free-form model output.

    Handles code fences, surrounding prose, and a sequence of top-level
    call objects. Returns a single parsed value (list or dict), or None.
    """
    if not isinstance(text, str):
        return None
    # Prefer fenced blocks if present.
    fences = re.findall(r"```(?:json)?\s*(.*?)```", text, flags=re.DOTALL)
    candidates = fences if fences else [text]

    for chunk in candidates:
        values = _decode_stream(chunk)
        if not values:
            continue
        if len(values) == 1:
            return values[0]
        # Several top-level objects: treat call-shaped dicts as a sequence.
        if all(isinstance(v, dict) and "tool" in v for v in values):
            return values
        return values[0]
    if fences:
        # Fall back to the whole text if the fences held no valid JSON.
        values = _decode_stream(text)
        if values:
            return values[0]
    return None


def _decode_stream(text):
    """Decode every top-level JSON object/array found left-to-right."""
    decoder = json.JSONDecoder()
    values = []
    i = 0
    n = len(text)
    while i < n:
        if text[i] not in "{[":
            i += 1
            continue
        try:
            value, end = decoder.raw_decode(text, i)
        except ValueError:
            i += 1
            continue
        values.append(value)
        i = end
    return values


# ----------------------------------------------------------------------
# Normalization helpers
# ----------------------------------------------------------------------

def parse_reference(value):
    """Return (step, field) if value is a "$N.field" reference, else None."""
    if not isinstance(value, str):
        return None
    m = _REFERENCE_RE.match(value.strip())
    if not m:
        return None
    return int(m.group(1)), m.group(2)


def _norm_scalar(value):
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        f = float(value)
        return int(f) if f.is_integer() else f
    if isinstance(value, str):
        s = value.strip()
        try:
            return _norm_scalar(float(s))
        except ValueError:
            return s.casefold()
    return value


def normalize_condition(cond):
    """Normalize a branch condition to a comparable tuple, or None if invalid.

    Accepts the structured form {"field", "op", "value"}, the strings
    "else"/"otherwise"/"default", or a plain string like "$1.balance > 1000".
    """
    if isinstance(cond, str):
        s = cond.strip()
        if s.casefold() in ("else", "otherwise", "default", ""):
            return ("else",)
        m = _CONDITION_STR_RE.match(s)
        if m:
            cond = {"field": m.group(1), "op": m.group(2), "value": m.group(3)}
        else:
            return None
    if isinstance(cond, dict) and {"field", "op", "value"} <= set(cond):
        op = "==" if cond["op"] == "=" else str(cond["op"]).strip()
        value = _norm_scalar(cond["value"])
        if isinstance(value, str):
            value = value.strip("'\"").casefold()
        return (str(cond["field"]).strip(), op, value)
    return None


def _fmt(value):
    return json.dumps(value, ensure_ascii=False)


def _type_mismatch(value, declared):
    """Whether a concrete literal violates its declared schema type.

    Declared types are "string" / "number" / "boolean". References
    ("$N.field") resolve at runtime and are exempt. bool is NOT accepted
    as a number (and vice versa), so a JSON true/false where a number is
    expected is a mismatch.
    """
    if parse_reference(value) is not None:
        return False
    if declared == "string":
        return not isinstance(value, str)
    if declared == "number":
        return isinstance(value, bool) or not isinstance(value, (int, float))
    if declared == "boolean":
        return not isinstance(value, bool)
    return False  # unknown declared type: do not enforce


# ----------------------------------------------------------------------
# Call-sequence comparison
# ----------------------------------------------------------------------

def _compare_arg(exp, got, where, fallos):
    """Compare one expected arg value with the model's value."""
    exp_ref = parse_reference(exp) if isinstance(exp, str) else None
    got_ref = parse_reference(got) if isinstance(got, str) else None

    if exp_ref is not None:
        if got_ref is None:
            fallos.append({
                "codigo": "referencia_no_resuelta",
                "detalle": f"{where}: expected reference {exp!r}, got raw value {_fmt(got)}",
            })
        elif got_ref != exp_ref:
            fallos.append({
                "codigo": "args_incorrectos",
                "detalle": f"{where}: expected reference {exp!r}, got {got!r}",
            })
        return

    if isinstance(exp, dict) and "contains" in exp:
        needles = exp["contains"]
        if isinstance(needles, str):
            needles = [needles]
        haystack = str(got).casefold() if got is not None else ""
        missing = [s for s in needles if s.casefold() not in haystack]
        if missing:
            fallos.append({
                "codigo": "args_incorrectos",
                "detalle": f"{where}: value {_fmt(got)} does not contain {missing}",
            })
        return

    if got_ref is not None:
        fallos.append({
            "codigo": "args_incorrectos",
            "detalle": f"{where}: expected literal {_fmt(exp)}, got reference {got!r}",
        })
        return

    if _norm_scalar(exp) != _norm_scalar(got):
        fallos.append({
            "codigo": "args_incorrectos",
            "detalle": f"{where}: expected {_fmt(exp)}, got {_fmt(got)}",
        })


def _compare_call(expected, got, where, fallos):
    """Compare args of one expected call vs one model call (same tool)."""
    exp_args = expected.get("args", {}) or {}
    got_args = got.get("args", {}) or {}
    if not isinstance(got_args, dict):
        fallos.append({"codigo": "formato_invalido",
                       "detalle": f"{where}: 'args' is not an object"})
        return
    param_types = TOOLS.get(expected.get("tool"), {}).get("params", {})
    for key in sorted(set(exp_args) | set(got_args)):
        if key not in got_args:
            fallos.append({"codigo": "args_incorrectos",
                           "detalle": f"{where}: missing argument '{key}'"})
        elif key not in exp_args:
            fallos.append({"codigo": "args_incorrectos",
                           "detalle": f"{where}: unexpected argument '{key}'"})
        else:
            declared = param_types.get(key)
            if declared is not None and _type_mismatch(got_args[key], declared):
                fallos.append({
                    "codigo": "args_incorrectos",
                    "detalle": (f"{where}.{key}: expected type '{declared}', "
                                f"got {_fmt(got_args[key])}"),
                })
            _compare_arg(exp_args[key], got_args[key], f"{where}.{key}", fallos)


def _call_signature(call):
    return call.get("tool") if isinstance(call, dict) else None


def _subsequence_positions(expected_names, got_names):
    """Greedily match expected_names as an ordered subsequence of got_names.

    Returns the list of matched positions in got_names (one per expected
    name, strictly increasing), or None if the subsequence is not present.
    """
    positions = []
    start = 0
    for name in expected_names:
        found = None
        for j in range(start, len(got_names)):
            if got_names[j] == name:
                found = j
                break
        if found is None:
            return None
        positions.append(found)
        start = found + 1
    return positions


def verify_calls(expected_calls, got, available_tools, fallos, where="call",
                 n_prior=0):
    """Verify a linear call sequence; appends failures to `fallos`.

    n_prior: number of steps that precede this sequence in the model's
    response (e.g. setup length for branch calls) — used to validate that
    every "$N.field" reference points at an already-existing step.
    """
    if not isinstance(got, list):
        got = [got]

    calls = []
    for i, item in enumerate(got, start=1):
        if not isinstance(item, dict) or "tool" not in item:
            fallos.append({"codigo": "formato_invalido",
                           "detalle": f"{where} {i}: not a call object"})
            continue
        if item["tool"] not in available_tools:
            fallos.append({"codigo": "herramienta_inexistente",
                           "detalle": f"{where} {i}: unknown tool '{item['tool']}'"})
        calls.append(item)

    # Dangling references: $N must point at a step strictly before the one
    # using it (checked in the model's own order, before any realignment).
    for i, call in enumerate(calls, start=1):
        args = call.get("args")
        if not isinstance(args, dict):
            continue
        for key, value in args.items():
            ref = parse_reference(value)
            if ref is not None and not (1 <= ref[0] <= n_prior + i - 1):
                fallos.append({
                    "codigo": "referencia_no_resuelta",
                    "detalle": (f"{where} {i}.{key}: referencia colgante "
                                f"{value!r} — step {ref[0]} does not exist "
                                f"before this call"),
                })

    exp_names = [c["tool"] for c in expected_calls]
    got_names = [_call_signature(c) for c in calls]

    # Superset policy: if the model produced MORE calls than the ground
    # truth and the ground-truth calls appear as an ordered subsequence,
    # accept it as long as every extra call is read-only. Extra calls to
    # side-effecting tools stay fatal.
    if len(calls) > len(expected_calls):
        positions = _subsequence_positions(exp_names, got_names)
        if positions is not None:
            matched = set(positions)
            extra = [calls[j] for j in range(len(calls)) if j not in matched]
            effectful = sorted({c["tool"] for c in extra
                                if c["tool"] in SIDE_EFFECT_TOOLS})
            if effectful:
                fallos.append({
                    "codigo": "paso_extra_con_efecto",
                    "detalle": (f"{where}s: extra unrequested side-effecting "
                                f"call(s) {effectful} beyond ground truth"),
                })
            else:
                fallos.append({
                    "codigo": "pasos_extra",
                    "detalle": (f"{where}s: {len(extra)} extra read-only "
                                f"call(s) {sorted({c['tool'] for c in extra})} "
                                f"beyond ground truth (benign superset)"),
                })
            for exp_i, pos in enumerate(positions):
                expected = expected_calls[exp_i]
                _compare_call(expected, calls[pos],
                              f"{where} {pos + 1} ({expected['tool']})", fallos)
            return

    if len(calls) != len(expected_calls):
        fallos.append({
            "codigo": "longitud_incorrecta",
            "detalle": (f"{where}s: expected {len(expected_calls)} call(s), "
                        f"got {len(calls)}"),
        })

    if exp_names != got_names and sorted(exp_names) == sorted(got_names):
        fallos.append({
            "codigo": "orden_incorrecto",
            "detalle": (f"{where}s: expected order {exp_names}, "
                        f"got {got_names}"),
        })
        # Align by tool name so arg errors can still be reported.
        remaining = list(calls)
        aligned = []
        for name in exp_names:
            match = next((c for c in remaining if c["tool"] == name), None)
            if match is not None:
                remaining.remove(match)
            aligned.append(match)
        calls = aligned

    for i, expected in enumerate(expected_calls):
        if i >= len(calls) or calls[i] is None:
            continue
        got_call = calls[i]
        if got_call["tool"] != expected["tool"]:
            fallos.append({
                "codigo": "args_incorrectos",
                "detalle": (f"{where} {i + 1}: expected tool "
                            f"'{expected['tool']}', got '{got_call['tool']}'"),
            })
            continue
        _compare_call(expected, got_call, f"{where} {i + 1} ({expected['tool']})",
                      fallos)


# ----------------------------------------------------------------------
# Per-type verification
# ----------------------------------------------------------------------

def _verify_rejection(expected, parsed, fallos):
    if isinstance(parsed, dict) and "error" in parsed:
        exp_msg = str(expected["error"]).strip().casefold()
        got_msg = str(parsed["error"]).strip().casefold()
        if got_msg != exp_msg:
            fallos.append({
                "codigo": "no_rechazo",
                "detalle": (f"rejection message mismatch: expected "
                            f"{expected['error']!r}, got {parsed['error']!r}"),
            })
    else:
        fallos.append({
            "codigo": "no_rechazo",
            "detalle": "expected the rejection object, got tool calls instead",
        })


def _verify_conditional(expected, parsed, available_tools, fallos):
    if not isinstance(parsed, dict) or "branches" not in parsed:
        fallos.append({
            "codigo": "rama_faltante",
            "detalle": "response has no 'branches' structure",
        })
        return

    setup = parsed.get("setup", [])
    verify_calls(expected.get("setup", []), setup, available_tools, fallos,
                 where="setup call")
    n_setup = len(setup) if isinstance(setup, list) else 1

    got_branches = parsed["branches"]
    if not isinstance(got_branches, list):
        fallos.append({"codigo": "formato_invalido",
                       "detalle": "'branches' is not a list"})
        return

    remaining = []
    for i, branch in enumerate(got_branches, start=1):
        if not isinstance(branch, dict):
            fallos.append({"codigo": "formato_invalido",
                           "detalle": f"branch {i}: not an object"})
            continue
        remaining.append(branch)

    for exp_branch in expected["branches"]:
        exp_cond = normalize_condition(exp_branch["condition"])
        match = next(
            (b for b in remaining
             if normalize_condition(b.get("condition")) == exp_cond),
            None)
        if match is None:
            fallos.append({
                "codigo": "rama_faltante",
                "detalle": f"missing branch for condition {_fmt(exp_branch['condition'])}",
            })
            continue
        remaining.remove(match)
        verify_calls(exp_branch["calls"], match.get("calls", []),
                     available_tools, fallos,
                     where=f"branch[{_fmt(exp_branch['condition'])}] call",
                     n_prior=n_setup)

    for extra in remaining:
        fallos.append({
            "codigo": "rama_sobrante",
            "detalle": f"unexpected branch with condition {_fmt(extra.get('condition'))}",
        })


# ----------------------------------------------------------------------
# Entry point
# ----------------------------------------------------------------------

def verificar(escenario, respuesta_modelo):
    """Verify a raw model response against a scenario's ground truth.

    Returns {"pasa": bool, "fallos": [{"codigo", "detalle"}, ...]}.
    """
    fallos = []
    parsed = extract_json(respuesta_modelo)

    if parsed is None:
        return {"pasa": False,
                "fallos": [{"codigo": "formato_invalido",
                            "detalle": "no JSON found in response"}]}

    stype = escenario["type"]
    expected = escenario["expected"]
    available = set(escenario["tools"])

    if stype == "rejection":
        _verify_rejection(expected, parsed, fallos)
    elif isinstance(parsed, dict) and "error" in parsed:
        fallos.append({
            "codigo": "rechazo_indebido",
            "detalle": ("model rejected the request although an available "
                        "tool satisfies it"),
        })
    elif stype == "conditional":
        _verify_conditional(expected, parsed, available, fallos)
    else:  # one_shot, data_chain
        if isinstance(parsed, dict) and "tool" in parsed:
            parsed = [parsed]
        elif (isinstance(parsed, dict) and "setup" in parsed
              and not parsed.get("branches")):
            # Tolerant unwrapping: linear plan wrapped in the conditional
            # shape with no real branches. Non-fatal, but recorded.
            fallos.append({
                "codigo": "envoltura_incorrecta",
                "detalle": ("linear plan wrapped in setup/branches "
                            "structure; unwrapped and verified normally"),
            })
            parsed = parsed["setup"]
        if not isinstance(parsed, list):
            fallos.append({"codigo": "formato_invalido",
                           "detalle": "expected a JSON array of calls"})
        else:
            verify_calls(expected, parsed, available, fallos)

    pasa = all(f["codigo"] in NON_FATAL_CODES for f in fallos)
    return {"pasa": pasa, "fallos": fallos}
