"""A discreet presence in the system tray. Requires the [ui] extra."""


def build_icon():
    import pystray
    from PIL import Image, ImageDraw

    from .summon import open_palette

    image = Image.new("RGB", (64, 64), "#1b1b2f")
    draw = ImageDraw.Draw(image)
    draw.ellipse((8, 8, 56, 56), outline="#e0c060", width=5)
    draw.text((25, 20), "C", fill="#e0c060")

    return pystray.Icon(
        "alfred", image, "Alfred — at your service",
        menu=pystray.Menu(
            pystray.MenuItem("Summon the palette", lambda: open_palette()),
            pystray.MenuItem("Dismiss", lambda icon: icon.stop()),
        ),
    )


def main() -> int:
    try:
        icon = build_icon()
    except ImportError:
        print("The tray requires the [ui] extra, sir: pip install -e .[ui]")
        return 1
    icon.run()
    return 0
