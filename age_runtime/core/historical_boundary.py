"""Strict, read-only historical window for strategic scenario preparation.

This is not the native Great War Event/Time! clock, and does not create actors,
resources or playable actions. It only validates the author-approved quarterly
matrix rehearsal calendar against dated source anchors.
"""
from collections.abc import Mapping

_STATUSES = frozenset({"FIXED", "WORKING", "OPEN"})


def quarterly_window(start_year, end_year, quarters_per_year=4):
    """Inclusive signed-year interval, in historical-model BCE/CE notation.

    The corpus uses negative BCE dates and zero for the CE epoch.
    No automatic calendar inference, Time! conversion or economic recovery.
    """
    if (type(start_year) is not int or type(end_year) is not int
            or type(quarters_per_year) is not int or quarters_per_year != 4
            or start_year > end_year or end_year - start_year > 100):
        raise ValueError("invalid quarterly historical interval")
    return [{"turn": index + 1, "year": year, "quarter": quarter}
            for index, (year, quarter) in enumerate(
                (year, quarter) for year in range(start_year, end_year + 1)
                for quarter in range(1, 5))]


def validate_opening_boundary(boundary):
    """Fail closed on uncertain chronology, authorial status and missing sources.

    Return an immutable-in-practice schedule (fresh dictionaries) without
    presenting an incomplete boundary as a playable scenario.
    """
    if not isinstance(boundary, Mapping) or set(boundary) != {
            "id", "clock", "start_year", "end_year", "start_status",
            "end_status", "map_reference_year", "map_epoch_status",
            "sources", "unresolved", "playable"}:
        raise ValueError("invalid historical boundary fields")
    if boundary["id"] != "great-war-quarterly-rehearsal":
        raise ValueError("unexpected historical boundary")
    if boundary["clock"] != "quarterly_matrix" or boundary["playable"] is not False:
        raise ValueError("historical boundary is not an executable scenario")
    if boundary["start_status"] not in _STATUSES or boundary["end_status"] not in _STATUSES:
        raise ValueError("invalid chronology status")
    if boundary["map_epoch_status"] != "FIXED" or boundary["map_reference_year"] != 286:
        raise ValueError("286 CE snapshot must remain separate")
    schedule = quarterly_window(boundary["start_year"], boundary["end_year"])
    if len(schedule) != 8 or (boundary["start_year"], boundary["end_year"]) != (-1524, -1523):
        raise ValueError("opening requires exactly eight quarters in 1524–1523 BCE")
    if boundary["start_status"] != "WORKING" or boundary["end_status"] != "WORKING":
        raise ValueError("scenario dates are working-design anchors, not fixed canon")
    sources = boundary["sources"]
    if (not isinstance(sources, list) or not sources
            or any(not isinstance(row, dict)
                   or set(row) != {"repo", "path", "blob_sha"}
                   or row["repo"] != "robert-kurcina/vault-great-war"
                   or not all(isinstance(row[key], str) and row[key] for key in row)
                   for row in sources)
            or len({row["path"] for row in sources}) != len(sources)):
        raise ValueError("missing or duplicate historical source provenance")
    unresolved = boundary["unresolved"]
    required = {"deity_roster", "deity_domains", "dated_prominence", "mortal_polities",
                "regional_geography", "starting_resources", "objectives"}
    if not isinstance(unresolved, list) or set(unresolved) != required:
        raise ValueError("historical setup cannot silently omit open questions")
    return schedule
