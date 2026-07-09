# ruff: noqa: E501  (embedded HTML/JS template lines run long)
"""Minimal web view of Net-Work (stdlib only, no build step).

Run: python -m surfaces.web  ->  http://localhost:8787
GET /            the dashboard page
GET /api/run     runs a full conquest on fixtures, returns events + plan JSON
"""

from __future__ import annotations

import json
import sys
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from sqlalchemy.orm import Session

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

PORT = 8787
ORBIT_DIR = Path(__file__).resolve().parent / "orbit"


def _orbit_html() -> bytes:
    return (ORBIT_DIR / "index.html").read_bytes()


def _person_brief_markdown(pb: dict) -> str:
    """Gamma one-pager markdown for a person-centric pre-call brief."""
    p = pb.get("person", {})
    rel = pb.get("relationship", {})
    lines = [
        f"# Pre-Call Brief — {p.get('name', '')}",
        f"{p.get('title', '')} · {p.get('company', '')} · {p.get('email', '')}",
        "",
        f"## Why This Call\n{pb.get('purpose', '')}",
        "",
        "## Our Relationship",
        f"Warmth {rel.get('warmth', 0)} · sentiment "
        f"{rel.get('person_sentiment', rel.get('account_recent_sentiment', 0))} · "
        f"{rel.get('sentiment_line', '')}",
    ]
    for c in rel.get("champion_signals", []):
        lines.append(f"- Champion: {c['text']} [{c['evidence']}]")
    for r in rel.get("risk_flags", []):
        lines.append(f"- Risk: {r['text']} [{r['evidence']}]")
    lines += ["", "## Ask Them To Introduce You To"]
    for o in pb.get("onward_intros", []):
        lines.append(f"- {o['name']} ({o['title']}) — {o['reason']} (reach {o['reachability']})")
    return "\n".join(lines)


def _brief_markdown(brief: dict) -> str:
    """Battle-plan-style markdown for the Gamma one-pager export."""
    a = brief.get("account", {})
    h = brief.get("relationship_health", {})
    lines = [
        f"# Pre-Call Brief — {a.get('name', '')}",
        "",
        f"## Context\n{brief.get('context', '')}",
        "",
        "## Relationship Health",
        f"Warmth {h.get('warmth', 0)} · sentiment {h.get('recent_sentiment', 0)} · "
        f"{h.get('sentiment_line', '')}",
    ]
    for c in h.get("champion_signals", []):
        lines.append(f"- Champion: {c['text']} [{c['evidence']}]")
    for r in h.get("risk_flags", []):
        lines.append(f"- Risk: {r['text']} [{r['evidence']}]")
    lines += ["", "## Recommended Plays"]
    for u in brief.get("upsells", []):
        val = f" (€{u['u_eur']:,.0f})" if u.get("u_eur") else ""
        lines.append(f"- {u['name']} ({u.get('title', '')}) — {u.get('action', 'stay warm')}{val}")
    lines += ["", "## Account Signals"]
    for s in brief.get("signals", []):
        lines.append(f"- {s['title']} — {s['talk']}")
    lines += ["", "## Say This On The Call"]
    for t in brief.get("talking_points", []):
        lines.append(f"- {t}")
    return "\n".join(lines)

