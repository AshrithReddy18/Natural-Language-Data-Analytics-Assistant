"""Deterministic generator for the "Sales Demo" dataset (Indian e-commerce, 2024–2025).

The data is synthetic but shaped like a real business so that analysis is non-trivial:
  * ~30% year-over-year growth that differs by category
  * seasonality with a festive (Diwali) peak in Oct/Nov and a year-end sale
  * weekend uplift and short sale events with deeper discounts
  * heavy-tailed customers: many one-time buyers, a loyal core of repeat buyers
  * products with individual trends (some rising, some clearly declining, some launched mid-2025)
  * category-specific cancellation / return rates; refunds reflected in payments
  * payment mix drifting from cash-on-delivery toward UPI
"""

import math
import random
from collections.abc import Iterable
from datetime import date, timedelta
from decimal import ROUND_HALF_UP, Decimal
from typing import Any

from sqlalchemy import (
    Column,
    Date,
    Engine,
    ForeignKey,
    Integer,
    MetaData,
    Numeric,
    String,
    Table,
    create_engine,
    inspect,
    text,
)

START = date(2024, 1, 1)
END = date(2025, 12, 31)
SEED = 20240101

metadata = MetaData()

customers = Table(
    "customers",
    metadata,
    Column("customer_id", Integer, primary_key=True),
    Column("first_name", String(40), nullable=False),
    Column("last_name", String(40), nullable=False),
    Column("email", String(120), nullable=False),
    Column("city", String(60), nullable=False),
    Column("state", String(60), nullable=False),
    Column("region", String(20), nullable=False),
    Column("segment", String(30), nullable=False),
    Column("acquisition_channel", String(30), nullable=False),
    Column("signup_date", Date, nullable=False),
)
products = Table(
    "products",
    metadata,
    Column("product_id", Integer, primary_key=True),
    Column("product_name", String(120), nullable=False),
    Column("category", String(40), nullable=False),
    Column("subcategory", String(40), nullable=False),
    Column("brand", String(40), nullable=False),
    Column("unit_price", Numeric(10, 2), nullable=False),
    Column("unit_cost", Numeric(10, 2), nullable=False),
    Column("launch_date", Date, nullable=False),
)
orders = Table(
    "orders",
    metadata,
    Column("order_id", Integer, primary_key=True),
    Column("customer_id", Integer, ForeignKey("customers.customer_id"), nullable=False, index=True),
    Column("order_date", Date, nullable=False, index=True),
    Column("status", String(20), nullable=False),
    Column("sales_channel", String(20), nullable=False),
)
order_items = Table(
    "order_items",
    metadata,
    Column("order_item_id", Integer, primary_key=True),
    Column("order_id", Integer, ForeignKey("orders.order_id"), nullable=False, index=True),
    Column("product_id", Integer, ForeignKey("products.product_id"), nullable=False, index=True),
    Column("quantity", Integer, nullable=False),
    Column("unit_price", Numeric(10, 2), nullable=False),
    Column("discount_pct", Numeric(5, 2), nullable=False),
    Column("line_total", Numeric(12, 2), nullable=False),
)
payments = Table(
    "payments",
    metadata,
    Column("payment_id", Integer, primary_key=True),
    Column("order_id", Integer, ForeignKey("orders.order_id"), nullable=False, index=True),
    Column("payment_date", Date, nullable=False),
    Column("payment_method", String(20), nullable=False),
    Column("amount", Numeric(12, 2), nullable=False),
    Column("payment_status", String(20), nullable=False),
)

# (city, state, region, relative market size)
CITIES = [
    ("Bengaluru", "Karnataka", "South", 10.0),
    ("Mumbai", "Maharashtra", "West", 9.5),
    ("Delhi", "Delhi", "North", 9.0),
    ("Hyderabad", "Telangana", "South", 8.6),
    ("Chennai", "Tamil Nadu", "South", 6.8),
    ("Pune", "Maharashtra", "West", 6.2),
    ("Kolkata", "West Bengal", "East", 5.4),
    ("Ahmedabad", "Gujarat", "West", 4.6),
    ("Noida", "Uttar Pradesh", "North", 3.6),
    ("Jaipur", "Rajasthan", "North", 3.1),
    ("Kochi", "Kerala", "South", 2.7),
    ("Lucknow", "Uttar Pradesh", "North", 2.6),
    ("Chandigarh", "Chandigarh", "North", 2.3),
    ("Indore", "Madhya Pradesh", "West", 2.2),
    ("Coimbatore", "Tamil Nadu", "South", 2.1),
    ("Surat", "Gujarat", "West", 2.0),
    ("Visakhapatnam", "Andhra Pradesh", "South", 1.8),
    ("Nagpur", "Maharashtra", "West", 1.7),
    ("Bhubaneswar", "Odisha", "East", 1.5),
    ("Thiruvananthapuram", "Kerala", "South", 1.4),
    ("Vadodara", "Gujarat", "West", 1.3),
    ("Guwahati", "Assam", "East", 1.2),
    ("Bhopal", "Madhya Pradesh", "West", 1.1),
    ("Mysuru", "Karnataka", "South", 1.0),
]

