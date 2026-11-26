"""Derive required characters from actual four-page layout rendering calls."""
import argparse
from collections import Counter
import importlib.util
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('-o', '--output', type=Path, required=True)
    args = parser.parse_args()
    source = ROOT / 'output/exam-note/build_note.py'
    spec = importlib.util.spec_from_file_location('plotnote_note_character_audit', source)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    original = module.render_glyph
    calls = Counter()
    def traced(char, matrix):
        if not char.isspace():
            calls[char] += 1
        return original(char, matrix)
    module.render_glyph = traced
    sheets = [module.sheet1(), module.sheet2(), module.sheet3(), module.sheet4()]
    for sheet in sheets:
        sheet.audit()
    result = {'characters': ''.join(sorted(calls)), 'unique_characters': len(calls),
              'pages': len(sheets), 'method': 'Actual render_glyph calls for the four note sheets; '
              'no worksheet, font fallback, printer action or output rendering',
              'source': str(source)}
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n')
    print(json.dumps({'required_unique': len(calls), 'pages': len(sheets)}))


if __name__ == '__main__':
    main()
