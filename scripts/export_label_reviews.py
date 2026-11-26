"""Turn the phone-review log into a plotnote-review-v1 file (does NOT touch the DB).

yes -> accepted under the proposed label; fix -> accepted under the typed label;
no  -> rejected only when the proposal equals the existing label (the existing
label was what was wrong); an AI-only proposal that is refused changes nothing;
unsure -> nothing. Import with: python -m plotnote.personal_review --import-reviews
"""
import argparse
import json
from pathlib import Path


def latest(path):
    state = {}
    for raw in Path(path).read_text().splitlines():
        if not raw.strip():
            continue
        try:
            rec = json.loads(raw)
        except ValueError:
            continue
        if rec['v'] == 'undo':
            state.pop(rec['id'], None)
        else:
            state[rec['id']] = rec
    return state


def convert(state):
    reviews, skipped = [], {'unsure': 0, 'refused_ai_only': 0}
    for item_id, rec in state.items():
        if rec['v'] == 'yes':
            reviews.append({'id': item_id, 'label': rec['proposed'], 'status': 'accepted'})
        elif rec['v'] == 'fix':
            reviews.append({'id': item_id, 'label': rec['label'], 'status': 'accepted'})
        elif rec['v'] == 'no':
            if rec['proposed'] == rec['goodnotes']:
                reviews.append({'id': item_id, 'label': rec['goodnotes'], 'status': 'rejected'})
            else:
                skipped['refused_ai_only'] += 1
        else:
            skipped['unsure'] += 1
    return {'format': 'plotnote-review-v1', 'reviews': reviews}, skipped


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--reviews', type=Path, required=True)
    p.add_argument('--output', type=Path, required=True)
    a = p.parse_args()
    data, skipped = convert(latest(a.reviews))
    a.output.write_text(json.dumps(data, ensure_ascii=False, indent=1) + '\n')
    counts = {}
    for r in data['reviews']:
        counts[r['status']] = counts.get(r['status'], 0) + 1
    print(json.dumps({'written': len(data['reviews']), **counts, 'skipped': skipped}))


if __name__ == '__main__':
    main()
