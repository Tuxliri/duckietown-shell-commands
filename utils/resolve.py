from __future__ import annotations
import os
import socket
import subprocess
from typing import Iterable, Optional


def _is_reachable(host: str, port: int = 22, timeout: float = 1.5) -> bool:
    """Fast check: try TCP connect; if blocked, fall back to getaddrinfo + ping."""
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return True
    except Exception:
        # DNS ok but SSH closed? Still verify host resolves and responds to ping.
        try:
            socket.getaddrinfo(host, None)
        except socket.gaierror:
            return False
        try:
            # -c 1 one packet, -W timeout seconds (Linux/BusyBox compatible)
            subprocess.run(
                ["ping", "-c", "1", "-W", str(int(timeout)), host],
                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True
            )
            return True
        except Exception:
            return False


def _magicdns_candidates(bot_name: str) -> Iterable[str]:
    # Optional: if a user exports TAILNET_DOMAIN=tailnet-xyz.ts.net we’ll try FQDN too
    tailnet = os.environ.get("TAILNET_DOMAIN", "").strip()
    if tailnet:
        yield f"{bot_name}.{tailnet}"


def get_duckiebot_host(
    duckiebot_name: str = "duckiebot",
    extra_candidates: Optional[Iterable[str]] = None,
) -> str:
    """Return the best hostname to reach the Duckiebot.
    Precedence:
      1) DUCKIEBOT_HOST (explicit override)
      2) `duckiebot_name`.local (mDNS)
      3) `duckiebot_name` (MagicDNS short name)
      4) `duckiebot_name`.<TAILNET_DOMAIN> (MagicDNS FQDN, optional)
      5) any extra candidates passed in
    Raises RuntimeError if none are reachable.
    """
    override = os.environ.get("DUCKIEBOT_HOST")
    if override:
        return override

    candidates = [ f"{duckiebot_name}.local", duckiebot_name]
    candidates += list(_magicdns_candidates(duckiebot_name))
    if extra_candidates:
        candidates += list(extra_candidates)

    tried = []
    for host in candidates:
        if _is_reachable(host):
            return host
        tried.append(host)

    raise RuntimeError(
        f"Could not reach Duckiebot via any hostname. Tried: {', '.join(tried)}.\n"
        "Tip: export DUCKIEBOT_HOST=<ip-or-host>, or set TAILNET_DOMAIN=tailnet-xyz.ts.net."
    )
