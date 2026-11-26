"""Export the exam note only after a measured A1 mini profile has been supplied."""
import argparse
from pathlib import Path
import sys

ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'src'))
from plotnote.cli import load_input,export_pages
from plotnote.profile import Profile
from plotnote.model import PlotNoteError


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--profile',required=True,type=Path)
    parser.add_argument('--stage',choices=['test-air','test-contact','notes-air','notes-contact'],required=True)
    parser.add_argument('--homed',action='store_true')
    parser.add_argument('--notes-directory',type=Path,help='Override prepared note SVG directory')
    parser.add_argument('-o','--output',required=True,type=Path)
    args=parser.parse_args()
    root=Path(__file__).resolve().parent
    latest=root/'handwritten-2_5mm'/'a1-mini-note'
    if not latest.is_dir():latest=root/'compact-2_5mm-final'/'a1-mini-note'
    notes=args.notes_directory or (latest if latest.is_dir() else root/'a1-mini-note')
    directory=root/'pen-test' if args.stage.startswith('test-') else notes
    try:
        profile=Profile.load(args.profile)
        profile.validate()
        pages=[page for path in sorted(directory.glob('page-*.svg')) for page in load_input(path)]
        if not pages:raise PlotNoteError('No prepared SVG pages found')
        export_pages(pages,profile,args.output,homed=args.homed,air_mm=5 if args.stage.endswith('air') else 0)
        print(f'Exported {len(pages)} page(s) to {args.output}. No printer command was sent.')
    except (PlotNoteError,OSError,ValueError) as error:
        parser.exit(2,f'出力を停止しました: {error}\n')


if __name__=='__main__':main()
