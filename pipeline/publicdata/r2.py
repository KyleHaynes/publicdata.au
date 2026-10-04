"""Move bytes between local trees and R2 over the S3 API.

Most objects are immutable once written, so an existing key is skipped. A key the caller marks
mutable is uploaded again when its bytes differ: by the listing's ETag, which is the MD5 of a
single-part upload, or else by the SHA-256 stored with the object. The S3 access key
is the Cloudflare API token id and the secret is the SHA-256 of the token, which is how R2 maps
account tokens onto S3 credentials.
"""

from __future__ import annotations

import hashlib
import mimetypes
import os
import re
import sys
from collections.abc import Callable
from pathlib import Path

TYPES = {
    ".parquet": "application/vnd.apache.parquet",
    ".sqlite": "application/vnd.sqlite3",
    ".ndjson": "application/x-ndjson",
    ".geojson": "application/geo+json",
    ".zst": "application/zstd",
    ".json": "application/json",
    ".csv": "text/csv; charset=utf-8",
    ".md": "text/markdown; charset=utf-8",
    ".xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    ".arrow": "application/vnd.apache.arrow.file",
    ".gpkg": "application/geopackage+sqlite3",
    ".pmtiles": "application/vnd.pmtiles",
    ".gz": "application/gzip",
    ".sql": "application/sql; charset=utf-8",
}

VERSIONED = re.compile(r"(^|/)v/\d{4}-\d{2}-\d{2}/")


def client():
    import boto3
    from botocore.config import Config

    token = os.environ.get("CLOUDFLARE_API_TOKEN")
    token_id = os.environ.get("CLOUDFLARE_API_TOKEN_ID")
    account = os.environ.get("CLOUDFLARE_ACCOUNT_ID")
    if not token or not token_id or not account:
        sys.exit(
            "CLOUDFLARE_API_TOKEN, CLOUDFLARE_API_TOKEN_ID and CLOUDFLARE_ACCOUNT_ID are needed for R2"
        )
    return boto3.client(
        "s3",
        endpoint_url=f"https://{account}.r2.cloudflarestorage.com",
        aws_access_key_id=token_id,
        aws_secret_access_key=hashlib.sha256(token.encode()).hexdigest(),
        region_name="auto",
        config=Config(signature_version="s3v4", retries={"max_attempts": 5}),
    )


def _etags(s3, bucket: str, prefix: str) -> dict[str, str]:
    out: dict[str, str] = {}
    for page in s3.get_paginator("list_objects_v2").paginate(Bucket=bucket, Prefix=prefix):
        out.update((o["Key"], o.get("ETag", "").strip('"')) for o in page.get("Contents", []))
    return out


def _md5(p: Path) -> str:
    h = hashlib.md5(usedforsecurity=False)
    with p.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def _sha256(p: Path) -> str:
    h = hashlib.sha256()
    with p.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def versioned(key: str) -> bool:
    return bool(VERSIONED.search(key))


def dated_file(key: str) -> bool:
    """A dated version's file, which never changes. Its page says whether it is the newest."""
    return versioned(key) and not key.endswith(("/index.html", "/index.md"))


