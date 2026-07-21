import webbrowser
from urllib.parse import quote_plus

from .. import schemas


def open_url(args: schemas.OpenUrl) -> None:
    webbrowser.open(args.url)


def web_search(args: schemas.WebSearch) -> None:
    from .. import settings
    webbrowser.open(settings.get("search") + quote_plus(args.query))


def play_media(args: schemas.PlayMedia) -> None:
    """Open a media page and set it going. The extension does the pressing —
    Alfred has no hands in a page. Without the bridge this degrades to simply
    opening the page, which is what he could always do."""
    from .. import tabs
    try:
        tabs.request_play(args.url)
    except RuntimeError:
        webbrowser.open(args.url)


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
