#!/usr/bin/env python3
"""Deterministic, deduplicated project archives with safe, hash-checked restoration.

pack --root SNAPSHOT --include output --archive-dir archives/project-materials
restore --archive-dir archives/project-materials --destination .

All paths are relative to the supplied snapshot root. This tool does not redact
file contents: pack a sanitized snapshot, not a directory containing credentials.
"""
from __future__ import annotations

import argparse
import fnmatch
import gzip
import hashlib
import io
import json
import os
from pathlib import Path, PurePosixPath
import shutil
import stat
import tempfile
import zipfile

FORMAT = 'writer-a1-mini-project-materials-v1'
BLOCK_BYTES = 4 * 1024 * 1024
PART_BYTES = 40 * 1024 * 1024
HARD_LIMIT = 45 * 1024 * 1024
EXCLUDE_PARTS = {'.git', '.venv', '__pycache__', '.pytest_cache', '.ruff_cache',
                 '.mypy_cache', 'node_modules', '.cache', '.playwright-cli'}
EXCLUDE_NAMES = {'.DS_Store', 'id_rsa', 'id_ed25519', 'credentials.json'}


def sha_file(path):
    digest = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b''):
            digest.update(block)
    return digest.hexdigest()


def safe_relative(value):
    if not isinstance(value, str) or not value or '\\' in value or '\x00' in value:
        raise ValueError(f'Unsafe archive path: {value!r}')
    path = PurePosixPath(value)
    if not path.parts or path.is_absolute() or any(p in ('..', '.') for p in path.parts) or ':' in path.parts[0]:
        raise ValueError(f'Unsafe archive path: {value!r}')
    if path.as_posix() != value:
        raise ValueError(f'Non-canonical archive path: {value!r}')
    return path


def excluded(relative, patterns):
    return (bool(set(relative.parts) & EXCLUDE_PARTS)
            or relative.name in EXCLUDE_NAMES
            or relative.name.startswith('.env')
            or relative.suffix in ('.pyc', '.pyo', '.pkl')
            or any(fnmatch.fnmatchcase(relative.as_posix(), pattern) for pattern in patterns))


def discover(root, includes, patterns):
    files, skipped, seen = [], [], set()
    for include in includes:
        rel = safe_relative(include)
        start = root.joinpath(*rel.parts)
        if not start.exists() and not start.is_symlink():
            raise ValueError(f'Include does not exist: {include}')
        if any(root.joinpath(*rel.parts[:i]).is_symlink() for i in range(1, len(rel.parts))):
            raise ValueError(f'Include traverses a symlink: {include}')
        candidates = [start]
        while candidates:
            path = candidates.pop()
            relative = path.relative_to(root)
            label = relative.as_posix()
            if label in seen:
                continue
            seen.add(label)
            if path.is_symlink():
                skipped.append({'path': label, 'reason': 'symlink'})
            elif excluded(relative, patterns):
                skipped.append({'path': label, 'reason': 'excluded cache/private/temporary path'})
            elif path.is_dir():
                candidates.extend(sorted(path.iterdir(), reverse=True))
            elif path.is_file():
                files.append(path)
            else:
                skipped.append({'path': label, 'reason': 'not a regular file'})
    return sorted(files, key=lambda p: p.relative_to(root).as_posix()), sorted(skipped, key=lambda x: x['path'])


