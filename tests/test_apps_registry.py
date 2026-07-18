"""App registration: the scan, the loader, and the allowlist boundary."""

from alfred.adapters.apps import scan_start_menu
from alfred.config import _BUILTIN_APPS, load_registered_apps


def test_scan_collects_shortcuts_and_skips_noise(tmp_path):
    (tmp_path / "Steam.lnk").touch()
    (tmp_path / "sub").mkdir()
    (tmp_path / "sub" / "VLC Media Player.lnk").touch()
    (tmp_path / "Uninstall Steam.lnk").touch()
    (tmp_path / "notes.txt").touch()
    apps = scan_start_menu(roots=[tmp_path])
    assert apps.keys() == {"steam", "vlc media player"}
    assert apps["steam"].endswith("Steam.lnk")


def test_missing_apps_file_falls_back_to_builtins(tmp_path):
    assert load_registered_apps(tmp_path / "nope.yaml") == _BUILTIN_APPS


def test_apps_file_extends_builtins_lowercased(tmp_path):
    path = tmp_path / "apps.yaml"
    path.write_text("Spotify: C:\\links\\Spotify.lnk\n", encoding="utf-8")
    apps = load_registered_apps(path)
    assert apps["spotify"].endswith("Spotify.lnk")
    assert apps["notepad"] == "notepad.exe"  # builtins survive


def test_corrupt_apps_file_falls_back(tmp_path):
    path = tmp_path / "apps.yaml"
    path.write_text("{{{not yaml", encoding="utf-8")
    assert load_registered_apps(path) == _BUILTIN_APPS
