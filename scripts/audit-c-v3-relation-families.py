#!/usr/bin/env python3
import argparse, collections, hashlib, json, pathlib

HARD_DISPOSITIONS = {
    'source_backed_derived_unresolved',
    'ambiguous_generic',
    'parent_unresolved',
    'blocked_by_context',
}
RESOLVER_NEEDED_DISPOSITIONS = {'registry_limited', 'specialized_anchor'}

RELATION_FAMILY = {
    'reference-acupoint': 'reference_point_dependency',
    'cross-reference': 'reference_point_dependency',
    'surface-landmark': 'surface_feature_or_region_constraint',
    'relative-to': 'directional_relative_constraint',
    'same-level': 'isolevel_plane_constraint',
    'on-line': 'constructed_line_constraint',
    'fraction-along-line': 'constructed_line_constraint',
    'between': 'between_entities_constraint',
    'midpoint-between': 'between_entities_constraint',
    'center-of': 'entity_center_constraint',
    'midpoint-of-entity': 'entity_center_constraint',
    'at-junction': 'intersection_constraint',
    'overlies': 'deep_entity_surface_projection',
    'superior-to': 'directional_halfspace_constraint',
    'inferior-to': 'directional_halfspace_constraint',
    'among': 'multi_entity_region_constraint',
}

CLASS_FAMILY = {
    'acupoint_reference': 'reference_acupoint',
    'region.body_region': 'body_region',
    'surface.aspect': 'surface_region',
    'surface.skin_region': 'surface_region',
    'line.anatomical_line': 'anatomical_line',
    'line.reference_line': 'constructed_reference_line',
    'hairline': 'specialized_surface_anchor',
    'crease.skin_crease': 'specialized_surface_anchor',
    'fossa_or_depression': 'specialized_surface_anchor',
    'soft_tissue_feature': 'specialized_surface_anchor',
    'orifice_or_cavity': 'specialized_surface_anchor',
    'boundary.border': 'boundary_feature',
    'boundary.junction': 'boundary_feature',
    'soft_tissue.notch': 'boundary_feature',
    'space.anatomical_space': 'anatomical_space',
    'bone.bone': 'entity_mesh',
    'bone.process_or_prominence': 'entity_subfeature',
    'bone.opening': 'entity_subfeature',
    'structure.part': 'entity_subfeature',
    'muscle': 'entity_mesh',
    'tendon': 'entity_mesh',
    'vessel': 'entity_mesh',
    'joint': 'entity_mesh',
    'cartilage': 'entity_mesh',
    'fascia_or_band': 'entity_mesh',
    'ligament': 'entity_mesh',
}

