"""Deterministic demo-world generator.

Phase 1 scope is mockcrm only, so this currently seeds
fixtures/mockcrm/accounts.json: 25 existing-customer accounts with a
log-normal ARR spread (EUR 8k to 400k), owned products, a renewal date, and
a current deal stage. Everything is derived from random.seed(42), so
running this twice produces byte-identical output.

When later connectors (Gmail, Sillage, FullEnrich, ...) are implemented,
this script grows into the single place that ties every fixture into one
consistent demo narrative, per the master prompt.
"""

from __future__ import annotations

import json
import random
from datetime import date, timedelta
from pathlib import Path

SEED = 42
ANCHOR_DATE = date(2026, 1, 1)
FIXTURE_PATH = Path(__file__).resolve().parents[1] / "fixtures" / "mockcrm" / "accounts.json"

COMPANY_NAMES = [
    "Luko", "Malt", "Alan", "Spendesk", "Payfit", "Qonto", "Swile", "Ledger",
    "Back Market", "Contentsquare", "Mirakl", "Doctolib", "Ankorstore", "Aircall",
    "Sorare", "Voodoo", "Dataiku", "Algolia", "Younited", "Shift Technology",
    "Ivalua", "Sendinblue", "PayPlug", "Lydia", "October",
]

INDUSTRIES = ["Fintech", "Insurtech", "HR Tech", "Retail Tech", "Healthtech", "Adtech", "Martech"]
SIZES = ["11-50", "51-200", "201-500", "501-2000", "2000+"]
PRODUCT_CATALOG = [
    "Expense Management", "Corporate Cards", "Treasury Automation",
    "Payroll Automation", "Pension Management", "Spend Controls",
    "Advanced AP Automation", "Invoice Ingestion",
]
DEAL_STAGES = ["closed_won", "closed_won", "closed_won", "renewal_pending"]


def _slugify(name: str) -> str:
    return name.lower().replace(" ", "")


def generate_accounts(seed: int = SEED, anchor: date = ANCHOR_DATE) -> list[dict]:
    rng = random.Random(seed)
    accounts: list[dict] = []

    for name in COMPANY_NAMES:
        domain = f"{_slugify(name)}.io"
        account_id = f"acct-{_slugify(name)}"

        arr = round(min(400_000, max(8_000, rng.lognormvariate(10.6, 0.9))), 2)

        months_since_open = rng.randint(6, 48)
        opened_at = anchor - timedelta(days=months_since_open * 30)
        closed_at = opened_at + timedelta(days=rng.randint(7, 45))
        renewal_date = anchor + timedelta(days=rng.randint(-60, 540))

        products = rng.sample(PRODUCT_CATALOG, k=rng.randint(1, 3))
        stage = rng.choice(DEAL_STAGES)

        accounts.append(
            {
                "id": account_id,
                "name": name,
                "domain": domain,
                "industry": rng.choice(INDUSTRIES),
                "size": rng.choice(SIZES),
                "arr": arr,
                "renewal_date": renewal_date.isoformat(),
                "deal": {
                    "stage": stage,
                    "amount": arr,
                    "products": products,
                    "opened_at": opened_at.isoformat(),
                    "closed_at": closed_at.isoformat(),
                },
            }
        )

    return accounts


def write_fixture(path: Path = FIXTURE_PATH) -> list[dict]:
    accounts = generate_accounts()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(accounts, indent=2) + "\n", encoding="utf-8")
    return accounts


def main() -> None:
    accounts = write_fixture()
    print(f"Seeded {len(accounts)} mockcrm accounts to {FIXTURE_PATH}")


if __name__ == "__main__":
    main()
