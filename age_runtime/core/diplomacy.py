"""Qualitative diplomatic history derived from actor-visible records only."""
from copy import deepcopy


def history(observation):
    actor = observation["actor"]
    result = {}

    def relationship(other):
        return result.setdefault(other, {"communications": [], "proposals": [],
                                         "agreements": [], "private_intentions": {}})

    for msg in observation.get("communications", []):
        others = msg["recipients"] if msg["speaker"] == actor else [msg["speaker"]]
        for other in others:
            rel = relationship(other)
            # A dispatch is not evidence of acknowledgement, and a claim
            # is not a commitment. Keep only the corresponding record ID.
            rel["communications"].append({
                "id": msg["id"], "direction": "outgoing" if msg["speaker"] == actor else "incoming",
                "sent_minute": msg["minute"],
                **({"delivery_minute": msg["delivery_minute"]} if "delivery_minute" in msg else {}),
                **({"scheduled_delivery": msg["scheduled_delivery"][other]}
                   if "scheduled_delivery" in msg and other in msg["scheduled_delivery"] else {})})
            intention = msg.get("private_intention")
            if msg["speaker"] == actor and intention and intention["counterpart"] == other:
                topic = intention["topic"]
                revisions = rel["private_intentions"].setdefault(topic, {"history": []})
                revisions["history"].append({"claim_id": msg["id"], "minute": msg["minute"],
                                             **deepcopy(intention)})
                revisions["latest"] = deepcopy(revisions["history"][-1])
    for proposal in observation.get("negotiation", {}).get("proposals", []):
        other = proposal["recipient"] if proposal["proposer"] == actor else proposal["proposer"]
        relationship(other)["proposals"].append({
            "id": proposal["id"], "status": proposal["status"],
            "due_minute": proposal["due_minute"],
            **({"parent": proposal["parent"]} if "parent" in proposal else {})})
    for aid, agreement in observation.get("strategic_support", {}).get("agreements", {}).items():
        # Signatory identities are disclosed only within an authorized
        # agreement projection. Do not infer consent from participation.
        for other in agreement.get("participants", []):
            if other != actor:
                relationship(other)["agreements"].append({
                    "id": aid, "status": agreement["status"], "due_minute": agreement["due_minute"],
                    "counterpart_consented": other in agreement["consenting"]})
    return result
