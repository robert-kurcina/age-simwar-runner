"""Standalone synthetic library service-desk example.

This example is deliberately domain-specific. It is not a generic action
effect interpreter, and does not alter the existing runner or checkpoints.
"""
import argparse
import json

def run_library(requests):
    """Two shifts, two closed study rooms, one inspection slot per shift.

    Each request identifies one study room. A completed inspection releases
    that room for use. Duplicate requests are recorded without consuming
    another slot. Unrequested rooms stay closed.
    """
    if not isinstance(requests, list) or any(
        type(room) is not int or room not in (1, 2) for room in requests
    ):
        raise ValueError("requests must identify study room 1 or 2")
    pending = list(requests)
    opened = set()
    ledger = []
    timeline = []
    for shift in (1, 2):
        remaining = 1
        while pending and remaining:
            room = pending.pop(0)
            if room in opened:
                ledger.append({"shift": shift, "room": room, "result": "already_open"})
                continue
            opened.add(room)
            remaining -= 1
            ledger.append({"shift": shift, "room": room, "result": "inspection_completed"})
        timeline.append({"shift": shift, "open_rooms": sorted(opened),
                         "pending_requests": len(pending),
                         "inspection_slots_used": 1 - remaining})
    return {"timeline": timeline, "ledger": ledger,
            "open_rooms": sorted(opened), "pending": pending,
            "milestone": {"expected_open_rooms": 2, "actual": len(opened),
                          "passed": len(opened) == 2}}

def comparison():
    baseline = run_library([])
    requested = run_library([1, 2])
    return {"baseline": baseline, "requested": requested,
            "additional_open_rooms": len(requested["open_rooms"]) - len(baseline["open_rooms"])}

def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--room", type=int, choices=(1, 2), action="append")
    args = p.parse_args()
    print(json.dumps(comparison() if args.room is None else run_library(args.room), indent=2))

if __name__ == "__main__":
    main()
