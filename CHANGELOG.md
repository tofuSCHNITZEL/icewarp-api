# Changelog

All notable changes to this project are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.1.0]

### Added

- Initial release.
- `IceWarpClient`: low level session/authentication handling and a generic
  `call()` method for any of the 174 documented IceWarp Maintenance API
  endpoints.
- `IceWarpAPI`: high level facade. `api.iw` (`IceWarpRawAPI`) exposes a
  typed, documented method for every one of the 174 endpoints, grouped into
  14 categories (`sessions`, `oauth`, `accounts`, `signup`, `rules`,
  `domains`, `devices`, `account_members`, `service`, `certificates`,
  `spam_queues`, `server`, `smart_discover`, `license`), plus the generic
  `api.iw.call(...)` escape hatch - all fully regenerated from
  `API_doc.json` and never hand-edited. `IceWarpAPI` itself only exposes
  hand-written session lifecycle methods (`login`, `logout`, `use_session`,
  `sid`, `is_authenticated`, `close`) plus curated, higher-level helpers,
  keeping room for more without ever colliding with the generated layer.
- `IceWarpAPI.get_all_accounts()`: curated helper that lists every account
  across all domains (or a single domain), paginating internally, since
  `GetAccountsInfoList` is scoped to one domain at a time. Also available
  from the CLI as `icewarp-api get-all-accounts`.
- `icewarp-api` command line interface with session caching (including the
  cached base URL, inspectable via `icewarp-api status`), a generic `call`
  passthrough command, and one sub-command per endpoint.
- `scripts/generate_client.py` developer tool to regenerate the typed
  wrappers from `API_doc.json`.
