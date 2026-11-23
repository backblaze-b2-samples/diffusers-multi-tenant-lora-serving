from app.repo import b2_client


def test_s3_client_carries_the_sample_user_agent(monkeypatch):
    captured = {}

    def fake_client(*_args, **kwargs):
        captured.update(kwargs)
        return object()

    monkeypatch.setattr(b2_client.boto3, "client", fake_client)
    b2_client.get_s3_client.cache_clear()
    b2_client.get_s3_client()

    config = captured["config"]
    assert config.user_agent_extra == "b2ai-diffusers-lora-weights-hub"
    assert config.signature_version == "s3v4"
    assert captured["endpoint_url"].startswith("https://s3.")
