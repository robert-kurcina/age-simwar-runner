"""Bounded epistemic dialogue records; no authority to change world truth.

An utterance is a historical claim, not proof of its content. Existing
scenario facts and mechanical effects remain authoritative. This module
deliberately does not infer truth, deception, or PC belief from prose.
"""
import copy
import re

def _text(value, limit):
    if not isinstance(value, str) or not value.strip() or len(value) > limit or any(ord(c) < 32 for c in value):
        raise ValueError("invalid dialogue text")
    return value.strip()

def conversation_available(state, rules, npc, npc_available):
    """Dialogue requires local presence, and optionally an authored encounter/window."""
    if state["ending"] or state["dxd"].get("activity", {}).get("status") == "asleep":
        return False
    if npc not in state["npcs"] or state["npcs"][npc]["location"] != state["location"]:
        return False
    if not npc_available(state, rules, {"npc": npc, "location": state["location"]}):
        return False
    if not rules.get("dialogue_requires_encounter"):
        return True
    if not state["npcs"][npc]["encounters"]:
        return False
    return any(a.get("npc") == npc and a.get("location") == state["location"]
               and (not a.get("available_from") or state["time"] >= a["available_from"])
               and (not a.get("available_until") or state["time"] < a["available_until"])
               for a in rules["actions"])


def record(state, rules, request, npc_available):
    if not rules.get("epistemic_dialogue") or state["ending"] or state["dxd"].get("activity", {}).get("status") == "asleep":
        raise ValueError("dialogue unavailable")
    required = {"npc", "speaker", "claim", "stance", "intent"}
    if not isinstance(request, dict) or not required <= set(request) or set(request) - required - {"proposition", "asserts", "listener_stance", "reaction", "relay"}:
        raise ValueError("invalid dialogue fields")
    npc, speaker = request["npc"], request["speaker"]
    if not isinstance(npc, str) or npc not in state["npcs"] or speaker not in ("pc", npc):
        raise ValueError("invalid dialogue participants")
    if not conversation_available(state, rules, npc, npc_available):
        raise ValueError("dialogue participant not present or encounter unavailable")
    claim = _text(request["claim"], 400)
    stance, intent = request["stance"], request["intent"]
    if stance not in ("unstated", "believes", "doubts", "disbelieves", "unknown"):
        raise ValueError("invalid speaker stance")
    if intent not in ("unstated", "sincere", "deceive", "fabricate"):
        raise ValueError("invalid speaker intent")
    if speaker == "pc" and (stance != "unstated" or intent != "unstated"):
        raise ValueError("do not infer PC internal state")
    if intent == "sincere" and stance == "disbelieves":
        raise ValueError("contradictory speaker metadata")
    ledger = state["dialogue"]
    if len(ledger) >= 256:
        raise ValueError("dialogue record limit")
    entry = {"id": len(ledger) + 1, "turn": state["turn"], "at": state["time"],
             "location": state["location"], "speaker": speaker,
             "listener": npc if speaker == "pc" else "pc", "claim": claim,
             "speaker_stance": stance, "speaker_intent": intent}
    linked = "proposition" in request or "asserts" in request or "listener_stance" in request
    if linked:
        pid = request.get("proposition")
        asserts = request.get("asserts")
        if not isinstance(pid, str) or type(asserts) is not bool:
            raise ValueError("linked claim requires proposition and boolean assertion")
        spec = registry(state, rules).get(pid)
        if spec is None:
            raise ValueError("unknown proposition")
        # A reference may not disclose an unearned canonical fact. PC may
        # repeat a received claim even when its content is not established.
        known = sources(state, rules, speaker, pid)
        if not known:
            raise ValueError("speaker lacks proposition access")
        if speaker != "pc" and spec["kind"] != "hypothesis" and not sources(state, rules, "pc", pid):
            raise ValueError("new canonical disclosures require authored action")
        listener_stance = request.get("listener_stance", "unstated")
        if listener_stance not in ("unstated", "believes", "doubts", "disbelieves", "unknown"):
            raise ValueError("invalid listener stance")
        if speaker != "pc" and listener_stance != "unstated":
            raise ValueError("do not infer PC belief")
        entry.update(proposition=pid, asserts=asserts, listener_stance=listener_stance)
    if "relay" in request:
        if not rules.get("social_epistemic") or speaker == "pc":
            raise ValueError("NPC relay unavailable")
        source = request["relay"]
        prior = next((c for c in ledger if type(source) is int and c["id"] == source
                      and npc in (c["speaker"], c["listener"])), None)
        if not prior:
            raise ValueError("relay requires own participated claim")
        if prior.get("proposition") != entry.get("proposition"):
            raise ValueError("relay proposition mismatch")
        if "proposition" in prior and prior["asserts"] != entry["asserts"] and intent not in ("deceive", "fabricate"):
            raise ValueError("changed relay assertion requires explicit distortion")
        entry["relay_source"] = source
    if "reaction" in request:
        if not rules.get("relational_continuity"):
            raise ValueError("relational continuity unavailable")
        reaction = request["reaction"]
        if not isinstance(reaction, dict) or not reaction or set(reaction) - {"emotion", "intention", "attachment", "tension", "significance"}:
            raise ValueError("invalid NPC reaction fields")
        # This is the NPC's subjective response to this actual exchange,
        # not a new fact, promise, mechanical modifier or PC inner state.
        entry["npc_reaction"] = {key: _text(value, 240) for key, value in reaction.items()}
    # Exact duplicates within one engine turn add no new continuity.
    if any({k: v for k, v in e.items() if k != "id"} == {k: v for k, v in entry.items() if k != "id"} for e in ledger):
        raise ValueError("duplicate dialogue claim")
    ledger.append(entry)

