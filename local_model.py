"""Local inference adapter; no automatic execution or remote fallback."""
import json
from urllib.parse import urlsplit
from urllib.request import Request, build_opener, ProxyHandler, HTTPRedirectHandler
from source_compiler import parse_json
from player_requests import packet, prompt, validate_proposal


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        raise ValueError("local model redirects are disabled")


def endpoint(base):
    url = urlsplit(base)
    if (url.scheme != "http" or url.hostname not in {"127.0.0.1", "::1"}
            or url.username is not None or url.password is not None
            or url.query or url.fragment or url.path.rstrip("/") != "/v1"):
        raise ValueError("use a loopback HTTP /v1 endpoint")
    return base.rstrip("/") + "/chat/completions"


def propose(session, instruction, model, base="http://127.0.0.1:1234/v1", timeout=60):
    if not isinstance(model, str) or not model.strip():
        raise ValueError("explicit model ID required")
    exchange = packet(session, instruction)
    body = {"model": model, "messages": [{"role": "user", "content": prompt(exchange)}],
            "temperature": 0, "max_tokens": 256, "stream": False}
    req = Request(endpoint(base), data=json.dumps(body).encode(), method="POST",
                  headers={"Content-Type": "application/json"})
    opener = build_opener(ProxyHandler({}), NoRedirect())
    with opener.open(req, timeout=timeout) as reply:
        raw = reply.read(1048577)
    if len(raw) > 1048576:
        raise ValueError("model response too large")
    result = parse_json(raw)
    response = parse_json(result["choices"][0]["message"]["content"])
    return {"response": response, "proposal": validate_proposal(session, exchange, response),
            "model": model}
