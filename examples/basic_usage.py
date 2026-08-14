"""Basic usage example for icewarp_api.

This connects to an IceWarp Maintenance API endpoint, authenticates with a
plain email/password, lists domains and the accounts in the first domain,
then logs out.

Usage:
    python examples/basic_usage.py https://mail.example.com:32001/icewarpapi admin@example.com

You will be prompted for the password. TLS verification is enabled by
default; pass --insecure to disable it (e.g. for self-signed certificates on
a local/test server).
"""

from __future__ import annotations

import argparse
import getpass
import json

from icewarp_api import IceWarpAPI, IceWarpError


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("base_url", help="e.g. https://mail.example.com:32001/icewarpapi")
    parser.add_argument("email", help="Admin account email/username")
    parser.add_argument("--insecure", action="store_true", help="Disable TLS certificate verification")
    args = parser.parse_args()

    password = getpass.getpass("Password: ")

    api = IceWarpAPI(args.base_url, args.email, password, verify_ssl=not args.insecure)

    try:
        api.login()
        print(f"Authenticated. Session id: {api.sid}")

        domains = api.iw.domains.get_domains_info_list()
        items = domains.get("item", []) if isinstance(domains, dict) else []
        if isinstance(items, dict):  # a single domain comes back as a dict, not a list
            items = [items]

        print(f"\nFound {len(items)} domain(s):")
        for domain in items:
            print(f"  - {domain.get('name')} ({domain.get('accountcount', '?')} accounts)")

        if items:
            first_domain = items[0]["name"]
            print(f"\nAccounts in {first_domain}:")
            accounts = api.iw.accounts.get_accounts_info_list(domainstr=first_domain)
            account_items = accounts.get("item", []) if isinstance(accounts, dict) else []
            if isinstance(account_items, dict):
                account_items = [account_items]
            for account in account_items:
                print(f"  - {account.get('email', account)}")
            if not account_items:
                print("  (no accounts, or the account list format differs - raw response:)")
                print(json.dumps(accounts, indent=2))
    except IceWarpError as exc:
        print(f"IceWarp API error: {exc}")
    finally:
        api.logout()
        print("\nLogged out.")


if __name__ == "__main__":
    main()
