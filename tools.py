"""Pool of enterprise tools available to benchmark scenarios.

Each tool has a schema: parameter names with types, and the fields it
returns. "side_effect" marks whether the tool mutates state or reaches
the outside world (transfer, notify, ...) versus a pure read/lookup
(find_customer, get_balance, ...). The verifier uses this to decide
whether an EXTRA call in a model's plan is a benign read or a real,
unrequested side effect. Scenarios expose a subset of this pool.
"""

TOOLS = {
    "find_customer": {
        "description": "Look up a customer by full name.",
        "params": {"name": "string"},
        "returns": {"id": "string"},
        "side_effect": False,
    },
    "get_account": {
        "description": "Get the account linked to a customer.",
        "params": {"customer_id": "string"},
        "returns": {"account_id": "string", "status": "string"},
        "side_effect": False,
    },
    "get_balance": {
        "description": "Get the current balance of an account.",
        "params": {"account_id": "string"},
        "returns": {"balance": "number"},
        "side_effect": False,
    },
    "transfer": {
        "description": "Transfer money between two accounts.",
        "params": {"source": "string", "destination": "string", "amount": "number"},
        "returns": {"transaction_id": "string"},
        "side_effect": True,
    },
    "open_ticket": {
        "description": "Open a support ticket for a customer. Severity is one of: low, medium, high.",
        "params": {"customer_id": "string", "severity": "string", "description": "string"},
        "returns": {"ticket_id": "string"},
        "side_effect": True,
    },
    "update_address": {
        "description": "Update the address stored under a record id.",
        "params": {"id": "string", "street": "string", "city": "string", "zip": "string"},
        "returns": {"updated": "boolean"},
        "side_effect": True,
    },
    "notify": {
        "description": "Send a notification message to a customer.",
        "params": {"customer_id": "string", "message": "string"},
        "returns": {"sent": "boolean"},
        "side_effect": True,
    },
    "find_equipment": {
        "description": "Find the equipment installed at a location.",
        "params": {"location": "string"},
        "returns": {"equipment_id": "string"},
        "side_effect": False,
    },
    "schedule_maintenance": {
        "description": "Schedule maintenance for a piece of equipment on a date (YYYY-MM-DD).",
        "params": {"equipment_id": "string", "date": "string"},
        "returns": {"maintenance_id": "string"},
        "side_effect": True,
    },
    "get_invoice": {
        "description": "Get the latest invoice for a customer.",
        "params": {"customer_id": "string"},
        "returns": {"invoice_id": "string", "amount": "number", "due_date": "string"},
        "side_effect": False,
    },
}

# Tools whose extra, unrequested invocation is a real side effect (fatal
# when it appears beyond the ground truth). Read-only tools are safe extras.
SIDE_EFFECT_TOOLS = {name for name, spec in TOOLS.items() if spec["side_effect"]}


def tool_schema(name):
    """Return the schema dict for a tool name (KeyError if unknown)."""
    return TOOLS[name]
