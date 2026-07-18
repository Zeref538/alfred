import os
import webbrowser
from urllib.parse import quote_plus

from .. import schemas

SEARCH_URL = os.environ.get("ALFRED_SEARCH", "https://www.google.com/search?q=")


def open_url(args: schemas.OpenUrl) -> None:
    webbrowser.open(args.url)


def web_search(args: schemas.WebSearch) -> None:
    webbrowser.open(SEARCH_URL + quote_plus(args.query))
