"""CLI utility to generate and extend long-lived / permanent Meta Page Access Tokens."""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import socket
import sys
from typing import Any, Dict, Optional, Tuple, Union
import urllib.error
import urllib.parse
import urllib.request

# Prefer IPv4 resolution to prevent macOS network hangs on blackholed IPv6 routes
_orig_getaddrinfo = socket.getaddrinfo


def _ipv4_first_getaddrinfo(host, port, family=0, type=0, proto=0, flags=0):
    res = _orig_getaddrinfo(host, port, family, type, proto, flags)
    return sorted(res, key=lambda x: 0 if x[0] == socket.AF_INET else 1)


socket.getaddrinfo = _ipv4_first_getaddrinfo

DEFAULT_PAGE_ID = "1216806404853891"
DEFAULT_API_VERSION = "v27.0"
ENV_PATH = Path(__file__).resolve().parents[4] / "tools" / "facebook_agent" / "dm_crawl" / ".env"


def graph_get(
    path: str, params: Dict[str, str], api_version: str = DEFAULT_API_VERSION, timeout: int = 10
) -> Dict[str, Any]:
    """Execute GET request against Meta Graph API."""
    qs = urllib.parse.urlencode(params)
    url = f"https://graph.facebook.com/{api_version}/{path.lstrip('/')}?{qs}"
    req = urllib.request.Request(url, headers={"User-Agent": "SocialContentBot/1.0"})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        err_msg = exc.read().decode("utf-8")
        try:
            parsed = json.loads(err_msg)
            msg = parsed.get("error", {}).get("message", err_msg)
        except Exception:
            msg = err_msg
        raise RuntimeError(f"Meta Graph API error ({exc.code}): {msg}") from exc
    except (urllib.error.URLError, TimeoutError, socket.timeout) as exc:
        raise RuntimeError(f"Network error connecting to Meta Graph API ({path}): {exc}") from exc


def exchange_long_lived_user_token(
    user_token: str, app_id: str, app_secret: str, api_version: str = DEFAULT_API_VERSION
) -> Tuple[str, Optional[int]]:
    """Exchange short-lived User/Page Token for an extended token, extracting expires_in from API."""
    res = graph_get(
        "oauth/access_token",
        {
            "grant_type": "fb_exchange_token",
            "client_id": app_id,
            "client_secret": app_secret,
            "fb_exchange_token": user_token,
        },
        api_version=api_version,
    )
    token = res.get("access_token")
    if not token:
        raise ValueError("Could not extract access_token from exchange response.")
    raw_expires = res.get("expires_in")
    expires_in = int(raw_expires) if raw_expires is not None else None
    return token, expires_in


def fetch_page_access_token(
    token: str,
    page_id: str,
    app_id: Optional[str] = None,
    app_secret: Optional[str] = None,
    api_version: str = DEFAULT_API_VERSION,
) -> Tuple[str, str]:
    """Fetch permanent Page Access Token using a User or Page Access Token."""
    # 0. Check if the token is already a Page Access Token
    debug_data = debug_token_expiry(token, app_id=app_id, app_secret=app_secret, api_version=api_version)
    if debug_data.get("type") == "PAGE":
        page_name = debug_data.get("application") or "Facebook Page"
        return token, page_name

    # 1. Try /{page_id}?fields=id,name,access_token
    try:
        res = graph_get(
            page_id,
            {"fields": "id,name,access_token", "access_token": token},
            api_version=api_version,
        )
        if "access_token" in res:
            return res["access_token"], res.get("name", "Facebook Page")
    except Exception:
        pass

    # 2. Try /me/accounts
    try:
        accounts = graph_get(
            "me/accounts",
            {"fields": "id,name,access_token", "limit": "100", "access_token": token},
            api_version=api_version,
        )
        pages = accounts.get("data", [])
        for page in pages:
            if str(page.get("id")) == str(page_id):
                return page["access_token"], page.get("name", "Facebook Page")

        if len(pages) == 1:
            return pages[0]["access_token"], pages[0].get("name", "Facebook Page")

        if pages:
            available = ", ".join(f"{p.get('name')} (ID: {p.get('id')})" for p in pages)
            raise ValueError(f"Page ID '{page_id}' not found. Available pages for this user: {available}")
    except Exception as exc:
        if "Tried accessing nonexisting field" not in str(exc):
            raise

    raise ValueError("No Facebook Pages found associated with this access token.")


