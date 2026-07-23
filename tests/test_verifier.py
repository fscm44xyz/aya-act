"""Verifier tests: each failure code is detected, correct answers pass."""

import json
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from verifier import verificar  # noqa: E402

CHAIN_SCENARIO = {
    "id": "t_chain",
    "type": "data_chain",
    "tools": ["find_customer", "get_account", "get_balance"],
    "request": "What is the balance of John Smith?",
    "expected": [
        {"tool": "find_customer", "args": {"name": "John Smith"}},
        {"tool": "get_account", "args": {"customer_id": "$1.id"}},
        {"tool": "get_balance", "args": {"account_id": "$2.account_id"}},
    ],
}

REJECTION_SCENARIO = {
    "id": "t_reject",
    "type": "rejection",
    "tools": ["find_customer", "notify"],
    "request": "Delete customer John Smith.",
    "expected": {"error": "no tool available"},
}

CONDITIONAL_SCENARIO = {
    "id": "t_cond",
    "type": "conditional",
    "tools": ["get_balance", "transfer", "notify"],
    "request": "Check ACC-5; if over 1000 transfer 500 to ACC-8, else notify C-77.",
    "expected": {
        "setup": [{"tool": "get_balance", "args": {"account_id": "ACC-5"}}],
        "branches": [
            {"condition": {"field": "$1.balance", "op": ">", "value": 1000},
             "calls": [{"tool": "transfer",
                        "args": {"source": "ACC-5", "destination": "ACC-8",
                                 "amount": 500}}]},
            {"condition": "else",
             "calls": [{"tool": "notify",
                        "args": {"customer_id": "C-77",
                                 "message": {"contains": ["insufficient"]}}}]},
        ],
    },
}

CHAIN_CORRECT = [
    {"tool": "find_customer", "args": {"name": "John Smith"}},
    {"tool": "get_account", "args": {"customer_id": "$1.id"}},
    {"tool": "get_balance", "args": {"account_id": "$2.account_id"}},
]

# Ground truth is the minimal find_customer -> notify; the scenario exposes
# extra read-only (get_invoice) and side-effecting (transfer) tools so tests
# can add benign vs undue extra steps.
SUPERSET_SCENARIO = {
    "id": "t_superset",
    "type": "data_chain",
    "tools": ["find_customer", "get_invoice", "notify", "transfer"],
    "request": "Notify Ana Torres that her invoice is ready.",
    "expected": [
        {"tool": "find_customer", "args": {"name": "Ana Torres"}},
        {"tool": "notify",
         "args": {"customer_id": "$1.id", "message": {"contains": ["invoice"]}}},
    ],
}


def codes(result):
    return {f["codigo"] for f in result["fallos"]}