def record_testimony(state, rules, request, npc_available):
    """Private NPC-to-NPC exchange in the same authoritative dialogue ledger."""
    required = {"speaker", "listener", "claim", "stance", "intent", "listener_stance", "source"}
    optional = {"asserts"} if rules.get("social_epistemic") else set()
    if not rules.get("npc_testimony") or not isinstance(request, dict) or not required <= set(request) or set(request)-required-optional:
        raise ValueError("invalid NPC testimony")
    speaker, listener = request["speaker"], request["listener"]
    if any(not isinstance(a, str) or a not in state["npcs"] for a in (speaker, listener)) or speaker == listener:
        raise ValueError("invalid testimony participants")
    location = state["npcs"][speaker]["location"]
    if location is None or state["npcs"][listener]["location"] != location or any(
            not npc_available(state, rules, {"npc": a, "location": location}) for a in (speaker, listener)):
        raise ValueError("testimony requires available co-located NPCs")
    claim = _text(request["claim"], 400)
    stance, intent, received = request["stance"], request["intent"], request["listener_stance"]
    if stance not in ("unstated", "believes", "doubts", "disbelieves", "unknown") or received not in ("unstated", "believes", "doubts", "disbelieves", "unknown"):
        raise ValueError("invalid testimony stance")
    if intent not in ("unstated", "sincere", "deceive", "fabricate") or (intent == "sincere" and stance == "disbelieves"):
        raise ValueError("invalid testimony intent")
    source = request["source"]
    if not isinstance(source, dict) or set(source) != {"kind", "id"}:
        raise ValueError("invalid testimony source")
    kind, sid = source["kind"], source["id"]
    metadata = {}
    ledger = state["dialogue"]
    if kind == "observation":
        o = next((o for o in state.get("action_observations", []) if o["id"] == sid and o["npc"] == speaker), None)
        if not o:
            raise ValueError("speaker lacks observation")
    elif kind == "claim":
        c = next((c for c in ledger if c["id"] == sid and speaker in (c["speaker"], c["listener"])), None)
        if not c:
            raise ValueError("speaker lacks prior claim")
        if "proposition" in c:
            if not sources(state, rules, speaker, c["proposition"]):
                raise ValueError("speaker lacks proposition access")
            # Pilot relays the same assertion, not a new proposition.
            metadata.update(proposition=c["proposition"], asserts=c["asserts"])
    else:
        raise ValueError("unsupported testimony source")
    if "asserts" in request:
        if "proposition" not in metadata or type(request["asserts"]) is not bool:
            raise ValueError("distortion requires linked assertion")
        if request["asserts"] != metadata["asserts"] and intent not in ("deceive", "fabricate"):
            raise ValueError("changed relay assertion requires explicit distortion")
        metadata["asserts"] = request["asserts"]
    entry = {"id": len(ledger) + 1, "turn": state["turn"], "at": state["time"],
             "location": location, "speaker": speaker, "listener": listener, "claim": claim,
             "speaker_stance": stance, "speaker_intent": intent, "listener_stance": received,
             "testimony_source": copy.deepcopy(source), **metadata}
    if len(ledger) >= 256 or any({k: v for k, v in e.items() if k != "id"} == {k: v for k, v in entry.items() if k != "id"} for e in ledger):
        raise ValueError("duplicate testimony or record limit")
    ledger.append(entry)

