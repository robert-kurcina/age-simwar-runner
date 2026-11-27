"""Explicitly acknowledged interpersonal agreements, separate from DXD effects."""
import copy
import re

def project(state):
    agreements = {}
    for event in state.get("agreement_history", []):
        if event["operation"] == "create":
            agreements[event["id"]] = copy.deepcopy(event)
            agreements[event["id"]]["status"] = "active"
        else:
            agreements[event["id"]]["status"] = event["status"]
            agreements[event["id"]]["resolution_claim_ids"] = list(event["claim_ids"])
            agreements[event["id"]]["resolved_at"] = event["at"]
    return agreements

def _claims(state, ids, npc, minimum_sequence=-1):
    if not isinstance(ids, list) or not 1 <= len(ids) <= 2 or any(type(i) is not int for i in ids) or len(set(ids)) != len(ids):
        raise ValueError("invalid agreement claim references")
    records = {e["id"]: e for e in state["dialogue"]}
    claims = []
    for i in ids:
        c = records.get(i)
        if (c is None or {c["speaker"], c["listener"]} != {"pc", npc}
                or c["location"] != state["location"] or c["turn"] != state["turn"]
                or i <= minimum_sequence):
            raise ValueError("agreement requires actual current local dialogue")
        claims.append(c)
    return claims

def record(state, rules, request, npc_available):
    if not rules.get("narrative_agreements"):
        raise ValueError("narrative agreements unavailable")
    if not isinstance(request, dict):
        raise ValueError("invalid agreement request")
    ledger = state["agreement_history"]
    if len(ledger) >= 256:
        raise ValueError("agreement record limit")
    eid = request.get("id")
    if not isinstance(eid, str) or not re.fullmatch(r"agr:[a-z][a-z0-9_]{0,63}", eid):
        raise ValueError("invalid agreement identity")
    current = project(state)
    operation = request.get("operation")
    if operation == "create":
        if set(request) != {"operation", "id", "kind", "npc", "issuer", "terms", "condition", "claim_ids"}:
            raise ValueError("invalid agreement fields")
        if eid in current:
            raise ValueError("agreement identity already exists")
        npc, issuer = request["npc"], request["issuer"]
        if request["kind"] not in ("permission", "commitment") or issuer not in ("pc", npc):
            raise ValueError("invalid agreement kind or issuer")
    elif operation == "resolve":
        if set(request) != {"operation", "id", "status", "claim_ids"}:
            raise ValueError("invalid resolution fields")
        if eid not in current or current[eid]["status"] != "active":
            raise ValueError("agreement not active")
        npc, issuer = current[eid]["npc"], current[eid]["issuer"]
    else:
        raise ValueError("invalid agreement operation")
    if (not isinstance(npc, str) or npc not in state["npcs"]
            or state["npcs"][npc]["location"] != state["location"]
            or not npc_available(state, rules, {"npc": npc, "location": state["location"]})):
        raise ValueError("agreement participant unavailable")
    event = {"id": eid, "operation": operation, "turn": state["turn"],
             "at": state["time"], "location": state["location"]}
    if operation == "create":
        claims = _claims(state, request["claim_ids"], npc)
        if {c["speaker"] for c in claims} != {"pc", npc}:
            raise ValueError("agreement requires both participants' recorded statements")
        # Deception does not make an acknowledged promise cease to exist.
        # The GM interprets speech faithfully; no semantic proof is implied.
        from age_runtime.mythos.establishment import text
        terms = text(request["terms"], 300)
        condition = request["condition"]
        if condition is not None:
            condition = text(condition, 240)
        for a in current.values():
            if (a["status"] == "active" and a["npc"] == npc and a["kind"] == request["kind"]
                    and a["issuer"] == issuer and a["terms"].casefold() == terms.casefold()
                    and a["condition"] == condition):
                raise ValueError("equivalent active agreement")
        event.update(kind=request["kind"], npc=npc, issuer=issuer,
                     terms=terms, condition=condition, claim_ids=list(request["claim_ids"]))
    else:
        a = current[eid]
        status = request["status"]
        allowed = ("revoked", "released") if a["kind"] == "permission" else ("fulfilled", "broken", "released")
        if status not in allowed:
            raise ValueError("invalid agreement status")
        claims = _claims(state, request["claim_ids"], npc, max(a["claim_ids"]))
        speakers = {c["speaker"] for c in claims}
        recipient = npc if issuer == "pc" else "pc"
        # A self-reported fulfillment is not enough. Require recipient
        # acknowledgement; a disputed claim remains dialogue only.
        if status == "revoked" and issuer not in speakers:
            raise ValueError("only issuer may revoke permission")
        if status == "released" and recipient not in speakers:
            raise ValueError("recipient must release agreement")
        if status == "fulfilled" and speakers != {"pc", npc}:
            raise ValueError("fulfillment requires mutual acknowledgement")
        if status == "broken" and issuer not in speakers:
            raise ValueError("breakage requires issuer acknowledgement")
        event.update(status=status, claim_ids=list(request["claim_ids"]))
    ledger.append(event)

def public_projection(state):
    return list(project(state).values())
