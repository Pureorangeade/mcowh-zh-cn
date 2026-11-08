"""Installer-only release; preserve every frozen 0.3.5 game resource byte."""
import copy
import json
import shutil
from bundle import metadata
from extract_japanese import read
from release_config import PATCH_VERSION
from resources import Archive, PROJECT, sha256
from game_compat import ORIGINAL_SHA256, FPS60_SHA256


def main():
    assert PATCH_VERSION == '0.3.6-fps-compat'
    pinned = json.loads((PROJECT/'docs/package-verification-0.3.5.json').read_text('utf8'))
    for key in ['player_zip','source_zip']:
        assert sha256(PROJECT/'dist'/pinned[key]) == pinned[key+'_sha256']
    frozen = metadata(PROJECT/'dist/MCOWH-zh-CN-0.3.5-trophy-fix/patch.mcpatch')
    base = PROJECT/'build/0.3.5-trophy-fix'
    out = PROJECT/'build'/PATCH_VERSION
    for item in frozen['report']['files']:
        assert sha256(base/item['path']) == item['sha256']
        dest = out/item['path']
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(base/item['path'], dest)
        assert sha256(dest) == item['sha256']
    arc = Archive(base)
    for item in frozen['report']['changed_resources']:
        raw = read(arc, item['name'])
        dest = PROJECT/'work/replacements'/item['name']
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(raw)
        assert sha256(dest) == item['sha256']
    report = copy.deepcopy(frozen['report'])
    report.update(version=PATCH_VERSION, stage='installer-fps-compatibility',
                  baseline_release=frozen['version'], minimal_change_proof='fps-compat-diff.json')
    report['executable_compatibility'] = {
        'original_sha256':ORIGINAL_SHA256, 'user_60fps_v1.0.0_sha256':FPS60_SHA256,
        'installer_writes_executable':False,
    }
    (out/'build-report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf8')
    proof = {'version':PATCH_VERSION,'baseline':frozen['version'],
             'unchanged_resource_count':len(report['changed_resources']),
             'all_output_bin_hashes_identical':True,'output_files':report['files'],
             'compatibility':report['executable_compatibility'],
             'actual_game_or_save_files_modified':False,'game_started':False}
    (PROJECT/'docs/fps-compat-diff.json').write_text(json.dumps(proof,ensure_ascii=False,indent=2),encoding='utf8')
    print(json.dumps(proof,ensure_ascii=False),flush=True)


if __name__ == '__main__':
    main()
