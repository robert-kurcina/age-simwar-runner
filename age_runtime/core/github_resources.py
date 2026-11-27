"""Optional authenticated GitHub transport for explicit pinned resources."""
import argparse
import base64
import json
import os
from pathlib import Path
import re
from urllib.parse import quote, urlencode
from urllib.request import Request, build_opener, HTTPRedirectHandler

from age_runtime.core.resource_acquisition import requirements, verify_resources
from age_runtime.core.source_compiler import parse_json, read_pinned_source

MAX_RESPONSE = 24 * 1024 * 1024
OWNER = re.compile(r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+")


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        # Never send credentials to a redirect target.
        return None


def fetch(item, token):
    owner = item["owner"]
    if not OWNER.fullmatch(owner) or any(p in (".", "..") for p in owner.split("/")):
        raise ValueError("invalid GitHub repository identity")
    url = ("https://api.github.com/repos/" + owner + "/contents/"
           + quote(item["path"], safe="/") + "?"
           + urlencode({"ref": item["revision"]}))
    request = Request(url, headers={
        "Authorization": "Bearer " + token,
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
        "User-Agent": "age-simwar-runner",
    })
    try:
        with build_opener(NoRedirect()).open(request, timeout=30) as response:
            raw = response.read(MAX_RESPONSE + 1)
        if len(raw) > MAX_RESPONSE:
            raise ValueError("GitHub response exceeds acquisition limit")
        return parse_json(raw)
    except OSError as exc:
        # Do not echo headers, response bodies, tokens or signed URLs.
        raise ValueError("GitHub resource unavailable: " + owner + ":" + item["path"]) from None


def acquire(path, approved_owners, token, transport=fetch):
    """Return existing connector-export-v1 mapping; no writes or source mutation."""
    if not isinstance(token, str) or not token.strip() or any(c.isspace() for c in token):
        raise ValueError("GitHub token required")
    plan = requirements(path)
    allowed = set(approved_owners)
    required = {r["owner"] for r in plan["resources"]}
    if not required <= allowed:
        raise ValueError("resource owner not explicitly approved")
    result = {}
    for item in plan["resources"]:
        response = transport(item, token)
        if (not isinstance(response, dict) or response.get("type") != "file"
                or response.get("path") != item["path"]
                or response.get("encoding") != "base64"
                or not isinstance(response.get("content"), str)
                or not isinstance(response.get("sha"), str)):
            raise ValueError("GitHub response does not contain exact file bytes")
        owner = item["owner"]
        record = {"revision": item["revision"], "path": item["path"],
                  "blob_sha": response["sha"],
                  "content_base64": re.sub(r"[\r\n]", "", response["content"])}
        source = result.setdefault(owner, {"kind": "connector-export-v1", "files": []})
        source["files"].append(record)
        raw = read_pinned_source(result, owner, item["revision"], item["path"])
        if raw.startswith(b"version https://git-lfs.github.com/spec/v1\n"):
            raise ValueError("Git LFS object transport is not supported")
    verify_resources(path, result)
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("inventory", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--allow-owner", action="append", required=True)
    args = parser.parse_args()
    try:
        output = args.output.resolve()
        roots = [Path(__file__).resolve().parents[2], args.inventory.resolve().parent]
        if any(output.is_relative_to(root) for root in roots):
            raise ValueError("private output must be outside runner and catalog")
        if output.exists():
            raise ValueError("output already exists")
        owners = acquire(args.inventory, args.allow_owner, os.environ.get("GH_TOKEN", ""))
        with os.fdopen(os.open(output, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600),
                       "w", encoding="utf-8") as stream:
            try:
                json.dump(owners, stream, ensure_ascii=False)
                stream.write("\n")
            except BaseException:
                stream.close()
                output.unlink()
                raise
    except (ValueError, TypeError, KeyError, OSError) as exc:
        parser.error(str(exc))
    print("Verified private source export written; compile using the existing compiler.")


if __name__ == "__main__":
    main()
