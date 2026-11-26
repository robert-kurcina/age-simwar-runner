"""Local canonical image maps: pixel coordinates, never inferred georeferencing."""
import base64
import hashlib
import math
from copy import deepcopy
import re
import struct
from pathlib import PurePosixPath
from age_runtime.core.source_compiler import read_pinned_source, checked_date


def resolve(entry, compiled, date, owners):
    config = entry.get("image_map")
    if config is None:
        return None
    if not isinstance(config, dict) or set(config) - {"title", "note", "owner", "revision", "path", "actors", "reviewed_for", "annotations"} or not {"title", "note", "owner", "revision", "path", "actors", "reviewed_for"} <= set(config):
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
    raw = read_pinned_source(owners, config["owner"], config["revision"], str(path))
    if len(raw) > 16 * 1024 * 1024 or len(raw) < 33 or raw[:16] != b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR":
        raise ValueError("image map must be a PNG under 16 MiB")
    width, height = struct.unpack(">II", raw[16:24])
    if not 0 < width <= 12000 or not 0 < height <= 12000 or width * height > 60_000_000:
        raise ValueError("image map dimensions exceed local viewer limits")
    validate_annotations(config.get("annotations", []), compiled["scenario"], date, audience, width, height)
    return {**deepcopy(config), "width": width, "height": height,
            "sha256": hashlib.sha256(raw).hexdigest(),
            "png_base64": base64.b64encode(raw).decode("ascii")}


def validate_annotations(items, scenario, date, audience, width, height):
    """Reviewed points on the exact raster, not geographic or movement coordinates."""
    if not isinstance(items, list) or len(items) > 200:
        raise ValueError("invalid image annotations")
    seen = set()
    for item in items:
        required = {"id", "label", "pixel", "actors", "known_from", "source"}
        if not isinstance(item, dict) or not required <= set(item) or set(item) - required - {"hex_id"}:
            raise ValueError("invalid image annotation fields")
        for key in ("id", "label", "source"):
            if not isinstance(item[key], str) or not item[key].strip():
                raise ValueError("invalid image annotation identity")
        if item["id"] in seen:
            raise ValueError("duplicate image annotation")
        seen.add(item["id"])
        if "hex_id" in item and (not isinstance(item["hex_id"], str) or not item["hex_id"].strip()):
            raise ValueError("invalid authored hex identifier")
        point = item["pixel"]
        if (not isinstance(point, list) or len(point) != 2 or
                any(type(v) not in (int, float) or not math.isfinite(v) for v in point)
                or not 0 <= point[0] < width or not 0 <= point[1] < height):
            raise ValueError("annotation outside image")
        actors = item["actors"]
        if not isinstance(actors, list) or not actors or any(a not in audience or a not in scenario["actors"] for a in actors):
            raise ValueError("invalid image annotation audience")
        if checked_date(item["known_from"]) > checked_date(date):
            raise ValueError("future image annotation")


def projection(session, include_image=False):
    item = session["header"].get("image_map")
    if item is None or session["header"]["actor"] not in item["actors"]:
        return None
    fields = ("title", "note", "width", "height", "sha256", "reviewed_for")
    result = {k: item[k] for k in fields}
    result["annotations"] = [{k: deepcopy(v) for k, v in annotation.items() if k != "actors"}
                             for annotation in item.get("annotations", [])
                             if session["header"]["actor"] in annotation["actors"]]
    if include_image:
        result["png_base64"] = item["png_base64"]
    return result
