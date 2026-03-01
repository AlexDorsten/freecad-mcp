import logging

from freecad_mcp import server

SAMPLE_PNG_B64 = "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO2mX6kAAAAASUVORK5CYII="


def test_build_screenshot_image_content_defaults_to_png():
    server._use_jpeg_screenshots = False

    image = server.build_screenshot_image_content(SAMPLE_PNG_B64)

    assert image.mimeType == "image/png"
    assert image.data == SAMPLE_PNG_B64


def test_build_screenshot_image_content_uses_jpeg_when_enabled(monkeypatch, caplog):
    def _fake_convert(_data_b64: str, quality: int = server.DEFAULT_JPEG_QUALITY):
        assert quality == server.DEFAULT_JPEG_QUALITY
        return "jpeg-base64", {
            "png_kb": 512.4,
            "jpeg_kb": 141.7,
            "saved_kb": 370.7,
            "saved_percent": 72.3,
        }

    monkeypatch.setattr(server, "convert_png_base64_to_jpeg_base64", _fake_convert)
    server._use_jpeg_screenshots = True

    with caplog.at_level(logging.INFO):
        image = server.build_screenshot_image_content(SAMPLE_PNG_B64)

    assert image.mimeType == "image/jpeg"
    assert image.data == "jpeg-base64"
    assert "JPEG screenshot converted" in caplog.text
    assert "saved_percent=72.3" in caplog.text


def test_build_screenshot_image_content_falls_back_to_png_on_error(monkeypatch, caplog):
    def _fail_convert(_data_b64: str, quality: int = server.DEFAULT_JPEG_QUALITY):
        raise RuntimeError("conversion failed")

    monkeypatch.setattr(server, "convert_png_base64_to_jpeg_base64", _fail_convert)
    server._use_jpeg_screenshots = True

    with caplog.at_level(logging.WARNING):
        image = server.build_screenshot_image_content(SAMPLE_PNG_B64)

    assert image.mimeType == "image/png"
    assert image.data == SAMPLE_PNG_B64
    assert "falling back to PNG" in caplog.text


def test_add_screenshot_if_available_respects_only_text_feedback():
    server._only_text_feedback = True
    response = ["before"]

    result = server.add_screenshot_if_available(response, SAMPLE_PNG_B64)

    assert len(result) == 1
    assert result[0] == "before"
