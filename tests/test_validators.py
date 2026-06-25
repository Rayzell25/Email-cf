from app.utils.validators import (
    MAX_LOCAL_PART_LENGTH,
    normalize_local_part,
    normalize_name,
    validate_local_part,
)


def test_normalize_name_case_insensitive():
    assert normalize_name("CasterBington") == "casterbington"
    assert normalize_name("CASTERBINGTON") == "casterbington"
    assert normalize_name("caster.bington") == "casterbington"


def test_normalize_local_part_lowercases():
    assert normalize_local_part(" Support ") == "support"


def test_valid_simple_names():
    for name in ("support", "admin.store", "order-2026", "akun_backup"):
        result = validate_local_part(name)
        assert result.ok, name
        assert result.value == name


def test_uppercase_is_lowercased():
    result = validate_local_part("Support")
    assert result.ok
    assert result.value == "support"


def test_invalid_names():
    invalids = [
        "support@example.com",  # has @
        "nama email",            # space
        "admin#",                # illegal char
        "@email",                # @ + leading
        "",                      # empty
        ".support",              # leading dot
        "support-",              # trailing dash
        "a..b",                  # double dot
    ]
    for name in invalids:
        assert not validate_local_part(name).ok, name


def test_too_long():
    result = validate_local_part("a" * (MAX_LOCAL_PART_LENGTH + 1))
    assert not result.ok
