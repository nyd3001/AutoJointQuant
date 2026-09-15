"""Compute the horizontal gap of JoinQuant's scrambled-image captcha.

The program prints only ``GAP_X=<integer>``. It never opens a browser, moves a
pointer, or submits a captcha; the caller decides whether and when to perform
the browser-side validation.
"""

from __future__ import annotations

import argparse
import base64
import binascii
import io
import json
import re
import sys

import numpy as np
from PIL import Image
from scipy.signal import correlate2d

DATA_URL_PATTERN = re.compile(r"^data:image/[a-zA-Z0-9.+-]+;base64,([a-zA-Z0-9+/=\r\n]+)$")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--response", required=True)
    parser.add_argument("--piece", required=True)
    return parser.parse_args()


def decode_data_url(value: str) -> bytes:
    match = DATA_URL_PATTERN.fullmatch(value)
    if not match:
        raise ValueError("captcha image is not a base64 data URL")
    try:
        return base64.b64decode(match.group(1), validate=True)
    except (binascii.Error, ValueError) as exc:
        raise ValueError("captcha image is not a base64 data URL") from exc


def solve(response_path: str, piece_path: str) -> int:
    with open(response_path, "r", encoding="utf-8") as handle:
        payload = json.load(handle)

    data = payload.get("data") or {}
    points = data.get("point")
    bg_img = data.get("bgImg")
    if not isinstance(points, list) or len(points) != 66 or not bg_img:
        raise ValueError("unexpected captcha response format")

    with Image.open(io.BytesIO(decode_data_url(bg_img))) as image:
        background = image.convert("RGBA")
    with Image.open(piece_path) as image:
        piece = image.convert("RGB").resize((56, 56), Image.Resampling.LANCZOS)

    # JoinQuant returns 66 11x71 tiles: 33 columns x 2 rows.
    reconstructed = Image.new("RGBA", (363, 142))
    for index, point in enumerate(points):
        if not isinstance(point, (list, tuple)) or len(point) < 2:
            raise ValueError("invalid captcha tile coordinate")
        source_x, source_y = abs(int(point[0])), abs(int(point[1]))
        if source_x + 11 > background.width or source_y + 71 > background.height:
            raise ValueError("captcha tile coordinate is outside the background")
        tile = background.crop((source_x, source_y, source_x + 11, source_y + 71))
        reconstructed.paste(tile, ((index % 33) * 11, (index // 33) * 71))

    target = np.asarray(piece, dtype=np.float64)
    source = np.asarray(reconstructed.convert("RGB"), dtype=np.float64)
    score = sum(
        correlate2d(source[:, :, channel], target[:, :, channel], mode="valid")
        for channel in range(3)
    )
    target_energy = float(np.sum(target * target))
    window_energy = np.zeros_like(score)
    for channel in range(3):
        channel_data = source[:, :, channel]
        window_energy += correlate2d(
            channel_data * channel_data,
            np.ones((target.shape[0], target.shape[1])),
            mode="valid",
        )

    denominator = np.sqrt(np.maximum(window_energy * target_energy, 1e-12))
    best_y, best_x = np.unravel_index(np.argmax(score / denominator), score.shape)
    del best_y
    return int(best_x)


def main() -> int:
    args = parse_args()
    try:
        print(f"GAP_X={solve(args.response, args.piece)}")
    except Exception as exc:  # noqa: BLE001  # keep stdout machine-readable; details go to stderr
        print(f"captcha_solver: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
