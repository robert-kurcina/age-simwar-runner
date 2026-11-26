"""Read-only local player visualization from verified private sessions."""
from html import escape
from private_play import briefing
from game_map import projection, render_map
from image_map import projection as image_projection
from loading_ui import CSS as LOADING_CSS

LABELS = {
    "households_assisted": "Households assisted",
    "aid_packages": "Aid packages remaining",
    "open_service_centers": "Open service centers",
    "restoration_credits": "Restoration credits remaining",
    "participating_councils": "Participating councils",
    "council_a_joined": "Council A participation",
    "council_b_joined": "Council B participation",
}


def snapshot(session):
    current = briefing(session)
    scenario = session["header"]["compiled"]["scenario"]
    metrics = []
    for key, report in current["reports"].items():
        points = []
        if report["status"] != "unknown":
            cutoff = report["as_of_minute"]
            points = [{"minute": 0, "value": scenario["initial"][key]}]
            for event in session["state"]["ledger"]:
                if event["key"] == key and event["minute"] <= cutoff:
                    point = {"minute": event["minute"], "value": event["value"]}
                    if points[-1]["minute"] == point["minute"]:
                        points[-1] = point
                    else:
                        points.append(point)
            if points[-1]["minute"] < cutoff:
                points.append({"minute": cutoff, "value": report["value"]})
        metrics.append({"id": key, "label": LABELS.get(key, key.replace("_", " ").capitalize()),
                        "report": report, "observed_history": points})
    # Do not export preset internals: a configured resource may be hidden.
    return {"version": 1, "title": current["scenario"], "perspective": current["perspective"],
            "date": current["date"], "turn": current["turn"],
            "elapsed_minutes": current["elapsed_minutes"], "complete": current["complete"],
            "continued": current["continued"], "metrics": metrics,
            "objectives": current["objectives"], "calibration": current["calibration"],
            "map": projection(session), "image_map": image_projection(session)}


def chart(points):
    if len(points) < 2:
        return '<p class="muted">No observed time series yet.</p>'
    maximum = max(1, *(abs(p["value"]) for p in points))
    duration = max(1, points[-1]["minute"])
    def xy(p):
        return 12 + 276 * p["minute"] / duration, 60 - 48 * p["value"] / maximum
    x, y = xy(points[0])
    path = f"M{x:.2f},{y:.2f}"
    for point in points[1:]:
        x, y = xy(point)
        path += f" H{x:.2f} V{y:.2f}"
    return (f'<svg viewBox="0 0 300 120" role="img" aria-label="Observed resource history">'
            f'<path d="{path}" fill="none" stroke="#20766e" stroke-width="2.5"/>'
            f'<path d="M12 108H288" stroke="#b9c5cd"/>'
            f'</svg><small>Observation minutes 0–{duration}</small>')


def render(session):
    data = snapshot(session)
    def esc(value):
        return escape(str(value), quote=True)
    cards = []
    for metric in data["metrics"]:
        report = metric["report"]
        status = report["status"]
        value = report.get("value", "Unknown")
        detail = "Not yet observed" if status == "unknown" else (
            f"{status.capitalize()} · as of minute {report['as_of_minute']}")
        cards.append(f'<article><h2>{esc(metric["label"])}</h2><strong>{esc(value)}</strong>'
                     f'<p class="muted">{esc(detail)}</p>{chart(metric["observed_history"])}</article>')
    goals = "".join(f'<li>{esc(obj["description"])} — {esc(obj["observed_result"] if obj["observed_result"] is not None else "Unknown")}</li>'
                    for obj in data["objectives"].values())
    return f"""<!doctype html>
<html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>{esc(data['title'])} — AGE SimWar</title>
<style>
{LOADING_CSS}
*{{box-sizing:border-box}}body{{margin:0;background:#f3f5f6;color:#202d36;font:16px system-ui,sans-serif}}
main{{max-width:1000px;margin:auto;padding:24px}}header{{border-bottom:1px solid #ccd5dc;padding-bottom:16px}}
h1{{font-size:clamp(22px,4vw,34px);margin:8px 0}}h2{{font-size:16px;margin:0 0 12px}}
.grid{{display:grid;grid-template-columns:repeat(auto-fit,minmax(min(100%,240px),1fr));gap:16px;margin:20px 0}}
article{{background:white;border:1px solid #d7dfe3;border-radius:8px;padding:20px}}
strong{{font-size:34px;font-variant-numeric:tabular-nums}}.muted,small{{color:#50616d}}
article > svg{{width:100%;height:auto;display:block}}li{{margin:8px 0}}
</style><main><header><small>AGE SIMWAR · READ-ONLY SESSION SNAPSHOT</small>
<h1>{esc(data['title'])}</h1><p>{esc(data['perspective'])} · {esc(data['date'])} · Turn {data['turn']} · {'Complete' if data['complete'] else 'In progress'}</p>
<p class="muted">{esc(data['calibration'])}</p></header>
{render_map(data["map"], image_projection(session, include_image=True))}
<section class="grid" aria-label="Observed resources">{''.join(cards) or '<p>No visible resource reports.</p>'}</section>
<article><h2>Objectives</h2><ul>{goals or '<li>No configured objectives.</li>'}</ul></article>
</main></html>"""
