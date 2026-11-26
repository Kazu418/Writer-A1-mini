import importlib.util
import json
import os
from pathlib import Path

import pytest

SCRIPT = Path(__file__).resolve().parents[1] / 'scripts/archive_project_materials.py'
spec = importlib.util.spec_from_file_location('archive_project_materials', SCRIPT)
archive = importlib.util.module_from_spec(spec)
spec.loader.exec_module(archive)


def sample(tmp_path):
    root = tmp_path / 'source'
    (root / 'output/nested').mkdir(parents=True)
    payload = b'notebook geometry\n' * 500
    (root / 'output/nested/note.bin').write_bytes(payload)
    (root / 'output/copy.bin').write_bytes(payload)
    (root / 'output/empty').write_bytes(b'')
    (root / 'output/run.sh').write_bytes(b'#!/bin/sh\ntrue\n')
    (root / 'output/run.sh').chmod(0o755)
    return root


def read_manifest(path):
    return json.loads((path / 'manifest.json').read_text())


def write_manifest(path, data):
    (path / 'manifest.json').write_text(json.dumps(data))


def test_roundtrip_deduplicates_and_preserves_executable(tmp_path):
    root = sample(tmp_path)
    target = tmp_path / 'archive'
    result = archive.pack(root, ['output'], target, block_bytes=1024)
    assert result['totals']['unique_uncompressed_bytes'] < result['totals']['logical_bytes']
    restored = tmp_path / 'restored'
    assert archive.restore(target, restored)['restored_files'] == 4
    for source in (root / 'output').rglob('*'):
        if source.is_file():
            assert source.read_bytes() == (restored / source.relative_to(root)).read_bytes()
    assert (restored / 'output/run.sh').stat().st_mode & 0o111
    assert archive.restore(target, restored) == {'restored_files': 0, 'skipped_identical_files': 4}


def test_deterministic_manifest_and_zip_bytes(tmp_path):
    root = sample(tmp_path)
    a, b = tmp_path / 'a', tmp_path / 'b'
    archive.pack(root, ['output'], a)
    archive.pack(root, ['output'], b)
    assert (a / 'manifest.json').read_bytes() == (b / 'manifest.json').read_bytes()
    for p in a.glob('*.zip'):
        assert p.read_bytes() == (b / p.name).read_bytes()


def test_default_exclusions_and_symlinks(tmp_path):
    root = sample(tmp_path)
    for name in ['.DS_Store', '.env.local', 'data.pkl', 'module.pyc']:
        (root / 'output' / name).write_text('excluded')
    (root / 'output/__pycache__').mkdir()
    (root / 'output/__pycache__/cache.pyc').write_text('excluded')
    (root / 'output/link').symlink_to(tmp_path / 'outside')
    result = archive.pack(root, ['output'], tmp_path / 'archive')
    assert len(result['files']) == 4
    assert any(x['reason'] == 'symlink' for x in result['excluded'])


def test_refuses_include_through_symlink(tmp_path):
    root = sample(tmp_path)
    outside = tmp_path / 'outside'
    outside.mkdir()
    (outside / 'secret').write_text('secret')
    (root / 'link').symlink_to(outside, target_is_directory=True)
    with pytest.raises(ValueError, match='symlink'):
        archive.pack(root, ['link/secret'], tmp_path / 'archive')


@pytest.mark.parametrize('path', ['../escape', '/absolute', 'a/../../escape', 'a\\b', 'C:/escape', './note', '.', 'a//b'])
def test_refuses_manifest_traversal(tmp_path, path):
    root = sample(tmp_path)
    target = tmp_path / 'archive'
    archive.pack(root, ['output'], target)
    manifest = read_manifest(target)
    manifest['files'][0]['path'] = path
    write_manifest(target, manifest)
    with pytest.raises(ValueError, match='path'):
        archive.restore(target, tmp_path / 'destination')


def test_refuses_different_existing_file_before_writing_anything(tmp_path):
    root = sample(tmp_path)
    target = tmp_path / 'archive'
    archive.pack(root, ['output'], target)
    destination = tmp_path / 'restored'
    (destination / 'output/nested').mkdir(parents=True)
    keep = destination / 'output/nested/note.bin'
    keep.write_bytes(b'keep me')
    with pytest.raises(ValueError, match='overwrite'):
        archive.restore(target, destination)
    assert keep.read_bytes() == b'keep me'
    assert not (destination / 'output/copy.bin').exists()


def test_refuses_symlink_destination_parent(tmp_path):
    root = sample(tmp_path)
    target = tmp_path / 'archive'
    archive.pack(root, ['output'], target)
    destination = tmp_path / 'restored'
    destination.mkdir()
    outside = tmp_path / 'outside'
    outside.mkdir()
    (destination / 'output').symlink_to(outside, target_is_directory=True)
    with pytest.raises(ValueError, match='Symlink'):
        archive.restore(target, destination)
    assert not list(outside.iterdir())


def test_corrupt_part_rejected(tmp_path):
    root = sample(tmp_path)
    target = tmp_path / 'archive'
    archive.pack(root, ['output'], target)
    part = next(target.glob('*.zip'))
    part.write_bytes(part.read_bytes()[:-1] + b'x')
    with pytest.raises(ValueError, match='hash/size'):
        archive.restore(target, tmp_path / 'restored')


def test_corrupt_blob_manifest_rejected(tmp_path):
    root = sample(tmp_path)
    target = tmp_path / 'archive'
    archive.pack(root, ['output'], target)
    manifest = read_manifest(target)
    next(iter(manifest['blobs'].values()))['compressed_sha256'] = '0' * 64
    write_manifest(target, manifest)
    with pytest.raises(ValueError, match='blob hash'):
        archive.restore(target, tmp_path / 'restored')


def test_splits_large_incompressible_material(tmp_path):
    root = tmp_path / 'source'
    (root / 'output').mkdir(parents=True)
    (root / 'output/random.bin').write_bytes(os.urandom(6 * 1024 * 1024))
    target = tmp_path / 'archive'
    result = archive.pack(root, ['output'], target, block_bytes=1024 * 1024, part_bytes=5 * 1024 * 1024)
    assert len(result['parts']) == 2
    assert all(x['size'] < archive.HARD_LIMIT for x in result['parts'])
    archive.restore(target, tmp_path / 'restored')
    assert (root / 'output/random.bin').read_bytes() == (tmp_path / 'restored/output/random.bin').read_bytes()
