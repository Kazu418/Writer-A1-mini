import hashlib
import json
from pathlib import Path
import zipfile

import pymupdf as fitz
import pytest

from plotnote.handoff import prepare, verify, approve, bundle, owner_profile
from plotnote.model import PlotNoteError
from plotnote.package import read_package

SVG = '<svg xmlns="http://www.w3.org/2000/svg" width="165mm" height="127.5mm" viewBox="0 0 165 127.5"><path fill="none" stroke="black" d="M4 4 L10 4 L10 10"/></svg>'


@pytest.fixture
def job_request(tmp_path):
    (tmp_path / 'a.svg').write_text(SVG)
    data = dict(job_id='test-note', max_sheets=1, duplex=False, font_size_mm=2.8,
        formula_policy='keep', faces=[dict(sheet=1, side='front', pass1='a.svg', pass2='a.svg')])
    path = tmp_path / 'job_request.json'
    path.write_text(json.dumps(data))
    return path


def revision(job_request):
    directory = job_request.parent / 'revision'
    return directory, prepare(job_request, directory)


def rehash(directory, name):
    path = directory / 'manifest.json'
    manifest = json.loads(path.read_text())
    manifest['files'][name] = hashlib.sha256((directory / name).read_bytes()).hexdigest()
    if name == 'preview.pdf':
        manifest['preview_sha256'] = manifest['files'][name]
    path.write_text(json.dumps(manifest))


def test_actual_gcode_drives_preview_and_fixed_placement(job_request):
    directory, manifest = revision(job_request)
    assert len(manifest['passes']) == 2
    assert manifest['passes'][0]['first_nozzle_xy_mm'] == pytest.approx([11.5, 170.3])
    assert manifest['passes'][1]['first_nozzle_xy_mm'] == pytest.approx([11.5, 159.3])
    assert owner_profile(1).draw_z == 4.8
    assert owner_profile(2).lift_z == 6.5
    for item in manifest['passes']:
        code = (directory / item['gcode']).read_text()
        assert read_package(directory / item['package']) == code
        assert 'G28' not in code and 'G1 Z4.800' in code
    with fitz.open(directory / 'preview.pdf') as pdf:
        assert len(pdf) == 1
        content = pdf[0].read_contents()
        assert b'26.500000 40.500000 m' in content
        assert b'26.500000 168.500000 m' in content
    assert verify(directory)['preview_sha256'] == manifest['preview_sha256']


def test_delivery_requires_explicit_matching_preview_approval(job_request):
    directory, manifest = revision(job_request)
    with pytest.raises(PlotNoteError):
        bundle(directory, job_request.parent / 'delivery.zip')
    with pytest.raises(PlotNoteError, match='reviewed preview hash'):
        approve(directory, 'Friend', '0' * 64)
    approve(directory, 'Friend', manifest['preview_sha256'])
    output = job_request.parent / 'delivery.zip'
    result = bundle(directory, output)
    assert result['sha256'] == hashlib.sha256(output.read_bytes()).hexdigest()
    with zipfile.ZipFile(output) as archive:
        assert {'preview.pdf', 'manifest.json', 'approval.json'} <= set(archive.namelist())
    with pytest.raises(PlotNoteError, match='already approved'):
        approve(directory, 'Friend', manifest['preview_sha256'])


def test_artifact_changed_after_review_invalidates_delivery(job_request):
    directory, manifest = revision(job_request)
    approve(directory, 'Friend', manifest['preview_sha256'])
    source = directory / manifest['passes'][0]['source']
    source.write_text(source.read_text().replace('L10 10', 'L11 10'))
    with pytest.raises(PlotNoteError, match='Artifact changed'):
        bundle(directory, job_request.parent / 'delivery.zip')


def test_changed_preview_rejected_even_if_hash_is_refreshed(job_request):
    directory, _ = revision(job_request)
    path = directory / 'preview.pdf'
    with fitz.open(path) as pdf:
        pdf[0].draw_line((1, 1), (10, 10))
        raw = pdf.tobytes()
    path.write_bytes(raw)
    rehash(directory, 'preview.pdf')
    with pytest.raises(PlotNoteError, match='Preview geometry differs'):
        verify(directory)


def test_machine_override_rejected_even_if_hash_refreshed(job_request):
    directory, manifest = revision(job_request)
    name = manifest['passes'][0]['profile']
    path = directory / name
    data = json.loads(path.read_text()); data['pen_offset_y'] = 0
    path.write_text(json.dumps(data)); rehash(directory, name)
    with pytest.raises(PlotNoteError, match='Owner profile parameters changed'):
        verify(directory)


def test_rewritten_manifest_does_not_reuse_old_approval(job_request):
    directory, manifest = revision(job_request)
    approve(directory, 'Friend', manifest['preview_sha256'])
    path = directory / 'manifest.json'
    data = json.loads(path.read_text()); data['non_geometry_revision_note'] = 'changed'
    path.write_text(json.dumps(data))
    with pytest.raises(PlotNoteError, match='Approval does not match'):
        bundle(directory, job_request.parent / 'delivery.zip')


@pytest.mark.parametrize('change', [
    {'max_sheets': 0}, {'duplex': 'yes'}, {'font_size_mm': float('nan')},
    {'faces': [dict(sheet=2, side='front', pass1='a.svg', pass2='a.svg')]},
    {'faces': [dict(sheet=1, side='back', pass1='a.svg', pass2='a.svg')]},
])
def test_paper_budget_and_required_choices_are_enforced(job_request, change):
    data = json.loads(job_request.read_text()); data.update(change); job_request.write_text(json.dumps(data))
    with pytest.raises(PlotNoteError):
        prepare(job_request, job_request.parent / 'revision')
    assert not (job_request.parent / 'revision').exists()


def test_wrong_tile_size_is_not_scaled(job_request):
    (job_request.parent / 'a.svg').write_text(SVG.replace('width="165mm"', 'width="160mm"'))
    with pytest.raises(PlotNoteError, match='must match profile'):
        prepare(job_request, job_request.parent / 'revision')


def test_clipped_svg_is_not_silently_accepted(job_request):
    (job_request.parent / 'a.svg').write_text(SVG.replace('<path ', '<path clip-path="url(#clip)" '))
    with pytest.raises(PlotNoteError, match='unclipped'):
        prepare(job_request, job_request.parent / 'revision')


def test_no_automatic_formula_or_text_removal(job_request):
    data = json.loads(job_request.read_text()); data['formula_policy'] = 'blank_display_formulas'
    job_request.write_text(json.dumps(data))
    directory, manifest = revision(job_request)
    assert (directory / manifest['passes'][0]['source']).read_text() == SVG
    assert manifest['passes'][0]['validation']['strokes'] == 1


def test_duplex_one_sheet_is_four_passes(job_request):
    data = json.loads(job_request.read_text()); data['duplex'] = True
    data['faces'].append(dict(sheet=1, side='back', pass1='a.svg', pass2='a.svg'))
    job_request.write_text(json.dumps(data))
    directory, manifest = revision(job_request)
    assert len(manifest['passes']) == 4
    with fitz.open(directory / 'preview.pdf') as pdf:
        assert len(pdf) == 2
