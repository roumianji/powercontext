import argparse
import hashlib
import json
from pathlib import Path

parser = argparse.ArgumentParser()
parser.add_argument('--write-manifest', action='store_true')
args = parser.parse_args()
root = Path(__file__).resolve().parents[1]
directory = root / 'public/models/Xenova/all-MiniLM-L6-v2/onnx'
manifest = {'model': 'Xenova/all-MiniLM-L6-v2', 'revision': '751bff37182d3f1213fa05d7196b954e230abad9', 'profiles': {}}
for profile, name in [('fp32', 'model.onnx'), ('fp16', 'model_fp16.onnx'), ('q8', 'model_quantized.onnx')]:
    path = directory / name
    digest = hashlib.sha256()
    with path.open('rb') as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b''): digest.update(block)
    manifest['profiles'][profile] = {'file': name, 'bytes': path.stat().st_size, 'sha256': digest.hexdigest()}
    print(f'{profile}: {path.stat().st_size} bytes, {path.stat().st_size/1048576:.3f} MiB, SHA256 {digest.hexdigest()}')
manifest['files'] = {}
for name in ['config.json', 'tokenizer.json', 'tokenizer_config.json', 'special_tokens_map.json', 'vocab.txt', 'onnx/model.onnx', 'onnx/model_fp16.onnx', 'onnx/model_quantized.onnx']:
    path = directory.parent / name
    digest = hashlib.sha256()
    with path.open('rb') as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b''): digest.update(block)
    manifest['files'][name] = {'bytes': path.stat().st_size, 'sha256': digest.hexdigest()}
if args.write_manifest:
    (root / 'public/model-manifest.json').write_text(json.dumps(manifest, indent=2) + '\n', encoding='utf-8')
