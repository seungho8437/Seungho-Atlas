import gzip, hashlib, pathlib

ROOT=pathlib.Path(__file__).resolve().parents[1]
SRC=ROOT/'scripts/data/anatomy-acupoint-relations-v2-final.json.gz'
DST=ROOT/'public/knowledge/anatomy-acupoint-relations-v2.json'
EXPECTED='0a27c6c080479a87d7dcf84f1cb3a45633d20c09458e739ebfe084ce03dd9bda'
raw=gzip.decompress(SRC.read_bytes())
actual=hashlib.sha256(raw).hexdigest()
if actual!=EXPECTED:
    raise SystemExit(f'B v2 final snapshot SHA mismatch: {actual} != {EXPECTED}')
DST.write_bytes(raw)
verify=hashlib.sha256(DST.read_bytes()).hexdigest()
if verify!=EXPECTED:
    raise SystemExit('materialized B v2 graph verification failed')
print(f'Materialized {DST} sha256={verify} bytes={len(raw)}')
