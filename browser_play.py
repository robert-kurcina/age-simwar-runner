"""Trusted single-writer loopback browser interface for supported civilian sessions."""
import argparse
import json
import secrets
from html import escape
from http.server import HTTPServer, BaseHTTPRequestHandler
from pathlib import Path
from private_play import read, verify, briefing, update
from runner import digest, save
from visualization import render
from loading_ui import status_markup, JS


def apply(path, revision, operation, action=None):
    session = verify(read(path))
    if digest(session) != revision:
        raise ValueError("Session changed. Reload before continuing.")
    info = briefing(session)
    if info["complete"]:
        raise ValueError("Scenario is complete.")
    if operation == "submit" and isinstance(action, str) and action in info["available_requests"]:
        candidate = update(session, request=action)
    elif operation == "advance" and action is None:
        candidate = update(session, turns=1)
    else:
        raise ValueError("Unsupported operation.")
    save(path, candidate)
    return candidate


def page(session, token):
    info = briefing(session)
    options = "".join('<option value="' + escape(key, quote=True) + '">' +
                      escape(item["description"]) + '</option>'
                      for key, item in info["available_requests"].items())
    requests = "".join('<li>' + escape(str(item["action"])) + ': ' +
                       escape(str(item["status"])) + ' / ' +
                       escape(str(item.get("fulfillment", "pending"))) + '</li>'
                       for item in info["own_requests"])
    controls = '<p>Scenario complete.</p>' if info["complete"] else (
        '<label for="action">Available request</label> <select id="action">' + options +
        '</select> <button type="button" id="submit" ' + ('disabled' if not options else '') +
        '>Confirm request</button> <button type="button" id="advance">Advance turn</button>')
    context = "".join('<p>' + escape(item["summary"]) + '</p>' for item in info["context"])
    panel = '<article id="play-panel" aria-busy="false"><h2>Gameplay</h2>' + context + controls
    panel += status_markup("play") + '<h2>Own requests</h2><ul>' + (requests or '<li>No requests submitted.</li>') + '</ul></article>'
    config = json.dumps({"revision": digest(session), "token": token})
    script = """<script>""" + JS + """
const playConfig = """ + config + """;
const playPanel=document.getElementById('play-panel');
let pending=false;
async function perform(operation,action){
 if(pending)return;
 if(!window.confirm(operation==='submit'?'Submit the selected request?':'Advance one turn?'))return;
 pending=true;
 const buttons=Array.from(playPanel.querySelectorAll('button'));
 const disabled=buttons.map(b=>b.disabled);
 buttons.forEach(b=>b.disabled=true);
 ageLoading('play',playPanel,'loading',operation==='submit'?'Submitting request…':'Adjudicating turn…');
 try{
  const response=await fetch('/operation',{method:'POST',headers:{'Content-Type':'application/json','X-Session-Token':playConfig.token},
   body:JSON.stringify({revision:playConfig.revision,operation,action})});
  const result=await response.json();
  if(!response.ok)throw new Error(result.error||'Request failed.');
  location.reload();
 }catch(error){
  ageLoading('play',playPanel,'error',error.message+' Reload if the session may have changed.');
  buttons.forEach((b,i)=>b.disabled=disabled[i]);pending=false;
 }
}
document.getElementById('submit')?.addEventListener('click',()=>perform('submit',document.getElementById('action').value));
document.getElementById('advance')?.addEventListener('click',()=>perform('advance',null));
</script>"""
    return render(session).replace("</main></html>", panel + script + "</main></html>")


def server(path, port=8765):
    path = Path(path).resolve()
    verify(read(path))
    token = secrets.token_hex(32)

    class Handler(BaseHTTPRequestHandler):
        def send(self, status, content, mime):
            body = content.encode("utf-8")
            self.send_response(status)
            self.send_header("Content-Type", mime)
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store")
            self.send_header("Referrer-Policy", "no-referrer")
            self.send_header("X-Content-Type-Options", "nosniff")
            self.send_header("X-Frame-Options", "DENY")
            self.end_headers()
            self.wfile.write(body)

        def valid_host(self):
            return self.headers.get("Host") == f"127.0.0.1:{self.server.server_port}"

        def do_GET(self):
            if not self.valid_host() or self.path != "/":
                self.send(404, "Not found", "text/plain")
                return
            try:
                self.send(200, page(verify(read(path)), token), "text/html; charset=utf-8")
            except (ValueError, KeyError, TypeError, OSError):
                self.send(409, "Session unavailable; reopen locally.", "text/plain")

        def do_POST(self):
            origin = f"http://127.0.0.1:{self.server.server_port}"
            if (not self.valid_host() or self.path != "/operation" or
                    self.headers.get("Origin") != origin or
                    not secrets.compare_digest(self.headers.get("X-Session-Token", ""), token)):
                self.send(403, '{"error":"Forbidden"}', "application/json")
                return
            try:
                size = int(self.headers.get("Content-Length", "0"))
                if not 0 < size <= 4096 or self.headers.get_content_type() != "application/json":
                    raise ValueError("Invalid request.")
                data = json.loads(self.rfile.read(size))
                if not isinstance(data, dict) or set(data) != {"revision", "operation", "action"}:
                    raise ValueError("Invalid request.")
                apply(path, data["revision"], data["operation"], data["action"])
                self.send(200, '{"saved":true}', "application/json")
            except (ValueError, KeyError, TypeError, OSError):
                self.send(409, '{"error":"Request not applied or session changed. Reload before retrying."}', "application/json")

    return HTTPServer(("127.0.0.1", port), Handler)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("session", type=Path)
    parser.add_argument("--port", type=int, default=8765)
    args = parser.parse_args(argv)
    with server(args.session, args.port) as http:
        print(f"Open http://127.0.0.1:{http.server_port}/ (Ctrl+C to stop)")
        try:
            http.serve_forever()
        except KeyboardInterrupt:
            pass


if __name__ == "__main__":
    main()
