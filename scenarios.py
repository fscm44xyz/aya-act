"""Hand-written benchmark scenarios.

Scenario format
---------------
{
  "id":      unique string,
  "type":    "one_shot" | "data_chain" | "rejection" | "conditional",
  "tools":   list of tool names from tools.TOOLS exposed to the model,
  "request": natural-language user request (English for the core set),
  "expected": ground truth, whose shape depends on "type":

    one_shot / data_chain: list of calls
        [{"tool": name, "args": {param: value, ...}}, ...]
      Arg values may be:
        - a literal ("ACC-5", 500)
        - a reference "$N.field" -> field of the result of step N (1-based)
        - a free-text matcher {"contains": [substr, ...]} (case-insensitive)

    rejection: exactly {"error": "no tool available"}

    conditional:
        {"setup":    [calls run unconditionally first],
         "branches": [{"condition": {"field": "$N.field", "op": ">", "value": 1000}
                                    | "else",
                       "calls": [calls]}, ...]}
      References inside branches count setup steps ($1 = first setup call).
      Supported ops: > < >= <= == !=
}
"""

REJECTION_ANSWER = {"error": "no tool available"}

CORE_SCENARIOS = [
    # ------------------------------------------------------------------
    # one_shot: a single call, no dependencies
    # ------------------------------------------------------------------
    {
        "id": "one_shot_01",
        "type": "one_shot",
        "tools": ["open_ticket", "notify"],
        "request": "Open a high severity ticket for customer C-1042: the portal is down.",
        "expected": [
            {"tool": "open_ticket",
             "args": {"customer_id": "C-1042", "severity": "high",
                      "description": {"contains": ["portal", "down"]}}},
        ],
    },
    {
        "id": "one_shot_02",
        "type": "one_shot",
        "tools": ["notify", "open_ticket"],
        "request": "Send a notification to customer C-2001 telling them their order has shipped.",
        "expected": [
            {"tool": "notify",
             "args": {"customer_id": "C-2001",
                      "message": {"contains": ["order", "shipped"]}}},
        ],
    },
    {
        "id": "one_shot_03",
        "type": "one_shot",
        "tools": ["schedule_maintenance", "find_equipment"],
        "request": "Schedule maintenance for equipment EQ-77 on 2026-08-01.",
        "expected": [
            {"tool": "schedule_maintenance",
             "args": {"equipment_id": "EQ-77", "date": "2026-08-01"}},
        ],
    },
    {
        "id": "one_shot_04",
        "type": "one_shot",
        "tools": ["update_address", "notify"],
        "request": "Update the address of record R-15 to 42 Oak Street, Springfield, zip 62704.",
        "expected": [
            {"tool": "update_address",
             "args": {"id": "R-15", "street": "42 Oak Street",
                      "city": "Springfield", "zip": "62704"}},
        ],
    },
    {
        "id": "one_shot_05",
        "type": "one_shot",
        "tools": ["get_balance", "get_account"],
        "request": "What is the balance of account ACC-9?",
        "expected": [
            {"tool": "get_balance", "args": {"account_id": "ACC-9"}},
        ],
    },
    # ------------------------------------------------------------------
    # data_chain: later calls consume results of earlier calls ($N.field)
    # ------------------------------------------------------------------
    {
        "id": "chain_01",
        "type": "data_chain",
        "tools": ["find_customer", "get_account", "get_balance"],
        "request": "What is the current balance of the customer named John Smith?",
        "expected": [
            {"tool": "find_customer", "args": {"name": "John Smith"}},
            {"tool": "get_account", "args": {"customer_id": "$1.id"}},
            {"tool": "get_balance", "args": {"account_id": "$2.account_id"}},
        ],
    },
    {
        "id": "chain_02",
        "type": "data_chain",
        "tools": ["find_customer", "open_ticket"],
        "request": "Open a low severity ticket for Maria Lopez about a billing question.",
        "expected": [
            {"tool": "find_customer", "args": {"name": "Maria Lopez"}},
            {"tool": "open_ticket",
             "args": {"customer_id": "$1.id", "severity": "low",
                      "description": {"contains": ["billing"]}}},
        ],
    },
    {
        "id": "chain_03",
        "type": "data_chain",
        "tools": ["find_customer", "notify", "get_invoice"],
        "request": "Notify Ana Torres that her invoice is ready.",
        "expected": [
            {"tool": "find_customer", "args": {"name": "Ana Torres"}},
            {"tool": "notify",
             "args": {"customer_id": "$1.id",
                      "message": {"contains": ["invoice", "ready"]}}},
        ],
    },
    {
        "id": "chain_04",
        "type": "data_chain",
        "tools": ["find_equipment", "schedule_maintenance"],
        "request": "Schedule maintenance for the equipment at the Dallas warehouse for 2026-09-15.",
        "expected": [
            {"tool": "find_equipment", "args": {"location": "Dallas warehouse"}},
            {"tool": "schedule_maintenance",
             "args": {"equipment_id": "$1.equipment_id", "date": "2026-09-15"}},
        ],
    },
    {
        "id": "chain_05",
        "type": "data_chain",
        "tools": ["find_customer", "get_account", "transfer"],
        "request": "Transfer 250 from account ACC-1 to David Kim's account.",
        "expected": [
            {"tool": "find_customer", "args": {"name": "David Kim"}},
            {"tool": "get_account", "args": {"customer_id": "$1.id"}},
            {"tool": "transfer",
             "args": {"source": "ACC-1", "destination": "$2.account_id",
                      "amount": 250}},
        ],
    },
    # ------------------------------------------------------------------
    # rejection: no available tool can satisfy the request
    # ------------------------------------------------------------------
    {
        "id": "reject_01",
        "type": "rejection",
        "tools": ["find_customer", "notify"],
        "request": "Delete customer John Smith from the database.",
        "expected": REJECTION_ANSWER,
    },
    {
        "id": "reject_02",
        "type": "rejection",
        "tools": ["get_balance", "transfer"],
        "request": "What will the weather be like in Madrid tomorrow?",
        "expected": REJECTION_ANSWER,
    },
    {
        "id": "reject_03",
        "type": "rejection",
        "tools": ["open_ticket", "notify", "find_customer"],
        "request": "Reset the password for the admin user.",
        "expected": REJECTION_ANSWER,
    },
    {
        "id": "reject_04",
        "type": "rejection",
        "tools": ["get_invoice", "notify"],
        "request": "Cancel invoice INV-33 and refund the customer.",
        "expected": REJECTION_ANSWER,
    },
    {
        "id": "reject_05",
        "type": "rejection",
        "tools": ["get_balance", "get_account", "update_address"],
        "request": "Give customer C-9 a 20% discount on their next order.",
        "expected": REJECTION_ANSWER,
    },
    # ------------------------------------------------------------------
    # conditional: the request branches on a fetched value
    # ------------------------------------------------------------------
    {
        "id": "cond_01",
        "type": "conditional",
        "tools": ["get_balance", "transfer", "notify"],
        "request": ("Check the balance of account ACC-5. If it is over 1000, "
                    "transfer 500 from ACC-5 to ACC-8; otherwise notify customer "
                    "C-77 that their funds are insufficient."),
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
    },
    {
        "id": "cond_02",
        "type": "conditional",
        "tools": ["get_account", "notify", "open_ticket"],
        "request": ("Look up the account of customer C-30. If its status is "
                    "'active', send them a renewal reminder; if not, open a "
                    "medium severity ticket about an inactive account."),
        "expected": {
            "setup": [{"tool": "get_account", "args": {"customer_id": "C-30"}}],
            "branches": [
                {"condition": {"field": "$1.status", "op": "==", "value": "active"},
                 "calls": [{"tool": "notify",
                            "args": {"customer_id": "C-30",
                                     "message": {"contains": ["renewal"]}}}]},
                {"condition": "else",
                 "calls": [{"tool": "open_ticket",
                            "args": {"customer_id": "C-30", "severity": "medium",
                                     "description": {"contains": ["inactive"]}}}]},
            ],
        },
    },
    {
        "id": "cond_03",
        "type": "conditional",
        "tools": ["get_invoice", "notify"],
        "request": ("Get the latest invoice for customer C-12. If the amount is "
                    "greater than 500, notify them about the available payment "
                    "plan; otherwise notify them that payment is due."),
        "expected": {
            "setup": [{"tool": "get_invoice", "args": {"customer_id": "C-12"}}],
            "branches": [
                {"condition": {"field": "$1.amount", "op": ">", "value": 500},
                 "calls": [{"tool": "notify",
                            "args": {"customer_id": "C-12",
                                     "message": {"contains": ["payment plan"]}}}]},
                {"condition": "else",
                 "calls": [{"tool": "notify",
                            "args": {"customer_id": "C-12",
                                     "message": {"contains": ["payment", "due"]}}}]},
            ],
        },
    },
    {
        "id": "cond_04",
        "type": "conditional",
        "tools": ["get_balance", "open_ticket", "notify"],
        "request": ("Check the balance of account ACC-77. If it is below 100, "
                    "open a high severity ticket for customer C-77 about a low "
                    "balance; otherwise do nothing."),
        "expected": {
            "setup": [{"tool": "get_balance", "args": {"account_id": "ACC-77"}}],
            "branches": [
                {"condition": {"field": "$1.balance", "op": "<", "value": 100},
                 "calls": [{"tool": "open_ticket",
                            "args": {"customer_id": "C-77", "severity": "high",
                                     "description": {"contains": ["low balance"]}}}]},
                {"condition": "else", "calls": []},
            ],
        },
    },
    {
        "id": "cond_05",
        "type": "conditional",
        "tools": ["find_customer", "get_account", "get_balance", "notify"],
        "request": ("Find the customer named Grace Chen and check her account "
                    "balance. If it is at least 5000, notify her that she is "
                    "eligible for the premium plan; otherwise notify her about "
                    "the standard plan."),
        "expected": {
            "setup": [
                {"tool": "find_customer", "args": {"name": "Grace Chen"}},
                {"tool": "get_account", "args": {"customer_id": "$1.id"}},
                {"tool": "get_balance", "args": {"account_id": "$2.account_id"}},
            ],
            "branches": [
                {"condition": {"field": "$3.balance", "op": ">=", "value": 5000},
                 "calls": [{"tool": "notify",
                            "args": {"customer_id": "$1.id",
                                     "message": {"contains": ["premium"]}}}]},
                {"condition": "else",
                 "calls": [{"tool": "notify",
                            "args": {"customer_id": "$1.id",
                                     "message": {"contains": ["standard"]}}}]},
            ],
        },
    },
]

# ----------------------------------------------------------------------
# Transfer-validation sets (NOT part of the core benchmark).
# Same scenario format; ids should carry the language suffix (e.g. "_es").
# Fill these with translated variants of core scenarios to measure
# cross-lingual transfer. One Spanish sample is included to show the shape.
# ----------------------------------------------------------------------
VALIDATION_SCENARIOS = {
    "es": [
        {
            "id": "chain_01_es",
            "type": "data_chain",
            "tools": ["find_customer", "get_account", "get_balance"],
            "request": "¿Cuál es el saldo actual del cliente llamado John Smith?",
            "expected": [
                {"tool": "find_customer", "args": {"name": "John Smith"}},
                {"tool": "get_account", "args": {"customer_id": "$1.id"}},
                {"tool": "get_balance", "args": {"account_id": "$2.account_id"}},
            ],
        },
    ],
    "pt": [],
    "hi": [],
}


def get_scenarios(langs=None):
    """Core scenarios, optionally extended with validation languages.

    langs: iterable of language codes from VALIDATION_SCENARIOS, or None
    for the core set only.
    """
    result = list(CORE_SCENARIOS)
    for lang in (langs or []):
        result.extend(VALIDATION_SCENARIOS[lang])
    return result
