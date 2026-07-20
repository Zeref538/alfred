"""The bell pull. Registration is exercised for real when the session allows it."""

import ctypes

import pytest

from alfred import summon


def _hotkeys_available() -> bool:
    # CI service sessions may refuse global hotkeys; skip rather than lie.
    if summon.user32.RegisterHotKey(None, 999, 0x0002 | 0x0001, 0x51):  # Ctrl+Alt+Q probe
        summon.user32.UnregisterHotKey(None, 999)
        return True
    return False


@pytest.mark.skipif(not _hotkeys_available(), reason="session refuses global hotkeys")
def test_register_and_release_the_bell():
    summon.register()
    try:
        # a second claim on the same combination must fail while we hold it
        assert not summon.user32.RegisterHotKey(
            None, 2, 0x0002 | 0x0001 | 0x4000, ord("C"))
    finally:
        summon.unregister()
    # and succeed once released
    summon.register()
    summon.unregister()


def test_check_only_registers_and_returns(capsys):
    if not _hotkeys_available():
        pytest.skip("session refuses global hotkeys")
    summon.summon_loop(check_only=True)
    assert "registered and released" in capsys.readouterr().out


def test_parse_hotkey_default_and_digit():
    mods, vk = summon.parse_hotkey("ctrl+alt+c")
    assert mods == (summon._MOD_CONTROL | summon._MOD_ALT | summon._MOD_NOREPEAT)
    assert vk == ord("C")
    mods, vk = summon.parse_hotkey("ctrl+shift+1")
    assert mods == (summon._MOD_CONTROL | summon._MOD_SHIFT | summon._MOD_NOREPEAT)
    assert vk == ord("1")


@pytest.mark.parametrize("bad", ["", "ctrl+alt", "ctrl+alt+esc", "flurb+c"])
def test_parse_hotkey_rejects_bad_combos(bad):
    with pytest.raises(ValueError):
        summon.parse_hotkey(bad)
