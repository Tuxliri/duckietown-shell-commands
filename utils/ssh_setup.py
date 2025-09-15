from __future__ import annotations

import os
import re
import shutil
import stat
import subprocess
from typing import List, Optional

from dt_shell import dtslogger


DEFAULT_USER = "duckie"
SECRETS_DIR = os.path.expanduser("~/.duckietown/secrets/ssh")
DEFAULT_KEY_BASENAME = "id_ed25519_duckietown"
DEFAULT_KEY_PATH = os.path.join(SECRETS_DIR, DEFAULT_KEY_BASENAME)
DEFAULT_PUB_PATH = DEFAULT_KEY_PATH + ".pub"
SNIPPET_PATH = os.path.join(SECRETS_DIR, "config")
MAIN_SSH_DIR = os.path.expanduser("~/.ssh")
MAIN_SSH_CONFIG = os.path.join(MAIN_SSH_DIR, "config")


def _ensure_dir(path: str, mode: int = 0o700):
    os.makedirs(path, exist_ok=True)
    try:
        os.chmod(path, mode)
    except PermissionError:
        # Non-fatal; continue
        pass


def _write_file(path: str, content: str, mode: int = 0o600):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        f.write(content)
    try:
        os.chmod(path, mode)
    except PermissionError:
        pass


def _append_line_if_missing(path: str, line: str):
    line_stripped = line.strip()
    os.makedirs(os.path.dirname(path), exist_ok=True)
    if not os.path.exists(path):
        with open(path, "w", encoding="utf-8") as f:
            f.write(line_stripped + "\n")
        try:
            os.chmod(path, 0o600)
        except PermissionError:
            pass
        return
    with open(path, "r", encoding="utf-8") as f:
        lines = [l.rstrip("\n") for l in f.readlines()]
    for l in lines:
        if l.strip() == line_stripped:
            return
    with open(path, "a", encoding="utf-8") as f:
        f.write("\n" + line_stripped + "\n")


def ensure_keypair(key_path: str = DEFAULT_KEY_PATH) -> str:
    """Ensure an ed25519 keypair exists at key_path. Return private key path."""
    pub_path = key_path + ".pub"
    _ensure_dir(os.path.dirname(key_path))
    if not os.path.exists(key_path) or not os.path.exists(pub_path):
        dtslogger.info(f"Creating SSH keypair at {key_path}...")
        # Generate key without passphrase
        cmd = [
            "ssh-keygen",
            "-t",
            "ed25519",
            "-f",
            key_path,
            "-N",
            "",
            "-C",
            "duckietown",
        ]
        res = subprocess.run(cmd, check=False)
        if res.returncode != 0:
            raise RuntimeError("Failed to generate SSH keypair with ssh-keygen")
        # Fix permissions
        try:
            os.chmod(key_path, 0o600)
            os.chmod(pub_path, 0o644)
        except PermissionError:
            pass
    return key_path


def _normalize_hosts(host: Optional[str], robot_name: Optional[str]) -> List[str]:
    patterns: List[str] = []
    if host:
        patterns.append(host)
        # If host given as name.local or name.fqdn, try to add bare name
        if "." in host and not re.fullmatch(r"\d+\.\d+\.\d+\.\d+", host):
            base = host.split(".")[0]
            if base:
                patterns.append(base)
            # ensure mDNS form
            patterns.append(f"{base}.local")
    if robot_name:
        patterns.append(robot_name)
        patterns.append(f"{robot_name}.local")
        tailnet = os.environ.get("TAILNET_DOMAIN", "").strip()
        if tailnet:
            patterns.append(f"{robot_name}.{tailnet}")
    # dedupe while preserving order
    seen = set()
    out: List[str] = []
    for p in patterns:
        if not p:
            continue
        if p in seen:
            continue
        seen.add(p)
        out.append(p)
    return out


def ensure_snippet_for_host(host: Optional[str], user: str = DEFAULT_USER, robot_name: Optional[str] = None,
                            key_path: str = DEFAULT_KEY_PATH):
    """Ensure the per-Duckietown SSH config snippet exists and contains a Host block for this host.

    Adds patterns for ip/host, robot_name, robot_name.local and robot_name.<TAILNET_DOMAIN> if available.
    """
    patterns = _normalize_hosts(host, robot_name)
    if not patterns:
        return
    # Use tilde path in config for portability
    identity_cfg_path = os.path.expanduser(key_path)
    identity_cfg_path = identity_cfg_path.replace(os.path.expanduser("~"), "~")
    _ensure_dir(os.path.dirname(SNIPPET_PATH))
    if not os.path.exists(SNIPPET_PATH):
        _write_file(SNIPPET_PATH, "", mode=0o644)

    with open(SNIPPET_PATH, "r", encoding="utf-8") as f:
        content = f.read()

    # Check if any of the patterns already appear in a Host line
    def host_block_exists() -> bool:
        for line in content.splitlines():
            ls = line.strip()
            if not ls.lower().startswith("host "):
                continue
            tokens = ls.split()[1:]
            for p in patterns:
                if p in tokens:
                    return True
        return False

    block = (
        "Host " + " ".join(patterns) + "\n"
        f"    User {user}\n"
        f"    IdentityFile {identity_cfg_path}\n"
        f"    IdentitiesOnly yes\n"
        f"    StrictHostKeyChecking accept-new\n"
    )

    if not host_block_exists():
        with open(SNIPPET_PATH, "a", encoding="utf-8") as f:
            if content and not content.endswith("\n"):
                f.write("\n")
            f.write(block + "\n")


