"""HTTP API smoke tests (requires fastapi in dev env)."""

import pytest

pytest.importorskip("fastapi")
from fastapi.testclient import TestClient

from copinance_os.interfaces.api.app import create_app


@pytest.fixture
def client() -> TestClient:
    return TestClient(create_app())


@pytest.mark.unit
def test_health(client: TestClient) -> None:
    r = client.get("/health")
    assert r.status_code == 200
    assert r.json() == {"status": "ok"}


@pytest.mark.unit
def test_backtest_endpoint(client: TestClient) -> None:
    payload = {
        "closes": [100.0, 110.0, 121.0],
        "weights": [1.0, 1.0, 1.0],
        "initial_cash": 1000.0,
        "commission_bps": 0,
        "slippage_bps": 0,
    }
    r = client.post("/v1/backtest/simple-long-only", json=payload)
    assert r.status_code == 200
    data = r.json()
    assert "equity_curve" in data
    assert data["equity_curve"][-1] == pytest.approx(1000.0 * 1.1 * 1.1)


@pytest.mark.unit
def test_backtest_mismatched_lengths(client: TestClient) -> None:
    r = client.post(
        "/v1/backtest/simple-long-only",
        json={"closes": [1.0, 2.0], "weights": [1.0]},
    )
    assert r.status_code == 422