def pack(root, includes, archive_dir, patterns=(), block_bytes=BLOCK_BYTES, part_bytes=PART_BYTES):
    root, archive_dir = Path(root).resolve(), Path(archive_dir).absolute()
    if archive_dir.exists():
        raise ValueError('Archive destination already exists; use a fresh directory')
    if not 1 <= block_bytes <= BLOCK_BYTES or not BLOCK_BYTES + 1024 <= part_bytes <= HARD_LIMIT - 1024 * 1024:
        raise ValueError('Invalid block/part limits; parts must remain below 45 MiB')
    files, skipped = discover(root, includes, patterns)
    if not files:
        raise ValueError('No files selected')
    archive_dir.parent.mkdir(parents=True, exist_ok=True)
    work = Path(tempfile.mkdtemp(prefix=f'.{archive_dir.name}-build-', dir=archive_dir.parent))
    manifest = {'format': FORMAT, 'block_bytes': block_bytes, 'files': [], 'blobs': {}, 'parts': [], 'excluded': skipped}
    writer = None
    part_path = None
    part_payload = 0
    part_count = 0

    def finish_part():
        nonlocal writer
        if writer is None:
            return
        writer.close()
        writer = None
        size = part_path.stat().st_size
        if size >= HARD_LIMIT:
            raise ValueError('Archive part exceeded hard 45 MiB limit')
        manifest['parts'].append({'path': part_path.name, 'size': size, 'sha256': sha_file(part_path)})

    try:
        for number, path in enumerate(files, 1):
            before = path.stat()
            file_hash, chunk_ids = hashlib.sha256(), []
            with path.open('rb') as stream:
                while block := stream.read(block_bytes):
                    file_hash.update(block)
                    identifier = hashlib.sha256(block).hexdigest()
                    chunk_ids.append(identifier)
                    if identifier in manifest['blobs']:
                        continue
                    compressed = gzip.compress(block, compresslevel=6, mtime=0)
                    # Reserve central-directory overhead for every stored member.
                    if writer is not None and part_payload + len(compressed) + 1024 > part_bytes:
                        finish_part()
                    if writer is None:
                        part_count += 1
                        part_path = work / f'materials-{part_count:04d}.zip'
                        writer = zipfile.ZipFile(part_path, 'w', compression=zipfile.ZIP_STORED)
                        part_payload = 0
                    member = f'blobs/{identifier}.gz'
                    info = zipfile.ZipInfo(member, date_time=(1980, 1, 1, 0, 0, 0))
                    info.external_attr = (stat.S_IFREG | 0o644) << 16
                    writer.writestr(info, compressed)
                    part_payload += len(compressed) + 1024
                    manifest['blobs'][identifier] = {'part': part_path.name, 'member': member,
                        'size': len(block), 'compressed_size': len(compressed),
                        'compressed_sha256': hashlib.sha256(compressed).hexdigest()}
            after = path.stat()
            if (before.st_size, before.st_mtime_ns) != (after.st_size, after.st_mtime_ns):
                raise ValueError(f'Source changed while archiving: {path.relative_to(root)}')
            manifest['files'].append({'path': path.relative_to(root).as_posix(), 'size': before.st_size,
                'sha256': file_hash.hexdigest(), 'mode': stat.S_IMODE(before.st_mode) & 0o777, 'chunks': chunk_ids})
            if number % 25 == 0:
                print(f'Packed {number}/{len(files)} files; {len(manifest["blobs"])} unique blocks', flush=True)
        finish_part()
        manifest['totals'] = {'files': len(manifest['files']), 'logical_bytes': sum(x['size'] for x in manifest['files']),
            'unique_uncompressed_bytes': sum(x['size'] for x in manifest['blobs'].values()),
            'archive_bytes': sum(x['size'] for x in manifest['parts'])}
        (work / 'manifest.json').write_text(json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True) + '\n')
        if archive_dir.exists():
            raise ValueError('Archive destination appeared while packing')
        work.rename(archive_dir)
        print(json.dumps(manifest['totals'], sort_keys=True), flush=True)
        return manifest
    finally:
        if writer is not None:
            writer.close()
        if work.exists():
            shutil.rmtree(work)


def destination_path(root, relative):
    target = root.joinpath(*safe_relative(relative).parts)
    cursor = root
    for part in target.relative_to(root).parts:
        cursor = cursor / part
        if cursor.is_symlink():
            raise ValueError(f'Symlink in restore destination: {relative}')
    if not target.resolve().is_relative_to(root):
        raise ValueError(f'Restore destination escapes root: {relative}')
    return target


