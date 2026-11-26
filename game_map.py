"""Optional player-visible geographic reference, not simulation adjudication."""
import json
import math
from html import escape
from copy import deepcopy
from source_compiler import checked_date


def coords(value):
    if (not isinstance(value, list) or len(value) != 2 or
            any(type(n) not in (int, float) or not math.isfinite(n) for n in value)
            or not -85 <= value[0] <= 85 or not -180 <= value[1] <= 180):
        raise ValueError("invalid map coordinate (latitude, longitude)")
    return value


def reviewed_map(entry, compiled, date):
    config = entry.get("game_map")
    if config is None:
        return None
    if not isinstance(config, dict) or set(config) != {"center", "zoom", "locations", "note"}:
        raise ValueError("invalid map configuration")
    coords(config["center"])
    if type(config["zoom"]) is not int or not 2 <= config["zoom"] <= 15:
        raise ValueError("invalid initial zoom")
    if not isinstance(config["note"], str) or not config["note"].strip():
        raise ValueError("map requires applicability note")
    if not isinstance(config["locations"], list) or len(config["locations"]) > 100:
        raise ValueError("invalid map locations")
    seen = set()
    for item in config["locations"]:
        if not isinstance(item, dict) or set(item) != {"id", "label", "coordinates", "actors", "known_from", "source"}:
            raise ValueError("invalid location fields")
        if any(not isinstance(item[k], str) or not item[k].strip() for k in ("id", "label", "source")):
            raise ValueError("invalid location identity")
        if item["id"] in seen:
            raise ValueError("duplicate location")
        seen.add(item["id"])
        coords(item["coordinates"])
        if (not isinstance(item["actors"], list) or not item["actors"] or
                any(a not in compiled["scenario"]["actors"] for a in item["actors"])):
            raise ValueError("invalid map audience")
        if checked_date(item["known_from"]) > checked_date(date):
            raise ValueError("future map location")
    # All map viewport fields are assumed public to the configured actors.
    # Referee authors must not encode a hidden location in the viewport.
    return deepcopy(config)


def projection(session):
    h = session["header"]
    config = h.get("game_map")
    if config is None:
        return None
    return {"center": config["center"], "zoom": config["zoom"], "note": config["note"],
            "locations": [{k: v for k, v in item.items() if k != "actors"}
                          for item in config["locations"] if h["actor"] in item["actors"]]}


def render_map(data, image=None):
    if data is None and image is None:
        return ""
    if data is None:
        data = {"note": "", "locations": []}
    data = {**data, "image": image}
    fallback = "" if image is None else ('<figure id="image-fallback"><img alt="' + escape(image["title"], quote=True) + '" style="width:100%;height:auto" src="data:image/png;base64,' + image["png_base64"] + '"><figcaption>' + escape(image["note"]) + '</figcaption></figure>')
    # JSON embedded in a script must not permit closing the script element.
    payload = json.dumps(data, ensure_ascii=True, allow_nan=False).replace("<", "\\u003c")
    return """<article style="margin:20px 0"><h2>Map reference</h2>
<p class="muted">""" + escape(data["note"]) + """</p>
""" + fallback + """
<p>Load interactive map to contact the external Leaflet CDN. Geographic mode also requests OpenStreetMap tiles. Image mode uses embedded local artwork and no map tiles.</p>
<button type="button" id="load-map">Load interactive map</button>
<div id="game-map" style="height:440px;max-height:65vh;margin-top:12px;background:#e5e8eb"></div>
<p id="map-distance" aria-live="polite">Select two named locations to measure straight-line distance.</p>
</article>
<script type="application/json" id="map-data">""" + payload + """</script>
<script>
document.getElementById('load-map').addEventListener('click', function () {
 const button = this; button.disabled = true;
 const css = document.createElement('link');
 css.rel = 'stylesheet'; css.href = 'https://unpkg.com/leaflet@1.9.4/dist/leaflet.css';
 css.integrity = 'sha256-p4NxAoJBhIIN+hmNHrzRCf9tD/miZyoHS5obTRR9BMY=';
 css.crossOrigin = 'anonymous'; document.head.appendChild(css);
 const script = document.createElement('script');
 script.src = 'https://unpkg.com/leaflet@1.9.4/dist/leaflet.js';
 script.integrity = 'sha256-20nQCchB9co0qIjJZRGuk2/Z9VM+kNiyxNV1lvTlZBo=';
 script.crossOrigin = 'anonymous';
 script.onerror = () => {button.disabled = false; document.getElementById('map-distance').textContent = 'Map library unavailable.';};
 script.onload = () => {
  const d = JSON.parse(document.getElementById('map-data').textContent);
  const image = d.image;
  const map = L.map('game-map', image ? {crs:L.CRS.Simple,minZoom:-6,maxZoom:3} : {preferCanvas:false});
  if (image) {
   const bounds = [[-image.height,0],[0,image.width]];
   L.imageOverlay('data:image/png;base64,'+image.png_base64,bounds).addTo(map);
   map.fitBounds(bounds);
   document.getElementById('image-fallback').hidden = true;
   document.getElementById('map-distance').textContent = 'Image coordinates only; geographic distances unavailable.';
   button.hidden = true;
   return;
  }
  map.setView(d.center,d.zoom);
  const tiles = L.tileLayer('https://tile.openstreetmap.org/{z}/{x}/{y}.png', {
    attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors', maxZoom:19
  }).addTo(map);
  const names = L.layerGroup().addTo(map), measurements = L.layerGroup().addTo(map);
  L.control.layers({'Reference map':tiles}, {'Named locations':names,'Measurements':measurements}).addTo(map);
  L.control.scale({imperial:false}).addTo(map);
  let first = null;
  const status = document.getElementById('map-distance');
  for (const item of d.locations) {
   const label = document.createElement('span'); label.textContent = item.label;
   const popup = document.createElement('div'); popup.textContent = item.label + ' — ' + item.source;
   const marker = L.circleMarker(item.coordinates,{radius:7,color:'#ffffff',weight:2,fillColor:'#246b75',fillOpacity:1}).addTo(names);
   marker.bindTooltip(label); marker.bindPopup(popup);
   marker.on('click', () => {
    if (!first) { first = item; measurements.clearLayers(); status.textContent = 'From '+item.label+'; choose another location.'; }
    else {
     const km = map.distance(first.coordinates,item.coordinates)/1000;
     // A straight-line measurement, not a road or movement route.
     L.polyline([first.coordinates,item.coordinates],{color:'#246b75',dashArray:'6 6'}).addTo(measurements);
     status.textContent = first.label+' to '+item.label+': '+km.toFixed(1)+' km (straight-line reference distance)';
     first = null;
    }
   });
  }
  button.hidden = true;
 };
 document.head.appendChild(script);
});
</script>"""