PAGE = """<!doctype html>
<html><head><meta charset="utf-8"><title>Net-Work</title>
<style>
:root { --bg:#0d1117; --panel:#161b22; --line:#30363d; --text:#e6edf3;
        --dim:#8b949e; --accent:#f0883e; --good:#3fb950; --warm:#f85149; }
* { box-sizing:border-box; margin:0; }
body { background:var(--bg); color:var(--text);
       font:14px/1.5 "Segoe UI",system-ui,sans-serif; padding:24px; }
h1 { font-size:20px; letter-spacing:2px; text-transform:uppercase; }
h1 span { color:var(--accent); }
#sub { color:var(--dim); margin:4px 0 20px; }
.grid { display:grid; grid-template-columns: 340px 1fr; gap:16px; }
.panel { background:var(--panel); border:1px solid var(--line);
         border-radius:8px; padding:16px; }
.panel h2 { font-size:12px; text-transform:uppercase; letter-spacing:1px;
            color:var(--dim); margin-bottom:10px; }
#events { height:520px; overflow-y:auto; font:12px/1.7 Consolas,monospace; }
.ev { opacity:0; transform:translateY(4px); transition:all .25s; }
.ev.show { opacity:1; transform:none; }
.ev b { color:var(--accent); }
.ev .kind { color:var(--good); }
table { width:100%; border-collapse:collapse; margin-top:6px; }
td,th { padding:5px 8px; border-bottom:1px solid var(--line); text-align:left;
        font-size:13px; }
th { color:var(--dim); font-weight:normal; }
.bar { height:8px; border-radius:4px;
       background:linear-gradient(90deg,#1f6feb,var(--warm)); }
.step { padding:6px 0; border-bottom:1px dashed var(--line); }
.p { color:var(--good); font-family:Consolas,monospace; }
#summary { margin:12px 0; padding:12px; border-left:3px solid var(--accent);
           background:#1c2128; border-radius:0 6px 6px 0; }
button { background:var(--accent); border:0; color:#0d1117; font-weight:600;
         padding:8px 18px; border-radius:6px; cursor:pointer; }
#next li { margin:4px 0 4px 16px; }
.muted { color:var(--dim); }
</style></head><body>
<h1><span>Net</span>-Work</h1>
<div id="sub">target: novapay.io &middot; objective: CRO &middot; mode: fixtures &middot;
  <a href="/orbit?account=novapay.io" style="color:var(--accent)">Orbit pre-call brief &rarr;</a></div>
<button id="go" onclick="run()">Run conquest</button>
<div class="grid" style="margin-top:16px">
  <div class="panel"><h2>Agent choreography</h2><div id="events" class="muted">
    press Run conquest</div></div>
  <div>
    <div class="panel"><h2>Unified battle plan</h2>
      <div id="summary" class="muted">waiting for run...</div>
      <h2>Conquest path</h2><div id="steps"></div>
      <h2 style="margin-top:14px">Warmth heatmap</h2>
      <table id="warm"><tr><th>person</th><th>title</th><th>warmth</th><th></th></tr></table>
      <h2 style="margin-top:14px">This week's allocation</h2>
      <table id="alloc"><tr><th>account</th><th>action</th><th>U (EUR)</th></tr></table>
      <h2 style="margin-top:14px">Next steps</h2><ul id="next"></ul>
    </div>
  </div>
</div>
<script>
async function run() {
  document.getElementById('go').disabled = true;
  document.getElementById('events').innerHTML = '';
  const data = await (await fetch('/api/run')).json();
  const box = document.getElementById('events');
  data.events.forEach((e, i) => {
    const div = document.createElement('div');
    div.className = 'ev';
    const payload = Object.entries(e.payload).map(([k,v]) => v).join(' ');
    div.innerHTML = `<b>${e.agent}</b> <span class="kind">${e.kind}</span> ${payload}`;
    box.appendChild(div);
    setTimeout(() => { div.classList.add('show'); box.scrollTop = box.scrollHeight; }, i*180);
  });
  const plan = data.plan;
  setTimeout(() => {
    document.getElementById('summary').textContent = plan.executive_summary;
    document.getElementById('summary').classList.remove('muted');
    document.getElementById('steps').innerHTML = plan.conquest.primary_play.steps.map(
      (s,i) => `<div class="step">${i+1}. ${s.from_person} &rarr; ${s.to_person}` +
               ` <span class="p">p=${s.p}</span><br><span class="muted">${s.ask}</span></div>`
    ).join('') + `<div class="step">reliability <span class="p">R=${plan.conquest.primary_play.reliability}</span>` +
                 ` &middot; <span class="p">EV=EUR ${Math.round(plan.conquest.primary_play.ev_eur).toLocaleString()}</span></div>`;
    document.getElementById('warm').innerHTML =
      '<tr><th>person</th><th>title</th><th>warmth</th><th></th></tr>' +
      plan.network.warm_nodes.map(n =>
        `<tr><td>${n.name}</td><td class="muted">${n.title}</td><td class="p">${n.warmth}</td>` +
        `<td width="120"><div class="bar" style="width:${Math.round(n.warmth*100)}%"></div></td></tr>`).join('');
    document.getElementById('alloc').innerHTML =
      '<tr><th>account</th><th>action</th><th>U (EUR)</th></tr>' +
      plan.allocation.map(a =>
        `<tr><td>${a.account}</td><td class="muted">${a.action}</td>` +
        `<td class="p">${Math.round(a.U_eur).toLocaleString()}</td></tr>`).join('');
    document.getElementById('next').innerHTML =
      plan.next_steps.map(s => `<li>${s}</li>`).join('');
    document.getElementById('go').disabled = false;
  }, data.events.length * 180 + 250);
}
</script></body></html>"""


