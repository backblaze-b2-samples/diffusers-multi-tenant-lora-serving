import pytest

from app.types.identifiers import is_name, is_version, parse_adapter_ref


@pytest.mark.parametrize("name", ["acme", "pixel-art", "a1b", "x" * 40])
def test_valid_names(name):
    assert is_name(name)


@pytest.mark.parametrize(
    "name", ["", "ab", "-acme", "acme-", "Acme", "ac/me", "ac..me", "ac me", "x" * 41, "../x"]
)
def test_invalid_names(name):
    assert not is_name(name)


@pytest.mark.parametrize("v", ["v1", "v1.2", "v10.0.3"])
def test_valid_versions(v):
    assert is_version(v)


@pytest.mark.parametrize("v", ["1", "v", "v1.2.3.4", "v1/..", "V1", "v1-beta"])
def test_invalid_versions(v):
    assert not is_version(v)


def test_parse_adapter_ref_shapes():
    assert parse_adapter_ref("pixel-art").owner is None
    r = parse_adapter_ref("globex/toy-face@v2")
    assert (r.owner, r.name, r.version) == ("globex", "toy-face", "v2")
    assert parse_adapter_ref("pixel-art@v1").version == "v1"


@pytest.mark.parametrize("ref", ["../acme/x", "acme/../x", "a/b/c", "pixel-art@latest", "Pixel"])
def test_parse_adapter_ref_rejects_bad_refs(ref):
    with pytest.raises(ValueError):
        parse_adapter_ref(ref)
