"""List all accounts across every domain on an IceWarp server.

The IceWarp Maintenance API lists accounts per-domain (`GetAccountsInfoList`
requires a `domainstr`) - there is no single "all accounts on the server"
endpoint. `IceWarpAPI.get_all_accounts()` is a built-in, curated helper that
handles this for you: it lists all domains, then lists (and paginates
through) the accounts in each one, returning a flat list.

Usage:
    python examples/list_all_accounts.py https://mail.example.com:32001/icewarpapi admin@example.com
"""

from __future__ import annotations

import argparse
import getpass

from icewarp_api import IceWarpAPI, IceWarpError


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("base_url", help="e.g. https://mail.example.com:32001/icewarpapi")
    parser.add_argument("email", help="Admin account email/username")
    parser.add_argument("--domain", help="Only list accounts in this domain, instead of every domain")
    parser.add_argument("--insecure", action="store_true", help="Disable TLS certificate verification")
    args = parser.parse_args()

    password = getpass.getpass("Password: ")

    with IceWarpAPI(args.base_url, args.email, password, verify_ssl=not args.insecure) as api:
        try:
            accounts = api.get_all_accounts(domain=args.domain)
        except IceWarpError as exc:
            print(f"IceWarp API error: {exc}")
            return

        print(f"Found {len(accounts)} account(s):\n")
        for account in accounts:
            email = account.get("email", account)
            print(f"  - {email} (domain: {account.get('domain')})")


if __name__ == "__main__":
    main()