def restore(archive_dir, destination):
    archive_dir, requested = Path(archive_dir).resolve(), Path(destination).absolute()
    if requested.is_symlink():
        raise ValueError('Restore root is a symlink')
    # Refuse symlink ancestors too, instead of following them through resolve().
    for ancestor in (requested, *requested.parents):
        if ancestor.is_symlink():
            raise ValueError('Restore root has a symlink ancestor')
    root = requested.resolve()
    manifest = json.loads((archive_dir / 'manifest.json').read_text())
    if manifest.get('format') != FORMAT or type(manifest.get('block_bytes')) is not int or not 1 <= manifest['block_bytes'] <= BLOCK_BYTES:
        raise ValueError('Unsupported archive manifest')
    parts, blobs, files = manifest['parts'], manifest['blobs'], manifest['files']
    part_names = set()
    for entry in parts:
        name = safe_relative(entry['path'])
        if len(name.parts) != 1 or entry['path'] in part_names:
            raise ValueError('Invalid or duplicate part name')
        part_names.add(entry['path'])
        path = archive_dir / entry['path']
        if type(entry['size']) is not int or not 1 <= entry['size'] < HARD_LIMIT:
            raise ValueError(f'Invalid archive part size: {name}')
        if path.is_symlink() or path.stat().st_size != entry['size'] or sha_file(path) != entry['sha256']:
            raise ValueError(f'Archive part hash/size mismatch: {name}')
    names, pending, skipped = set(), [], 0
    for entry in files:
        relative = safe_relative(entry['path']).as_posix()
        if relative in names:
            raise ValueError('Duplicate file path in archive')
        names.add(relative)
        target = destination_path(root, relative)
        if type(entry['size']) is not int or entry['size'] < 0 or sum(blobs[x]['size'] for x in entry['chunks']) != entry['size']:
            raise ValueError(f'Invalid file size/chunk list: {relative}')
        if target.exists():
            if not target.is_file() or sha_file(target) != entry['sha256']:
                raise ValueError(f'Refusing to overwrite differing existing path: {relative}')
            skipped += 1
        else:
            pending.append((entry, target))
    for identifier, entry in blobs.items():
        if len(identifier) != 64 or any(c not in '0123456789abcdef' for c in identifier):
            raise ValueError('Invalid blob identifier')
        if entry['part'] not in part_names or entry['member'] != f'blobs/{identifier}.gz':
            raise ValueError('Invalid blob location')
        if type(entry['size']) is not int or not 1 <= entry['size'] <= manifest['block_bytes']:
            raise ValueError('Invalid blob size')
        if type(entry['compressed_size']) is not int or not 1 <= entry['compressed_size'] <= BLOCK_BYTES + 65536:
            raise ValueError('Invalid compressed blob size')
    root.mkdir(parents=True, exist_ok=True)
    restored = 0
    for entry, target in pending:
        target.parent.mkdir(parents=True, exist_ok=True)
        destination_path(root, entry['path'])
        fd, temp_name = tempfile.mkstemp(prefix='.writer-restore-', dir=target.parent)
        temp = Path(temp_name)
        try:
            digest = hashlib.sha256()
            with os.fdopen(fd, 'wb') as output:
                for identifier in entry['chunks']:
                    info = blobs[identifier]
                    with zipfile.ZipFile(archive_dir / info['part']) as part:
                        member = part.getinfo(info['member'])
                        if member.file_size != info['compressed_size']:
                            raise ValueError('Compressed blob size mismatch')
                        compressed = part.read(member)
                    if hashlib.sha256(compressed).hexdigest() != info['compressed_sha256']:
                        raise ValueError('Compressed blob hash mismatch')
                    with gzip.GzipFile(fileobj=io.BytesIO(compressed), mode='rb') as stream:
                        block = stream.read(info['size'] + 1)
                    if len(block) != info['size'] or hashlib.sha256(block).hexdigest() != identifier:
                        raise ValueError('Blob hash/size mismatch')
                    output.write(block)
                    digest.update(block)
            if temp.stat().st_size != entry['size'] or digest.hexdigest() != entry['sha256']:
                raise ValueError(f'Restored file hash/size mismatch: {entry["path"]}')
            destination_path(root, entry['path'])
            os.chmod(temp, entry['mode'] & 0o777)
            # Link refuses an existing destination, including one created after preflight.
            os.link(temp, target)
            restored += 1
        finally:
            temp.unlink(missing_ok=True)
    result = {'restored_files': restored, 'skipped_identical_files': skipped}
    print(json.dumps(result, sort_keys=True), flush=True)
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest='command', required=True)
    p = sub.add_parser('pack', help='Archive a sanitized project snapshot')
    p.add_argument('--root', type=Path, required=True)
    p.add_argument('--include', action='append', required=True, help='Relative path; repeat for multiple folders/files')
    p.add_argument('--exclude', action='append', default=[], help='Additional root-relative glob pattern')
    p.add_argument('--archive-dir', type=Path, required=True)
    r = sub.add_parser('restore', help='Restore, skip identical existing files, refuse different existing files')
    r.add_argument('--archive-dir', type=Path, required=True)
    r.add_argument('--destination', type=Path, required=True)
    args = parser.parse_args()
    try:
        if args.command == 'pack':
            pack(args.root, args.include, args.archive_dir, args.exclude)
        else:
            restore(args.archive_dir, args.destination)
    except (ValueError, KeyError, OSError, zipfile.BadZipFile, EOFError) as error:
        parser.exit(2, f'Archive operation stopped: {error}\n')


if __name__ == '__main__':
    main()