def ensure_main_config_includes_snippet():
    """Ensure our Include block (with comments) is at the very top of ~/.ssh/config.

    - Writes a small comment block around the Include line.
    - Places it as the first non-empty content at the top.
    - Removes duplicates of our Include (tilde or absolute) and our comment lines elsewhere.
    - Keeps permissions at 0600.
    """
    _ensure_dir(MAIN_SSH_DIR)
    abs_snippet = os.path.abspath(SNIPPET_PATH)
    tilde_snippet = abs_snippet.replace(os.path.expanduser("~"), "~")
    include_line = f"Include {tilde_snippet}"
    header = "# Duckietown DTS SSH Integration"
    header2 = "# This must be at the top of ssh_config (before any Host blocks)."
    footer = "# End of Duckietown DTS SSH Integration"

    block_lines = [header, header2, include_line, footer]
    block_set = {l.strip() for l in block_lines}

    if not os.path.exists(MAIN_SSH_CONFIG):
        new_content = "\n".join(block_lines) + "\n\n"
        _write_file(MAIN_SSH_CONFIG, new_content, mode=0o600)
        return

    with open(MAIN_SSH_CONFIG, "r", encoding="utf-8") as f:
        orig = f.read()

    lines = orig.splitlines()
    # Determine if our block is already the first non-empty content
    idx = 0
    while idx < len(lines) and lines[idx].strip() == "":
        idx += 1
    already_top = False
    if idx <= len(lines) - len(block_lines):
        cand = [l.strip() for l in lines[idx:idx+len(block_lines)]]
        if cand == [l.strip() for l in block_lines]:
            already_top = True
    if already_top:
        return

    # Filter out any of our previous include lines or comments scattered in the file
    filtered: List[str] = []
    for l in lines:
        ls = l.strip()
        if ls in block_set or ls == f"Include {abs_snippet}":
            continue
        filtered.append(l)

    # Prepend our block at the very top, followed by a blank line, then the rest
    new_content = "\n".join(block_lines) + "\n\n" + "\n".join(filtered).rstrip() + "\n"
    _write_file(MAIN_SSH_CONFIG, new_content, mode=0o600)


def _key_login_works(host: str, user: str, key_path: str) -> bool:
    # BatchMode=yes prevents password prompts; we just test
    cmd = [
        "ssh",
        "-i",
        key_path,
        "-o",
        "BatchMode=yes",
        "-o",
        "IdentitiesOnly=yes",
        "-o",
        "StrictHostKeyChecking=accept-new",
        f"{user}@{host}",
        "exit",
    ]
    res = subprocess.run(cmd, check=False, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    return res.returncode == 0


def _install_pubkey_via_ssh_copy_id(host: str, user: str, pub_path: str) -> bool:
    if shutil.which("ssh-copy-id") is None:
        return False
    dtslogger.info("Installing public key on robot using ssh-copy-id (you may be prompted for password)...")
    cmd = ["ssh-copy-id", "-i", pub_path, f"{user}@{host}"]
    res = subprocess.run(cmd, check=False)
    return res.returncode == 0


def _install_pubkey_fallback(host: str, user: str, pub_path: str) -> bool:
    try:
        with open(pub_path, "r", encoding="utf-8") as f:
            pubkey = f.read().strip()
    except Exception as e:
        dtslogger.error(f"Failed to read public key: {e}")
        return False
    dtslogger.info("Installing public key on robot using a fallback method (you may be prompted for password)...")
    # Safe append: ensure ~/.ssh exists and append only if not already present
    remote_cmd = (
        "mkdir -p ~/.ssh && chmod 700 ~/.ssh && "
        "touch ~/.ssh/authorized_keys && chmod 600 ~/.ssh/authorized_keys && "
        # Use grep -qxF to check exact line presence
        f"grep -qxF '{pubkey}' ~/.ssh/authorized_keys || echo '{pubkey}' >> ~/.ssh/authorized_keys"
    )
    cmd = ["ssh", f"{user}@{host}", remote_cmd]
    res = subprocess.run(cmd, check=False)
    return res.returncode == 0


def ensure_ssh_for_host(host: Optional[str], user: str = DEFAULT_USER, robot_name: Optional[str] = None) -> str:
    """Ensure local SSH keypair and config are ready, and attempt to install pubkey on the remote host.

    Returns the path to the private key.
    """
    key_path = ensure_keypair(DEFAULT_KEY_PATH)
    ensure_snippet_for_host(host, user=user, robot_name=robot_name, key_path=key_path)
    ensure_main_config_includes_snippet()

    if host:
        # Attempt key-based login; if it fails, try to install the key
        if not _key_login_works(host, user, key_path):
            pub_path = key_path + ".pub"
            if not _install_pubkey_via_ssh_copy_id(host, user, pub_path):
                _install_pubkey_fallback(host, user, pub_path)
        else:
            dtslogger.debug("Key-based SSH login already works for this host.")
    return key_path