def sha256_bytes(b):
    return hashlib.sha256(b).hexdigest()

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('graph')
    ap.add_argument('--json-out')
    ap.add_argument('--md-out')
    args = ap.parse_args()

    b = pathlib.Path(args.graph).read_bytes()
    g = json.loads(b)
    landmarks = {n['node_id']: n for n in g['landmark_nodes']}

    type_counts = collections.Counter()
    disposition_counts = collections.Counter()
    matrix = collections.Counter()
    hard_relations = []
    resolver_needed_relations = []
    affected_hard_points = set()

    for r in g['relation_instances']:
        rt = r['relation_type']
        type_counts[rt] += 1
        args_nodes = [landmarks[x] for x in r.get('argument_node_ids', []) if x in landmarks]
        classes = sorted({n.get('landmark_class') or '<none>' for n in args_nodes}) or ['<none>']
        dispositions = {n.get('terminal_disposition') for n in args_nodes}
        for c in classes:
            matrix[(rt, c)] += 1
        for d in dispositions:
            disposition_counts[d] += 1
        if dispositions & HARD_DISPOSITIONS:
            hard_relations.append(r['relation_id'])
            affected_hard_points.add(str(r['subject_node_id']).removeprefix('P:'))
        if dispositions & RESOLVER_NEEDED_DISPOSITIONS:
            resolver_needed_relations.append(r['relation_id'])

    rows = []
    for (rt, lc), count in sorted(matrix.items(), key=lambda x: (-x[1], x[0][0], x[0][1])):
        rows.append({
            'relation_type': rt,
            'relation_family': RELATION_FAMILY.get(rt, 'unclassified_relation'),
            'landmark_class': lc,
            'landmark_family': CLASS_FAMILY.get(lc, 'unclassified_or_contextual'),
            'relation_argument_incidence_count': count,
        })

    out = {
        'schema_version': '1.0.0',
        'artifact': 'C-v3-pre-S2-relation-family-audit',
        'scope': 'Static design audit only. Does not solve coordinates, promote coordinates, or alter B v2.1.',
        'input': {
            'graph_artifact': g.get('artifact'),
            'graph_schema_version': g.get('schema_version'),
            'graph_sha256': sha256_bytes(b),
            'source_statements': len(g.get('source_statements', [])),
            'landmark_nodes': len(g.get('landmark_nodes', [])),
            'geometry_nodes': len(g.get('geometry_nodes', [])),
            'relation_instances': len(g.get('relation_instances', [])),
        },
        'summary': {
            'relation_types': len(type_counts),
            'landmark_classes': len({n.get('landmark_class') or '<none>' for n in g['landmark_nodes']}),
            'relations_touching_hard_unresolved_disposition': len(hard_relations),
            'points_affected_by_hard_unresolved_disposition': len(affected_hard_points),
            'relations_touching_registry_or_specialized_anchor': len(resolver_needed_relations),
            'note': 'These are static dependency counts, not the C runtime unresolved count. Runtime validity requires the corresponding family resolver plus relation-satisfaction QC.'
        },
        'relation_type_counts': dict(type_counts.most_common()),
        'terminal_disposition_relation_incidence': dict(disposition_counts.most_common()),
        'relation_type_x_landmark_class': rows,
        'design_contract': {
            'unit_of_implementation': 'relation_family × landmark_family',
            'unit_of_validation': 'all relation instances in each family, then all 361 logical acupoints',
            'individual_point_patch_policy': 'forbidden unless the source semantics are genuinely point-specific and the exception is explicit, source-backed, and regression-tested',
            'coordinate_promotion_policy': 'no coordinate is valid merely because it renders plausibly; all hard source constraints for that point must be computable and satisfied',
            'legacy_coordinate_policy': 'not a solver input',
        },
        'resolver_order': [
            'reference_point_dependency × reference_acupoint',
            'surface_feature_or_region_constraint × body_region/surface_region',
            'constructed_line_constraint × anatomical_line/constructed_reference_line/reference_acupoint',
            'between_entities_constraint × entity_mesh/entity_subfeature/specialized_surface_anchor',
            'entity_center_constraint × entity_mesh/entity_subfeature/specialized_surface_anchor',
            'intersection_constraint × constructed_reference_line/boundary_feature/entity_subfeature',
            'directional_relative_constraint × entity_mesh/entity_subfeature/specialized_surface_anchor',
            'isolevel_plane_constraint × entity_mesh/reference_acupoint',
            'deep_entity_surface_projection × entity_mesh',
            'remaining unclassified_or_contextual nodes by source-backed exception class',
        ],
        'hard_relation_ids': hard_relations,
    }

    if args.json_out:
        pathlib.Path(args.json_out).parent.mkdir(parents=True, exist_ok=True)
        pathlib.Path(args.json_out).write_text(json.dumps(out, ensure_ascii=False, indent=2)+'\n')

    md = []
    md.append('# C v3 pre-S2 relation-family audit')
    md.append('')
    md.append('This is a **design/coverage audit**, not coordinate solving. B v2.1 is not modified and no legacy coordinate is used.')
    md.append('')
    md.append('## Decision')
    md.append('')
    md.append('Remaining dependencies must be reduced by **relation family × landmark family**, not by patching individual acupoints. A resolver is considered valid only after it passes every relation instance in its family and then the 361-point global regression/QC.')
    md.append('')
    md.append('## Current B v2.1 static inventory')
    md.append('')
    md.append(f"- graph SHA-256: `{out['input']['graph_sha256']}`")
    md.append(f"- source statements: **{out['input']['source_statements']}**")
    md.append(f"- landmark nodes: **{out['input']['landmark_nodes']}**")
    md.append(f"- geometry nodes: **{out['input']['geometry_nodes']}**")
    md.append(f"- relation instances: **{out['input']['relation_instances']}**")
    md.append(f"- relations touching hard-unresolved dispositions: **{out['summary']['relations_touching_hard_unresolved_disposition']}** across **{out['summary']['points_affected_by_hard_unresolved_disposition']}** points")
    md.append(f"- relations touching registry-limited/specialized-anchor dependencies: **{out['summary']['relations_touching_registry_or_specialized_anchor']}**")
    md.append('')
    md.append('The two counts above are **not** the runtime unresolved count; they are static dependency incidence counts used to design resolvers.')
    md.append('')
    md.append('## Relation-type distribution')
    md.append('')
    md.append('| relation type | count |')
    md.append('|---|---:|')
    for k,v in type_counts.most_common():
        md.append(f'| `{k}` | {v} |')
    md.append('')
    md.append('## Highest-volume relation type × landmark class pairs')
    md.append('')
    md.append('| relation type | landmark class | incidence | resolver family |')
    md.append('|---|---|---:|---|')
    for row in rows[:40]:
        md.append(f"| `{row['relation_type']}` | `{row['landmark_class']}` | {row['relation_argument_incidence_count']} | `{row['relation_family']} × {row['landmark_family']}` |")
    md.append('')
    md.append('## Implementation contract')
    md.append('')
    md.append('1. Implement one resolver per recurring semantic family; never special-case an acupoint merely to make its coordinate look correct.')
    md.append('2. Validate each resolver against **all** relation instances of that family, including laterality, body-region, surface projection, and source-derived conditions.')
    md.append('3. Only after family-level relation satisfaction passes, run 361-point global QC. Point-specific exceptions are allowed only when the WHO source itself is point-specific and the exception is explicit and regression-tested.')
    md.append('4. Do not promote a coordinate when a hard dependency is unresolved. Plausible rendering is not evidence of semantic validity.')
    md.append('5. Legacy C v1/v2 coordinates remain audit references only, never solver inputs.')
    md.append('')
    md.append('## Resolver order')
    md.append('')
    for i,x in enumerate(out['resolver_order'],1):
        md.append(f'{i}. `{x}`')
    md.append('')
    md_text='\n'.join(md)+'\n'
    if args.md_out:
        pathlib.Path(args.md_out).parent.mkdir(parents=True, exist_ok=True)
        pathlib.Path(args.md_out).write_text(md_text)
    else:
        print(md_text)

if __name__ == '__main__':
    main()