SEGMENTS = [("Consumer", 0.64), ("Small Business", 0.24), ("Corporate", 0.12)]
ACQUISITION = [
    ("Organic Search", 0.30),
    ("Paid Social", 0.22),
    ("Referral", 0.14),
    ("Email", 0.10),
    ("Marketplace", 0.14),
    ("Offline Event", 0.10),
]

# category -> (subcategories, brands, (median price, spread), yoy growth, return rate, festive boost)
CATEGORIES: dict[str, tuple[list[str], list[str], tuple[float, float], float, float, float]] = {
    "Electronics": (
        ["Smartphones", "Laptops", "Audio", "Wearables", "Accessories"],
        ["Voltix", "Nimbus", "Kairo", "Auralis"],
        (5200, 0.85),
        0.34,
        0.04,
        1.55,
    ),
    "Home & Kitchen": (
        ["Cookware", "Appliances", "Decor", "Storage"],
        ["Hearthly", "CasaNova", "Brewden"],
        (2200, 0.7),
        0.28,
        0.03,
        1.45,
    ),
    "Fashion": (
        ["Men's Apparel", "Women's Apparel", "Footwear", "Bags"],
        ["Loomstreet", "Tatva", "Urban Kite"],
        (1400, 0.55),
        0.22,
        0.11,
        1.50,
    ),
    "Beauty & Personal Care": (
        ["Skincare", "Haircare", "Grooming", "Fragrance"],
        ["Glowleaf", "Mira & Co", "Ayuveda"],
        (650, 0.5),
        0.41,
        0.02,
        1.20,
    ),
    "Sports & Fitness": (
        ["Gym Equipment", "Yoga", "Cycling", "Outdoor"],
        ["Stridex", "Peakform"],
        (2600, 0.8),
        0.18,
        0.05,
        1.05,
    ),
    "Books & Stationery": (
        ["Fiction", "Non-fiction", "Notebooks", "Art Supplies"],
        ["Inkwell", "Papercraft"],
        (450, 0.45),
        0.06,
        0.02,
        1.00,
    ),
}

PRODUCT_NOUNS = {
    "Smartphones": ["Phone X{n}", "Phone Lite {n}", "Phone Pro {n}"],
    "Laptops": ["Book Air {n}", "Book Pro {n}", "Workstation {n}"],
    "Audio": ["Buds {n}", "Headphones H{n}", "Soundbar S{n}"],
    "Wearables": ["Watch {n}", "Fit Band {n}"],
    "Accessories": ["Power Bank {n}0W", "Fast Charger {n}", "USB-C Hub {n}"],
    "Cookware": ["Tri-ply Kadai {n}", "Non-stick Tawa {n}", "Pressure Cooker {n}L"],
    "Appliances": ["Air Fryer {n}", "Mixer Grinder {n}", "Induction Cooktop {n}"],
    "Decor": ["Brass Diya Set {n}", "Wall Art {n}", "Cushion Covers {n}"],
    "Storage": ["Modular Rack {n}", "Airtight Jars {n}"],
    "Men's Apparel": ["Linen Shirt {n}", "Chinos {n}", "Kurta {n}"],
    "Women's Apparel": ["Cotton Kurti {n}", "Silk Saree {n}", "Denim Jacket {n}"],
    "Footwear": ["Running Shoes {n}", "Kolhapuri {n}", "Sneakers {n}"],
    "Bags": ["Laptop Backpack {n}", "Tote {n}"],
    "Skincare": ["Vitamin C Serum {n}", "Sunscreen SPF{n}0", "Face Wash {n}"],
    "Haircare": ["Onion Hair Oil {n}", "Shampoo {n}"],
    "Grooming": ["Beard Trimmer {n}", "Shaving Kit {n}"],
    "Fragrance": ["Eau de Parfum {n}", "Attar {n}"],
    "Gym Equipment": ["Adjustable Dumbbells {n}", "Resistance Bands {n}"],
    "Yoga": ["Yoga Mat {n}mm", "Yoga Block Set {n}"],
    "Cycling": ["City Bike {n}", "Cycling Helmet {n}"],
    "Outdoor": ["Trek Backpack {n}0L", "Camping Tent {n}P"],
    "Fiction": ["Novel Collection Vol {n}", "Mystery Box Set {n}"],
    "Non-fiction": ["Business Classics {n}", "Personal Finance {n}"],
    "Notebooks": ["Ruled Notebook Pack {n}", "Dot Grid Journal {n}"],
    "Art Supplies": ["Watercolour Set {n}", "Sketch Pens {n}"],
}

