#!/usr/bin/env python3
"""Independent G1-A validator.

Deliberately does not import the builder or spatial_core.
Re-reads atlas and binary chunks directly.
"""
from __future__ import annotations
import argparse, hashlib, json, math, struct
from pathlib import Path

def sha256_file(p:Path)->str:
    h=hashlib.sha256()
    with p.open("rb") as f:
        for b in iter(lambda:f.read(1<<20),b""): h.update(b)
    return h.hexdigest()

def infer_laterality(name:str):
    s=name.strip().lower()
    l=s.startswith("left ") or s.endswith(" left") or " left " in s
    r=s.startswith("right ") or s.endswith(" right") or " right " in s
    if l and r:return "AMBIGUOUS"
    if l:return "left"
    if r:return "right"
    return None

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("registry")
    ap.add_argument("--model-dir",default="public/models")
    ap.add_argument("--report",default=".tmp/c-v3-s1/g1-a-registry-validation.json")
    args=ap.parse_args()
    md=Path(args.model_dir)
    atlas_path=md/"atlas.json"
    atlas=json.loads(atlas_path.read_text(encoding="utf-8"))
    reg=json.loads(Path(args.registry).read_text(encoding="utf-8"))
    errors=[]; checks=0

    def ck(cond,code,detail=None):
        nonlocal checks
        checks+=1
        if not cond: errors.append({"code":code,"detail":detail})

    ck(reg.get("status")=="GENERATED_NOT_VALIDATED","REGISTRY_PREMATURE_STATUS",reg.get("status"))
    ck(reg["source"]["atlas_sha256"]==sha256_file(atlas_path),"ATLAS_SHA_MISMATCH")
    ck(len(reg["parts"])==len(atlas["parts"]),"PART_COUNT_MISMATCH")
    ck(len(reg["concepts"])==len(atlas["concepts"]),"CONCEPT_COUNT_MISMATCH")
    atlas_parts={p["id"]:p for p in atlas["parts"]}
    reg_parts={p["id"]:p for p in reg["parts"]}
    ck(len(atlas_parts)==len(atlas["parts"]),"DUPLICATE_ATLAS_PART_ID")
    ck(len(reg_parts)==len(reg["parts"]),"DUPLICATE_REGISTRY_PART_ID")

    chunks=[]
    for i,c in enumerate(atlas["chunks"]):
        path=md/Path(c["url"]).name; data=path.read_bytes(); chunks.append(data)
        ck(len(data)==c["bytes"],"CHUNK_BYTE_MISMATCH",{"chunk":i})
        expected=reg["source"]["chunk_hashes"][str(i)]
        ck(expected["sha256"]==sha256_file(path),"CHUNK_SHA_MISMATCH",{"chunk":i})

    tris=0
    for pid,p in atlas_parts.items():
        rr=reg_parts.get(pid)
        ck(rr is not None,"MISSING_REGISTRY_PART",pid)
        if rr is None:continue
        ck(rr["name"]==p["name"],"NAME_MISMATCH",pid)
        ck(rr["concept_id"]==p["conceptId"],"CONCEPT_MISMATCH",pid)
        ck(rr["system"]==p["system"],"SYSTEM_MISMATCH",pid)
        ck(rr["laterality"]==infer_laterality(p["name"]),"LATERALITY_MISMATCH",pid)
        ck(p["indexCount"]%3==0,"NON_TRIANGULAR_INDEX_COUNT",pid)
        raw=chunks[p["chunk"]]
        ck(p["positions"]+p["vertexCount"]*3*4<=len(raw),"POSITION_RANGE_OOB",pid)
        ck(p["indices"]+p["indexCount"]*4<=len(raw),"INDEX_RANGE_OOB",pid)
        if p["positions"]+p["vertexCount"]*12<=len(raw):
            vals=struct.unpack_from("<"+"f"*(p["vertexCount"]*3),raw,p["positions"])
            finite=all(math.isfinite(x) for x in vals)
            ck(finite,"NONFINITE_VERTEX",pid)
            if finite:
                lo=[min(vals[j::3]) for j in range(3)]; hi=[max(vals[j::3]) for j in range(3)]
                for j in range(3):
                    ck(abs(lo[j]-rr["bounds"]["min"][j])<=1e-9,"BOUND_MIN_MISMATCH",{"part":pid,"axis":j})
                    ck(abs(hi[j]-rr["bounds"]["max"][j])<=1e-9,"BOUND_MAX_MISMATCH",{"part":pid,"axis":j})
        if p["indices"]+p["indexCount"]*4<=len(raw):
            ii=struct.unpack_from("<"+"I"*p["indexCount"],raw,p["indices"])
            ck(all(x<p["vertexCount"] for x in ii),"INDEX_VERTEX_OOB",pid)
        tris += p["indexCount"]//3

    ck(tris==atlas["triangles"],"TRIANGLE_TOTAL_MISMATCH",{"computed":tris,"atlas":atlas["triangles"]})
    ids=set(atlas_parts)
    for c in atlas["concepts"]:
        ck(bool(c["elements"]),"EMPTY_CONCEPT",c["id"])
        for pid in c["elements"]:
            ck(pid in ids,"CONCEPT_MISSING_PART",{"concept":c["id"],"part":pid})

    status="PASS" if not errors else "FAIL"
    report={
        "schema_version":"1.0.0","gate":"G1-A","status":status,
        "independence":"validator re-read atlas and binary chunks without importing S1 builder/core",
        "checks_executed":checks,"error_count":len(errors),"errors":errors,
        "input":{"atlas_sha256":sha256_file(atlas_path),"registry_path":args.registry},
        "promotion_allowed":False,
        "note":"PASS validates registry integrity only; it does not approve frames, topology queries, landmark realization, relations, or acupoint coordinates."
    }
    rp=Path(args.report);rp.parent.mkdir(parents=True,exist_ok=True)
    rp.write_text(json.dumps(report,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    print(json.dumps({"gate":"G1-A","status":status,"checks":checks,"errors":len(errors)}))
    raise SystemExit(0 if status=="PASS" else 1)

if __name__=="__main__":
    main()
