import base64
import io
import math
from pathlib import Path

import pytest

pytest.importorskip("PIL")
from PIL import Image, ImageChops, ImageDraw

from freecad_mcp import server


def _generate_fixture_images() -> dict[str, bytes]:
    fixtures: dict[str, bytes] = {}
    width, height = 640, 420

    for name, base_tint in (
        ("isometric_scene", (38, 84, 124)),
        ("assembly_view", (64, 76, 96)),
        ("material_preview", (82, 98, 116)),
    ):
        image = Image.new("RGB", (width, height))
        pixels = image.load()

        for y in range(height):
            for x in range(width):
                grad_x = x / (width - 1)
                grad_y = y / (height - 1)
                r = int(base_tint[0] + 100 * grad_x)
                g = int(base_tint[1] + 80 * grad_y)
                b = int(base_tint[2] + 60 * (1 - grad_x * grad_y))
                pixels[x, y] = (r, g, b)

        draw = ImageDraw.Draw(image)
        draw.rectangle([(45, 58), (255, 340)], outline=(235, 235, 245), width=2)
        draw.rectangle([(285, 120), (550, 332)], outline=(245, 245, 250), width=2)
        draw.polygon([(100, 110), (220, 80), (300, 160), (180, 188)], outline=(255, 255, 255), width=2)
        draw.line([(64, 360), (590, 56)], fill=(250, 250, 250), width=2)
        draw.line([(64, 56), (590, 360)], fill=(250, 250, 250), width=1)
        draw.ellipse([(382, 162), (502, 282)], outline=(240, 240, 250), width=2)
        draw.text((62, 26), f"Fixture: {name}", fill=(248, 248, 252))

        out = io.BytesIO()
        image.save(out, format="PNG")
        fixtures[name] = out.getvalue()

    return fixtures


def _psnr_db(reference_png: bytes, jpeg_bytes: bytes) -> float:
    ref = Image.open(io.BytesIO(reference_png)).convert("RGB")
    candidate = Image.open(io.BytesIO(jpeg_bytes)).convert("RGB")
    if ref.size != candidate.size:
        raise ValueError("Image size mismatch for PSNR calculation")

    diff = ImageChops.difference(ref, candidate)
    histogram = diff.histogram()
    squared_error_sum = sum(count * ((idx % 256) ** 2) for idx, count in enumerate(histogram))
    mse = squared_error_sum / (ref.width * ref.height * 3)
    if mse == 0:
        return float("inf")
    return 20 * math.log10(255.0) - 10 * math.log10(mse)


def test_generate_jpeg_savings_report():
    fixtures = _generate_fixture_images()
    rows: list[dict[str, float | str]] = []

    for fixture_name, png_bytes in fixtures.items():
        png_b64 = base64.b64encode(png_bytes).decode("utf-8")
        jpeg_b64, _metrics = server.convert_png_base64_to_jpeg_base64(png_b64)
        jpeg_bytes = base64.b64decode(jpeg_b64)

        png_kb = len(png_bytes) / 1024
        jpeg_kb = len(jpeg_bytes) / 1024
        saved_kb = png_kb - jpeg_kb
        saved_percent = ((len(png_bytes) - len(jpeg_bytes)) / len(png_bytes)) * 100
        psnr = _psnr_db(png_bytes, jpeg_bytes)

        rows.append(
            {
                "fixture": fixture_name,
                "png_kb": png_kb,
                "jpeg_kb": jpeg_kb,
                "saved_kb": saved_kb,
                "saved_percent": saved_percent,
                "psnr_db": psnr,
            }
        )

    avg_saved_percent = sum(float(row["saved_percent"]) for row in rows) / len(rows)
    avg_psnr = sum(float(row["psnr_db"]) for row in rows) / len(rows)

    report_path = Path(__file__).resolve().parents[1] / "docs" / "reports" / "jpeg-savings.md"
    report_path.parent.mkdir(parents=True, exist_ok=True)

    report_lines = [
        "# JPEG Savings Report",
        "",
        "| Fixture | PNG (KB) | JPEG (KB) | Saved (KB) | Saved (%) | PSNR (dB) |",
        "|---|---:|---:|---:|---:|---:|",
    ]

    for row in rows:
        report_lines.append(
            f"| {row['fixture']} | {float(row['png_kb']):.1f} | {float(row['jpeg_kb']):.1f} | "
            f"{float(row['saved_kb']):.1f} | {float(row['saved_percent']):.1f} | {float(row['psnr_db']):.2f} |"
        )

    report_lines.extend(
        [
            "",
            f"Average saved percent: {avg_saved_percent:.1f}",
            f"Average PSNR (dB): {avg_psnr:.2f}",
        ]
    )
    report_path.write_text("\n".join(report_lines) + "\n", encoding="utf-8")

    assert report_path.exists()
    assert avg_saved_percent >= 20.0
    assert avg_psnr >= 38.0