FIRST_NAMES = [
    "Aarav",
    "Vivaan",
    "Aditya",
    "Arjun",
    "Sai",
    "Reyansh",
    "Krishna",
    "Ishaan",
    "Rohan",
    "Kabir",
    "Ananya",
    "Diya",
    "Aadhya",
    "Saanvi",
    "Priya",
    "Meera",
    "Kavya",
    "Nisha",
    "Riya",
    "Sneha",
    "Rahul",
    "Vikram",
    "Harsha",
    "Lakshmi",
    "Deepika",
    "Farhan",
    "Zoya",
    "Gurpreet",
    "Simran",
    "Tanvi",
    "Nikhil",
    "Pooja",
    "Siddharth",
    "Anjali",
]
LAST_NAMES = [
    "Sharma",
    "Reddy",
    "Iyer",
    "Nair",
    "Patel",
    "Gupta",
    "Singh",
    "Rao",
    "Menon",
    "Das",
    "Kulkarni",
    "Chatterjee",
    "Joshi",
    "Khan",
    "Mehta",
    "Pillai",
    "Verma",
    "Bose",
    "Naidu",
    "Shetty",
    "Agarwal",
    "Mishra",
    "Banerjee",
    "Kapoor",
]

MONTH_SEASONALITY = {
    1: 0.92,
    2: 0.84,
    3: 0.95,
    4: 0.90,
    5: 0.93,
    6: 0.88,
    7: 1.02,
    8: 1.06,
    9: 1.08,
    10: 1.42,
    11: 1.26,
    12: 1.14,
}
# Relative demand per category (how often items from it are picked), independent of price.
CATEGORY_DEMAND = {
    "Electronics": 0.55,
    "Home & Kitchen": 1.1,
    "Fashion": 1.7,
    "Beauty & Personal Care": 2.0,
    "Sports & Fitness": 0.8,
    "Books & Stationery": 1.1,
}
# Short sale events: (start, end, demand multiplier, discount range)
SALE_EVENTS = [
    (date(2024, 7, 15), date(2024, 7, 18), 1.7, (0.10, 0.30)),
    (date(2024, 10, 3), date(2024, 10, 10), 2.1, (0.15, 0.40)),
    (date(2024, 12, 24), date(2024, 12, 31), 1.4, (0.10, 0.25)),
    (date(2025, 7, 12), date(2025, 7, 15), 1.8, (0.10, 0.30)),
    (date(2025, 9, 23), date(2025, 10, 2), 2.2, (0.15, 0.40)),
    (date(2025, 12, 24), date(2025, 12, 31), 1.45, (0.10, 0.25)),
]


