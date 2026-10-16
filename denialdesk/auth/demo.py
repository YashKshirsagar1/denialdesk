"""Demo-only accounts for synthetic data. Used by the seed script and the dev login helper.

Never reuse this password anywhere real. The /auth/demo-accounts endpoint that exposes it
is disabled whenever dev_mode is off.
"""
from denialdesk.auth.models import Role

DEMO_PASSWORD = "DenialDesk-Demo1"

# (email, full name, role, belongs to the demo clinic)
DEMO_USERS = [
    ("admin@lakesidefp.com", "Dr. Maria Santos", Role.clinic_admin, True),
    ("staff@lakesidefp.com", "Jordan Lee", Role.clinic_staff, True),
    ("ops@denialdesk.com", "Alex Rivera", Role.ops_admin, False),
    ("reviewer@denialdesk.com", "Sam Patel", Role.reviewer, False),
]
