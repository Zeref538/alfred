import webbrowser
from urllib.parse import quote_plus

from .. import schemas


def open_url(args: schemas.OpenUrl) -> None:
    webbrowser.open(args.url)


def web_search(args: schemas.WebSearch) -> None:
    from .. import settings
    webbrowser.open(settings.get("search") + quote_plus(args.query))
