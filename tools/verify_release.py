"""Exercise the actual standalone EXE on a minimal clean file fixture."""
import json
from pathlib import Path
import subprocess
import shutil
import time

from bundle import metadata
from resources import PROJECT, GAME, sha256
from release_config import PATCH_VERSION, RELEASE_FOLDER


def main():
    release = PROJECT / "dist" / RELEASE_FOLDER
    executable = release / "MCOWH_Chinese_Patch.exe"
    bundle = release / "patch.mcpatch"
    fixture = (PROJECT / "work" / f"release-test-{PATCH_VERSION}").resolve()
    clean = (PROJECT / "work/clean-fixture").resolve()
    if not fixture.is_relative_to((PROJECT/'work').resolve()) or fixture in {GAME.resolve(),clean}:
        raise ValueError('Release test must use a separate isolated fixture')
    manifest = metadata(bundle)
    if not fixture.exists():
        for item in manifest["baseline"]["files"]:
            source = clean / item["path"]
            if not source.is_file() or sha256(source) != item["sha256"]:
                raise ValueError("A clean original or verified backup is required")
            destination = fixture / item["path"]
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, destination)
    results = []
    steps = [("verify", bundle)]
    for previous_bundle in [PROJECT / "dist/MCOWH-zh-CN-0.3.0-llm-review/patch.mcpatch",
                            PROJECT / "dist/MCOWH-zh-CN-0.3.3-menu-fix/patch.mcpatch"]:
        if previous_bundle.exists():
            steps += [("install", previous_bundle), ("restore", bundle)]
    steps += [("install", bundle), ("install", bundle), ("restore", bundle)]
    for action, package in steps:
        step_manifest = metadata(package)
        started = time.monotonic()
        print(f'Testing standalone {action}: {step_manifest["version"]}',flush=True)
        process = subprocess.run([str(executable), "--action", action, "--game", str(fixture),
                                  "--bundle", str(package)], creationflags=subprocess.CREATE_NO_WINDOW,
                                 timeout=180, capture_output=True)
        if process.returncode != 0:
            raise RuntimeError(f"Standalone {action} failed: {process.returncode}")
        message = (package.parent / "last-operation.txt").read_text("utf8")
        expected = step_manifest["report"]["files"] if action == "install" else step_manifest["baseline"]["files"]
        if action != "verify":
            for item in expected:
                if sha256(fixture / item["path"]) != item["sha256"]:
                    raise RuntimeError(f"Standalone output mismatch: {item['path']}")
        results.append({"action": action, "package_version": step_manifest["version"],
                        "exit_code": process.returncode, "message": message,
                        "seconds": round(time.monotonic() - started, 2)})
        if action=='install' and package==bundle and not any(r.get('resource_audit') for r in results):
            from audit_installation import audit
            verified=audit(fixture,bundle)
            if not verified['installed_content_verified'] or not verified['original_backups_verified']:
                raise RuntimeError('Installed resource or font audit failed')
            (PROJECT/'docs/isolated-install-audit.json').write_text(json.dumps(verified,ensure_ascii=False,indent=2),encoding='utf8')
            results[-1]['resource_audit']=True
    report = {"version": manifest["version"], "executable_sha256": sha256(executable), "bundle_sha256": sha256(bundle),
              "test_fixture": "Minimal original files required by patch; game executable not launched",
              "test_fixture_path":str(fixture),"actual_game_modified":False,
              "runtime_display_verified": False, "results": results}
    (PROJECT / "docs/release-verification.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf8")
    print(json.dumps(results, ensure_ascii=False))


if __name__ == "__main__":
    main()
