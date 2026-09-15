import base64
import io
import json
import sys
from pathlib import Path
from tempfile import TemporaryDirectory

import numpy as np
import pytest
from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from captcha_solver import decode_data_url, solve


def test_decode_data_url_round_trip():
    payload = b"joinquant-checkin"
    encoded = base64.b64encode(payload).decode("ascii")
    assert decode_data_url(f"data:image/png;base64,{encoded}") == payload


def test_decode_data_url_rejects_non_data_url():
    for value in ["not-a-data-url", "prefix,am9pbnF1YW50", "data:image/png;base64,%%%"]:
        with pytest.raises(ValueError):
            decode_data_url(value)


def test_solver_recovers_synthetic_gap():
    rng = np.random.default_rng(7)
    original = Image.fromarray(rng.integers(0, 256, (142, 363, 3), dtype=np.uint8), "RGB")
    scrambled = Image.new("RGB", original.size)
    permutation = rng.permutation(66)
    points = []
    for original_index, scrambled_index in enumerate(permutation):
        source_x = (original_index % 33) * 11
        source_y = (original_index // 33) * 71
        target_x = (int(scrambled_index) % 33) * 11
        target_y = (int(scrambled_index) // 33) * 71
        scrambled.paste(original.crop((source_x, source_y, source_x + 11, source_y + 71)), (target_x, target_y))
        points.append([target_x, target_y])

    def data_url(image: Image.Image) -> str:
        buffer = io.BytesIO()
        image.save(buffer, format="PNG")
        return "data:image/png;base64," + base64.b64encode(buffer.getvalue()).decode("ascii")

    expected_x = 120
    piece = original.crop((expected_x, 40, expected_x + 56, 96))
    with TemporaryDirectory() as directory:
        response_path = Path(directory) / "response.json"
        piece_path = Path(directory) / "piece.png"
        response_path.write_text(json.dumps({"data": {"point": points, "bgImg": data_url(scrambled)}}))
        piece.save(piece_path)
        assert solve(str(response_path), str(piece_path)) == expected_x
