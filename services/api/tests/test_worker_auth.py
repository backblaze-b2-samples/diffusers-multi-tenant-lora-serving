from app.config import settings

HELLO = {"worker_id": "w1", "device": "cpu", "dtype": "float32",
         "base_model": "stabilityai/stable-diffusion-xl-base-1.0"}


async def test_worker_routes_open_without_token(client, monkeypatch):
    monkeypatch.setattr(settings, "worker_token", "")
    assert (await client.post("/worker/register", json=HELLO)).status_code == 200


async def test_worker_routes_require_token_when_set(client, monkeypatch):
    monkeypatch.setattr(settings, "worker_token", "s3cret-token")
    r = await client.post("/worker/register", json=HELLO)
    assert r.status_code == 401 and r.json()["code"] == "worker_unauthorized"
    r = await client.post("/worker/register", json=HELLO,
                          headers={"Authorization": "Bearer wrong"})
    assert r.status_code == 401
    r = await client.post("/worker/register", json=HELLO,
                          headers={"Authorization": "Bearer s3cret-token"})
    assert r.status_code == 200


async def test_worker_routes_are_not_rate_limited(client, monkeypatch):
    monkeypatch.setattr(settings, "rate_limit_write_per_minute", 2)
    for _ in range(5):
        assert (await client.post("/worker/register", json=HELLO)).status_code == 200
