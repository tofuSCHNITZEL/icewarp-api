"""Context manager usage example for icewarp_api.

Shows the recommended pattern: `with IceWarpAPI(...) as api:` logs in on
enter and always logs out on exit (even if an exception is raised).

Usage:
    python examples/context_manager_usage.py https://mail.example.com:32001/icewarpapi admin@example.com
"""

from __future__ import annotations

import argparse
import getpass

from icewarp_api import IceWarpAPI, IceWarpError


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("base_url")
    parser.add_argument("email")
    parser.add_argument("--insecure", action="store_true")
    args = parser.parse_args()

    password = getpass.getpass("Password: ")

    try:
        with IceWarpAPI(args.base_url, args.email, password, verify_ssl=not args.insecure) as api:
            info = api.iw.sessions.get_session_info()
            print("Session info:", info)

            server_props = api.iw.server.get_server_properties()
            print("Server properties:", server_props)

            license_info = api.iw.license.get_license_info()
            print("License info:", license_info)
        # `api.logout()` has already been called here, even though we never called it explicitly.
    except IceWarpError as exc:
        print(f"IceWarp API error: {exc}")


if __name__ == "__main__":
    main()
