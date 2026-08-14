"""Command line interface for the IceWarp Maintenance API.

Installed as the ``icewarp-api`` console script (see ``pyproject.toml``).
Every category of the generated API (``icewarp_api.generated``) is exposed as
a CLI sub-command group, plus a generic ``call`` passthrough and ``login``/
``logout``/``version`` helpers. Run ``icewarp-api --help`` to explore.
"""

from __future__ import annotations

import inspect
import json
import os
import typing
from dataclasses import dataclass
from pathlib import Path
from typing import Any, List, Optional, Union, get_args, get_origin

import typer

from . import generated as gen
from .api import IceWarpAPI
from .exceptions import IceWarpError

app = typer.Typer(
    help=(
        "CLI for the IceWarp Maintenance API - see https://pypi.org/project/icewarp-api/\n\n"
        "Note: --url/-u, --email/-e, --password/-p, --insecure, --timeout and "
        "--no-session-cache are global options of this base command - place them "
        "BEFORE the sub-command name, e.g. "
        "'icewarp-api --url ... --email ... --password ... login', not "
        "'icewarp-api login --url ...'. Environment variables "
        "(ICEWARP_API_URL/ICEWARP_API_EMAIL/ICEWARP_API_PASSWORD) avoid this "
        "ordering requirement entirely."
    ),
    add_completion=False,
    no_args_is_help=True,
)

# Rich help panel names - keep hand-written/curated commands visually
# separate from the raw, 1:1 generated API category groups in `--help`.
HIGH_LEVEL_PANEL = "Client commands (session management, generic call)"
TOOLKIT_PANEL = "Toolkit (curated helpers built on top of the raw API)"
RAW_API_PANEL = "Raw API categories (1:1 wrappers, one group per API category)"

# category CLI group name -> (generated class, IceWarpAPI facade attribute, help text)
CATEGORY_APPS = [
    ("sessions", gen.SessionMethods, "sessions", "Session, login and authentication related commands"),
    ("oauth", gen.OauthMethods, "oauth", "OAuth client/authorization related commands"),
    ("accounts", gen.AccountMethods, "accounts", "Account management commands"),
    ("signup", gen.SignupMethods, "signup", "Signup / self-service commands"),
    ("rules", gen.RuleMethods, "rules", "Mail rule management commands"),
    ("domains", gen.DomainMethods, "domains", "Domain management commands"),
    ("devices", gen.DeviceMethods, "devices", "Mobile device management commands"),
    (
        "account-members",
        gen.AccountMembersMethods,
        "account_members",
        "Account member (groups/mailing lists) commands",
    ),
    ("service", gen.ServiceStatisticsMethods, "service", "Service & statistics commands"),
    ("certificates", gen.CertificateMethods, "certificates", "TLS certificate management commands"),
    ("spam-queues", gen.SpamQueuesMethods, "spam_queues", "Spam queue commands"),
    ("server", gen.ServerMethods, "server", "Server property commands"),
    ("smart-discover", gen.SmartDiscoverMethods, "smart_discover", "SmartDiscover commands"),
    ("license", gen.LicenseMethods, "license", "License info commands"),
]

CONFIG_DIR = Path(os.environ.get("ICEWARP_API_CONFIG_DIR", str(Path.home() / ".icewarp_api")))
SESSION_FILE = CONFIG_DIR / "session.json"


@dataclass
class CliConfig:
    base_url: Optional[str]
    email: Optional[str]
    password: Optional[str]
    verify_ssl: bool
    timeout: float
    use_cache: bool


