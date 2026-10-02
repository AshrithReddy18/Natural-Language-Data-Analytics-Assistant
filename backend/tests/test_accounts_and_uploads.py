import io
from datetime import date, datetime

import pytest
from fastapi.testclient import TestClient
from openpyxl import Workbook

from app.core.auth import create_session_token, hash_password, read_session_token, verify_password
from app.datasources.uploads import parse_files
from app.main import app

SALES_CSV = (
    b"Order ID,Order Date,Region,Amount (INR),PIN code\n"
    b'1,03/04/2025,North,"1,250.50",011001\n'
    b"2,15/04/2025,South,980,560001\n"
    b"3,02/05/2025,North,,110001\n"
)


def _xlsx() -> bytes:
    wb = Workbook()
    ws = wb.active
    ws.title = "Targets"
    ws.append(["Region", "Target", "Starts"])
    ws.append(["North", 2000, datetime(2025, 4, 1)])
    ws.append(["South", 1500, datetime(2025, 4, 1)])
    wb.create_sheet("Empty")
    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()


def _upload(client: TestClient, *files: tuple[str, bytes], name: str = "My sales") -> dict:
    res = client.post(
        "/api/datasets/upload",
        data={"name": name, "currency": "inr"},
        files=[("files", (fname, content, "application/octet-stream")) for fname, content in files],
    )
    assert res.status_code == 201, res.text
    return res.json()


# -- accounts --------------------------------------------------------------------------------


def test_password_hashing_round_trip() -> None:
    stored = hash_password("s3cret-pass")
    assert "s3cret-pass" not in stored
    assert verify_password("s3cret-pass", stored)
    assert not verify_password("wrong-pass", stored)
    assert not verify_password("s3cret-pass", "garbage")


def test_session_tokens_are_signed_and_expire() -> None:
    token = create_session_token("abc")
    assert read_session_token(token) == "abc"
    _, expires, sig = token.split(".")
    assert read_session_token(f"other.{expires}.{sig}") is None
    assert read_session_token(create_session_token("abc", ttl=-1)) is None
    assert read_session_token("nonsense") is None


def test_endpoints_require_sign_in(client: TestClient) -> None:
    anon = TestClient(app)
    for method, path in [("get", "/api/datasets"), ("get", "/api/conversations"), ("get", "/api/query/history")]:
        res = getattr(anon, method)(path)
        assert res.status_code == 401
        assert res.json()["error"]["code"] == "unauthorized"
    assert anon.get("/api/health").status_code == 200


def test_signup_login_logout() -> None:
    c = TestClient(app)
    creds = {"email": "  New.User@Example.com ", "password": "long-enough"}
    assert c.post("/api/auth/signup", json=creds).json()["email"] == "new.user@example.com"
    assert c.post("/api/auth/signup", json=creds).status_code == 409
    assert c.get("/api/auth/me").status_code == 200

    assert c.post("/api/auth/logout").status_code == 204
    assert c.get("/api/auth/me").status_code == 401

    bad = c.post("/api/auth/login", json={**creds, "password": "wrong-password"})
    assert bad.status_code == 401
    assert bad.json()["error"]["message"] == "Incorrect email or password."
    # A short password at sign-in is just wrong, not a validation error.
    assert c.post("/api/auth/login", json={**creds, "password": "x"}).status_code == 401
    assert c.post("/api/auth/login", json=creds).status_code == 200
    assert c.get("/api/auth/me").json()["email"] == "new.user@example.com"


@pytest.mark.parametrize(
    "body", [{"email": "not-an-email", "password": "long-enough"}, {"email": "a@b.co", "password": "short"}]
)
def test_signup_validation(body: dict) -> None:
    assert TestClient(app).post("/api/auth/signup", json=body).status_code == 422


def test_users_cannot_see_each_others_data(client: TestClient, other_client: TestClient, demo_id: str) -> None:
    mine = _upload(client, ("private.csv", SALES_CSV), name="Private")
    convo = client.post("/api/chat", json={"data_source_id": demo_id, "question": "Revenue?"}).json()
    client.post("/api/query/execute", json={"data_source_id": mine["id"], "sql": "SELECT 1"})

    # Both see the shared demo; only the owner sees the upload, its conversations and history.
    other_ids = {s["id"] for s in other_client.get("/api/datasets").json()}
    assert demo_id in other_ids and mine["id"] not in other_ids
    assert other_client.get(f"/api/datasets/{mine['id']}").status_code == 404
    assert other_client.get(f"/api/datasets/{mine['id']}/schema").status_code == 404
    assert other_client.delete(f"/api/datasets/{mine['id']}").status_code == 404
    sql = {"data_source_id": mine["id"], "sql": "SELECT * FROM private"}
    assert other_client.post("/api/query/execute", json=sql).status_code == 404
    assert other_client.get("/api/conversations").json() == []
    assert other_client.get(f"/api/conversations/{convo['conversation_id']}").status_code == 404
    assert other_client.delete(f"/api/conversations/{convo['conversation_id']}").status_code == 404
    follow_up = {"data_source_id": demo_id, "question": "And?", "conversation_id": convo["conversation_id"]}
    assert other_client.post("/api/chat", json=follow_up).status_code == 404
    assert other_client.get("/api/query/history").json() == []

    assert any(c["id"] == convo["conversation_id"] for c in client.get("/api/conversations").json())
    client.delete(f"/api/datasets/{mine['id']}")