class Handler(BaseHTTPRequestHandler):
    def _send(self, body: bytes, content_type: str) -> None:
        self.send_response(200)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self) -> None:  # noqa: N802 (http.server API)
        parsed = urlparse(self.path)
        if parsed.path == "/":
            self._send(PAGE.encode("utf-8"), "text/html; charset=utf-8")
            return
        if parsed.path == "/api/run":
            from agents.bus import EventBus
            from agents.orchestrator import conquer_sync

            query = parse_qs(parsed.query)
            bus = EventBus()
            plan = conquer_sync(
                target=query.get("target", ["novapay.io"])[0],
                objective=query.get("objective", ["CRO"])[0],
                bus=bus,
            )
            body = json.dumps(
                {
                    "events": [e.__dict__ for e in bus.log],
                    "plan": plan.model_dump(),
                },
                default=str,
            ).encode("utf-8")
            self._send(body, "application/json")
            return
        if parsed.path in ("/orbit", "/orbit/", "/orbit/calendar", "/orbit/calendar.html"):
            self._send((ORBIT_DIR / "calendar.html").read_bytes(), "text/html; charset=utf-8")
            return
        if parsed.path in ("/orbit/brief", "/orbit/brief.html"):
            self._send((ORBIT_DIR / "brief.html").read_bytes(), "text/html; charset=utf-8")
            return
        if parsed.path == "/orbit/index.html":  # legacy account-centric brief
            self._send(_orbit_html(), "text/html; charset=utf-8")
            return
        if parsed.path == "/orbit/orbit.css":
            self._send((ORBIT_DIR / "orbit.css").read_bytes(), "text/css; charset=utf-8")
            return
        if parsed.path in ("/orbit/fortress-plan.html", "/orbit/book-of-business.html", "/orbit/fortress-viz.html"):
            name = parsed.path.rsplit("/", 1)[-1]
            self._send((ORBIT_DIR / name).read_bytes(), "text/html; charset=utf-8")
            return
        if parsed.path == "/api/calendar":
            from agents.brief import calendar

            try:
                data = {"slots": calendar()}
            except Exception as exc:
                data = {"error": str(exc)}
            self._send(json.dumps(data, default=str).encode("utf-8"), "application/json")
            return
        if parsed.path == "/api/book":
            from agents.brief import book_of_business

            try:
                data = {"accounts": book_of_business()}
            except Exception as exc:
                data = {"error": str(exc)}
            self._send(json.dumps(data, default=str).encode("utf-8"), "application/json")
            return
        if parsed.path == "/api/brief":
            from agents.brief import build_brief, build_person_brief

            query = parse_qs(parsed.query)
            try:
                if "person" in query:  # person-centric one-pager
                    brief = build_person_brief(query["person"][0])
                else:  # account-centric (back-compat)
                    brief = build_brief(query.get("account", ["novapay.io"])[0])
            except Exception as exc:  # surface, don't 500 silently
                brief = {"error": str(exc)}
            self._send(json.dumps(brief, default=str).encode("utf-8"), "application/json")
            return
        if parsed.path == "/api/call-script":
            from agents.brief import build_call_script

            query = parse_qs(parsed.query)
            try:
                data = build_call_script(query.get("person", [""])[0])
            except Exception as exc:
                data = {"error": str(exc)}
            self._send(json.dumps(data, default=str).encode("utf-8"), "application/json")
            return
        if parsed.path == "/api/action-plan":
            from agents.brief import build_action_plan

            query = parse_qs(parsed.query)
            try:
                data = build_action_plan(query.get("person", [""])[0])
            except Exception as exc:
                data = {"error": str(exc)}
            self._send(json.dumps(data, default=str).encode("utf-8"), "application/json")
            return
        if parsed.path == "/api/send-email":
            from agents.brief import send_email

            query = parse_qs(parsed.query)
            try:
                data = send_email(
                    query.get("to", [""])[0],
                    query.get("subject", [""])[0],
                    query.get("body", [""])[0],
                )
            except Exception as exc:
                data = {"error": str(exc)}
            self._send(json.dumps(data, default=str).encode("utf-8"), "application/json")
            return
        if parsed.path == "/api/book-meeting":
            from agents.brief import book_meeting

            query = parse_qs(parsed.query)
            try:
                data = book_meeting(
                    query.get("person", [""])[0],
                    query.get("when", [""])[0],
                    int(query.get("duration", ["30"])[0]),
                    query.get("agenda", [""])[0],
                )
            except Exception as exc:
                data = {"error": str(exc)}
            self._send(json.dumps(data, default=str).encode("utf-8"), "application/json")
            return
        if parsed.path == "/api/deck":
            import asyncio

            from agents.brief import build_brief, build_person_brief
            from surfaces.gamma import generate_deck

            query = parse_qs(parsed.query)
            if "person" in query:
                pb = build_person_brief(query["person"][0])
                md = _person_brief_markdown(pb)
            else:
                md = _brief_markdown(build_brief(query.get("account", ["novapay.io"])[0]))
            result = asyncio.run(generate_deck(md))
            self._send(json.dumps(result, default=str).encode("utf-8"), "application/json")
            return
        if parsed.path == "/api/fortress-graph":
            import networkx as nx
            from engines import fortress, warmth as warmth_engine
            from fabric.store import get_engine as get_db_engine, WarmthRow, PersonRow

            query = parse_qs(parsed.query)
            company = query.get("company", ["novapay.io"])[0]
            target_title = query.get("target", ["CRO"])[0]
            v_deal = float(query.get("v_deal", ["50000"])[0])
            try:
                session = Session(get_db_engine())
                g = fortress.build_graph(session, company)
                result = fortress.solve(company, target_title, v_deal, session=session, graph=g)
                nodes = []
                target_id = None
                for nid, data in g.nodes(data=True):
                    w_row = session.get(WarmthRow, nid)
                    warmth_val = w_row.score if w_row else 0.0
                    is_source = nid == fortress.VIRTUAL_SOURCE
                    is_target = (result["target"]["name"] == data.get("name", ""))
                    is_warm = g.has_edge(fortress.VIRTUAL_SOURCE, nid)
                    if is_target:
                        target_id = nid
                    nodes.append({
                        "id": nid, "name": data.get("name", ""),
                        "title": data.get("title", ""), "dept": data.get("dept", ""),
                        "seniority": next((p.seniority_level for p in [session.get(PersonRow, nid)] if p), "IC") if not is_source else "SOURCE",
                        "warmth": round(warmth_val, 4),
                        "is_source": is_source, "is_target": is_target, "is_warm": is_warm,
                    })
                edges = []
                for u, v, data in g.edges(data=True):
                    edges.append({
                        "source": u, "target": v,
                        "p": round(data.get("p", 0), 4),
                        "rel_type": data.get("components", {}).get("rel_type", "unknown"),
                        "components": data.get("components", {}),
                    })
                paths = []
                for i, path in enumerate(result.get("paths", [])):
                    path["rank"] = i + 1
                    paths.append(path)
                payload = {
                    "nodes": nodes, "edges": edges, "paths": paths,
                    "target": result["target"], "v_deal": v_deal,
                    "company": company,
                    "config": {"warm_tau": 0.35, "effort_per_hop": 1.0},
                }
                session.close()
                self._send(json.dumps(payload, default=str).encode("utf-8"), "application/json")
            except Exception as exc:
                self._send(json.dumps({"error": str(exc)}, default=str).encode("utf-8"), "application/json")
            return
        self.send_response(404)
        self.end_headers()

    def log_message(self, fmt: str, *args: object) -> None:
        print(f"[web] {fmt % args}")


def main() -> None:
    print(f"Net-Work -> http://localhost:{PORT}")
    ThreadingHTTPServer(("127.0.0.1", PORT), Handler).serve_forever()


if __name__ == "__main__":
    main()
