"""Create/apply a distributable containing resource deltas, not full game files."""
import argparse
import hashlib
import json
from pathlib import Path
import zipfile

from delta import create, apply
from resources import Archive, GAME, PROJECT, rebuild, sha256
from install_local import safe_path
from game_compat import EXE_NAME, require_executable
from release_config import PATCH_VERSION, SUPPORTED_PATCH_VERSIONS, RELEASE_FOLDER


def make(source: Path, build: Path, output: Path):
    archive = Archive(source)
    by_name = {e.name: e for e in archive.entries}
    report = json.loads((build / "build-report.json").read_text("utf8"))
    baseline = json.loads((PROJECT / "work/baseline.json").read_text("utf8"))
    wanted = {f["path"] for f in report["files"]} | {"MC_OneWayHeroics.exe"}
    baseline["files"] = [f for f in baseline["files"] if f["path"] in wanted]
    if report.get("version") != PATCH_VERSION:
        raise ValueError("Build version differs from current release; rebuild first")
    manifest = {"schema": 1, "version": PATCH_VERSION, "baseline": baseline, "report": report, "resources": []}
    output.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(output, "w", zipfile.ZIP_DEFLATED, compresslevel=9) as package:
        for index, resource in enumerate(report["changed_resources"]):
            original = archive.read(by_name[resource["base"]])
            modified = (PROJECT / "work/replacements" / resource["name"]).read_bytes()
            patch = create(original, modified)
            if apply(original, patch) != modified:
                raise ValueError("Delta round-trip failed")
            member = f"resources/{index:03d}.mcd"
            package.writestr(member, patch)
            manifest["resources"].append({**resource, "member": member,
                "patch_sha256": hashlib.sha256(patch).hexdigest()})
        package.writestr("manifest.json", json.dumps(manifest, ensure_ascii=False, indent=2))
    print(f"Delta bundle: {output.stat().st_size:,} bytes")
    return manifest


def metadata(bundle: Path):
    with zipfile.ZipFile(bundle) as package:
        if package.getinfo("manifest.json").file_size > 1024 * 1024:
            raise ValueError("Oversized package manifest")
        result = json.loads(package.read("manifest.json"))
    if result["schema"] != 1 or result["version"] not in SUPPORTED_PATCH_VERSIONS:
        raise ValueError("Unsupported patch package")
    return result


def prepare(bundle: Path, game: Path, output: Path):
    manifest = metadata(bundle)
    for original in manifest["baseline"]["files"]:
        if original["path"] == EXE_NAME:
            require_executable(safe_path(game.resolve(), EXE_NAME), original["sha256"])
            continue
        if sha256(safe_path(game.resolve(), original["path"])) != original["sha256"]:
            raise ValueError(f"原版文件已修改或版本不符：{original['path']}")
    archive = Archive(game)
    by_name = {e.name: e for e in archive.entries}
    replacements = {}
    with zipfile.ZipFile(bundle) as package:
        for resource in manifest["resources"]:
            if package.getinfo(resource["member"]).file_size > 128 * 1024 * 1024:
                raise ValueError("Oversized resource delta")
            patch = package.read(resource["member"])
            if hashlib.sha256(patch).hexdigest() != resource["patch_sha256"]:
                raise ValueError("补丁数据校验失败。")
            result = apply(archive.read(by_name[resource["base"]]), patch)
            if hashlib.sha256(result).hexdigest() != resource["sha256"]:
                raise ValueError("重建资源校验失败。")
            replacements[resource["name"]] = result
    rebuild(archive, replacements, output)
    for item in manifest["report"]["files"]:
        if sha256(safe_path(output.resolve(), item["path"])) != item["sha256"]:
            raise ValueError("重建文件校验失败，请使用随补丁提供的安装程序。")
    (output / "build-report.json").write_text(json.dumps(manifest["report"], ensure_ascii=False, indent=2), encoding="utf8")
    return manifest


if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--source", type=Path, default=PROJECT / "work/clean-fixture")
    p.add_argument("--build", type=Path, default=PROJECT / "build" / PATCH_VERSION)
    p.add_argument("--out", type=Path, default=PROJECT / "dist" / RELEASE_FOLDER / "patch.mcpatch")
    args = p.parse_args()
    make(args.source, args.build, args.out)
