"""Local canonical image maps: pixel coordinates, never inferred georeferencing."""
import base64
import hashlib
import re
import struct
from pathlib import PurePosixPath
from source_compiler import git, checked_date


def resolve(entry, compiled, date, owners):
    config = entry.get("image_map")
    if config is None:
        return None
    if not isinstance(config, dict) or set(config) != {"title", "note", "owner", "revision", "path", "actors", "reviewed_for"}:
        raise ValueError("invalid image map configuration")
    for key in ("title", "note", "owner", "revision", "path", "reviewed_for"):
        if not isinstance(config[key], str) or not config[key].strip():
            raise ValueError("invalid image map field")
    if config["owner"] not in owners or not re.fullmatch(r"[0-9a-f]{40}", config["revision"]):
        raise ValueError("image map requires approved pinned owner")
    path = PurePosixPath(config["path"])
    if path.is_absolute() or ".." in path.parts or str(path) != config["path"] or path.suffix.lower() != ".png":
        raise ValueError("image map requires relative PNG path")
    if checked_date(config["reviewed_for"]) != checked_date(date):
        raise ValueError("image map requires date-specific review")
    audience = config["actors"]
    if not isinstance(audience, list) or not audience or any(a not in compiled["scenario"]["actors"] for a in audience):
        raise ValueError("invalid image map audience")
    root = owners[config["owner"]]
    if git(root, "cat-file", "-t", config["revision"]).strip() != b"commit":
        raise ValueError("image map revision must be a commit")
    raw = git(root, "show", config["revision"] + ":" + str(path))
    if len(raw) > 16 * 1024 * 1024 or len(raw) < 33 or raw[:16] != b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR":
        raise ValueError("image map must be a PNG under 16 MiB")
    width, height = struct.unpack(">II", raw[16:24])
    if not 0 < width <= 12000 or not 0 < height <= 12000 or width * height > 60_000_000:
        raise ValueError("image map dimensions exceed local viewer limits")
    return {**config, "width": width, "height": height,
            "sha256": hashlib.sha256(raw).hexdigest(),
            "png_base64": base64.b64encode(raw).decode("ascii")}


def projection(session, include_image=False):
    item = session["header"].get("image_map")
    if item is None or session["header"]["actor"] not in item["actors"]:
        return None
    fields = ("title", "note", "width", "height", "sha256", "reviewed_for")
    result = {k: item[k] for k in fields}
    if include_image:
        result["png_base64"] = item["png_base64"]
    return result
