"""Build the narrowly scoped trophy-query fix on frozen 0.3.4."""
import copy
import hashlib
import json
from bundle import metadata
from extract_japanese import read
from release_config import PATCH_VERSION
from resources import Archive, PROJECT, rebuild, sha256
from trophy_query_fix import patch


def main():
    assert PATCH_VERSION == '0.3.5-trophy-fix'
    pinned = json.loads((PROJECT/'docs/package-verification-0.3.4.json').read_text('utf8'))
    for key in ['player_zip', 'source_zip']:
        assert sha256(PROJECT/'dist'/pinned[key]) == pinned[key+'_sha256']
    frozen = metadata(PROJECT/'dist/MCOWH-zh-CN-0.3.4-story-compat/patch.mcpatch')
    base = PROJECT/'build/0.3.4-story-compat'
    for item in frozen['report']['files']:
        assert sha256(base/item['path']) == item['sha256']
    clean = Archive(PROJECT/'work/clean-fixture')
    arc = Archive(base)
    for item in frozen['baseline']['files']:
        assert sha256(PROJECT/'work/clean-fixture'/item['path']) == item['sha256']
    name = 'd3d11/data/basicdata/commonevent.dat'
    replacements = {r['name']: read(arc, r['name']) for r in frozen['report']['changed_resources']}
    replacements[name], proof = patch(replacements[name])
    assert all(raw == read(arc, n) for n, raw in replacements.items() if n != name)
    for n, raw in replacements.items():
        dest = PROJECT/'work/replacements'/n
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(raw)
    out = PROJECT/'build'/PATCH_VERSION
    out.mkdir(parents=True, exist_ok=True)
    rebuild(clean, replacements, out)
    report = copy.deepcopy(frozen['report'])
    report.update(version=PATCH_VERSION, stage='trophy-query-variable-fix',
                  baseline_release=frozen['version'], minimal_change_proof='trophy-query-diff.json')
    report['review_snapshot']['runtime_followups'] = ['User to verify Pirate / Wanderer clear badges; other 0.3.4 fixes confirmed by user']
    report['changed_resources'] = [{'name': n, 'base': n, 'sha256': hashlib.sha256(raw).hexdigest()}
                                   for n, raw in replacements.items()]
    report['files'] = [{'path': p.relative_to(out).as_posix(), 'size': p.stat().st_size, 'sha256': sha256(p)}
                       for p in sorted((out/'D3D11/Data').glob('*.bin'))]
    (out/'build-report.json').write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf8')
    proof.update(version=PATCH_VERSION, baseline=frozen['version'],
                 unchanged_resource_count=len(replacements)-1,
                 unchanged_resources=[n for n in replacements if n != name],
                 fonts_images_translations_identical_to_034=True,
                 actual_game_or_save_files_modified=False)
    (PROJECT/'docs/trophy-query-diff.json').write_text(json.dumps(proof, ensure_ascii=False, indent=2), encoding='utf8')
    print(json.dumps({k:v for k,v in proof.items() if k not in {'changes','unchanged_resources'}}, ensure_ascii=False), flush=True)


if __name__ == '__main__':
    main()
