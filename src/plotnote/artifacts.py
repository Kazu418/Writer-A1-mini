from pathlib import Path
from html import escape
import json
import pymupdf as fitz
from .model import PlotNoteError

PT = 72 / 25.4


def svg(page, pen_width=0.3):
    page.validate()
    lines = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{page.width:.6f}mm" height="{page.height:.6f}mm" viewBox="0 0 {page.width:.6f} {page.height:.6f}">',
        "<metadata>Ordered centerline paths. Japanese strokes: KanjiVG, Ulrich Apel et al., CC BY-SA 3.0. Latin/Greek: HersheyText, MIT. Do not reorder/reverse paths.</metadata>",
        f'<g fill="none" stroke="#111111" stroke-width="{pen_width:.6f}" stroke-linecap="round" stroke-linejoin="round">',
    ]
    for i, s in enumerate(page.strokes):
        d = "M" + "L".join(f"{x:.6f} {y:.6f}" for x, y in s.points)
        lines.append(
            f'<path id="stroke-{i + 1}" data-source="{escape(s.source, quote=True)}" d="{d}"/>'
        )
    return "\n".join(lines + ["</g>", "</svg>"]) + "\n"


def pdf_document(pages, pen_width=0.3):
    doc = fitz.open()
    for page in pages:
        p = doc.new_page(width=page.width * PT, height=page.height * PT)
        shape = p.new_shape()
        for s in page.strokes:
            shape.draw_polyline([(x * PT, y * PT) for x, y in s.points])
        shape.finish(
            color=(0, 0, 0),
            width=pen_width * PT,
            lineCap=1,
            lineJoin=1,
            closePath=False,
        )
        shape.commit()
    doc.set_metadata(
        {
            "title": "PlotNote stroke preview",
            "author": "PlotNote / KanjiVG contributors",
            "subject": "KanjiVG CC BY-SA 3.0; ordered centerline strokes",
        }
    )
    return doc


def png_bytes(page, pen_width=0.3, dpi=150):
    with pdf_document([page], pen_width) as doc:
        return doc[0].get_pixmap(dpi=dpi).tobytes("png")


def html_preview(pages, pen_width=0.3):
    # Embed only numeric geometry, escaped independently of any source document strings.
    data = json.dumps(
        [
            {"w": p.width, "h": p.height, "s": [s.points for s in p.strokes]}
            for p in pages
        ],
        separators=(",", ":"),
    )
    return """<!doctype html><html lang="ja"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>PlotNote プレビュー</title><style>
body{font:16px system-ui;background:#edf0f3;color:#152735;margin:0}header{padding:20px 28px;background:#172e3d;color:white}h1{font-size:22px;margin:0 0 8px}main{max-width:1000px;margin:auto;padding:20px}nav{display:flex;gap:12px;align-items:center;flex-wrap:wrap;margin-bottom:18px}button,select{font:inherit;padding:8px 12px}input[type=range]{width:240px}svg{background:white;width:min(95%,780px);max-height:75vh;box-shadow:0 4px 24px #182c3a22}#status{font-variant-numeric:tabular-nums}p{line-height:1.6}</style>
<header><h1>PlotNote / ペン軌跡プレビュー</h1>黒：筆記　青：ペンを上げた移動。ページ寸法は実寸です。</header>
<main><nav><label>ページ <select id="page"></select></label><button id="play">再生</button><button id="reset">最初へ</button><label><input id="travel" type="checkbox" checked>空中移動</label><label>速度 <select id="speed"><option>1</option><option>5</option><option selected>20</option><option>100</option></select></label><input id="progress" type="range" min="0" value="0"><span id="status"></span></nav>
<svg id="canvas" xmlns="http://www.w3.org/2000/svg"></svg><p id="size"></p><p>筆順と線の方向を保持しています。これは描画経路の確認用です。実機の位置・高さ・干渉は校正と空描きで確認してください。紙の交換は手動です。</p></main><script>
const pages=DATA, ns='http://www.w3.org/2000/svg';let playing=false,position=0,last=0;
const page=document.getElementById('page'),canvas=document.getElementById('canvas'),progress=document.getElementById('progress');
pages.forEach((p,i)=>page.add(new Option(String(i+1),String(i))));
function path(ps,color,width){const el=document.createElementNS(ns,'path');el.setAttribute('d','M'+ps.map(p=>p.join(' ')).join('L'));el.setAttribute('fill','none');el.setAttribute('stroke',color);el.setAttribute('stroke-width',width);el.setAttribute('stroke-linecap','round');canvas.append(el);}
function render(){const p=pages[+page.value];canvas.replaceChildren();canvas.setAttribute('viewBox',`0 0 ${p.w} ${p.h}`);progress.max=p.s.length;progress.value=position;
for(let i=0;i<Math.floor(position);i++){if(i&&document.getElementById('travel').checked)path([p.s[i-1].at(-1),p.s[i][0]],'#33a1dc',.12);path(p.s[i],'#101010',PENWIDTH);}
document.getElementById('status').textContent=`${Math.floor(position)} / ${p.s.length}画`;document.getElementById('size').textContent=`横 ${p.w.toFixed(3)} mm × 縦 ${p.h.toFixed(3)} mm ／ 拡大・縮小なし`;}
function stop(){playing=false;document.getElementById('play').textContent='再生';}
document.getElementById('play').onclick=()=>{if(!playing&&position>=pages[+page.value].s.length)position=0;playing=!playing;document.getElementById('play').textContent=playing?'停止':'再生';render();};
document.getElementById('reset').onclick=()=>{stop();position=0;render();};progress.oninput=()=>{stop();position=+progress.value;render();};
page.onchange=()=>{stop();position=pages[+page.value].s.length;render();};document.getElementById('travel').onchange=render;
function tick(t){if(playing){const p=pages[+page.value];position=Math.min(p.s.length,position+(t-last)/1000*+document.getElementById('speed').value);render();if(position>=p.s.length)stop();}last=t;requestAnimationFrame(tick);}position=pages[0].s.length;render();requestAnimationFrame(tick);
</script></html>""".replace("DATA", data).replace("PENWIDTH", str(pen_width))


def write_artifacts(pages, out_dir, pen_width=0.3):
    out = Path(out_dir)
    if out.exists():
        raise PlotNoteError(
            f"Output already exists: {out}. Choose a new directory; existing files are never overwritten."
        )
    for p in pages:
        p.validate()
    out.mkdir(parents=True)
    for i, p in enumerate(pages, 1):
        (out / f"page-{i:03d}.svg").write_text(svg(p, pen_width))
        (out / f"page-{i:03d}.png").write_bytes(png_bytes(p, pen_width))
    with pdf_document(pages, pen_width) as doc:
        doc.save(out / "preview.pdf")
    (out / "preview.html").write_text(html_preview(pages, pen_width))
    (out / "report.json").write_text(
        json.dumps(
            {
                "pages": [p.summary() for p in pages],
                "stroke_order": "preserved",
                "direction": "preserved",
                "scale": 1,
                "font_attribution": "KanjiVG (Ulrich Apel and contributors), CC BY-SA 3.0; HersheyText, MIT",
            },
            indent=2,
            ensure_ascii=False,
        )
        + "\n"
    )
    return out