def public_projection(state):
    """Only what was actually communicated; no truth or intent annotation."""
    return [{k: v for k, v in e.items() if k not in ("speaker_stance", "speaker_intent", "proposition", "asserts", "listener_stance", "npc_reaction", "relay_source")}
            for e in state.get("dialogue", []) if "pc" in (e["speaker"], e["listener"])]

def referee_projection(state, participants):
    """Return relevant private records, with stable references to prior claims."""
    return copy.deepcopy([e for e in state.get("dialogue", [])
                         if e["speaker"] in participants or e["listener"] in participants])

def validate_propositions(rules):
    """Author registry points to existing facts, not a second world model."""
    grants = {f for a in rules["actions"] for f in a.get("grant", [])}
    for group in ("events", "encounter_table"):
        grants.update(f for a in rules.get(group, []) for f in a.get("grant", []))
    for pid, spec in rules.get("propositions", {}).items():
        _text(pid, 80)
        _text(spec["text"], 400)
        if set(spec) != {"text", "kind", "flag", "initial_knowers"}:
            raise ValueError("invalid proposition fields")
        if spec["kind"] not in ("fact", "report", "inference") or spec["flag"] not in grants:
            raise ValueError("invalid proposition basis")
        if not isinstance(spec["initial_knowers"], list) or not set(spec["initial_knowers"]) <= set(rules["npcs"]):
            raise ValueError("invalid initial knowers")

def registry(state, rules):
    return {**rules.get("propositions", {}), **state.get("dynamic_propositions", {})}

def establish_hypothesis(state, rules, request, npc_available):
    """A proposition under consideration, never an established world fact."""
    if not rules.get("social_epistemic") or not isinstance(request, dict) or set(request) != {"id", "npc", "text", "source"}:
        raise ValueError("invalid hypothesis")
    pid, nid, cid = request["id"], request["npc"], request["source"]
    if not isinstance(pid, str) or not re.fullmatch(r"hyp:[a-z][a-z0-9_]{0,63}", pid) or pid in registry(state, rules):
        raise ValueError("invalid or duplicate hypothesis identity")
    if not isinstance(nid, str) or nid not in state["npcs"]:
        raise ValueError("unknown hypothesis actor")
    location = state["npcs"][nid]["location"]
    if location is None or not npc_available(state, rules, {"npc": nid, "location": location}):
        raise ValueError("hypothesis requires available anchored actor")
    claim = next((c for c in state["dialogue"] if type(cid) is int and c["id"] == cid and nid in (c["speaker"], c["listener"])), None)
    if not claim or len(state["dynamic_propositions"]) >= 64:
        raise ValueError("hypothesis requires actor-scoped claim or record limit")
    text = _text(request["text"], 400)
    if any(spec["text"].casefold() == text.casefold() for spec in registry(state, rules).values()):
        raise ValueError("reuse existing proposition")
    state["dynamic_propositions"][pid] = {"kind": "hypothesis", "text": text, "initial_knowers": [nid],
                                          "source": cid, "at": state["time"]}