def _load_session() -> Optional[dict]:
    if not SESSION_FILE.exists():
        return None
    try:
        return json.loads(SESSION_FILE.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return None


def _save_session(base_url: str, email: Optional[str], sid: str) -> None:
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    SESSION_FILE.write_text(
        json.dumps({"base_url": base_url, "email": email, "sid": sid}), encoding="utf-8"
    )


def _clear_session() -> None:
    if SESSION_FILE.exists():
        SESSION_FILE.unlink()


def _convert_cli_value(raw: str, kind: str) -> Any:
    """Convert a raw CLI string into the value passed to the API method.

    ``kind`` is derived from the generated method's parameter annotation:
    ``"str"`` values are passed through unchanged, ``"int"`` values are
    converted with ``int()`` and ``"any"`` (object-typed) values are parsed
    as JSON so nested parameters (filters, lists, ...) can be supplied as a
    JSON string, e.g. ``--filter '{"namemask": "*"}'``.
    """
    if kind == "int":
        try:
            return int(raw)
        except ValueError:
            return raw
    if kind == "any":
        try:
            return json.loads(raw)
        except (json.JSONDecodeError, ValueError):
            return raw
    return raw


def _param_kind(annotation: Any) -> str:
    if get_origin(annotation) is Union:
        args = [a for a in get_args(annotation) if a is not type(None)]
        annotation = args[0] if args else str
    if annotation is int:
        return "int"
    if annotation is str:
        return "str"
    return "any"


def _get_api(ctx: typer.Context) -> IceWarpAPI:
    cfg: CliConfig = ctx.obj
    cached = _load_session() if cfg.use_cache else None
    base_url = cfg.base_url or (cached.get("base_url") if cached else None)

    if not base_url:
        typer.secho(
            "Missing API base URL. Pass --url/-u BEFORE the sub-command name "
            "(e.g. 'icewarp-api --url https://mail.example.com:32001 domains ...'), "
            "set ICEWARP_API_URL, or run `icewarp-api login --url ...` once to "
            "cache it for later calls.",
            fg=typer.colors.RED,
            err=True,
        )
        raise typer.Exit(code=1)

    api = IceWarpAPI(
        base_url, cfg.email, cfg.password, verify_ssl=cfg.verify_ssl, timeout=cfg.timeout
    )

    if cached and cached.get("base_url") == base_url and cached.get("sid"):
        api.use_session(cached["sid"])
        try:
            api.iw.sessions.get_session_info()
            return api
        except IceWarpError:
            _clear_session()

    if cfg.email and cfg.password is not None:
        sid = api.login()
        if cfg.use_cache:
            _save_session(base_url, cfg.email, sid)
        return api

    typer.secho(
        "Not authenticated: pass --email/-e and --password/-p BEFORE the "
        "sub-command name (e.g. 'icewarp-api --email ... --password ... "
        "domains ...'), set ICEWARP_API_EMAIL/ICEWARP_API_PASSWORD, or run "
        "`icewarp-api login` first.",
        fg=typer.colors.RED,
        err=True,
    )
    raise typer.Exit(code=1)


def _print_result(result: Any) -> None:
    typer.echo(json.dumps(result, indent=2, ensure_ascii=False, default=str))


def _make_cli_command(method_name: str, method: Any, category_attr: str):
    sig = inspect.signature(method)
    # generated modules use `from __future__ import annotations`, so
    # signature().annotation is a string; resolve real types via get_type_hints.
    type_hints = typing.get_type_hints(method)
    cli_params: List[tuple] = []
    parameters = [inspect.Parameter("ctx", kind=inspect.Parameter.POSITIONAL_OR_KEYWORD, annotation=typer.Context)]

    for pname, p in sig.parameters.items():
        if pname == "self":
            continue
        kind = _param_kind(type_hints.get(pname, str))
        flag = "--" + pname.rstrip("_").replace("_", "-")
        help_text = "Maps to the API parameter of the same name."
        if kind == "any":
            help_text += " Accepts a JSON string for nested/list values."
        elif kind == "int":
            help_text += " Integer."
        cli_params.append((pname, kind))
        option = typer.Option(None, flag, help=help_text)
        parameters.append(
            inspect.Parameter(pname, kind=inspect.Parameter.KEYWORD_ONLY, default=option, annotation=Optional[str])
        )

    def _command(**kwargs):
        ctx = kwargs.pop("ctx")
        api = _get_api(ctx)
        target = getattr(getattr(api.iw, category_attr), method_name)
        call_kwargs = {}
        for pname, kind in cli_params:
            raw = kwargs.get(pname)
            if raw is None:
                continue
            call_kwargs[pname] = _convert_cli_value(raw, kind)
        result = target(**call_kwargs)
        _print_result(result)

    _command.__signature__ = inspect.Signature(parameters)
    _command.__name__ = method_name
    doc = (method.__doc__ or "").strip()
    _command.__doc__ = doc.split("\n\n")[0].strip() if doc else method_name
    return _command


def _register_category_apps() -> None:
    for cli_name, cls, attr_name, help_text in CATEGORY_APPS:
        sub_app = typer.Typer(help=help_text, no_args_is_help=True)
        for method_name, method in inspect.getmembers(cls, predicate=inspect.isfunction):
            if method_name.startswith("_"):
                continue
            command = _make_cli_command(method_name, method, attr_name)
            sub_app.command(name=method_name.replace("_", "-"))(command)
        app.add_typer(sub_app, name=cli_name, rich_help_panel=RAW_API_PANEL)


@app.callback()
def main(
    ctx: typer.Context,
    url: Optional[str] = typer.Option(
        None, "--url", "-u", envvar="ICEWARP_API_URL", help="Base API URL, e.g. https://mail.example.com:32001/icewarpapi"
    ),
    email: Optional[str] = typer.Option(
        None, "--email", "-e", envvar="ICEWARP_API_EMAIL", help="Account email/username"
    ),
    password: Optional[str] = typer.Option(
        None, "--password", "-p", envvar="ICEWARP_API_PASSWORD", help="Account password"
    ),
    insecure: bool = typer.Option(False, "--insecure", help="Disable TLS certificate verification"),
    timeout: float = typer.Option(30.0, "--timeout", help="HTTP timeout in seconds"),
    no_session_cache: bool = typer.Option(
        False, "--no-session-cache", help="Do not read/write the local session cache file"
    ),
) -> None:
    ctx.obj = CliConfig(
        base_url=url.rstrip("/") if url else None,
        email=email,
        password=password,
        verify_ssl=not insecure,
        timeout=timeout,
        use_cache=not no_session_cache,
    )


@app.command(rich_help_panel=HIGH_LEVEL_PANEL)
def login(ctx: typer.Context) -> None:
    """Authenticate and cache the session id (and base URL) for subsequent CLI calls.

    --url/-u, --email/-e and --password/-p are global options - pass them
    BEFORE 'login', e.g. 'icewarp-api --url ... --email ... --password ...
    login' (or set ICEWARP_API_URL/ICEWARP_API_EMAIL/ICEWARP_API_PASSWORD).
    """
    cfg: CliConfig = ctx.obj
    cached = _load_session() if cfg.use_cache else None
    base_url = cfg.base_url or (cached.get("base_url") if cached else None)

    if not base_url:
        typer.secho(
            "Missing API base URL. Pass --url/-u BEFORE the sub-command name "
            "(e.g. 'icewarp-api --url https://mail.example.com:32001 login'), "
            "or set ICEWARP_API_URL.",
            fg=typer.colors.RED,
            err=True,
        )
        raise typer.Exit(code=1)
    if not cfg.email or cfg.password is None:
        typer.secho(
            "Both --email/-e and --password/-p are required, and must be passed "
            "BEFORE the sub-command name (e.g. 'icewarp-api --email ... --password ... "
            "login'), or set ICEWARP_API_EMAIL/ICEWARP_API_PASSWORD.",
            fg=typer.colors.RED,
            err=True,
        )
        raise typer.Exit(code=1)

    api = IceWarpAPI(base_url, cfg.email, cfg.password, verify_ssl=cfg.verify_ssl, timeout=cfg.timeout)
    try:
        sid = api.login()
    except IceWarpError as exc:
        typer.secho(f"Login failed: {exc}", fg=typer.colors.RED, err=True)
        raise typer.Exit(code=1) from exc

    if cfg.use_cache:
        _save_session(base_url, cfg.email, sid)
        typer.secho(f"Logged in as {cfg.email}. Session id: {sid}", fg=typer.colors.GREEN)
        typer.secho(
            "Cached session (including the API URL) - later calls don't need --url/--email/--password.",
            fg=typer.colors.GREEN,
        )
    else:
        typer.secho(f"Logged in as {cfg.email}. Session id: {sid}", fg=typer.colors.GREEN)


@app.command(rich_help_panel=HIGH_LEVEL_PANEL)
def logout(ctx: typer.Context) -> None:
    """Log out and clear the cached session, if any."""
    cfg: CliConfig = ctx.obj
    cached = _load_session()
    base_url = cfg.base_url or (cached.get("base_url") if cached else None)
    if cached and cached.get("sid") and base_url:
        api = IceWarpAPI(base_url, verify_ssl=cfg.verify_ssl, timeout=cfg.timeout)
        api.use_session(cached["sid"])
        try:
            api.logout()
        except IceWarpError:
            pass
    _clear_session()
    typer.secho("Logged out.", fg=typer.colors.GREEN)


@app.command(rich_help_panel=HIGH_LEVEL_PANEL)
def whoami(ctx: typer.Context) -> None:
    """Print info about the current session (calls GetSessionInfo)."""
    api = _get_api(ctx)
    _print_result(api.iw.sessions.get_session_info())


@app.command(rich_help_panel=HIGH_LEVEL_PANEL)
def status(ctx: typer.Context) -> None:
    """Show the cached session/config, without making any API calls.

    Unlike `whoami` (which calls the live GetSessionInfo endpoint), this only
    reads the local session cache file (~/.icewarp_api/session.json by
    default) and the currently active --url/--email/env var configuration -
    useful to check what would be used for the next command, or to confirm
    whether `login` actually cached a session.
    """
    cfg: CliConfig = ctx.obj
    cached = _load_session()

    info = {
        "session_cache_file": str(SESSION_FILE),
        "session_cache_enabled": cfg.use_cache,
        "cached_session": cached,
        "effective_base_url": cfg.base_url or (cached.get("base_url") if cached else None),
        "verify_ssl": cfg.verify_ssl,
        "timeout": cfg.timeout,
    }
    _print_result(info)

    if not cfg.use_cache:
        typer.secho("Note: --no-session-cache is set, so the cache above is not being used.", fg=typer.colors.YELLOW)
    elif not cached:
        typer.secho("No cached session found. Run `icewarp-api login` to create one.", fg=typer.colors.YELLOW)


@app.command(name="get-all-accounts", rich_help_panel=TOOLKIT_PANEL)
def get_all_accounts_command(
    ctx: typer.Context,
    domain: Optional[str] = typer.Option(
        None, "--domain", help="Only list accounts in this domain, instead of every domain on the server"
    ),
    page_size: int = typer.Option(
        100, "--page-size", help="Number of accounts requested per page while paginating"
    ),
) -> None:
    """List every account across all domains (curated helper, not a 1:1 endpoint).

    IceWarp's GetAccountsInfoList is scoped to a single domain - this command
    lists every domain first (unless --domain is given), then paginates
    through the accounts in each, returning a flat, combined list. See
    `icewarp-api accounts get-accounts-info-list` for the raw, single-domain
    endpoint this is built on top of.
    """
    api = _get_api(ctx)
    result = api.get_all_accounts(domain=domain, page_size=page_size)
    _print_result(result)


@app.command(name="call", rich_help_panel=HIGH_LEVEL_PANEL)
def call_command(
    ctx: typer.Context,
    command_name: str = typer.Argument(..., help="Endpoint command name, e.g. GetDomainsInfoList"),
    param: List[str] = typer.Option(
        [], "--param", "-P", help="key=value pair, repeatable. Value is parsed as JSON when possible."
    ),
) -> None:
    """Call any of the 174 documented endpoints directly by command name.

    Useful for endpoints you prefer to call generically, or ones added to the
    API after this library was last regenerated.
    """
    api = _get_api(ctx)
    kwargs = {}
    for item in param:
        if "=" not in item:
            typer.secho(f"Invalid --param {item!r}, expected key=value", fg=typer.colors.RED, err=True)
            raise typer.Exit(code=1)
        key, _, value = item.partition("=")
        kwargs[key] = _convert_cli_value(value, "any")
    result = api.iw.call(command_name, **kwargs)
    _print_result(result)


@app.command(rich_help_panel=HIGH_LEVEL_PANEL)
def version() -> None:
    """Print the icewarp_api package version."""
    from . import __version__

    typer.echo(__version__)


_register_category_apps()


def main_entrypoint() -> None:  # pragma: no cover - thin wrapper
    app()


if __name__ == "__main__":  # pragma: no cover
    app()
