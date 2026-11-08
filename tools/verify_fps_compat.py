"""Exercise the user's FPS patch core and the standalone Chinese installer.

All writes are limited to work/fps-test-<version>. No game process is started.
The separate FPS patch source is supplied locally, not redistributed here.
"""
import argparse
import importlib.util
import json
from pathlib import Path
import shutil
import subprocess
from audit_installation import audit
from bundle import metadata
from game_compat import EXE_NAME, ORIGINAL_SHA256, FPS60_SHA256
from release_config import PATCH_VERSION, RELEASE_FOLDER
from resources import PROJECT, GAME, sha256


def main(fps_source):
    spec=importlib.util.spec_from_file_location('user_fps_core',fps_source)
    core=importlib.util.module_from_spec(spec);spec.loader.exec_module(core)
    assert core.ORIGINAL_HASH == ORIGINAL_SHA256 and core.PATCHED_HASH == FPS60_SHA256
    package=PROJECT/'dist'/RELEASE_FOLDER/'patch.mcpatch'
    installer=package.parent/'MCOWH_Chinese_Patch.exe'
    manifest=metadata(package)
    root=(PROJECT/'work'/f'fps-test-{PATCH_VERSION}').resolve()
    assert root.is_relative_to((PROJECT/'work').resolve()) and root != GAME.resolve()
    clean=PROJECT/'work/clean-fixture'
    if root.exists():
        raise ValueError('Use a fresh isolated FPS test fixture')
    for entry in manifest['baseline']['files']:
        assert sha256(clean/entry['path']) == entry['sha256']
        dest=root/entry['path'];dest.parent.mkdir(parents=True,exist_ok=True)
        shutil.copy2(clean/entry['path'],dest)
    target=root/EXE_NAME
    results=[]

    def files(expected):
        for item in expected:
            if item['path'] != EXE_NAME:assert sha256(root/item['path']) == item['sha256']

    def fps(install,localized):
        core.change(target,install,running_check=lambda:False)
        assert sha256(target) == (FPS60_SHA256 if install else ORIGINAL_SHA256)
        files(manifest['report']['files'] if localized else manifest['baseline']['files'])
        results.append({'tool':'user_fps_core','action':'install' if install else 'restore',
                        'localized_resources_preserved':localized,'passed':True})

    def zh(action,package=package):
        exe_hash=sha256(target)
        subprocess.run([str(installer),'--action',action,'--game',str(root),'--bundle',str(package)],
                       check=True,timeout=180,creationflags=subprocess.CREATE_NO_WINDOW)
        assert sha256(target) == exe_hash
        m=metadata(package)
        if action!='verify':files(m['report']['files'] if action=='install' else m['baseline']['files'])
        results.append({'tool':'standalone_zh_exe','action':action,'bundle':m['version'],
                        'exe_sha256_unchanged':exe_hash,'passed':True})
        print('Verified:',action,m['version'],'on', '60FPS' if exe_hash==FPS60_SHA256 else '30FPS',flush=True)

    # FPS first, then old localization; current installer restores it at 60 FPS.
    fps(True,False)
    zh('verify')
    previous=PROJECT/'dist/MCOWH-zh-CN-0.3.5-trophy-fix/patch.mcpatch'
    zh('install',previous);zh('restore')
    zh('install');zh('install')
    installed_audit=audit(root,package)
    assert installed_audit['installed_content_verified'] and installed_audit['original_backups_verified']
    exe_row=next(r for r in installed_audit['files'] if r['path']==EXE_NAME)
    assert exe_row['state']=='compatible' and exe_row['profile']=='user_60fps_v1.0.0'
    # Remove/reapply FPS while localization stays installed, then restore ZH.
    fps(False,True);zh('install');fps(True,True);zh('restore');fps(False,False)
    # Localization first, then FPS; remove ZH while retaining 60 FPS.
    zh('install');fps(True,True);zh('restore');fps(False,False)
    report={'version':PATCH_VERSION,'standalone_exe_sha256':sha256(installer),
            'bundle_sha256':sha256(package),'fps_core_source_sha256':sha256(fps_source),
            'fixture':str(root),'actual_game_modified':False,'game_started':False,
            'all_passed':True,'steps':results,'resource_audit':installed_audit,
            'final_original_files_verified':True}
    (PROJECT/'docs/fps-compat-verification.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf8')
    print(json.dumps({'passed':True,'steps':len(results),'resources':len(installed_audit['resources']),
                      'fonts':len(installed_audit['fonts']),'actual_game_modified':False},ensure_ascii=False))


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--fps-source',type=Path,default=GAME/'_fps_unlock/installer/patch_core.py')
    main(p.parse_args().fps_source.resolve())
