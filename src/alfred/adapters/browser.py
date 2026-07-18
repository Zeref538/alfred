import webbrowser
from urllib.parse import quote_plus

from .. import schemas


def open_url(args: schemas.OpenUrl) -> None:
    webbrowser.open(args.url)


def web_search(args: schemas.WebSearch) -> None:
    webbrowser.open(f"https://duckduckgo.com/?q={quote_plus(args.query)}")