# -- uploads ---------------------------------------------------------------------------------


def test_upload_infers_names_and_types() -> None:
    [table] = parse_files([("Q2 Sales.csv", SALES_CSV)])
    assert table.name == "q2_sales"
    assert table.columns == ["order_id", "order_date", "region", "amount_inr", "pin_code"]


def test_upload_csv_and_excel_then_query(client: TestClient) -> None:
    source = _upload(client, ("Q2 Sales.csv", SALES_CSV), ("targets.xlsx", _xlsx()))
    assert source["kind"] == "upload"
    assert source["status"] == "connected"
    assert source["table_count"] == 2
    assert source["currency"] == "INR"
    assert "Q2 Sales.csv" in source["display_url"]

    schema = client.get(f"/api/datasets/{source['id']}/schema").json()
    types = {t["name"]: {c["name"]: c["type"] for c in t["columns"]} for t in schema["tables"]}
    assert types["q2_sales"] == {
        "order_id": "INTEGER",
        "order_date": "DATE",
        "region": "TEXT",
        "amount_inr": "REAL",
        "pin_code": "TEXT",  # leading zeros are kept
    }
    assert types["targets"] == {"region": "TEXT", "target": "INTEGER", "starts": "DATE"}

    sql = (
        "SELECT s.region, SUM(s.amount_inr) AS revenue, MAX(t.target) AS target "
        "FROM q2_sales s JOIN targets t ON t.region = s.region GROUP BY s.region ORDER BY s.region"
    )
    body = client.post("/api/query/execute", json={"data_source_id": source["id"], "sql": sql}).json()
    assert body["status"] == "success", body
    assert body["result"]["rows"] == [["North", 1250.5, 2000], ["South", 980.0, 1500]]

    dates = client.post(
        "/api/query/execute",
        json={"data_source_id": source["id"], "sql": "SELECT order_date, pin_code FROM q2_sales ORDER BY order_id"},
    ).json()
    assert dates["result"]["rows"][0] == [date(2025, 4, 3).isoformat(), "011001"]

    assert client.delete(f"/api/datasets/{source['id']}").status_code == 204
    assert client.get(f"/api/datasets/{source['id']}").status_code == 404


def test_uploaded_data_survives_a_fresh_server_disk(client: TestClient) -> None:
    """Serverless instances start with an empty disk: the stored copy is written back on demand."""
    from app.datasources.registry import registry
    from app.services import schema_service
    from app.services.datasource_service import DATA_DIR

    source = _upload(client, ("sales.csv", SALES_CSV))
    registry.evict(source["id"])
    schema_service.invalidate(source["id"])
    (DATA_DIR / "uploads" / f"{source['id']}.db").unlink()

    body = client.post(
        "/api/query/execute", json={"data_source_id": source["id"], "sql": "SELECT COUNT(*) AS n FROM sales"}
    ).json()
    assert body["result"]["rows"] == [[3]]
    client.delete(f"/api/datasets/{source['id']}")


@pytest.mark.parametrize(
    ("filename", "content", "fragment"),
    [
        ("data.json", b"{}", "isn't a supported file"),
        ("old.xls", b"\xd0\xcf", "Save it as .xlsx"),
        ("empty.csv", b"\n\n", "no data"),
        ("broken.xlsx", b"not a zip", "could not be read"),
    ],
)
def test_upload_rejects_bad_files(client: TestClient, filename: str, content: bytes, fragment: str) -> None:
    res = client.post("/api/datasets/upload", files={"files": (filename, content, "application/octet-stream")})
    assert res.status_code == 400
    assert fragment in res.json()["error"]["message"]


def test_upload_size_limit(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    from app.core.config import get_settings

    monkeypatch.setattr(get_settings(), "max_upload_mb", 0.001)
    res = client.post("/api/datasets/upload", files={"files": ("big.csv", b"a\n" + b"1\n" * 2000, "text/csv")})
    assert res.status_code == 400
    assert "limited to" in res.json()["error"]["message"]