def _money(value: float) -> Decimal:
    return Decimal(str(value)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def _weighted(rng: random.Random, pairs: list[tuple[str, float]]) -> str:
    return rng.choices([p[0] for p in pairs], weights=[p[1] for p in pairs])[0]


def _round_price(value: float) -> float:
    """Retail-style price points: 499, 1299, 24999..."""
    if value < 1000:
        return max(99.0, math.floor(value / 50) * 50 + 49)
    if value < 10_000:
        return math.floor(value / 100) * 100 + 99
    return math.floor(value / 1000) * 1000 + 999


def generate(seed: int = SEED) -> dict[str, list[dict[str, Any]]]:
    rng = random.Random(seed)
    horizon = (END - START).days

    # -- products ---------------------------------------------------------------------------
    product_rows: list[dict[str, Any]] = []
    product_meta: list[dict[str, Any]] = []  # hidden generation attributes
    pid = 0
    for category, (subcats, brands, (median, spread), growth, ret, festive) in CATEGORIES.items():
        for sub in subcats:
            templates = PRODUCT_NOUNS[sub]
            for i in range(rng.randint(3, 5)):
                pid += 1
                brand = rng.choice(brands)
                name = f"{brand} {rng.choice(templates).format(n=rng.randint(2, 9))}"
                price = _round_price(median * math.exp(rng.gauss(0, spread)))
                margin = rng.uniform(0.18, 0.45)
                launch = START - timedelta(days=rng.randint(60, 900))
                trend = rng.gauss(0, 0.45)  # log-change in demand across the two years
                if i == 0 and rng.random() < 0.35:  # new launches that ramp up in 2025
                    launch = date(2025, rng.randint(2, 9), rng.randint(1, 28))
                    trend = abs(trend) + 0.4
                product_rows.append(
                    {
                        "product_id": pid,
                        "product_name": name,
                        "category": category,
                        "subcategory": sub,
                        "brand": brand,
                        "unit_price": _money(price),
                        "unit_cost": _money(price * (1 - margin)),
                        "launch_date": launch,
                    }
                )
                product_meta.append(
                    {
                        "id": pid,
                        "price": price,
                        "category": category,
                        "launch": launch,
                        "trend": trend,
                        "popularity": rng.paretovariate(1.3) * CATEGORY_DEMAND[category],
                        "growth": growth,
                        "return_rate": ret,
                        "festive": festive,
                    }
                )

    # -- customers --------------------------------------------------------------------------
    n_customers = 12000
    customer_rows: list[dict[str, Any]] = []
    customer_meta: list[dict[str, Any]] = []
    city_weights = [c[3] for c in CITIES]
    signup_start = date(2023, 6, 1)
    signup_span = (END - timedelta(days=20) - signup_start).days
    for cid in range(1, n_customers + 1):
        city, state, region, _ = rng.choices(CITIES, weights=city_weights)[0]
        first, last = rng.choice(FIRST_NAMES), rng.choice(LAST_NAMES)
        # Acquisition accelerates over time (sqrt skews signups later).
        signup = signup_start + timedelta(days=int(signup_span * math.sqrt(rng.random())))
        segment = _weighted(rng, SEGMENTS)
        customer_rows.append(
            {
                "customer_id": cid,
                "first_name": first,
                "last_name": last,
                "email": f"{first}.{last}{cid}@example.com".lower(),
                "city": city,
                "state": state,
                "region": region,
                "segment": segment,
                "acquisition_channel": _weighted(rng, ACQUISITION),
                "signup_date": signup,
            }
        )
        # Heavy tail: most customers buy rarely, a loyal core buys often.
        propensity = rng.lognormvariate(0, 1.1) * (1.6 if segment == "Corporate" else 1.0)
        customer_meta.append({"id": cid, "signup": signup, "propensity": propensity, "segment": segment})
    customer_meta.sort(key=lambda c: c["signup"])

    # -- orders, items, payments ------------------------------------------------------------
    order_rows: list[dict[str, Any]] = []
    item_rows: list[dict[str, Any]] = []
    payment_rows: list[dict[str, Any]] = []
    oid = iid = pay_id = 0
    # First purchases come from customers who signed up but have not bought yet; repeat
    # purchases come from existing buyers weighted by their (heavy-tailed) propensity.
    prospects: list[dict[str, Any]] = []
    buyers: list[dict[str, Any]] = []
    buyer_weights: list[float] = []
    next_customer = 0

    for day_idx in range(horizon + 1):
        day = START + timedelta(days=day_idx)
        t = day_idx / horizon  # 0 → 1 across the two years
        while next_customer < len(customer_meta) and customer_meta[next_customer]["signup"] <= day:
            prospects.append(customer_meta[next_customer])
            next_customer += 1
        if not prospects and not buyers:
            continue

        sale = next((s for s in SALE_EVENTS if s[0] <= day <= s[1]), None)
        demand = 16.0 * 1.28 ** (t * 2) * MONTH_SEASONALITY[day.month]
        demand *= 1.14 if day.weekday() >= 5 else 1.0
        demand *= sale[2] if sale else 1.0
        n_orders = max(0, int(rng.gauss(demand, math.sqrt(demand))))

        festive_season = day.month in (10, 11)
        # Product weights for the day: popularity × individual trend × category growth × festive.
        weights = []
        for p in product_meta:
            if p["launch"] > day:
                weights.append(0.0)
                continue
            w = p["popularity"] * math.exp(p["trend"] * (t - 0.5)) * (1 + p["growth"]) ** t
            if festive_season:
                w *= p["festive"]
            if p["category"] == "Sports & Fitness" and day.month == 1:
                w *= 1.6  # new-year resolutions
            weights.append(w)

        for _ in range(n_orders):
            if prospects and (not buyers or rng.random() < 0.55):
                customer = prospects.pop(rng.randrange(len(prospects)))
                buyers.append(customer)
                buyer_weights.append(customer["propensity"])
            else:
                customer = rng.choices(buyers, weights=buyer_weights)[0]
            oid += 1
            channel = _weighted(
                rng, [("mobile_app", 0.42 + 0.12 * t), ("web", 0.40 - 0.10 * t), ("marketplace", 0.18 - 0.02 * t)]
            )
            n_items = rng.choices([1, 2, 3, 4, 5], weights=[58, 25, 10, 5, 2])[0]
            chosen = rng.choices(product_meta, weights=weights, k=n_items)
            order_total = 0.0
            max_return_rate = 0.0
            for p in {p["id"]: p for p in chosen}.values():
                iid += 1
                qty = rng.choices([1, 2, 3, 4], weights=[80, 13, 5, 2])[0]
                if customer["segment"] == "Corporate" and p["price"] < 5000:
                    qty += rng.choice([0, 2, 5, 10])
                price = p["price"] * (1.04 if day.year == 2025 else 1.0)  # annual price revision
                if sale:
                    discount = round(rng.uniform(*sale[3]), 2)
                elif rng.random() < 0.22:
                    discount = round(rng.uniform(0.05, 0.12), 2)
                else:
                    discount = 0.0
                line = qty * price * (1 - discount)
                order_total += line
                max_return_rate = max(max_return_rate, p["return_rate"])
                item_rows.append(
                    {
                        "order_item_id": iid,
                        "order_id": oid,
                        "product_id": p["id"],
                        "quantity": qty,
                        "unit_price": _money(price),
                        "discount_pct": _money(discount * 100),
                        "line_total": _money(line),
                    }
                )

            days_before_end = (END - day).days
            r = rng.random()
            if days_before_end < 6:
                status = "shipped" if r > 0.05 else "cancelled"
            elif r < 0.045:
                status = "cancelled"
            elif r < 0.045 + max_return_rate:
                status = "returned"
            else:
                status = "delivered"
            order_rows.append(
                {
                    "order_id": oid,
                    "customer_id": customer["id"],
                    "order_date": day,
                    "status": status,
                    "sales_channel": channel,
                }
            )

            method = _weighted(
                rng,
                [
                    ("UPI", 0.36 + 0.14 * t),
                    ("credit_card", 0.20),
                    ("debit_card", 0.12),
                    ("net_banking", 0.06),
                    ("wallet", 0.06),
                    ("cash_on_delivery", 0.20 - 0.12 * t),
                ],
            )
            if status == "cancelled" and method == "cash_on_delivery":
                continue  # nothing was ever paid
            pay_id += 1
            pay_status = {"cancelled": "refunded", "returned": "refunded"}.get(status, "captured")
            pay_date = day + timedelta(days=rng.randint(2, 6) if method == "cash_on_delivery" else 0)
            payment_rows.append(
                {
                    "payment_id": pay_id,
                    "order_id": oid,
                    "payment_date": min(pay_date, END),
                    "payment_method": method,
                    "amount": _money(order_total),
                    "payment_status": pay_status,
                }
            )

    return {
        "customers": customer_rows,
        "products": product_rows,
        "orders": order_rows,
        "order_items": item_rows,
        "payments": payment_rows,
    }


def _chunks(rows: list[dict[str, Any]], size: int = 5000) -> Iterable[list[dict[str, Any]]]:
    for i in range(0, len(rows), size):
        yield rows[i : i + size]


def is_seeded(engine: Engine) -> bool:
    return inspect(engine).has_table("orders")


def seed(url: str, *, if_empty: bool = True) -> dict[str, int]:
    """Create and populate the demo tables. Returns row counts per table."""
    engine = create_engine(url)
    try:
        if if_empty and is_seeded(engine):
            return {}
        metadata.drop_all(engine)
        metadata.create_all(engine)
        data = generate()
        with engine.begin() as conn:
            for tbl in metadata.sorted_tables:
                for chunk in _chunks(data[tbl.name]):
                    conn.execute(tbl.insert(), chunk)
        if engine.dialect.name == "postgresql":
            with engine.connect() as conn:
                conn.execution_options(isolation_level="AUTOCOMMIT").execute(text("ANALYZE"))
        return {name: len(rows) for name, rows in data.items()}
    finally:
        engine.dispose()
