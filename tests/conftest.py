import pytest
import pymupdf as fitz
from plotnote.model import Page, Stroke
from plotnote.profile import Profile


@pytest.fixture
def profile():
    return Profile(
        calibrated=True,
        calibration_notes="SYNTHETIC TEST FIXTURE - not a real printer calibration",
    )


@pytest.fixture
def page():
    return Page(
        148,
        148,
        [
            Stroke([(10, 10), (30, 10), (30, 30)], "text:木"),
            Stroke([(15, 20), (25, 20)]),
        ],
    )


@pytest.fixture
def make_pdf(tmp_path):
    def make(
        *,
        text="三角関数の基本 ABC xyz αβ = sin(x)",
        width=148,
        height=148,
        rotation=0,
        image=False,
        fill=False,
    ):
        path = tmp_path / "input.pdf"
        doc = fitz.open()
        p = doc.new_page(width=width * 72 / 25.4, height=height * 72 / 25.4)
        # Built-in Japanese CJK font stays Unicode text; math/ASCII separately if needed.
        p.insert_text((25, 40), text, fontname="japan", fontsize=12)
        p.draw_line((25, 60), (200, 60))
        p.draw_bezier((25, 100), (60, 60), (120, 140), (200, 100))
        p.draw_rect((25, 150, 150, 200), fill=(0, 0, 0) if fill else None)
        if image:
            pix = fitz.Pixmap(fitz.csRGB, fitz.IRect(0, 0, 5, 5), False)
            pix.clear_with(0)
            p.insert_image((220, 60, 250, 90), stream=pix.tobytes("png"))
        p.set_rotation(rotation)
        doc.save(path)
        doc.close()
        return path

    return make
