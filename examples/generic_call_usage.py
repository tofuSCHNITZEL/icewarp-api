"""Generic call() / escape-hatch usage example for icewarp_api.

Every one of the 174 documented endpoints has a typed wrapper method under
`api.iw` (see `api.iw.domains.get_domains_info_list(...)`, etc.), but you can
always call any endpoint directly by its command name with `api.iw.call(...)`
- useful for endpoints added after this library was last regenerated, or when
you simply prefer working with plain dicts. Both `api.iw.<category>.<method>`
and `api.iw.call(...)` are raw/generated - hand-written, higher-level helpers
(if any) live directly on `IceWarpAPI`, outside of `.iw`.

This example also shows `icewarp_api.helpers.string_list()`, used to build
the "TPropertyStringList" shaped parameter several endpoints expect for
lists of strings (e.g. deleting several accounts at once).

Usage:
    python examples/generic_call_usage.py https://mail.example.com:32001/icewarpapi admin@example.com
"""

from __future__ import annotations

import argparse
import getpass
import json

from icewarp_api import IceWarpAPI, IceWarpError
from icewarp_api.helpers import string_list


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("base_url")
    parser.add_argument("email")
    parser.add_argument("--insecure", action="store_true")
    args = parser.parse_args()

    password = getpass.getpass("Password: ")

    with IceWarpAPI(args.base_url, args.email, password, verify_ssl=not args.insecure) as api:
        try:
            # Equivalent to api.iw.domains.get_domains_info_list(filter={"namemask": "*"}, count=10)
            result = api.iw.call("GetDomainsInfoList", filter={"namemask": "*"}, count=10)
            print("GetDomainsInfoList via call():")
            print(json.dumps(result, indent=2))

            # Building a TPropertyStringList parameter for a bulk operation, e.g.:
            #   api.iw.accounts.delete_accounts(
            #       domainstr="example.com",
            #       accountlist=string_list(["user1@example.com", "user2@example.com"]),
            #   )
            accountlist_param = string_list(["user1@example.com", "user2@example.com"])
            print("\nExample accountlist parameter shape (not sent - dry run):")
            print(json.dumps(accountlist_param, indent=2))
        except IceWarpError as exc:
            print(f"IceWarp API error: {exc}")


if __name__ == "__main__":
    main()
