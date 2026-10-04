"""Cloudflare's edge cache. A dated file is cached as immutable, so a version replaced in R2 is
served stale until its prefix is purged."""

from __future__ import annotations

import requests

API = "https://api.cloudflare.com/client/v4"
HOST = "publicdata.au"
BATCH = 30  # prefixes per purge request


def purge(prefixes: list[str], token: str, host: str = HOST, session=requests) -> int:
    """Purges each d/<slug>/v/<date>/ prefix on host. Returns the number of prefixes purged."""
    auth = {"Authorization": f"Bearer {token}"}
    r = session.get(f"{API}/zones", params={"name": host}, headers=auth, timeout=30)
    r.raise_for_status()
    zones = r.json().get("result") or []
    if not zones:
        raise RuntimeError(f"no zone named {host} for this token")
    url = f"{API}/zones/{zones[0]['id']}/purge_cache"
    full = [f"{host}/{p.lstrip('/')}" for p in prefixes]
    for i in range(0, len(full), BATCH):
        r = session.post(url, json={"prefixes": full[i : i + BATCH]}, headers=auth, timeout=30)
        body = r.json()
        if not r.ok or not body.get("success"):
            raise RuntimeError(f"purge refused: {body.get('errors') or r.status_code}")
    return len(full)