def debug_token_expiry(
    token: str,
    app_id: Optional[str] = None,
    app_secret: Optional[str] = None,
    api_version: str = DEFAULT_API_VERSION,
) -> Dict[str, Any]:
    """Debug access token to inspect expiry and permissions."""
    auth_token = f"{app_id}|{app_secret}" if (app_id and app_secret) else token
    try:
        res = graph_get(
            "debug_token",
            {"input_token": token, "access_token": auth_token},
            api_version=api_version,
            timeout=5,
        )
        return res.get("data", {})
    except Exception:
        return {}


def resolve_env_path(target: Optional[Union[str, Path, bool]] = None) -> Path:
    """Resolve target directory or file to a specific .env file path."""
    if not target or isinstance(target, bool):
        return ENV_PATH
    p = Path(target).expanduser()
    if p.is_file() or p.name.endswith(".env"):
        return p.resolve()
    return (p / ".env").resolve()


def save_token_to_env(token: str, page_id: str, env_path: Union[Path, str] = ENV_PATH) -> Path:
    """Save PAGE_ID and FACEBOOK_ACCESS_TOKEN into the resolved .env file."""
    path = Path(env_path).resolve()
    lines = []
    if path.exists():
        lines = path.read_text(encoding="utf-8").splitlines()

    has_token = False
    has_page = False
    new_lines = []
    for line in lines:
        if line.startswith("FACEBOOK_ACCESS_TOKEN=") or line.startswith("PAGE_ACCESS_TOKEN="):
            new_lines.append(f"FACEBOOK_ACCESS_TOKEN={token}")
            has_token = True
        elif line.startswith("PAGE_ID="):
            new_lines.append(f"PAGE_ID={page_id}")
            has_page = True
        else:
            new_lines.append(line)

    if not has_page:
        new_lines.insert(0, f"PAGE_ID={page_id}")
    if not has_token:
        new_lines.append(f"FACEBOOK_ACCESS_TOKEN={token}")

    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(new_lines) + "\n", encoding="utf-8")
    return path


def get_page_access_token(
    facebook_access_token: str,
    page_id: str = DEFAULT_PAGE_ID,
    app_id: Optional[str] = None,
    app_secret: Optional[str] = None,
    save: Optional[Union[str, Path, bool]] = None,
    api_version: str = DEFAULT_API_VERSION,
) -> Dict[str, Any]:
    """Execute token exchange pipeline and return page token with metadata."""
    working_token = facebook_access_token.strip()

    # Step 1: Optional exchange for extended token if app credentials provided
    exchanged = False
    exchanged_expires_in: Optional[int] = None
    if app_id and app_secret:
        print("[*] Exchanging user token for long-lived token...", file=sys.stderr)
        working_token, exchanged_expires_in = exchange_long_lived_user_token(
            working_token, app_id, app_secret, api_version=api_version
        )
        print("[+] Long-lived token acquired.", file=sys.stderr)
        exchanged = True

    # Step 2: Fetch Page Access Token
    print(f"[*] Fetching Page Access Token for Page ID {page_id}...", file=sys.stderr)
    page_token, page_name = fetch_page_access_token(
        working_token, page_id=page_id, app_id=app_id, app_secret=app_secret, api_version=api_version
    )
    print(f"[+] Page Access Token acquired for '{page_name}'.", file=sys.stderr)

    # Step 3: Debug token expiry
    print("[*] Inspecting token permissions and expiration...", file=sys.stderr)
    debug_info = debug_token_expiry(page_token, app_id=app_id, app_secret=app_secret, api_version=api_version)
    expires_at = debug_info.get("expires_at", 0)
    is_permanent = (expires_at == 0) or (debug_info.get("data_access_expires_at") == 0)

    # Step 4: Save if requested
    saved_path = None
    if save:
        target_path = resolve_env_path(save)
        print(f"[*] Saving token to {target_path}...", file=sys.stderr)
        saved_path = str(save_token_to_env(page_token, page_id=page_id, env_path=target_path))
        print(f"[+] Successfully saved to {saved_path}", file=sys.stderr)

    return {
        "ok": True,
        "page_id": page_id,
        "page_name": page_name,
        "page_access_token": page_token,
        "is_permanent": is_permanent,
        "expires_at": "Never" if is_permanent else str(expires_at),
        "expires_in": exchanged_expires_in,
        "scopes": debug_info.get("scopes", []),
        "saved_to_env": bool(saved_path),
        "env_path": saved_path,
        "exchanged_user_token": exchanged,
    }


