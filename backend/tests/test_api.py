import json

import pytest
from fastapi.testclient import TestClient

from app.schemas.llm_outputs import InsightText
from tests.fakes import FakeProvider, plan

MONTHLY_SQL = (
    "SELECT strftime('%Y-%m', o.order_date) AS month, ROUND(SUM(oi.line_total), 2) AS revenue "
    "FROM orders o JOIN order_items oi ON oi.order_id = o.order_id "
    "WHERE o.order_date >= '2025-01-01' GROUP BY 1 ORDER BY 1"
)


@pytest.fixture
def fake_llm(monkeypatch: pytest.MonkeyPatch) -> FakeProvider:
    provider = FakeProvider(insight=InsightText(headline="Revenue peaked in 2025-10.", bullets=[]))
    monkeypatch.setattr("app.services.chat_service.get_llm_provider", lambda: provider)
    return provider


def test_health(client: TestClient) -> None:
    res = client.get("/api/health")
    assert res.status_code == 200
    body = res.json()
    assert body["database"] is True
    assert body["llm_configured"] is False
    assert res.headers["X-Request-ID"]


def test_request_id_is_echoed(client: TestClient) -> None:
    assert client.get("/api/health", headers={"X-Request-ID": "abc123"}).headers["X-Request-ID"] == "abc123"


def test_demo_dataset_is_registered(client: TestClient) -> None:
    sources = client.get("/api/datasets").json()
    demo = next(s for s in sources if s["is_demo"])
    assert demo["status"] == "connected"
    assert demo["table_count"] == 5
    assert "encrypted_url" not in demo


def test_schema_endpoint(client: TestClient, demo_id: str) -> None:
    body = client.get(f"/api/datasets/{demo_id}/schema").json()
    assert {t["name"] for t in body["tables"]} >= {"orders", "customers"}
    assert any(r["from_table"] == "orders" and r["to_table"] == "customers" for r in body["relationships"])


def test_unknown_dataset_is_404_with_error_envelope(client: TestClient) -> None:
    res = client.get("/api/datasets/nope/schema")
    assert res.status_code == 404
    assert res.json() == {"error": {"code": "not_found", "message": "Data source not found."}}


@pytest.mark.parametrize(
    ("url", "fragment"),
    [
        ("mysql://u:p@localhost/db", "Unsupported database type"),
        ("sqlite:///C:/Windows/system.db", "Upload your data"),
        ("not a url", "Invalid"),
    ],
)
def test_create_dataset_rejects_bad_urls(client: TestClient, url: str, fragment: str) -> None:
    res = client.post("/api/datasets", json={"name": "x", "url": url})
    assert res.status_code == 400
    assert fragment in res.json()["error"]["message"]


def test_create_dataset_with_unreachable_postgres(client: TestClient) -> None:
    res = client.post("/api/datasets", json={"name": "pg", "url": "postgresql://u:secret@127.0.0.1:1/db"})
    assert res.status_code == 400
    assert "secret" not in res.text


def test_shared_demo_dataset_cannot_be_changed(client: TestClient, demo_id: str) -> None:
    assert client.delete(f"/api/datasets/{demo_id}").status_code == 403
    assert client.patch(f"/api/datasets/{demo_id}", json={"business_notes": "x"}).status_code == 403


def test_update_business_notes(client: TestClient) -> None:
    files = {"files": ("notes.csv", b"region,amount\nNorth,10\n", "text/csv")}
    source_id = client.post("/api/datasets/upload", files=files).json()["id"]
    res = client.patch(f"/api/datasets/{source_id}", json={"business_notes": "Amounts exclude tax."})
    assert res.json()["business_notes"] == "Amounts exclude tax."
    client.delete(f"/api/datasets/{source_id}")


def test_query_validate_and_execute(client: TestClient, demo_id: str) -> None:
    res = client.post("/api/query/validate", json={"data_source_id": demo_id, "sql": "SELECT city FROM customers"})
    assert res.json()["validation"]["ok"] is True

    res = client.post("/api/query/execute", json={"data_source_id": demo_id, "sql": MONTHLY_SQL})
    body = res.json()
    assert body["status"] == "success"
    assert body["chart"]["type"] == "line"
    assert body["result"]["row_count"] == 12
    assert body["insight"]["generated_by"] == "rules"


def test_query_execute_rejects_writes(client: TestClient, demo_id: str) -> None:
    body = client.post("/api/query/execute", json={"data_source_id": demo_id, "sql": "DELETE FROM orders"}).json()
    assert body["status"] == "error"
    assert body["error"]["code"] == "sql_invalid"


