"""Apply the EMNIST-trained 62-class CNN as INDEPENDENT EVIDENCE for ASCII alphanumeric samples.

Evidence only: nothing is approved and the font database is opened read-only.
Run with an interpreter that has torch (the cnn62.pt weights come from train_emnist_cnn.py).
"""
import json
import sqlite3
import sys
import zlib
from pathlib import Path

import numpy as np
import torch
import torch.nn as nn
from PIL import Image, ImageDraw, ImageFilter

ROOT = Path(__file__).resolve().parents[1]
PF = ROOT / 'output/personal-font'
DB = 'file:' + str(PF / 'goodnotes.sqlite3') + '?mode=ro&immutable=1'


def build():
    return nn.Sequential(
        nn.Conv2d(1, 32, 3, padding=1), nn.ReLU(), nn.Conv2d(32, 32, 3, padding=1), nn.ReLU(), nn.MaxPool2d(2),
        nn.Conv2d(32, 64, 3, padding=1), nn.ReLU(), nn.Conv2d(64, 64, 3, padding=1), nn.ReLU(), nn.MaxPool2d(2),
        nn.Flatten(), nn.Dropout(.3), nn.Linear(64 * 49, 256), nn.ReLU(), nn.Dropout(.3), nn.Linear(256, 62))


def render(paths):
    pts = [p for q in paths for p in q]
    x0, x1 = min(p[0] for p in pts), max(p[0] for p in pts)
    y0, y1 = min(p[1] for p in pts), max(p[1] for p in pts)
    e = max(x1 - x0, y1 - y0, 1e-6)
    sc = 19.0 / e
    ox, oy = 4 + (20 - (x1 - x0) * sc) / 2, 4 + (20 - (y1 - y0) * sc) / 2
    im = Image.new('L', (28, 28), 0)
    d = ImageDraw.Draw(im)
    for q in paths:
        z = [((x - x0) * sc + ox, (y - y0) * sc + oy) for x, y in q]
        d.line(z * 2 if len(z) == 1 else z, fill=255, width=2)
    return np.asarray(im.filter(ImageFilter.GaussianBlur(.6)), np.float32) / 255.


def main():
    saved = torch.load(ROOT / 'output/datasets/cnn62.pt')
    classes = saved['classes']
    net = build()
    net.load_state_dict(saved['state'])
    net.eval()
    db = sqlite3.connect(DB, uri=True)
    rows = [(gid, label, status, json.loads(zlib.decompress(blob))['paths'])
            for gid, label, status, blob in db.execute('SELECT id,label,status,payload FROM exemplars')
            if len(label) == 1 and label in classes]
    probs = []
    with torch.no_grad():
        for i in range(0, len(rows), 512):
            x = torch.from_numpy(np.stack([render(r[3]) for r in rows[i:i + 512]])).unsqueeze(1)
            probs.append(torch.softmax(net(x), 1).numpy())
    p = np.concatenate(probs)
    out = []
    for r, pp in zip(rows, p):
        top = np.argsort(-pp)[:3]
        out.append({'id': r[0], 'label': r[1], 'status': r[2],
                    'top3': [classes[j] for j in top], 'p3': [round(float(pp[j]), 4) for j in top],
                    'in_top3': r[1] in [classes[j] for j in top],
                    'in_top3_case_insensitive': r[1].lower() in [classes[j].lower() for j in top]})
    path = PF / 'lt8/emnist_alnum_evidence.json'
    path.write_text(json.dumps({'note': 'Evidence only; nothing approved.', 'items': out}, ensure_ascii=False))
    for tag, sel in (('accepted(own, verified)', [o for o in out if o['status'] == 'accepted']),
                     ('not yet verified', [o for o in out if o['status'] != 'accepted'])):
        print(tag, len(sel), 'top3', round(np.mean([o['in_top3'] for o in sel]), 3),
              'top3 case-insens.', round(np.mean([o['in_top3_case_insensitive'] for o in sel]), 3))


if __name__ == '__main__':
    main()
