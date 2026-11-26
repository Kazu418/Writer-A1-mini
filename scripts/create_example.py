"""Build a text-bearing Japanese mathematical PDF at 148 x 148 mm."""

from pathlib import Path
import math
import sys
import pymupdf as fitz

MM = 72 / 25.4


def create(path):
    doc = fitz.open()

    def page():
        return doc.new_page(width=148 * MM, height=148 * MM)

    def text(p, x, y, t, size=10):
        p.insert_text((x * MM, y * MM), t, fontname="japan", fontsize=size)

    def line(p, pts, width=0.25):
        p.draw_polyline(
            [(x * MM, y * MM) for x, y in pts], width=width * MM, color=(0, 0, 0)
        )

    p = page()
    text(p, 12, 20, "三角関数とデータの可視化", 14)
    line(p, [(12, 24), (136, 24)])
    text(p, 12, 33, "正弦波は周期的に変化する関数である。")
    text(p, 12, 41, "振幅は１、周期は２π。角度はラジアンで表す。")
    text(p, 18, 55, "y = sin(x)     -2π ≤ x ≤ 2π", 12)
    text(p, 12, 69, "グラフ：正弦波", 11)
    # Graph coordinate system: x=-2pi..2pi and y=-1..1.
    line(p, [(18, 101), (131, 101)])
    line(p, [(74, 78), (74, 125)])
    line(p, [(127, 99), (131, 101), (127, 103)])
    points = [
        (18 + 112 * i / 160, 101 - 19 * math.sin(-2 * math.pi + 4 * math.pi * i / 160))
        for i in range(161)
    ]
    line(p, points)
    for x, label in [(18, "-2π"), (46, "-π"), (74, "0"), (102, "π"), (130, "2π")]:
        line(p, [(x, 100), (x, 102)])
        text(p, x - 3, 110, label, 8)
    text(p, 77, 83, "1", 8)
    text(p, 77, 122, "-1", 8)
    text(p, 132, 100, "x", 8)
    text(p, 12, 137, "要点：同じ形が一定の間隔で繰り返される。", 9)
    p = page()
    text(p, 12, 20, "平均と分散", 14)
    line(p, [(12, 24), (136, 24)])
    text(p, 12, 34, "データの中心と散らばりを数値で表す。")
    text(p, 15, 49, "平均", 11)
    text(p, 45, 47, "x =", 12)
    # Fraction layouts are explicit PDF text and vector strokes.
    text(p, 65, 43, "x₁ + x₂ + x₃", 10)
    line(p, [(63, 46), (119, 46)])
    text(p, 88, 52, "3", 10)
    text(p, 15, 69, "分散", 11)
    text(p, 45, 69, "σ² =", 12)
    text(p, 68, 64, "Σ (x - 平均)²", 10)
    line(p, [(66, 67), (120, 67)])
    text(p, 91, 74, "n", 10)
    text(p, 12, 88, "例：３人の測定値", 11)
    for y in [94, 104, 114, 124]:
        line(p, [(15, y), (130, y)])
    for x in [15, 53, 91, 130]:
        line(p, [(x, 94), (x, 124)])
    for x, t in [(23, "測定１"), (61, "測定２"), (99, "測定３")]:
        text(p, x, 101, t, 9)
    for x, t in [(30, "10"), (69, "20"), (108, "30")]:
        text(p, x, 111, t, 10)
    text(p, 20, 121, "平均20", 9)
    text(p, 57, 121, "分散200/3", 8)
    text(p, 100, 121, "n = 3", 9)
    text(p, 12, 137, "小さな添字も、元の位置にストロークで描く。", 9)
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    doc.save(path)
    doc.close()


if __name__ == "__main__":
    create(sys.argv[1] if len(sys.argv) > 1 else "examples/japanese-note.pdf")
