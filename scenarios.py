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
    {
        "id": "one_shot_06",
        "type": "one_shot",
        "tools": ["get_invoice", "notify"],
        "request": "Pull up the latest invoice for customer C-500.",
        "expected": [
            {"tool": "get_invoice", "args": {"customer_id": "C-500"}},
        ],
    },
    {
        "id": "one_shot_07",
        "type": "one_shot",
        "tools": ["find_equipment", "schedule_maintenance"],
        "request": "Which equipment is installed at the Denver plant?",
        "expected": [
            {"tool": "find_equipment", "args": {"location": "Denver plant"}},
        ],
    },
    {
        "id": "one_shot_08",
        "type": "one_shot",
        "tools": ["transfer", "get_balance"],
        "request": "Move 1200 from ACC-3 to ACC-4.",
        "expected": [
            {"tool": "transfer",
             "args": {"source": "ACC-3", "destination": "ACC-4", "amount": 1200}},
        ],
    },
    {
        "id": "one_shot_09",
        "type": "one_shot",
        "tools": ["get_account", "get_balance"],
        "request": "Look up the account for customer C-88.",
        "expected": [
            {"tool": "get_account", "args": {"customer_id": "C-88"}},
        ],
    },
    {
        "id": "one_shot_10",
        "type": "one_shot",
        "tools": ["find_customer", "notify"],
        "request": "Find the customer record for Priya Nair.",
        "expected": [
            {"tool": "find_customer", "args": {"name": "Priya Nair"}},
        ],
    },
    {
        "id": "one_shot_11",
        "type": "one_shot",
        "tools": ["open_ticket", "notify"],
        "request": ("Hey, can you file a medium priority ticket for C-321? "
                    "Their dashboard keeps freezing."),
        "expected": [
            {"tool": "open_ticket",
             "args": {"customer_id": "C-321", "severity": "medium",
                      "description": {"contains": ["dashboard", "freez"]}}},
        ],
    },
    {
        "id": "one_shot_12",
        "type": "one_shot",
        "tools": ["update_address"],
        "request": ("For record R-88, set the city to Austin, the zip to 78701, "
                    "and the street to 9 Pine Ave."),
        "expected": [
            {"tool": "update_address",
             "args": {"id": "R-88", "street": "9 Pine Ave", "city": "Austin",
                      "zip": "78701"}},
        ],
    },
    {
        "id": "one_shot_13",
        "type": "one_shot",
        "tools": ["notify", "open_ticket"],
        "request": ("Shoot customer C-9002 a message that their appointment is "
                    "confirmed for Friday."),
        "expected": [
            {"tool": "notify",
             "args": {"customer_id": "C-9002",
                      "message": {"contains": ["appointment", "confirmed"]}}},
        ],
    },
    {
        "id": "one_shot_14",
        "type": "one_shot",
        "tools": ["schedule_maintenance", "find_equipment"],
        "request": "Book maintenance on machine EQ-1200 for 2026-12-03.",
        "expected": [
            {"tool": "schedule_maintenance",
             "args": {"equipment_id": "EQ-1200", "date": "2026-12-03"}},
        ],
    },
    {
        "id": "one_shot_15",
        "type": "one_shot",
        "tools": ["get_balance", "get_invoice"],
        "request": "How much is left in account ACC-450?",
        "expected": [
            {"tool": "get_balance", "args": {"account_id": "ACC-450"}},
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
    {
        "id": "chain_06",
        "type": "data_chain",
        "tools": ["find_customer", "get_invoice"],
        "request": "Pull up the latest invoice for the customer named Robert Lang.",
        "expected": [
            {"tool": "find_customer", "args": {"name": "Robert Lang"}},
            {"tool": "get_invoice", "args": {"customer_id": "$1.id"}},
        ],
    },
    {
        "id": "chain_07",
        "type": "data_chain",
        "tools": ["find_customer", "get_account"],
        "request": "What is the account status of the customer named Lucia Ferrari?",
        "expected": [
            {"tool": "find_customer", "args": {"name": "Lucia Ferrari"}},
            {"tool": "get_account", "args": {"customer_id": "$1.id"}},
        ],
    },
    {
        "id": "chain_08",
        "type": "data_chain",
        "tools": ["find_equipment", "schedule_maintenance"],
        "request": "The elevator at the Miami office is due for servicing on 2026-10-10.",
        "expected": [
            {"tool": "find_equipment", "args": {"location": "Miami office"}},
            {"tool": "schedule_maintenance",
             "args": {"equipment_id": "$1.equipment_id", "date": "2026-10-10"}},
        ],
    },
    {
        "id": "chain_09",
        "type": "data_chain",
        "tools": ["find_customer", "open_ticket"],
        "request": "Open a high severity ticket for Nadia Petrova — her account is locked.",
        "expected": [
            {"tool": "find_customer", "args": {"name": "Nadia Petrova"}},
            {"tool": "open_ticket",
             "args": {"customer_id": "$1.id", "severity": "high",
                      "description": {"contains": ["locked"]}}},
        ],
    },
    {
        "id": "chain_10",
        "type": "data_chain",
        "tools": ["find_customer", "notify"],
        "request": "Let the customer named Sam O'Neil know that his refund has been processed.",
        "expected": [
            {"tool": "find_customer", "args": {"name": "Sam O'Neil"}},
            {"tool": "notify",
             "args": {"customer_id": "$1.id",
                      "message": {"contains": ["refund", "processed"]}}},
        ],
    },
    {
        "id": "chain_11",
        "type": "data_chain",
        "tools": ["find_customer", "get_account", "get_balance"],
        "request": "How much money is in Kenji Tanaka's account right now?",
        "expected": [
            {"tool": "find_customer", "args": {"name": "Kenji Tanaka"}},
            {"tool": "get_account", "args": {"customer_id": "$1.id"}},
            {"tool": "get_balance", "args": {"account_id": "$2.account_id"}},
        ],
    },
    {
        "id": "chain_12",
        "type": "data_chain",
        "tools": ["find_customer", "get_account", "transfer"],
        "request": ("Send 750 from the corporate account ACC-CORP to the account "
                    "belonging to Elena Duarte."),
        "expected": [
            {"tool": "find_customer", "args": {"name": "Elena Duarte"}},
            {"tool": "get_account", "args": {"customer_id": "$1.id"}},
            {"tool": "transfer",
             "args": {"source": "ACC-CORP", "destination": "$2.account_id",
                      "amount": 750}},
        ],
    },
    {
        "id": "chain_13",
        "type": "data_chain",
        "tools": ["find_customer", "get_account", "transfer"],
        "request": "Withdraw 300 from Grace Okoro's account into the petty cash account ACC-PC.",
        "expected": [
            {"tool": "find_customer", "args": {"name": "Grace Okoro"}},
            {"tool": "get_account", "args": {"customer_id": "$1.id"}},
            {"tool": "transfer",
             "args": {"source": "$2.account_id", "destination": "ACC-PC",
                      "amount": 300}},
        ],
    },
    {
        "id": "chain_14",
        "type": "data_chain",
        "tools": ["find_equipment", "schedule_maintenance"],
        "request": "Book servicing for the generator at the Reno data center on 2026-11-22.",
        "expected": [
            {"tool": "find_equipment", "args": {"location": "Reno data center"}},
            {"tool": "schedule_maintenance",
             "args": {"equipment_id": "$1.equipment_id", "date": "2026-11-22"}},
        ],
    },
    {
        "id": "chain_15",
        "type": "data_chain",
        "tools": ["find_customer", "get_account", "get_balance"],
        "request": "I need the current balance for Frank Mueller's account.",
        "expected": [
            {"tool": "find_customer", "args": {"name": "Frank Mueller"}},
            {"tool": "get_account", "args": {"customer_id": "$1.id"}},
            {"tool": "get_balance", "args": {"account_id": "$2.account_id"}},
        ],
    },
    {
        "id": "chain_16",
        "type": "data_chain",
        "tools": ["find_customer", "get_invoice"],
        "request": "Grab the newest invoice for Chloe Dubois, please.",
        "expected": [
            {"tool": "find_customer", "args": {"name": "Chloe Dubois"}},
            {"tool": "get_invoice", "args": {"customer_id": "$1.id"}},
        ],
    },
    {
        "id": "chain_17",
        "type": "data_chain",
        "tools": ["find_customer", "get_account", "transfer"],
        "request": "Transfer 1500 into Ahmed Farouk's account from the payroll account ACC-PAY.",
        "expected": [
            {"tool": "find_customer", "args": {"name": "Ahmed Farouk"}},
            {"tool": "get_account", "args": {"customer_id": "$1.id"}},
            {"tool": "transfer",
             "args": {"source": "ACC-PAY", "destination": "$2.account_id",
                      "amount": 1500}},
        ],
    },
    {
        "id": "chain_18",
        "type": "data_chain",
        "tools": ["find_customer", "notify"],
        "request": "Message the customer named Wei Zhang that his subscription has been renewed.",
        "expected": [
            {"tool": "find_customer", "args": {"name": "Wei Zhang"}},
            {"tool": "notify",
             "args": {"customer_id": "$1.id",
                      "message": {"contains": ["subscription", "renewed"]}}},
        ],
    },
    {
        "id": "chain_19",
        "type": "data_chain",
        "tools": ["find_customer", "get_account", "get_balance"],
        "request": "Check what Olga Ivanova's account balance is.",
        "expected": [
            {"tool": "find_customer", "args": {"name": "Olga Ivanova"}},
            {"tool": "get_account", "args": {"customer_id": "$1.id"}},
            {"tool": "get_balance", "args": {"account_id": "$2.account_id"}},
        ],
    },
    {
        "id": "chain_20",
        "type": "data_chain",
        "tools": ["find_customer", "open_ticket"],
        "request": ("File a low priority ticket for Diego Ramos — he reported a "
                    "typo on his statement."),
        "expected": [
            {"tool": "find_customer", "args": {"name": "Diego Ramos"}},
            {"tool": "open_ticket",
             "args": {"customer_id": "$1.id", "severity": "low",
                      "description": {"contains": ["typo", "statement"]}}},
        ],
    },
    {
        "id": "chain_21",
        "type": "data_chain",
        "tools": ["find_customer", "get_account", "get_balance", "transfer"],
        "request": ("Find customer Omar Haddad and move his entire account balance "
                    "to the holding account ACC-0."),
        "expected": [
            {"tool": "find_customer", "args": {"name": "Omar Haddad"}},
            {"tool": "get_account", "args": {"customer_id": "$1.id"}},
            {"tool": "get_balance", "args": {"account_id": "$2.account_id"}},
            {"tool": "transfer",
             "args": {"source": "$2.account_id", "destination": "ACC-0",
                      "amount": "$3.balance"}},
        ],
    },
    {
        "id": "chain_22",
        "type": "data_chain",
        "tools": ["find_customer", "get_account", "transfer"],
        "request": "Please send 200 from the rewards pool ACC-RWD to Sara Kim's account.",
        "expected": [
            {"tool": "find_customer", "args": {"name": "Sara Kim"}},
            {"tool": "get_account", "args": {"customer_id": "$1.id"}},
            {"tool": "transfer",
             "args": {"source": "ACC-RWD", "destination": "$2.account_id",
                      "amount": 200}},
        ],
    },
    {
        "id": "chain_23",
        "type": "data_chain",
        "tools": ["find_customer", "get_account", "transfer"],
        "request": ("Pull 900 out of Tomás Herrera's account and send it to the "
                    "escrow account ACC-ESC."),
        "expected": [
            {"tool": "find_customer", "args": {"name": "Tomás Herrera"}},
            {"tool": "get_account", "args": {"customer_id": "$1.id"}},
            {"tool": "transfer",
             "args": {"source": "$2.account_id", "destination": "ACC-ESC",
                      "amount": 900}},
        ],
    },
    {
        "id": "chain_24",
        "type": "data_chain",
        "tools": ["find_customer", "get_account"],
        "request": "Is the account of the customer named Fatima Ali active? Look it up.",
        "expected": [
            {"tool": "find_customer", "args": {"name": "Fatima Ali"}},
            {"tool": "get_account", "args": {"customer_id": "$1.id"}},
        ],
    },
    {
        "id": "chain_25",
        "type": "data_chain",
        "tools": ["find_customer", "get_account", "get_balance", "transfer"],
        "request": ("Find Lars Andersen, and sweep his whole balance into the "
                    "consolidation account ACC-CON."),
        "expected": [
            {"tool": "find_customer", "args": {"name": "Lars Andersen"}},
            {"tool": "get_account", "args": {"customer_id": "$1.id"}},
            {"tool": "get_balance", "args": {"account_id": "$2.account_id"}},
            {"tool": "transfer",
             "args": {"source": "$2.account_id", "destination": "ACC-CON",
                      "amount": "$3.balance"}},
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
    {
        "id": "reject_06",
        "type": "rejection",
        "tools": ["get_balance", "get_account", "transfer"],
        "request": "Convert 500 US dollars to euros and tell me the exchange rate.",
        "expected": REJECTION_ANSWER,
    },
    {
        "id": "reject_07",
        "type": "rejection",
        "tools": ["find_customer", "open_ticket"],
        "request": "Schedule a callback from a human support agent for tomorrow at 3pm.",
        "expected": REJECTION_ANSWER,
    },
    {
        "id": "reject_08",
        "type": "rejection",
        "tools": ["get_invoice", "notify", "find_customer"],
        "request": "Print and mail a physical copy of invoice INV-90 to the customer.",
        "expected": REJECTION_ANSWER,
    },
    {
        "id": "reject_09",
        "type": "rejection",
        "tools": ["find_equipment", "schedule_maintenance"],
        "request": "Order a replacement part for equipment EQ-5 from the supplier.",
        "expected": REJECTION_ANSWER,
    },
    {
        "id": "reject_10",
        "type": "rejection",
        "tools": ["get_account", "get_balance", "update_address"],
        "request": "Close customer C-14's account permanently.",
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
    {
        "id": "cond_06",
        "type": "conditional",
        "tools": ["get_balance", "open_ticket", "notify"],
        "request": ("Check the balance of account ACC-200. If it is 10000 or more, "
                    "open a low severity ticket for customer C-200 to review a tier "
                    "upgrade; otherwise notify them that they haven't qualified yet."),
        "expected": {
            "setup": [{"tool": "get_balance", "args": {"account_id": "ACC-200"}}],
            "branches": [
                {"condition": {"field": "$1.balance", "op": ">=", "value": 10000},
                 "calls": [{"tool": "open_ticket",
                            "args": {"customer_id": "C-200", "severity": "low",
                                     "description": {"contains": ["tier upgrade"]}}}]},
                {"condition": "else",
                 "calls": [{"tool": "notify",
                            "args": {"customer_id": "C-200",
                                     "message": {"contains": ["qualif"]}}}]},
            ],
        },
    },
    {
        "id": "cond_07",
        "type": "conditional",
        "tools": ["get_account", "open_ticket", "notify"],
        "request": ("Look up customer C-40's account. If the status is 'suspended', "
                    "open a high severity ticket about the suspension; otherwise "
                    "notify them that their account is in good standing."),
        "expected": {
            "setup": [{"tool": "get_account", "args": {"customer_id": "C-40"}}],
            "branches": [
                {"condition": {"field": "$1.status", "op": "==", "value": "suspended"},
                 "calls": [{"tool": "open_ticket",
                            "args": {"customer_id": "C-40", "severity": "high",
                                     "description": {"contains": ["suspend"]}}}]},
                {"condition": "else",
                 "calls": [{"tool": "notify",
                            "args": {"customer_id": "C-40",
                                     "message": {"contains": ["good standing"]}}}]},
            ],
        },
    },
    {
        "id": "cond_08",
        "type": "conditional",
        "tools": ["get_account", "notify"],
        "request": ("Pull the account for customer C-51. If its status is anything "
                    "other than 'active', send them a reactivation notice; if it is "
                    "active, take no action."),
        "expected": {
            "setup": [{"tool": "get_account", "args": {"customer_id": "C-51"}}],
            "branches": [
                {"condition": {"field": "$1.status", "op": "!=", "value": "active"},
                 "calls": [{"tool": "notify",
                            "args": {"customer_id": "C-51",
                                     "message": {"contains": ["reactivat"]}}}]},
                {"condition": "else", "calls": []},
            ],
        },
    },
    {
        "id": "cond_09",
        "type": "conditional",
        "tools": ["get_invoice", "notify"],
        "request": ("Get the latest invoice for customer C-60. If the amount is "
                    "under 50, notify them that we'll waive it this month; otherwise "
                    "notify them that the payment is due."),
        "expected": {
            "setup": [{"tool": "get_invoice", "args": {"customer_id": "C-60"}}],
            "branches": [
                {"condition": {"field": "$1.amount", "op": "<", "value": 50},
                 "calls": [{"tool": "notify",
                            "args": {"customer_id": "C-60",
                                     "message": {"contains": ["waive"]}}}]},
                {"condition": "else",
                 "calls": [{"tool": "notify",
                            "args": {"customer_id": "C-60",
                                     "message": {"contains": ["payment", "due"]}}}]},
            ],
        },
    },
    {
        "id": "cond_10",
        "type": "conditional",
        "tools": ["get_balance", "open_ticket"],
        "request": ("Check account ACC-300. If the balance is zero or negative, open "
                    "a high severity ticket for customer C-300 flagging an overdrawn "
                    "account; otherwise do nothing."),
        "expected": {
            "setup": [{"tool": "get_balance", "args": {"account_id": "ACC-300"}}],
            "branches": [
                {"condition": {"field": "$1.balance", "op": "<=", "value": 0},
                 "calls": [{"tool": "open_ticket",
                            "args": {"customer_id": "C-300", "severity": "high",
                                     "description": {"contains": ["overdrawn"]}}}]},
                {"condition": "else", "calls": []},
            ],
        },
    },
    {
        "id": "cond_11",
        "type": "conditional",
        "tools": ["find_customer", "get_account", "get_balance", "transfer", "notify"],
        "request": ("Find the customer Harold Voss, look up his account and its "
                    "balance. If the balance is greater than 2500, transfer 2500 "
                    "from his account to the savings account ACC-SAV; otherwise "
                    "notify him that his balance is too low to transfer."),
        "expected": {
            "setup": [
                {"tool": "find_customer", "args": {"name": "Harold Voss"}},
                {"tool": "get_account", "args": {"customer_id": "$1.id"}},
                {"tool": "get_balance", "args": {"account_id": "$2.account_id"}},
            ],
            "branches": [
                {"condition": {"field": "$3.balance", "op": ">", "value": 2500},
                 "calls": [{"tool": "transfer",
                            "args": {"source": "$2.account_id",
                                     "destination": "ACC-SAV", "amount": 2500}}]},
                {"condition": "else",
                 "calls": [{"tool": "notify",
                            "args": {"customer_id": "$1.id",
                                     "message": {"contains": ["too low"]}}}]},
            ],
        },
    },
    {
        "id": "cond_12",
        "type": "conditional",
        "tools": ["find_customer", "get_account", "open_ticket", "notify"],
        "request": ("Find the customer named Bianca Rossi and check her account. If "
                    "the status equals 'pending', open a medium ticket to expedite "
                    "activation; otherwise send her a welcome notification."),
        "expected": {
            "setup": [
                {"tool": "find_customer", "args": {"name": "Bianca Rossi"}},
                {"tool": "get_account", "args": {"customer_id": "$1.id"}},
            ],
            "branches": [
                {"condition": {"field": "$2.status", "op": "==", "value": "pending"},
                 "calls": [{"tool": "open_ticket",
                            "args": {"customer_id": "$1.id", "severity": "medium",
                                     "description": {"contains": ["expedite", "activation"]}}}]},
                {"condition": "else",
                 "calls": [{"tool": "notify",
                            "args": {"customer_id": "$1.id",
                                     "message": {"contains": ["welcome"]}}}]},
            ],
        },
    },
    {
        "id": "cond_13",
        "type": "conditional",
        "tools": ["get_invoice", "open_ticket", "notify"],
        "request": ("Get customer C-70's latest invoice. If the amount is greater "
                    "than 1000, open a high severity ticket to arrange a payment "
                    "plan; otherwise just notify them the invoice is ready."),
        "expected": {
            "setup": [{"tool": "get_invoice", "args": {"customer_id": "C-70"}}],
            "branches": [
                {"condition": {"field": "$1.amount", "op": ">", "value": 1000},
                 "calls": [{"tool": "open_ticket",
                            "args": {"customer_id": "C-70", "severity": "high",
                                     "description": {"contains": ["payment plan"]}}}]},
                {"condition": "else",
                 "calls": [{"tool": "notify",
                            "args": {"customer_id": "C-70",
                                     "message": {"contains": ["invoice", "ready"]}}}]},
            ],
        },
    },
    {
        "id": "cond_14",
        "type": "conditional",
        "tools": ["get_balance", "notify", "open_ticket"],
        "request": ("Check ACC-410's balance. If it is at least 500, notify customer "
                    "C-410 that they can proceed with checkout; otherwise open a low "
                    "ticket about insufficient funds."),
        "expected": {
            "setup": [{"tool": "get_balance", "args": {"account_id": "ACC-410"}}],
            "branches": [
                {"condition": {"field": "$1.balance", "op": ">=", "value": 500},
                 "calls": [{"tool": "notify",
                            "args": {"customer_id": "C-410",
                                     "message": {"contains": ["proceed", "checkout"]}}}]},
                {"condition": "else",
                 "calls": [{"tool": "open_ticket",
                            "args": {"customer_id": "C-410", "severity": "low",
                                     "description": {"contains": ["insufficient"]}}}]},
            ],
        },
    },
    {
        "id": "cond_15",
        "type": "conditional",
        "tools": ["get_balance", "transfer"],
        "request": ("Look at the balance of ACC-420. If it drops below 200, transfer "
                    "300 from the reserve account ACC-RES into ACC-420; otherwise do "
                    "nothing."),
        "expected": {
            "setup": [{"tool": "get_balance", "args": {"account_id": "ACC-420"}}],
            "branches": [
                {"condition": {"field": "$1.balance", "op": "<", "value": 200},
                 "calls": [{"tool": "transfer",
                            "args": {"source": "ACC-RES", "destination": "ACC-420",
                                     "amount": 300}}]},
                {"condition": "else", "calls": []},
            ],
        },
    },
    {
        "id": "cond_16",
        "type": "conditional",
        "tools": ["get_account", "notify"],
        "request": ("Check customer C-80's account. If the status is not 'verified', "
                    "send them a notification to complete verification; otherwise do "
                    "nothing."),
        "expected": {
            "setup": [{"tool": "get_account", "args": {"customer_id": "C-80"}}],
            "branches": [
                {"condition": {"field": "$1.status", "op": "!=", "value": "verified"},
                 "calls": [{"tool": "notify",
                            "args": {"customer_id": "C-80",
                                     "message": {"contains": ["verif"]}}}]},
                {"condition": "else", "calls": []},
            ],
        },
    },
    {
        "id": "cond_17",
        "type": "conditional",
        "tools": ["find_customer", "get_account", "get_balance", "open_ticket", "notify"],
        "request": ("Find Yuki Sato, get her account and balance. If the balance is "
                    "100 or less, open a high severity ticket for a low-balance "
                    "alert; otherwise notify her that everything looks good."),
        "expected": {
            "setup": [
                {"tool": "find_customer", "args": {"name": "Yuki Sato"}},
                {"tool": "get_account", "args": {"customer_id": "$1.id"}},
                {"tool": "get_balance", "args": {"account_id": "$2.account_id"}},
            ],
            "branches": [
                {"condition": {"field": "$3.balance", "op": "<=", "value": 100},
                 "calls": [{"tool": "open_ticket",
                            "args": {"customer_id": "$1.id", "severity": "high",
                                     "description": {"contains": ["low balance"]}}}]},
                {"condition": "else",
                 "calls": [{"tool": "notify",
                            "args": {"customer_id": "$1.id",
                                     "message": {"contains": ["looks good"]}}}]},
            ],
        },
    },
    {
        "id": "cond_18",
        "type": "conditional",
        "tools": ["find_customer", "get_invoice", "notify"],
        "request": ("Find the customer Malik Johnson and pull his latest invoice. If "
                    "the amount exceeds 750, notify him about the installment option; "
                    "otherwise notify him the invoice is due."),
        "expected": {
            "setup": [
                {"tool": "find_customer", "args": {"name": "Malik Johnson"}},
                {"tool": "get_invoice", "args": {"customer_id": "$1.id"}},
            ],
            "branches": [
                {"condition": {"field": "$2.amount", "op": ">", "value": 750},
                 "calls": [{"tool": "notify",
                            "args": {"customer_id": "$1.id",
                                     "message": {"contains": ["installment"]}}}]},
                {"condition": "else",
                 "calls": [{"tool": "notify",
                            "args": {"customer_id": "$1.id",
                                     "message": {"contains": ["due"]}}}]},
            ],
        },
    },
    {
        "id": "cond_19",
        "type": "conditional",
        "tools": ["get_account", "notify", "open_ticket"],
        "request": ("Check customer C-90's account. If the status is 'active', notify "
                    "them of a loyalty reward; otherwise open a low severity ticket "
                    "to reactivate the account."),
        "expected": {
            "setup": [{"tool": "get_account", "args": {"customer_id": "C-90"}}],
            "branches": [
                {"condition": {"field": "$1.status", "op": "==", "value": "active"},
                 "calls": [{"tool": "notify",
                            "args": {"customer_id": "C-90",
                                     "message": {"contains": ["loyalty", "reward"]}}}]},
                {"condition": "else",
                 "calls": [{"tool": "open_ticket",
                            "args": {"customer_id": "C-90", "severity": "low",
                                     "description": {"contains": ["reactivate"]}}}]},
            ],
        },
    },
    {
        "id": "cond_20",
        "type": "conditional",
        "tools": ["get_balance", "transfer", "notify"],
        "request": ("Review ACC-500's balance. If it's over 25000, transfer 5000 to "
                    "the investment account ACC-INV; otherwise notify customer C-500 "
                    "that they don't meet the threshold."),
        "expected": {
            "setup": [{"tool": "get_balance", "args": {"account_id": "ACC-500"}}],
            "branches": [
                {"condition": {"field": "$1.balance", "op": ">", "value": 25000},
                 "calls": [{"tool": "transfer",
                            "args": {"source": "ACC-500", "destination": "ACC-INV",
                                     "amount": 5000}}]},
                {"condition": "else",
                 "calls": [{"tool": "notify",
                            "args": {"customer_id": "C-500",
                                     "message": {"contains": ["threshold"]}}}]},
            ],
        },
    },
    {
        "id": "cond_21",
        "type": "conditional",
        "tools": ["get_invoice", "notify", "open_ticket"],
        "request": ("Get the invoice for C-101. If the amount is less than 100, notify "
                    "them it will be auto-charged; otherwise open a medium ticket to "
                    "arrange manual payment."),
        "expected": {
            "setup": [{"tool": "get_invoice", "args": {"customer_id": "C-101"}}],
            "branches": [
                {"condition": {"field": "$1.amount", "op": "<", "value": 100},
                 "calls": [{"tool": "notify",
                            "args": {"customer_id": "C-101",
                                     "message": {"contains": ["auto-charge"]}}}]},
                {"condition": "else",
                 "calls": [{"tool": "open_ticket",
                            "args": {"customer_id": "C-101", "severity": "medium",
                                     "description": {"contains": ["manual payment"]}}}]},
            ],
        },
    },
    {
        "id": "cond_22",
        "type": "conditional",
        "tools": ["get_invoice", "open_ticket", "notify"],
        "request": ("Pull the latest invoice for customer C-110. If the amount is 2000 "
                    "or more, open a high severity ticket for account review; "
                    "otherwise notify the customer with a payment reminder."),
        "expected": {
            "setup": [{"tool": "get_invoice", "args": {"customer_id": "C-110"}}],
            "branches": [
                {"condition": {"field": "$1.amount", "op": ">=", "value": 2000},
                 "calls": [{"tool": "open_ticket",
                            "args": {"customer_id": "C-110", "severity": "high",
                                     "description": {"contains": ["review"]}}}]},
                {"condition": "else",
                 "calls": [{"tool": "notify",
                            "args": {"customer_id": "C-110",
                                     "message": {"contains": ["reminder"]}}}]},
            ],
        },
    },
    {
        "id": "cond_23",
        "type": "conditional",
        "tools": ["find_customer", "get_account", "transfer", "notify"],
        "request": ("Find customer Ingrid Larsen, look up her account. If the status "
                    "is 'active', transfer a 100 credit from the promo account "
                    "ACC-PROMO to her account; otherwise notify her the promo "
                    "requires an active account."),
        "expected": {
            "setup": [
                {"tool": "find_customer", "args": {"name": "Ingrid Larsen"}},
                {"tool": "get_account", "args": {"customer_id": "$1.id"}},
            ],
            "branches": [
                {"condition": {"field": "$2.status", "op": "==", "value": "active"},
                 "calls": [{"tool": "transfer",
                            "args": {"source": "ACC-PROMO",
                                     "destination": "$2.account_id", "amount": 100}}]},
                {"condition": "else",
                 "calls": [{"tool": "notify",
                            "args": {"customer_id": "$1.id",
                                     "message": {"contains": ["active"]}}}]},
            ],
        },
    },
    {
        "id": "cond_24",
        "type": "conditional",
        "tools": ["get_balance", "open_ticket", "notify"],
        "request": ("Check ACC-600's balance. If it is at most 50, open a high ticket "
                    "for customer C-600 about critically low funds; otherwise send a "
                    "routine balance summary notification."),
        "expected": {
            "setup": [{"tool": "get_balance", "args": {"account_id": "ACC-600"}}],
            "branches": [
                {"condition": {"field": "$1.balance", "op": "<=", "value": 50},
                 "calls": [{"tool": "open_ticket",
                            "args": {"customer_id": "C-600", "severity": "high",
                                     "description": {"contains": ["low funds"]}}}]},
                {"condition": "else",
                 "calls": [{"tool": "notify",
                            "args": {"customer_id": "C-600",
                                     "message": {"contains": ["balance", "summary"]}}}]},
            ],
        },
    },
    {
        "id": "cond_25",
        "type": "conditional",
        "tools": ["find_customer", "get_account", "get_balance", "transfer", "notify"],
        "request": ("Find Dominic Bruno, get his account and balance. If he has at "
                    "least 3000, transfer 1000 to the joint account ACC-JT; otherwise "
                    "notify him he needs a higher balance."),
        "expected": {
            "setup": [
                {"tool": "find_customer", "args": {"name": "Dominic Bruno"}},
                {"tool": "get_account", "args": {"customer_id": "$1.id"}},
                {"tool": "get_balance", "args": {"account_id": "$2.account_id"}},
            ],
            "branches": [
                {"condition": {"field": "$3.balance", "op": ">=", "value": 3000},
                 "calls": [{"tool": "transfer",
                            "args": {"source": "$2.account_id",
                                     "destination": "ACC-JT", "amount": 1000}}]},
                {"condition": "else",
                 "calls": [{"tool": "notify",
                            "args": {"customer_id": "$1.id",
                                     "message": {"contains": ["higher balance"]}}}]},
            ],
        },
    },
    {
        "id": "cond_26",
        "type": "conditional",
        "tools": ["get_account", "open_ticket", "notify"],
        "request": ("Look up customer C-120's account. If the status isn't 'active', "
                    "open a medium ticket to review it; otherwise notify them their "
                    "account is active and healthy."),
        "expected": {
            "setup": [{"tool": "get_account", "args": {"customer_id": "C-120"}}],
            "branches": [
                {"condition": {"field": "$1.status", "op": "!=", "value": "active"},
                 "calls": [{"tool": "open_ticket",
                            "args": {"customer_id": "C-120", "severity": "medium",
                                     "description": {"contains": ["review"]}}}]},
                {"condition": "else",
                 "calls": [{"tool": "notify",
                            "args": {"customer_id": "C-120",
                                     "message": {"contains": ["active", "healthy"]}}}]},
            ],
        },
    },
    {
        "id": "cond_27",
        "type": "conditional",
        "tools": ["get_balance", "transfer", "notify"],
        "request": ("Quick one — peek at ACC-700's balance. Over 800? Move 800 into "
                    "ACC-701. If not, ping customer C-700 that we couldn't do the "
                    "transfer."),
        "expected": {
            "setup": [{"tool": "get_balance", "args": {"account_id": "ACC-700"}}],
            "branches": [
                {"condition": {"field": "$1.balance", "op": ">", "value": 800},
                 "calls": [{"tool": "transfer",
                            "args": {"source": "ACC-700", "destination": "ACC-701",
                                     "amount": 800}}]},
                {"condition": "else",
                 "calls": [{"tool": "notify",
                            "args": {"customer_id": "C-700",
                                     "message": {"contains": ["transfer"]}}}]},
            ],
        },
    },
    {
        "id": "cond_28",
        "type": "conditional",
        "tools": ["find_customer", "get_invoice", "notify", "open_ticket"],
        "request": ("Find the customer named Rosa Mendez and get her invoice. If the "
                    "amount is below 25, notify her we'll write it off; otherwise open "
                    "a low ticket to follow up on payment."),
        "expected": {
            "setup": [
                {"tool": "find_customer", "args": {"name": "Rosa Mendez"}},
                {"tool": "get_invoice", "args": {"customer_id": "$1.id"}},
            ],
            "branches": [
                {"condition": {"field": "$2.amount", "op": "<", "value": 25},
                 "calls": [{"tool": "notify",
                            "args": {"customer_id": "$1.id",
                                     "message": {"contains": ["write it off"]}}}]},
                {"condition": "else",
                 "calls": [{"tool": "open_ticket",
                            "args": {"customer_id": "$1.id", "severity": "low",
                                     "description": {"contains": ["follow up", "payment"]}}}]},
            ],
        },
    },
    {
        "id": "cond_29",
        "type": "conditional",
        "tools": ["get_account", "open_ticket", "notify"],
        "request": ("Check the account for customer C-130. If the status equals "
                    "'frozen', open a high severity ticket to unfreeze it; otherwise "
                    "notify the customer no action is needed."),
        "expected": {
            "setup": [{"tool": "get_account", "args": {"customer_id": "C-130"}}],
            "branches": [
                {"condition": {"field": "$1.status", "op": "==", "value": "frozen"},
                 "calls": [{"tool": "open_ticket",
                            "args": {"customer_id": "C-130", "severity": "high",
                                     "description": {"contains": ["unfreeze"]}}}]},
                {"condition": "else",
                 "calls": [{"tool": "notify",
                            "args": {"customer_id": "C-130",
                                     "message": {"contains": ["no action"]}}}]},
            ],
        },
    },
    {
        "id": "cond_30",
        "type": "conditional",
        "tools": ["find_customer", "get_account", "get_balance", "notify"],
        "request": ("Find Aisha Bello, retrieve her account and current balance. If "
                    "the balance is greater than 15000, notify her she qualifies for "
                    "the private banking tier; otherwise notify her about the "
                    "standard savings options."),
        "expected": {
            "setup": [
                {"tool": "find_customer", "args": {"name": "Aisha Bello"}},
                {"tool": "get_account", "args": {"customer_id": "$1.id"}},
                {"tool": "get_balance", "args": {"account_id": "$2.account_id"}},
            ],
            "branches": [
                {"condition": {"field": "$3.balance", "op": ">", "value": 15000},
                 "calls": [{"tool": "notify",
                            "args": {"customer_id": "$1.id",
                                     "message": {"contains": ["private banking"]}}}]},
                {"condition": "else",
                 "calls": [{"tool": "notify",
                            "args": {"customer_id": "$1.id",
                                     "message": {"contains": ["standard", "savings"]}}}]},
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
