"""Generate a signed dev JWT for testing with curl or browser devtools.

Usage:
    python scripts/generate_dev_token.py --role ops_admin
    python scripts/generate_dev_token.py --role clinic_admin --tenant-id 1 --email alice@clinic.com
"""
import argparse
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from denialdesk.auth.jwt import create_dev_token
from denialdesk.auth.models import Role


def main():
    parser = argparse.ArgumentParser(description="Generate a DenialDesk dev JWT")
    parser.add_argument("--role", default="ops_admin", choices=[r.value for r in Role])
    parser.add_argument("--tenant-id", type=int, default=None)
    parser.add_argument("--email", default="dev@denialdesk.local")
    parser.add_argument("--user-id", default="dev-user")
    args = parser.parse_args()

    token = create_dev_token(
        user_id=args.user_id,
        email=args.email,
        tenant_id=args.tenant_id,
        role=Role(args.role),
    )
    print(token)


if __name__ == "__main__":
    main()
