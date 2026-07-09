"""Deterministic demo-world generator.

Writes fixtures for all 8 connectors that tell ONE consistent story:
- Atlas Revenue OS (us), 5 reps, sells to 25 customer accounts.
- Meridian Bank is the whale (top ARR) and has gone silent for 72 days.
- NovaPay (novapay.io) is the conquest target: 35 people, 5 departments,
  reporting lines, 4 warm nodes who appear in our Gmail fixture.
- Sillage sees a champion move INTO NovaPay, a NovaPay Sales Ops hiring
  spike, another champion move, and a competitor touch on a customer.
- Gradium holds one discovery call with 3 objections and one happy renewal.
Everything is deterministic under seed(42). Future-dated events (the gcal
meeting tomorrow) are stored as relative day offsets so the demo never rots.
"""

from __future__ import annotations

import json
import math
import random
import sys
from datetime import datetime, timedelta
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

FIX = REPO_ROOT / "fixtures"
NOW = datetime.now().replace(minute=0, second=0, microsecond=0)

REPS = [
    ("Lena Fischer", "lena@atlasrev.io"),
    ("Marco Duval", "marco@atlasrev.io"),
    ("Priya Nair", "priya@atlasrev.io"),
    ("Tom Okafor", "tom@atlasrev.io"),
    ("Sofia Lindqvist", "sofia@atlasrev.io"),
]

INDUSTRIES = ["fintech", "logistics", "healthtech", "retail", "SaaS", "manufacturing"]
PRODUCTS = ["Atlas Core", "Atlas Insights", "Atlas Connect", "Atlas Guard"]
STAGES = ["live", "renewal_due", "expansion_talks", "at_risk"]

COMPANY_NAMES = [
    "Meridian Bank", "Cargolux Digital", "Helios Health", "Northwind Retail",
    "Quantiq Labs", "Ferrostahl Group", "BlueRiver Payments", "Optima Logistics",
    "Cortex Medical", "Urban Basket", "Vektor Software", "Alpenstahl AG",
    "Finexa Capital", "TransEuro Freight", "MediSphere", "Marche Central",
    "Nimbus Cloudworks", "Rheinwerk Industrie", "LedgerLine", "SwiftHaul",
    "VitalSign Systems", "Boutique Nord", "Datafjord", "Eisenhof Metall",
    "PayNordic",
]

FIRST = [
    "Emma", "Lucas", "Mia", "Noah", "Lea", "Finn", "Clara", "Jonas", "Ida",
    "Elias", "Nora", "Paul", "Elsa", "Hugo", "Alma", "Oscar", "Ines", "Theo",
    "Lina", "Max", "Aya", "Nils", "Zoe", "Ruben", "Maja", "Karl", "Livia",
    "Anton", "Freja", "Milan", "Selma", "Jan", "Vera", "Otto", "Nadia",
]
LAST = [
    "Keller", "Moreau", "Jansen", "Berg", "Weber", "Rossi", "Novak", "Dubois",
    "Andersen", "Schmid", "Costa", "Meyer", "Blanc", "Eriksen", "Vogel",
    "Marchetti", "Kovacs", "Lindgren", "Bauer", "Fontaine",
]


def domain_of(name: str) -> str:
    return name.lower().replace(" ", "").replace(".", "")[:14] + ".example"


def iso(dt: datetime) -> str:
    return dt.isoformat(timespec="seconds")


def write(rel: str, data: object) -> None:
    path = FIX / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=1), encoding="utf-8")
    print(f"  wrote {rel}")


def person_name(rng: random.Random) -> str:
    return f"{rng.choice(FIRST)} {rng.choice(LAST)}"