def push(
    root: Path,
    bucket: str,
    prefix: str = "",
    replace: tuple[str, ...] = (),
    immutable: Callable[[str], bool] = lambda key: True,
    expect: list[str] = (),
    include: Callable[[str], bool] = lambda key: True,
) -> int:
    """Upload every file under root that include accepts. An existing immutable key is skipped unless it starts
    with one of the replace prefixes, which name the versions whose serialisation was rebuilt on
    purpose; the version notes for such a rebuild are committed separately. Every key in expect,
    which a cached build left out, must already be in the bucket, or nothing is uploaded."""
    s3 = client()
    files = sorted(x for x in root.rglob("*") if x.is_file())
    files = [p for p in files if include(prefix + str(p.relative_to(root)).replace(os.sep, "/"))]
    keys = [prefix + str(p.relative_to(root)).replace(os.sep, "/") for p in files]
    # One listing per dataset directory, which is a page per thousand keys.
    scopes = sorted(
        {
            "/".join(k.split("/")[:2]) + "/" if k.startswith("d/") else prefix
            for k in [*keys, *expect]
        }
    )
    etags: dict[str, str] = {}
    for sc in scopes:
        etags |= _etags(s3, bucket, sc)
    existing = set(etags)
    check_expected(expect, existing, replace)
    n = 0
    for p, key in zip(files, keys, strict=True):
        forced = key.startswith(replace or ("\0",))
        if key in existing and not forced and immutable(key):
            continue
        digest = None
        if key in existing and not forced:
            # A single-part upload's ETag is the MD5 of its bytes, so the listing settles most
            # mutable keys without a HEAD each; a multipart one is checked by its stored SHA-256.
            tag = etags[key]
            if len(tag) == 32 and "-" not in tag:
                if tag == _md5(p):
                    continue
            else:
                digest = _sha256(p)
                meta = s3.head_object(Bucket=bucket, Key=key).get("Metadata", {})
                if meta.get("sha256") == digest:
                    continue
        digest = digest or _sha256(p)
        ctype = TYPES.get(p.suffix) or mimetypes.guess_type(p.name)[0] or "application/octet-stream"
        s3.upload_file(
            str(p), bucket, key, ExtraArgs={"ContentType": ctype, "Metadata": {"sha256": digest}}
        )
        n += 1
        print(f"put {bucket}/{key} ({p.stat().st_size} bytes)")
    return n


def check_expected(expect, existing: set[str], replace: tuple[str, ...] = ()) -> None:
    rebuilt = [k for k in expect if replace and k.startswith(replace)]
    if rebuilt:
        sys.exit(
            f"{len(rebuilt)} file(s) under --replace came from the build cache, e.g. {rebuilt[0]}; "
            "build without the cache to replace them"
        )
    missing = sorted(set(expect) - existing)
    if missing:
        sys.exit(
            f"{len(missing)} file(s) the cached build left out are not in R2, e.g. "
            + ", ".join(missing[:5])
            + "; build without the cache so they are written again"
        )


def pull_store(
    store: Path,
    bucket: str = "publicdata-raw",
    only: tuple[str, ...] = (),
    skip: set[tuple[str, str]] = frozenset(),
) -> int:
    """Fetch every source file a committed manifest names and is missing locally, except the
    versions in skip, which the build takes from its cache. Only the newest catalogue snapshot is
    needed to build."""
    from . import store as st
    from .catalogue import SLUG as CATALOGUE

    s3 = client()
    n = 0
    paths = sorted(store.glob("*/*/manifest.json"))
    old_catalogues = [p for p in paths if p.parts[-3] == CATALOGUE][:-1]
    for mp in (p for p in paths if p not in old_catalogues and (not only or p.parts[-3] in only)):
        if (mp.parts[-3], mp.parts[-2]) in skip:
            continue
        m = st.Manifest.read(mp)
        dest = st.source_path(store, m)
        if dest.exists() and st.sha256_file(dest) == m.sha256:
            continue
        key = f"{m.dataset}/{m.version}/source.{m.ext}"
        s3.download_file(bucket, key, str(dest))
        st.verify(store, m)
        n += 1
        print(f"got {bucket}/{key}")
    return n


def pull_fonts(dest: Path, bucket: str = "publicdata-raw") -> int:
    """Fetch the brand fonts the repository leaves out, checked against their pinned hashes."""
    from .brand import FONT_KEY, FONT_SHA256

    s3 = client()
    dest.mkdir(parents=True, exist_ok=True)
    n = 0
    for name, sha in FONT_SHA256.items():
        p = dest / name
        if p.is_file() and _sha256(p) == sha:
            continue
        s3.download_file(bucket, FONT_KEY + name, str(p))
        if _sha256(p) != sha:
            p.unlink()
            sys.exit(f"{bucket}/{FONT_KEY}{name} does not match its pinned SHA-256")
        n += 1
    return n