def revise_belief(state, rules, request, npc_available):
    if not rules.get("social_epistemic") or not isinstance(request, dict) or set(request) != {"npc", "proposition", "stance", "asserts", "sources", "basis"}:
        raise ValueError("invalid belief revision")
    nid, pid = request["npc"], request["proposition"]
    if not isinstance(nid, str) or nid not in state["npcs"] or not isinstance(pid, str) or pid not in registry(state, rules):
        raise ValueError("unknown belief actor or proposition")
    location = state["npcs"][nid]["location"]
    if location is None or not npc_available(state, rules, {"npc": nid, "location": location}):
        raise ValueError("belief revision requires available anchored NPC")
    if not sources(state, rules, nid, pid):
        raise ValueError("actor lacks proposition access")
    if request["stance"] not in ("believes", "doubts", "disbelieves", "unknown") or type(request["asserts"]) is not bool:
        raise ValueError("invalid subjective stance")
    refs = request["sources"]
    if not isinstance(refs, list) or not 1 <= len(refs) <= 4 or any(type(i) is not int for i in refs) or len(set(refs)) != len(refs):
        raise ValueError("invalid belief sources")
    spec = registry(state, rules)[pid]
    eligible = {c["id"] for c in state["dialogue"] if nid in (c["speaker"], c["listener"]) and c.get("proposition") == pid}
    if spec.get("kind") == "hypothesis" and nid in spec["initial_knowers"]:
        eligible.add(spec["source"])
    if not set(refs) <= eligible:
        raise ValueError("belief sources must concern proposition and be actor-scoped")
    entry = {"npc": nid, "proposition": pid, "stance": request["stance"], "asserts": request["asserts"],
             "sources": list(refs), "basis": _text(request["basis"], 240),
             "at": state["time"], "turn": state["turn"], "sequence": len(state["history"]),
             "claim_cursor": len(state["dialogue"])}
    ledger = state["belief_revisions"]
    if len(ledger) >= 128 or any(all(e[k] == entry[k] for k in ("npc", "proposition", "stance", "asserts", "sources")) for e in ledger):
        raise ValueError("duplicate belief revision or record limit")
    ledger.append(entry)

def sources(state, rules, actor, pid):
    """Access is not belief. Keep authored access and received claims distinct."""
    spec = registry(state, rules)[pid]
    result = []
    if actor in spec["initial_knowers"]:
        result.append({"kind": "hypothesis_origin", "id": spec["source"]} if spec["kind"] == "hypothesis" else {"kind": "authored_access"})
    if actor == "pc" and spec.get("flag") in state["flags"]:
        result.append({"kind": "earned", "flag": spec["flag"]})
    for e in state.get("dialogue", []):
        if e.get("proposition") == pid and e["listener"] == actor:
            result.append({"kind": "received_claim", "id": e["id"], "asserts": e["asserts"]})
    return result

def proposition_projection(state, rules, participants):
    """Private, derived on demand from flags and the existing claim ledger."""
    result = []
    for pid, spec in registry(state, rules).items():
        actors = {}
        for actor in sorted(set(participants) | {"pc"}):
            access = sources(state, rules, actor, pid)
            if not access:
                continue
            revisions = []
            for e in state.get("dialogue", []):
                if e.get("proposition") != pid:
                    continue
                if e["speaker"] == actor and e["speaker_stance"] != "unstated":
                    revisions.append({"id": e["id"], "stance": e["speaker_stance"], "asserts": e["asserts"]})
                if e["listener"] == actor and e["listener_stance"] != "unstated":
                    revisions.append({"id": e["id"], "stance": e["listener_stance"], "asserts": e["asserts"]})
            latest = revisions[-1] if revisions else None
            explicit = [e for e in state.get("belief_revisions", []) if e["npc"] == actor and e["proposition"] == pid]
            if explicit and (latest is None or explicit[-1]["claim_cursor"] >= latest["id"]):
                latest = copy.deepcopy(explicit[-1])
            actors[actor] = {"access": access, "latest_stance": latest}
            if rules.get("social_epistemic"):
                received = [e for e in state["dialogue"] if e.get("proposition") == pid and e["listener"] == actor]
                actors[actor]["conflicting_accounts"] = bool({e["asserts"] for e in received} == {True, False})
                actors[actor]["account_ids"] = [e["id"] for e in received]
        if actors:
            result.append({"id": pid, "text": spec["text"], "kind": spec["kind"],
                           "established": spec.get("flag") in state["flags"], "actors": actors})
    return result

def relational_projection(state, participants):
    """Derive evolving private NPC reactions from committed dialogue.

    Source motivation/traits remain unchanged in the NPC profile. Each
    field has its own provenance; omitted fields do not erase earlier
    reactions. An intention is not an accomplished action.
    """
    result = {}
    for npc in sorted(participants):
        current = {}
        experiences = []
        for entry in state.get("dialogue", []):
            if npc not in (entry["speaker"], entry["listener"]):
                continue
            if "pc" not in (entry["speaker"], entry["listener"]):
                continue
            reaction = entry.get("npc_reaction", {})
            for field, value in reaction.items():
                if field != "significance":
                    current[field] = {"text": value, "claim_id": entry["id"],
                                      "at": entry["at"]}
            if "significance" in reaction:
                experiences.append({"claim_id": entry["id"], "at": entry["at"],
                                    "significance": reaction["significance"]})
        result[npc] = {"current": current, "experiences": experiences}
    return result