def main() -> None:
    rng = random.Random(42)

    # ---- mockcrm: 25 customer accounts, contacts, deals -------------------
    companies = []
    contacts = []
    deals = []
    used_names: set[str] = set()
    for i, cname in enumerate(COMPANY_NAMES):
        dom = domain_of(cname)
        arr = 400_000.0 if i == 0 else round(
            min(400_000, max(8_000, math.exp(rng.gauss(10.3, 0.9)))), 2
        )
        companies.append(
            {
                "id": f"company:{dom}",
                "name": cname,
                "domain": dom,
                "industry": INDUSTRIES[i % len(INDUSTRIES)],
                "size": rng.randint(40, 3000),
                "is_customer": True,
                "arr": arr,
                "renewal_date": iso(NOW + timedelta(days=rng.randint(20, 320))),
                "owner": REPS[i % len(REPS)][1],
            }
        )
        n_contacts = rng.randint(2, 3)
        for _ in range(n_contacts):
            name = person_name(rng)
            while name in used_names:
                name = person_name(rng)
            used_names.add(name)
            email = name.lower().replace(" ", ".") + "@" + dom
            contacts.append(
                {
                    "id": f"person:{email}",
                    "company_domain": dom,
                    "full_name": name,
                    "title": rng.choice(
                        ["Head of Payments", "VP Operations", "CTO", "Procurement Lead",
                         "Finance Director", "IT Manager"]
                    ),
                    "dept": rng.choice(["Finance", "Ops", "Engineering", "Procurement"]),
                    "seniority_level": rng.choice(["MGR", "DIR", "VP", "C"]),
                    "email": email,
                }
            )
        for k in range(rng.randint(1, 2)):
            deals.append(
                {
                    "id": f"deal:{dom}:{k}",
                    "company_domain": dom,
                    "stage": rng.choice(STAGES),
                    "amount": round(arr * rng.uniform(0.2, 1.0), 2),
                    "products": rng.sample(PRODUCTS, rng.randint(1, 3)),
                    "opened_at": iso(NOW - timedelta(days=rng.randint(60, 400))),
                    "closed_at": None,
                }
            )
    write("mockcrm/companies.json", companies)
    write("mockcrm/contacts.json", contacts)
    write("mockcrm/deals.json", deals)
    write("mockcrm/sellers.json", [
        {"id": f"person:{email}", "full_name": name, "email": email,
         "title": "Account Executive", "dept": "Sales", "seniority_level": "IC"}
        for name, email in REPS
    ])

    # ---- fullenrich: NovaPay, 35 people, 5 departments, reporting lines ----
    depts = {
        "C-suite": ["CEO", "CRO", "CFO", "CTO", "COO"],
        "Sales": ["VP Sales", "Sales Ops Manager", "AE", "AE", "AE", "SDR", "SDR", "SDR"],
        "Finance": ["Finance Director", "Controller", "Analyst", "Analyst", "Analyst"],
        "Engineering": ["VP Engineering", "Eng Manager", "Eng Manager", "Engineer",
                        "Engineer", "Engineer", "Engineer", "Engineer", "Engineer"],
        "Ops": ["Head of Ops", "Ops Manager", "Ops Specialist", "Ops Specialist",
                "Ops Specialist", "Support Lead", "Support Agent", "Support Agent"],
    }
    seniority_for = {
        "CEO": "C", "CRO": "C", "CFO": "C", "CTO": "C", "COO": "C",
        "VP Sales": "VP", "VP Engineering": "VP", "Finance Director": "DIR",
        "Head of Ops": "DIR", "Sales Ops Manager": "MGR", "Eng Manager": "MGR",
        "Ops Manager": "MGR", "Controller": "MGR", "Support Lead": "MGR",
    }
    novapay_people = []
    head_email: dict[str, str] = {}
    for dept, titles in depts.items():
        for title in titles:
            name = person_name(rng)
            while name in used_names:
                name = person_name(rng)
            used_names.add(name)
            email = name.lower().replace(" ", ".") + "@novapay.io"
            novapay_people.append(
                {
                    "id": f"person:{email}",
                    "full_name": name,
                    "title": title,
                    "dept": "Sales" if dept == "C-suite" and title == "CRO" else dept,
                    "seniority_level": seniority_for.get(title, "IC"),
                    "email": email,
                    "manager_email": None,
                }
            )
            if title in ("CEO", "CRO", "CFO", "CTO", "COO", "VP Sales", "VP Engineering",
                         "Finance Director", "Head of Ops"):
                head_email[title] = email
    ceo = head_email["CEO"]
    for p in novapay_people:
        t = p["title"]
        if t == "CEO":
            continue
        if t in ("CRO", "CFO", "CTO", "COO"):
            p["manager_email"] = ceo
        elif t in ("VP Sales",):
            p["manager_email"] = head_email["CRO"]
        elif t in ("VP Engineering",):
            p["manager_email"] = head_email["CTO"]
        elif t == "Finance Director":
            p["manager_email"] = head_email["CFO"]
        elif t == "Head of Ops":
            p["manager_email"] = head_email["COO"]
        elif p["dept"] == "Sales":
            p["manager_email"] = head_email["VP Sales"]
        elif p["dept"] == "Engineering":
            p["manager_email"] = head_email["VP Engineering"]
        elif p["dept"] == "Finance":
            p["manager_email"] = head_email["Finance Director"]
        else:
            p["manager_email"] = head_email["Head of Ops"]
    # 4 warm nodes: people our reps already email. Pick mid-seniority spread.
    warm_nodes = [
        head_email["VP Sales"],
        head_email["Finance Director"],
        next(p["email"] for p in novapay_people if p["title"] == "Sales Ops Manager"),
        next(p["email"] for p in novapay_people if p["title"] == "Eng Manager"),
    ]
    write("fullenrich/novapay.json", {
        "company": {"id": "company:novapay.io", "name": "NovaPay", "domain": "novapay.io",
                    "industry": "fintech", "size": 35, "is_customer": False},
        "people": novapay_people,
        "warm_nodes": warm_nodes,
    })
    write("fullenrich/lookalikes.json", {
        "novapay.io": [domain_of(n) for n in
                       ["BlueRiver Payments", "PayNordic", "LedgerLine", "Finexa Capital"]],
    })

    # ---- gmail: 12 months, realistic decay, whale silent 72 days ----------
    whale = companies[0]
    quiet = {companies[idx]["domain"]: 0.3 for idx in (5, 11, 17, 21)}
    messages = []
    mid = 0
    subjects = ["Quarterly sync", "Invoice question", "Feature request", "Renewal terms",
                "Onboarding follow-up", "Usage review", "Support escalation", "Intro"]
    for comp in companies:
        dom = comp["domain"]
        owner = comp["owner"]
        others = [c for c in contacts if c["company_domain"] == dom]
        base = rng.uniform(5.0, 9.0)
        for month in range(12):
            month_end = NOW - timedelta(days=30 * (11 - month))
            rate = base * quiet.get(dom, 1.0) * (0.6 + 0.4 * rng.random())
            n_msgs = max(0, int(rng.gauss(rate, 1.2)))
            for _ in range(n_msgs):
                ts = month_end - timedelta(days=rng.uniform(0, 29), hours=rng.uniform(0, 12))
                if dom == whale["domain"] and (NOW - ts).days < 72:
                    continue  # the whale has gone dark
                contact = rng.choice(others)
                direction = rng.choice(["outbound", "inbound"])
                mid += 1
                messages.append(
                    {
                        "id": f"gmail:{mid}",
                        "thread_id": f"thread:{dom}:{mid // 3}",
                        "ts": iso(ts),
                        "direction": direction,
                        "from": owner if direction == "outbound" else contact["email"],
                        "to": [contact["email"] if direction == "outbound" else owner],
                        "subject": rng.choice(subjects) + f" - {comp['name']}",
                        "latency_hours": round(rng.uniform(0.5, 48), 1)
                        if direction == "inbound" else None,
                        "sentiment": round(rng.uniform(-0.2, 0.9), 2),
                        "company_domain": dom,
                    }
                )
    # warm-node threads with NovaPay (the 4 warm nodes, recent and friendly)
    for w_email in warm_nodes:
        for k in range(rng.randint(3, 5)):
            ts = NOW - timedelta(days=rng.uniform(5, 120))
            direction = "outbound" if k % 2 == 0 else "inbound"
            mid += 1
            messages.append(
                {
                    "id": f"gmail:{mid}",
                    "thread_id": f"thread:novapay.io:{w_email}",
                    "ts": iso(ts),
                    "direction": direction,
                    "from": REPS[0][1] if direction == "outbound" else w_email,
                    "to": [w_email if direction == "outbound" else REPS[0][1]],
                    "subject": "Catching up on payment infra",
                    "latency_hours": round(rng.uniform(0.5, 12), 1)
                    if direction == "inbound" else None,
                    "sentiment": round(rng.uniform(0.4, 0.95), 2),
                    "company_domain": "novapay.io",
                }
            )
    messages.sort(key=lambda m: m["ts"])
    write("gmail/threads.json", messages)

    # ---- gcal: past meetings + one meeting tomorrow (relative offset) ------
    events = []
    eid = 0
    for comp in companies:
        dom = comp["domain"]
        others = [c["email"] for c in contacts if c["company_domain"] == dom]
        for _ in range(rng.randint(6, 12)):
            eid += 1
            events.append(
                {
                    "id": f"gcal:{eid}",
                    "title": f"{comp['name']} sync",
                    "offset_days": -rng.randint(2, 350),
                    "attendees": [comp["owner"], rng.choice(others)],
                    "company_domain": dom,
                }
            )
    events.append(
        {
            "id": "gcal:tomorrow",
            "title": "NovaPay discovery call",
            "offset_days": 1,
            "attendees": [REPS[0][1], warm_nodes[0]],
            "company_domain": "novapay.io",
        }
    )
    write("gcal/events.json", events)

    # ---- slack: #acct-* channels + champion mentions -----------------------
    slack_msgs = []
    sid = 0
    snippets = [
        "renewal convo went well, they want a usage review",
        "flagging slow response from their IT team",
        "they mentioned budget freeze until next quarter",
        "champion said the CFO loved the dashboard",
        "asked for a reference in their industry",
    ]
    for comp in rng.sample(companies, 15):
        dom = comp["domain"]
        for _ in range(rng.randint(4, 12)):
            sid += 1
            slack_msgs.append(
                {
                    "id": f"slack:{sid}",
                    "channel": f"#acct-{dom.split('.')[0]}",
                    "ts": iso(NOW - timedelta(days=rng.uniform(1, 300))),
                    "user_email": rng.choice(REPS)[1],
                    "text": rng.choice(snippets),
                    "company_domain": dom,
                    "champion_mention": rng.random() < 0.15,
                }
            )
    write("slack/messages.json", slack_msgs)

    # ---- notion: 6 case studies + account notes -----------------------------
    case_studies = []
    for i, (ind, metric) in enumerate(
        [("fintech", "38% faster settlement"), ("logistics", "22% cost reduction"),
         ("healthtech", "4x reporting speed"), ("retail", "17% churn drop"),
         ("SaaS", "2.1x pipeline coverage"), ("manufacturing", "31% fewer outages")]
    ):
        case_studies.append(
            {
                "id": f"ref:case-{i}",
                "type": "case_study",
                "source_doc": f"notion://case-studies/{i}",
                "industry": ind,
                "product": PRODUCTS[i % len(PRODUCTS)],
                "outcome": f"Customer in {ind} achieved {metric} within two quarters.",
                "quote": "Atlas paid for itself before the first renewal.",
                "metric": metric,
            }
        )
    notes = [
        {
            "id": f"note:{c['domain']}",
            "type": "note",
            "company_domain": c["domain"],
            "ts": iso(NOW - timedelta(days=rng.randint(10, 200))),
            "text": f"Account plan for {c['name']}: stage {rng.choice(STAGES)}, "
                    f"owner {c['owner']}.",
        }
        for c in rng.sample(companies, 10)
    ]
    write("notion/pages.json", case_studies + notes)

    # ---- sillage: the 4 scripted signals ------------------------------------
    champion_into_novapay = warm_nodes[1]
    sillage = [
        {
            "id": "sillage:1",
            "company_domain": "novapay.io",
            "person_email": champion_into_novapay,
            "kind": "champion_move",
            "strength": 0.9,
            "ts": iso(NOW - timedelta(days=18)),
            "payload": {
                "note": "Former champion at Finexa Capital joined NovaPay as "
                        "Finance Director.",
                "from_company": domain_of("Finexa Capital"),
            },
        },
        {
            "id": "sillage:2",
            "company_domain": domain_of("Vektor Software"),
            "person_email": None,
            "kind": "champion_move",
            "strength": 0.7,
            "ts": iso(NOW - timedelta(days=40)),
            "payload": {"note": "Champion left Vektor Software for a competitor account."},
        },
        {
            "id": "sillage:3",
            "company_domain": "novapay.io",
            "person_email": None,
            "kind": "hiring_spike",
            "strength": 0.8,
            "ts": iso(NOW - timedelta(days=9)),
            "payload": {"note": "NovaPay posted 4 Sales Ops roles in two weeks.",
                        "dept": "Sales Ops", "open_roles": 4},
        },
        {
            "id": "sillage:4",
            "company_domain": whale["domain"],
            "person_email": None,
            "kind": "competitor_engagement",
            "strength": 0.85,
            "ts": iso(NOW - timedelta(days=6)),
            "payload": {"note": f"{whale['name']} engaged with a competitor webinar "
                                "series. Combined with 72 days of email silence."},
        },
        {
            "id": "sillage:5",
            "company_domain": "novapay.io",
            "person_email": None,
            "kind": "buying_intent",
            "strength": 0.75,
            "ts": iso(NOW - timedelta(days=3)),
            "payload": {"note": "NovaPay researching payment reconciliation tooling."},
        },
        {
            "id": "sillage:6",
            "company_domain": domain_of("PayNordic"),
            "person_email": None,
            "kind": "job_change",
            "strength": 0.5,
            "ts": iso(NOW - timedelta(days=25)),
            "payload": {"note": "New CTO at PayNordic."},
        },
    ]
    write("sillage/signals.json", sillage)

    # ---- gradium: 2 transcripts (raw text only, objections left to Phase 3) --
    discovery = (
        "Rep: Thanks for taking the time. Walk me through how reconciliation works "
        "today at NovaPay.\n"
        "Prospect: Mostly spreadsheets plus a nightly batch job. It breaks monthly.\n"
        "Rep: That matches what we hear. Atlas Core automates the matching layer.\n"
        "Prospect: Honestly, the price point worries me. We are a 35 person company.\n"
        "Rep: Fair. Pricing scales with volume, not seats.\n"
        "Prospect: Second concern, we already committed to an internal build this year, "
        "so timing is difficult.\n"
        "Rep: Understood. Many customers ran us alongside the internal tool first.\n"
        "Prospect: And third, our CTO is skeptical about adding another vendor with "
        "access to payment data. Security review would be heavy.\n"
        "Rep: We are SOC 2 Type II and can start with read-only sandbox data.\n"
        "Prospect: Okay. Send the security pack and a pilot proposal."
    )
    renewal = (
        "Rep: Renewal time. How has the year been with Atlas Insights?\n"
        "Customer: Genuinely great. The finance team lives in the dashboards now.\n"
        "Rep: Love to hear it. Any gaps?\n"
        "Customer: Minor export quirks, nothing blocking. We want to add two more teams.\n"
        "Rep: We can bundle that into the renewal with a multi-year discount.\n"
        "Customer: Send the paperwork. Happy to be a reference too."
    )
    write("gradium/transcripts.json", [
        {"id": "transcript:novapay-discovery", "company_domain": "novapay.io",
         "call_ts": iso(NOW - timedelta(days=12)), "text": discovery},
        {"id": "transcript:helios-renewal", "company_domain": domain_of("Helios Health"),
         "call_ts": iso(NOW - timedelta(days=30)), "text": renewal},
    ])

    print(f"seeded demo world at {FIX} (anchor {iso(NOW)})")
    print(f"  gmail messages: {len(messages)}, gcal events: {len(events)}, "
          f"slack: {len(slack_msgs)}")


if __name__ == "__main__":
    main()
