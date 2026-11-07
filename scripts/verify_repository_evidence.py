"""Verify the curated evidence manifest without accessing devices or services."""
import hashlib
import json
from pathlib import Path


def main():
    root = Path(__file__).resolve().parents[1]
    manifest = json.loads((root / 'results/MANIFEST.json').read_text(encoding='utf-8'))
    checked = 0
    for entry in manifest['files']:
        path = (root / entry['path']).resolve()
        if not path.is_relative_to(root):
            raise ValueError('Manifest path leaves repository')
        data = path.read_bytes()
        if entry['hash_mode'] == 'LF-normalized':
            data = data.replace(b'\r\n', b'\n')
        elif entry['hash_mode'] != 'bytes':
            raise ValueError('Unknown checksum mode')
        if hashlib.sha256(data).hexdigest() != entry['sha256']:
            raise ValueError('Evidence checksum mismatch: ' + entry['path'])
        checked += 1
    print(f'PASS: {checked} curated evidence files verified; no hardware accessed.')


if __name__ == '__main__':
    main()
