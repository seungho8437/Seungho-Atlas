#!/usr/bin/env python3
from __future__ import annotations
import argparse, json, math
from pathlib import Path
from spatial_core import AtlasStore, sha256_file

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--model-dir",default="public/models")
    ap.add_argument("--out",default=".tmp/c-v3-s1/mesh-registry.json")
    args=ap.parse_args()

    model_dir=Path(args.model_dir)
    store=AtlasStore(model_dir)
    records=[]
    chunk_hashes={}
    for i,c in enumerate(store.atlas["chunks"]):
        p=model_dir/Path(c["url"]).name
        chunk_hashes[str(i)]={"file":p.name,"bytes":p.stat().st_size,"sha256":sha256_file(p)}
    ambiguous=[]
    for pid in sorted(store.parts):
        m=store.metadata(pid)
        if m.laterality=="AMBIGUOUS": ambiguous.append(pid)
        records.append({
            "id":m.id,"name":m.name,"concept_id":m.concept_id,"system":m.system,
            "laterality":m.laterality,"chunk":m.chunk,"positions_offset":m.positions,
            "vertex_count":m.vertex_count,"indices_offset":m.indices,"index_count":m.index_count,
            "triangle_count":m.index_count//3,
            "bounds":{"min":list(m.bounds_min),"max":list(m.bounds_max)},
        })
    if ambiguous:
        raise SystemExit(f"ambiguous part-name laterality: {ambiguous[:20]}")
    out={
        "schema_version":"1.0.0",
        "artifact":"c-v3-s1-mesh-registry",
        "status":"GENERATED_NOT_VALIDATED",
        "source":{
            "atlas_path":str(model_dir/"atlas.json"),
            "atlas_sha256":sha256_file(model_dir/"atlas.json"),
            "atlas_version":store.atlas.get("version"),
            "atlas_sex":store.atlas.get("sex"),
            "chunk_hashes":chunk_hashes,
        },
        "invariants":{
            "part_count":len(store.parts),
            "concept_count":len(store.concepts),
            "atlas_triangle_count":store.atlas["triangles"],
            "exclusive_region_partition":False,
            "legacy_coordinate_input":False,
        },
        "parts":records,
        "concepts":[{
            "id":c["id"],"name":c["name"],"elements":list(c["elements"])
        } for c in sorted(store.atlas["concepts"],key=lambda x:x["id"])],
    }
    path=Path(args.out); path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(json.dumps(out,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    print(json.dumps({"artifact":str(path),"parts":len(records),"concepts":len(out["concepts"]),"status":out["status"]}))

if __name__=="__main__":
    main()
