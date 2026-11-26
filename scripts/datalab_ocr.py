"""Submit/resume a locally prepared glyph sheet without duplicate POST retries.

Uses system curl's certificate store; credentials enter curl through stdin only.
The state file deliberately survives failures after a possibly accepted upload.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import time
from urllib.parse import urlparse


def authenticated_url(url):
    parsed = urlparse(url)
    if (parsed.scheme != 'https' or parsed.hostname != 'www.datalab.to'
            or parsed.port not in (None, 443) or parsed.username or parsed.password):
        raise ValueError('Refusing to send credentials to an unexpected URL')
    return url


def request(url, fields=None, source=None, authenticated=True):
    config = ''
    if authenticated:
        authenticated_url(url)
        config = 'header = ' + json.dumps('X-API-Key: ' + os.environ['DATALAB_API_KEY']) + '\n'
    elif urlparse(url).scheme != 'https':
        raise ValueError('Result download must use HTTPS')
    command = ['curl', '--config', '-', '--silent', '--show-error', '--fail-with-body',
               '--connect-timeout', '20', '--max-time', '120']
    for key, value in (fields or {}).items():
        command += ['--form-string', f'{key}={value}']
    if source:
        is_pdf = source.suffix.lower() == '.pdf'
        name, mime = ('glyph-sheets.pdf', 'application/pdf') if is_pdf else ('glyph-sheet.png', 'image/png')
        command += ['--form', f'file=@{source};filename={name};type={mime}']
    command.append(url)
    result = subprocess.run(command, input=config, capture_output=True, text=True)
    if result.returncode:
        raise RuntimeError(f'curl exit {result.returncode}: {result.stderr[:300]} {result.stdout[:300]}')
    return json.loads(result.stdout)


def save(path, data):
    temporary = path.with_suffix(path.suffix + '.tmp')
    temporary.write_text(json.dumps(data, ensure_ascii=False, indent=2) + '\n')
    temporary.replace(path)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('image', type=Path)
    parser.add_argument('--state', type=Path, required=True)
    parser.add_argument('--planned-pages', type=int, required=True,
                        help='Whole campaign OCR pages, not HTTP poll count')
    args = parser.parse_args()
    if args.planned_pages < 1:
        parser.error('planned-pages must be positive')
    mode = 'fast' if args.planned_pages <= 500 else 'lite'
    if args.image.suffix.lower() == '.pdf':
        import pymupdf
        with pymupdf.open(args.image) as document:
            pages = len(document)
    elif args.image.suffix.lower() == '.png':
        pages = 1
    else:
        parser.error('Input must be a PNG or PDF')
    if pages < 1 or pages > args.planned_pages:
        parser.error('Input pages exceed the whole campaign page count')
    fingerprint = hashlib.sha256(args.image.read_bytes()).hexdigest()
    args.state.parent.mkdir(parents=True, exist_ok=True)
    if args.state.exists():
        state = json.loads(args.state.read_text())
        if state['sha256'] != fingerprint or state['mode'] != mode:
            raise ValueError('Existing job differs from requested image or mode')
        if state['status'] == 'complete':
            print('Already complete:', args.state)
            return
        if not state.get('request_check_url'):
            raise RuntimeError('Prior submission may have been accepted; inspect state before resubmitting')
    else:
        state = {'sha256': fingerprint, 'mode': mode, 'pages': pages,
                 'planned_pages': args.planned_pages, 'status': 'submitting'}
        # Exclusive creation also prevents simultaneous duplicate submissions.
        with args.state.open('x') as handle:
            json.dump(state, handle, indent=2)
        fields = {'mode': mode, 'max_pages': str(pages), 'output_format': 'json,markdown',
                  'disable_image_extraction': 'true', 'disable_image_captions': 'true',
                  'merge_cross_page': 'false', 'skip_cache': 'false'}
        if mode == 'fast':
            fields['exact_transcription'] = 'true'
        initial = request('https://www.datalab.to/api/v1/convert', fields, args.image.resolve())
        state['submission'] = initial
        state['request_check_url'] = authenticated_url(initial['request_check_url'])
        state['status'] = 'submitted'
        save(args.state, state)
        print('Submitted:', initial.get('request_id'), 'mode:', mode, flush=True)
    while True:
        result = request(state['request_check_url'])
        state['last_status'] = result.get('status')
        save(args.state, state)
        if result.get('status') == 'complete':
            if result.get('success') is False:
                state.update(status='failed', result=result)
                save(args.state, state)
                raise RuntimeError('Datalab processing failed: ' + str(result.get('error')))
            if result.get('result_url'):
                downloaded = request(result['result_url'], authenticated=False)
                result = {**downloaded, **{k:v for k,v in result.items() if v is not None}}
            result_path = args.state.with_suffix('.result.json')
            save(result_path, result)
            state.update(status='complete', result_file=result_path.name)
            save(args.state, state)
            print('Complete:', result_path, flush=True)
            return
        if result.get('status') in ('failed', 'error') or result.get('success') is False:
            state.update(status='failed', result=result)
            save(args.state, state)
            raise RuntimeError('Datalab processing failed')
        print('Status:', result.get('status'), flush=True)
        time.sleep(3)


if __name__ == '__main__':
    main()
