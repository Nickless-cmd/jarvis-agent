import types

from jarvis.server import is_admin_user


def test_is_admin_user_truthy_variants():
    assert is_admin_user({"is_admin": True})
    assert is_admin_user({"is_admin": 1})
    assert is_admin_user({"is_admin": "1"})
    assert is_admin_user({"role": "admin"})


def test_is_admin_user_false_variants():
    assert not is_admin_user({})
    assert not is_admin_user({"is_admin": 0})
    assert not is_admin_user({"is_admin": "no"})
    assert not is_admin_user(None)
