#!/usr/bin/env python3

import sys
import requests
from PIL import Image
from io import BytesIO
from urllib.parse import urlparse, unquote
import subprocess

OUTPUT_FILE = "/tmp/cover_color.txt"


def persist_color(color):
    with open(OUTPUT_FILE, "w") as f:
        f.write(color)


def read_current_color():
    try:
        with open(OUTPUT_FILE, "r") as f:
            color = f.read().strip()
        return color if color.startswith("#") else None
    except OSError:
        return None


def normalize_art_url(url):
    if not url:
        return None

    if url.startswith("file://"):
        parsed = urlparse(url)
        path = unquote(parsed.path)
        if parsed.netloc and parsed.netloc != "localhost":
            return f"//{parsed.netloc}{path}"
        return path

    return url


def get_album_art():
    try:
        # get current playing URL from playerctl (MPRIS)
        result = subprocess.run(
            ["playerctl", "metadata", "mpris:artUrl"],
            capture_output=True,
            text=True,
            timeout=2
        )
        return normalize_art_url(result.stdout.strip())
    except Exception:
        return None


def get_dominant_color(image):
    image = image.convert("RGB").resize((50, 50))
    pixels = list(image.getdata())

    r = sum(p[0] for p in pixels) // len(pixels)
    g = sum(p[1] for p in pixels) // len(pixels)
    b = sum(p[2] for p in pixels) // len(pixels)

    return "#{:02x}{:02x}{:02x}".format(r, g, b)


def main():
    fallback_color = read_current_color() or "#ffffff"

    try:
        url = normalize_art_url(sys.argv[1]) if len(sys.argv) > 1 else get_album_art()

        if not url:
            color = fallback_color
        else:
            if url.startswith("/"):  # local file
                image = Image.open(url)
            else:
                response = requests.get(url, timeout=3)
                image = Image.open(BytesIO(response.content))

            color = get_dominant_color(image)

        persist_color(color)
        print(color)

    except Exception:
        # Keep the last good color to avoid flashing white during metadata handoff.
        persist_color(fallback_color)
        print(fallback_color)


if __name__ == "__main__":
    main()