def load_default_env_files():
    """Load default credentials from backend or dm_crawl .env if present."""
    candidates = [
        Path(__file__).resolve().parents[1] / ".env",  # tools/app/backend/.env
        ENV_PATH,                                       # tools/facebook_agent/dm_crawl/.env
    ]
    for env_file in candidates:
        if env_file.exists():
            for line in env_file.read_text(encoding="utf-8").splitlines():
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    k, v = line.split("=", 1)
                    k, v = k.strip(), v.strip().strip("\"'")
                    if k and k not in os.environ:
                        os.environ[k] = v


def main():
    load_default_env_files()
    default_token = os.environ.get("FACEBOOK_ACCESS_TOKEN") or os.environ.get("PAGE_ACCESS_TOKEN")

    parser = argparse.ArgumentParser(
        description="Exchange Facebook User/Page Token for an Extended / Permanent Page Access Token"
    )
    parser.add_argument(
        "-t",
        "--token",
        "--facebook-access-token",
        dest="facebook_access_token",
        default=default_token,
        required=not bool(default_token),
        help="Facebook Access Token (from Graph API Explorer or .env)",
    )
    parser.add_argument(
        "--page-id",
        default=os.environ.get("PAGE_ID", DEFAULT_PAGE_ID),
        help=f"Facebook Page ID (default: {DEFAULT_PAGE_ID})",
    )
    parser.add_argument(
        "--app-id",
        default=os.environ.get("FACEBOOK_APP_ID") or os.environ.get("APP_ID"),
        help="Facebook App ID (optional, for 60-day user token exchange)",
    )
    parser.add_argument(
        "--app-secret",
        default=os.environ.get("FACEBOOK_APP_SECRET") or os.environ.get("APP_SECRET"),
        help="Facebook App Secret (optional, for 60-day user token exchange)",
    )
    parser.add_argument(
        "--save",
        nargs="?",
        const=str(ENV_PATH.parent),
        default=None,
        metavar="DIR",
        help=f"Directory to save .env with PAGE_ID and FACEBOOK_ACCESS_TOKEN (defaults to {ENV_PATH.parent} if passed without path)",
    )
    parser.add_argument(
        "--api-version",
        default=DEFAULT_API_VERSION,
        help=f"Graph API Version (default: {DEFAULT_API_VERSION})",
    )

    args = parser.parse_args()

    try:
        result = get_page_access_token(
            facebook_access_token=args.facebook_access_token,
            page_id=args.page_id,
            app_id=args.app_id,
            app_secret=args.app_secret,
            save=args.save,
            api_version=args.api_version,
        )
        print(json.dumps(result, indent=2, ensure_ascii=False))
        return 0
    except Exception as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