def test_request_validation_error_shape(client: TestClient) -> None:
    res = client.post("/api/query/execute", json={"sql": "SELECT 1"})
    assert res.status_code == 422
    assert res.json()["error"]["code"] == "invalid_request"


def test_chat_without_llm_returns_clear_error(client: TestClient, demo_id: str) -> None:
    body = client.post("/api/chat", json={"data_source_id": demo_id, "question": "Revenue by city?"}).json()
    analysis = body["assistant_message"]["analysis"]
    assert analysis["status"] == "error"
    assert analysis["error"]["code"] == "llm_not_configured"


def test_chat_conversation_flow(client: TestClient, demo_id: str, fake_llm: FakeProvider) -> None:
    fake_llm.plans = [plan(MONTHLY_SQL, title="Monthly revenue, 2025")]
    first = client.post("/api/chat", json={"data_source_id": demo_id, "question": "Show monthly revenue for 2025"})
    assert first.status_code == 200
    body = first.json()
    conversation_id = body["conversation_id"]
    analysis = body["assistant_message"]["analysis"]
    assert analysis["status"] == "success"
    assert analysis["chart"]["type"] == "line"
    assert analysis["query_run_id"]

    # Follow-up in the same conversation receives the previous SQL as context.
    fake_llm.plans = [plan(MONTHLY_SQL + " LIMIT 1")]
    follow = client.post(
        "/api/chat",
        json={"data_source_id": demo_id, "question": "Which month was highest?", "conversation_id": conversation_id},
    )
    assert follow.status_code == 200
    context = fake_llm.sql_calls[-1].messages
    assert context[0].content == "Show monthly revenue for 2025"
    assert "strftime" in context[1].content.lower()

    detail = client.get(f"/api/conversations/{conversation_id}").json()
    assert [m["role"] for m in detail["messages"]] == ["user", "assistant", "user", "assistant"]
    assert detail["title"] == "Show monthly revenue for 2025"
    assert any(c["id"] == conversation_id for c in client.get("/api/conversations").json())

    history = client.get("/api/query/history", params={"data_source_id": demo_id}).json()
    assert history[0]["question"] == "Which month was highest?"
    assert history[0]["status"] == "success"

    assert client.delete(f"/api/conversations/{conversation_id}").status_code == 204
    assert client.get(f"/api/conversations/{conversation_id}").status_code == 404


def test_chat_stream_emits_steps_then_result(client: TestClient, demo_id: str, fake_llm: FakeProvider) -> None:
    fake_llm.plans = [plan(MONTHLY_SQL)]
    with client.stream(
        "POST", "/api/chat/stream", json={"data_source_id": demo_id, "question": "Monthly revenue"}
    ) as res:
        assert res.headers["content-type"].startswith("application/x-ndjson")
        events = [json.loads(line) for line in res.iter_lines() if line]
    types = [e["type"] for e in events]
    assert types[0] == "conversation"
    assert types[-1] == "result"
    assert {"step"} == set(types[1:-1])
    assert events[-1]["data"]["assistant_message"]["analysis"]["status"] == "success"


def test_chat_stream_reports_missing_dataset(client: TestClient) -> None:
    with client.stream("POST", "/api/chat/stream", json={"data_source_id": "missing", "question": "x"}) as res:
        events = [json.loads(line) for line in res.iter_lines() if line]
    assert events == [{"type": "error", "code": "not_found", "message": "Data source not found."}]


def test_follow_up_uses_the_conversations_data_source(client: TestClient, demo_id: str, fake_llm: FakeProvider) -> None:
    files = {"files": ("other.csv", b"month,revenue\n2025-01,10\n", "text/csv")}
    other = client.post("/api/datasets/upload", data={"name": "Other"}, files=files)
    assert other.status_code == 201, other.text
    try:
        fake_llm.plans = [plan(MONTHLY_SQL), plan(MONTHLY_SQL)]
        first = client.post("/api/chat", json={"data_source_id": demo_id, "question": "Monthly revenue"}).json()
        conversation_id = first["conversation_id"]
        client.post(
            "/api/chat",
            json={
                "data_source_id": other.json()["id"],
                "question": "And the peak?",
                "conversation_id": conversation_id,
            },
        )
        runs = [r for r in client.get("/api/query/history").json() if r["conversation_id"] == conversation_id]
        assert {r["data_source_id"] for r in runs} == {demo_id}
    finally:
        client.delete(f"/api/datasets/{other.json()['id']}")


def test_unknown_conversation(client: TestClient, demo_id: str) -> None:
    res = client.post("/api/chat", json={"data_source_id": demo_id, "question": "x", "conversation_id": "nope"})
    assert res.status_code == 404