class VerifierTests(unittest.TestCase):

    def test_correct_chain_passes_even_wrapped_in_prose(self):
        response = ("Of course! Here is the plan:\n```json\n"
                    + json.dumps(CHAIN_CORRECT, indent=2)
                    + "\n```\nHope that helps.")
        result = verificar(CHAIN_SCENARIO, response)
        self.assertTrue(result["pasa"], result["fallos"])
        self.assertEqual(result["fallos"], [])

    def test_unresolved_reference_detected(self):
        calls = json.loads(json.dumps(CHAIN_CORRECT))
        calls[1]["args"]["customer_id"] = "CUST-42"  # raw value, not "$1.id"
        result = verificar(CHAIN_SCENARIO, json.dumps(calls))
        self.assertFalse(result["pasa"])
        self.assertIn("referencia_no_resuelta", codes(result))

    def test_wrong_order_detected(self):
        calls = [CHAIN_CORRECT[1], CHAIN_CORRECT[0], CHAIN_CORRECT[2]]
        result = verificar(CHAIN_SCENARIO, json.dumps(calls))
        self.assertFalse(result["pasa"])
        self.assertIn("orden_incorrecto", codes(result))

    def test_unknown_tool_detected(self):
        calls = json.loads(json.dumps(CHAIN_CORRECT))
        calls[2]["tool"] = "delete_account"
        result = verificar(CHAIN_SCENARIO, json.dumps(calls))
        self.assertFalse(result["pasa"])
        self.assertIn("herramienta_inexistente", codes(result))

    def test_wrong_args_detected(self):
        calls = json.loads(json.dumps(CHAIN_CORRECT))
        calls[0]["args"]["name"] = "Jane Doe"
        result = verificar(CHAIN_SCENARIO, json.dumps(calls))
        self.assertFalse(result["pasa"])
        self.assertIn("args_incorrectos", codes(result))

    def test_rejection_answered_with_calls_is_no_rechazo(self):
        response = json.dumps(
            [{"tool": "find_customer", "args": {"name": "John Smith"}}])
        result = verificar(REJECTION_SCENARIO, response)
        self.assertFalse(result["pasa"])
        self.assertIn("no_rechazo", codes(result))

    def test_correct_rejection_passes(self):
        result = verificar(REJECTION_SCENARIO,
                           '{"error": "no tool available"}')
        self.assertTrue(result["pasa"], result["fallos"])

    def test_undue_rejection_detected(self):
        result = verificar(CHAIN_SCENARIO,
                           '{"error": "no tool available"}')
        self.assertFalse(result["pasa"])
        self.assertIn("rechazo_indebido", codes(result))

    def test_conditional_missing_branch_detected(self):
        response = json.dumps({
            "setup": [{"tool": "get_balance", "args": {"account_id": "ACC-5"}}],
            "branches": [
                {"condition": {"field": "$1.balance", "op": ">", "value": 1000},
                 "calls": [{"tool": "transfer",
                            "args": {"source": "ACC-5", "destination": "ACC-8",
                                     "amount": 500}}]},
                # else branch missing
            ],
        })
        result = verificar(CONDITIONAL_SCENARIO, response)
        self.assertFalse(result["pasa"])
        self.assertIn("rama_faltante", codes(result))

    def test_conditional_passes_with_string_condition(self):
        # Tolerant format: condition given as a plain string, message wording free.
        response = json.dumps({
            "setup": [{"tool": "get_balance", "args": {"account_id": "ACC-5"}}],
            "branches": [
                {"condition": "$1.balance > 1000",
                 "calls": [{"tool": "transfer",
                            "args": {"source": "ACC-5", "destination": "ACC-8",
                                     "amount": 500}}]},
                {"condition": "otherwise",
                 "calls": [{"tool": "notify",
                            "args": {"customer_id": "C-77",
                                     "message": "Your funds are insufficient."}}]},
            ],
        })
        result = verificar(CONDITIONAL_SCENARIO, response)
        self.assertTrue(result["pasa"], result["fallos"])

    def test_wrapped_linear_plan_unwrapped_and_passes(self):
        # Correct calls wrapped in the conditional shape with empty branches:
        # non-fatal envoltura_incorrecta, but the attempt passes.
        response = json.dumps({"setup": CHAIN_CORRECT, "branches": []})
        result = verificar(CHAIN_SCENARIO, response)
        self.assertTrue(result["pasa"], result["fallos"])
        self.assertEqual(codes(result), {"envoltura_incorrecta"})

    def test_wrapped_linear_plan_still_reports_real_failures(self):
        calls = json.loads(json.dumps(CHAIN_CORRECT))
        calls[1]["args"]["customer_id"] = "CUST-42"  # raw value inside wrapper
        response = json.dumps({"setup": calls})  # no "branches" key at all
        result = verificar(CHAIN_SCENARIO, response)
        self.assertFalse(result["pasa"])
        self.assertIn("envoltura_incorrecta", codes(result))
        self.assertIn("referencia_no_resuelta", codes(result))

    def test_dangling_reference_detected(self):
        calls = json.loads(json.dumps(CHAIN_CORRECT))
        calls[1]["args"]["customer_id"] = "$3.id"  # step 3 comes after call 2
        result = verificar(CHAIN_SCENARIO, json.dumps(calls))
        self.assertFalse(result["pasa"])
        self.assertIn("referencia_no_resuelta", codes(result))
        self.assertTrue(any("referencia colgante" in f["detalle"]
                            for f in result["fallos"]), result["fallos"])

    def test_self_reference_in_first_call_is_dangling(self):
        response = json.dumps([
            {"tool": "find_customer", "args": {"name": "$1.id"}}])
        result = verificar(CHAIN_SCENARIO, response)
        self.assertFalse(result["pasa"])
        self.assertTrue(any("referencia colgante" in f["detalle"]
                            for f in result["fallos"]), result["fallos"])

    def test_benign_superset_passes_with_pasos_extra(self):
        # find_customer -> get_invoice (extra read-only) -> notify.
        response = json.dumps([
            {"tool": "find_customer", "args": {"name": "Ana Torres"}},
            {"tool": "get_invoice", "args": {"customer_id": "$1.id"}},
            {"tool": "notify",
             "args": {"customer_id": "$1.id", "message": "Your invoice is ready."}},
        ])
        result = verificar(SUPERSET_SCENARIO, response)
        self.assertTrue(result["pasa"], result["fallos"])
        self.assertEqual(codes(result), {"pasos_extra"})

    def test_superset_with_side_effect_fails(self):
        # find_customer -> notify -> transfer (extra, undue side effect).
        response = json.dumps([
            {"tool": "find_customer", "args": {"name": "Ana Torres"}},
            {"tool": "notify",
             "args": {"customer_id": "$1.id", "message": "Your invoice is ready."}},
            {"tool": "transfer",
             "args": {"source": "ACC-1", "destination": "ACC-2", "amount": 999}},
        ])
        result = verificar(SUPERSET_SCENARIO, response)
        self.assertFalse(result["pasa"])
        self.assertIn("paso_extra_con_efecto", codes(result))

    def test_superset_does_not_hide_wrong_args(self):
        # Benign extra step present, but a required call has a wrong arg:
        # the real failure must still surface (and stay fatal).
        response = json.dumps([
            {"tool": "find_customer", "args": {"name": "WRONG NAME"}},
            {"tool": "get_invoice", "args": {"customer_id": "$1.id"}},
            {"tool": "notify",
             "args": {"customer_id": "$1.id", "message": "Your invoice is ready."}},
        ])
        result = verificar(SUPERSET_SCENARIO, response)
        self.assertFalse(result["pasa"])
        self.assertIn("args_incorrectos", codes(result))

    def test_extra_call_out_of_order_is_not_a_benign_superset(self):
        # Required subsequence not preserved (notify before find_customer):
        # must NOT be accepted as a superset.
        response = json.dumps([
            {"tool": "notify",
             "args": {"customer_id": "C-1", "message": "Your invoice is ready."}},
            {"tool": "get_invoice", "args": {"customer_id": "C-1"}},
            {"tool": "find_customer", "args": {"name": "Ana Torres"}},
        ])
        result = verificar(SUPERSET_SCENARIO, response)
        self.assertFalse(result["pasa"])
        self.assertNotIn("pasos_extra", codes(result))

    def test_correct_arg_type_passes(self):
        # zip declared as "string": a string value is accepted.
        scenario = {
            "id": "t_type_ok", "type": "one_shot", "tools": ["update_address"],
            "request": "Update record R-15.",
            "expected": [{"tool": "update_address",
                          "args": {"id": "R-15", "street": "42 Oak Street",
                                   "city": "Springfield", "zip": "62704"}}],
        }
        response = json.dumps([{"tool": "update_address",
                                "args": {"id": "R-15", "street": "42 Oak Street",
                                         "city": "Springfield", "zip": "62704"}}])
        result = verificar(scenario, response)
        self.assertTrue(result["pasa"], result["fallos"])

    def test_wrong_arg_type_fails(self):
        # zip declared as "string" but the model emits an integer 62704.
        scenario = {
            "id": "t_type_bad", "type": "one_shot", "tools": ["update_address"],
            "request": "Update record R-15.",
            "expected": [{"tool": "update_address",
                          "args": {"id": "R-15", "street": "42 Oak Street",
                                   "city": "Springfield", "zip": "62704"}}],
        }
        response = json.dumps([{"tool": "update_address",
                                "args": {"id": "R-15", "street": "42 Oak Street",
                                         "city": "Springfield", "zip": 62704}}])
        result = verificar(scenario, response)
        self.assertFalse(result["pasa"])
        self.assertIn("args_incorrectos", codes(result))
        self.assertTrue(any("expected type 'string'" in f["detalle"]
                            for f in result["fallos"]), result["fallos"])

    def test_number_arg_type_enforced(self):
        # transfer.amount declared "number": a stringified number is a mismatch.
        scenario = {
            "id": "t_num", "type": "data_chain",
            "tools": ["find_customer", "get_account", "transfer"],
            "request": "Transfer 250 from ACC-1 to David Kim.",
            "expected": [
                {"tool": "find_customer", "args": {"name": "David Kim"}},
                {"tool": "get_account", "args": {"customer_id": "$1.id"}},
                {"tool": "transfer", "args": {"source": "ACC-1",
                                              "destination": "$2.account_id",
                                              "amount": 250}}],
        }
        response = json.dumps([
            {"tool": "find_customer", "args": {"name": "David Kim"}},
            {"tool": "get_account", "args": {"customer_id": "$1.id"}},
            {"tool": "transfer", "args": {"source": "ACC-1",
                                          "destination": "$2.account_id",
                                          "amount": "250"}}])
        result = verificar(scenario, response)
        self.assertFalse(result["pasa"])
        self.assertIn("args_incorrectos", codes(result))

    def test_reference_exempt_from_type_check(self):
        # A "$N.field" reference must not be flagged as a type mismatch even
        # where the schema declares a non-string type.
        result = verificar(CHAIN_SCENARIO, json.dumps(CHAIN_CORRECT))
        self.assertTrue(result["pasa"], result["fallos"])

    def test_unparseable_response_is_formato_invalido(self):
        result = verificar(CHAIN_SCENARIO, "I would call find_customer first.")
        self.assertFalse(result["pasa"])
        self.assertIn("formato_invalido", codes(result))


if __name__ == "__main__":
    unittest.main()
