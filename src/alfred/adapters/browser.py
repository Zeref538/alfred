import webbrowser
from urllib.parse import quote_plus

from .. import schemas


def open_url(args: schemas.OpenUrl) -> None:
    webbrowser.open(args.url)


def web_search(args: schemas.WebSearch) -> None:
    from .. import settings
    webbrowser.open(settings.get("search") + quote_plus(args.query))


def focus_tab(args: schemas.FocusTab) -> None:
    """Switch to an already-open tab. Alfred never reaches into the browser
    himself — he matches the spoken name against the last report locally, then
    asks the extension to do the switching."""
    from .. import tabs
    tab = tabs.VIEW.match(args.name)
    if tab is None:
        if not tabs.VIEW.fresh():
            raise RuntimeError(
                "I can't see your tabs, sir — the browser extension isn't "
                "connected (or has gone quiet)")
        raise RuntimeError(f"no open tab looks like '{args.name}', sir")
    tabs.request_focus(tab.id)
