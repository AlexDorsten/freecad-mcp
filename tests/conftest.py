from pathlib import Path
import sys

import pytest

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))


@pytest.fixture(autouse=True)
def _reset_server_globals():
    from freecad_mcp import server

    original_only_text = server._only_text_feedback
    original_use_jpeg = server._use_jpeg_screenshots
    try:
        yield
    finally:
        server._only_text_feedback = original_only_text
        server._use_jpeg_screenshots = original_use_jpeg
