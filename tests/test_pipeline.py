"""Regression checks for file integrity, source validation and interrupted installs."""
import hashlib
import json
from pathlib import Path
import struct
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
import delta
import install_local
from formats import database_fields, pack_scripts, unpack_scripts, replace_database
from resources import Archive, xor
from build import check_tokens
from fonts import extend, inspect


class CodecTests(unittest.TestCase):
    def test_font_redraws_existing_and_missing_chinese_with_explicit_weight(self):
        original = (ROOT / "work/extracted/d3d11/common/text/win32-seurat-pro-m-14.fgen.phyre").read_bytes()
        old = inspect(original)
        codes = {r[0] for r in old[0]}
        text = set("键盘设置恢复默认")
        self.assertTrue({ord(c) for c in text} & codes)
        self.assertTrue({ord(c) for c in text} - codes)
        modified, report = extend(original, text, Path("C:/Windows/Fonts/NotoSansSC-VF.ttf"), weight=600)
        new = inspect(modified)
        self.assertEqual(report["font_weight"], 600)
        self.assertEqual(report["redrawn"], len(text))
        self.assertEqual(len(new[0]), len(old[0]))
        self.assertEqual(report["added"], len({ord(c) for c in text} - codes))
        for row in new[0]:
            if row[0] in {ord(c) for c in text}:
                self.assertGreaterEqual(row[4], old[4])
                self.assertEqual(row[-1], 0)

    def test_font_existing_only_is_redrawn_and_weight_changes_ink(self):
        original = (ROOT / "work/extracted/d3d11/common/text/win32-seurat-pro-m-14.fgen.phyre").read_bytes()
        codes = {r[0] for r in inspect(original)[0]}
        self.assertIn(ord("置"), codes)
        ink = []
        for weight in [100, 700]:
            modified, report = extend(original, {"置"}, Path("C:/Windows/Fonts/NotoSansSC-VF.ttf"), weight=weight)
            info = inspect(modified)
            self.assertEqual(report["added"], 0)
            self.assertEqual(report["redrawn"], 1)
            self.assertEqual(report["removed_codes"], [])
            ink.append(sum(modified[info[5] + info[3] * report["height_before"]:]))
        self.assertGreater(ink[1], ink[0] * 1.5)

    def test_font_extension_preserves_ascii_and_original_texture(self):
        path = ROOT / "work/extracted/d3d11/common/text/win32-seurat-pro-m-14.fgen.phyre"
        original = path.read_bytes()
        old = inspect(original)
        modified, report = extend(original, set("汉化补丁"), Path("C:/Windows/Fonts/NotoSansSC-VF.ttf"))
        new = inspect(modified)
        self.assertTrue(report["added"] > 0)
        self.assertTrue({ord(c) for c in "汉化补丁"} <= {r[0] for r in new[0]})
        self.assertEqual([r for r in old[0] if r[0] < 128], [r for r in new[0] if r[0] < 128])
        self.assertEqual(original[old[5]:], modified[new[5]:new[5] + old[3] * old[4]])

    def test_xor_trailing_bytes_follow_executable(self):
        self.assertEqual(xor(bytes.fromhex("00000000010203")), bytes.fromhex("efbeadde010203"))
        for size in range(1, 20):
            data = bytes(range(size))
            self.assertEqual(xor(xor(data)), data)

    def test_real_database_lossless_and_variable_length(self):
        data = (ROOT / "work/extracted/d3d11/data/basicdata/database.dat").read_bytes()
        fields = database_fields(data)
        self.assertEqual(len(fields), 63821)
        self.assertEqual(replace_database(data, {}), data)
        new = replace_database(data, {"db/5/10/0": "木盾：变长测试"})
        by_id = {f.id: f.raw for f in database_fields(new)}
        for field in fields:
            self.assertEqual(by_id[field.id], "木盾：变长测试".encode() if field.id == "db/5/10/0" else field.raw)
        with self.assertRaises(ValueError):
            database_fields(data[:-1])

    def test_script_pack_lossless_and_truncation(self):
        for filename in ["event/event.pack", "uiscript/uiscript.pack"]:
            data = (ROOT / "work/extracted/d3d11/data" / filename).read_bytes()
            self.assertEqual(pack_scripts(unpack_scripts(data)), data)
            with self.assertRaises((ValueError, struct.error)):
                unpack_scripts(data[:-1])

    def test_delta_rejects_wrong_source_and_corruption(self):
        source = bytes(range(256)) * 32
        target = source[:400] + "中文变长".encode() + source[410:] + b"tail"
        encoded = delta.create(source, target)
        self.assertEqual(delta.apply(source, encoded), target)
        with self.assertRaises(ValueError):
            delta.apply(source + b"wrong", encoded)
        with self.assertRaises(Exception):
            delta.apply(source, encoded[:-3])

    def test_variable_tokens_are_preserved(self):
        check_tokens(r"Hello <PLAYER> \c[1]yes\c[0]", r"你好 <PLAYER> \c[1]是\c[0]")
        with self.assertRaises(ValueError):
            check_tokens(r"<PLAYER> \c[1]", r"<PLAYER> \c[2]")

    def test_index_checksum_rejects_corruption(self):
        with tempfile.TemporaryDirectory() as temp:
            game = Path(temp)
            dest = game / "D3D11/Data"
            dest.mkdir(parents=True)
            data = bytearray((ROOT.parent / "D3D11/Data/archive.bin").read_bytes())
            data[90] ^= 1
            (dest / "archive.bin").write_bytes(data)
            with self.assertRaisesRegex(ValueError, "checksum"):
                Archive(game)


class InstallTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.game = (Path(self.temp.name) / "game").resolve()
        self.build = (Path(self.temp.name) / "build").resolve()
        self.game.mkdir()
        self.build.mkdir()
        self.names = ["MC_OneWayHeroics.exe", "D3D11/Data/archive.bin", "D3D11/Data/data0000.bin"]
        self.baseline = {"files": []}
        report = {"files": []}
        self.originals = {}
        for i, name in enumerate(self.names):
            raw = f"original {i}".encode()
            self.originals[name] = raw
            p = self.game / name
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_bytes(raw)
            self.baseline["files"].append({"path": name, "sha256": hashlib.sha256(raw).hexdigest()})
            if i:
                p = self.build / name
                p.parent.mkdir(parents=True, exist_ok=True)
                patched = f"patched {i}".encode()
                p.write_bytes(patched)
                report["files"].append({"path": name, "size": len(patched), "sha256": hashlib.sha256(patched).hexdigest()})
        (self.build / "build-report.json").write_text(json.dumps(report), encoding="utf8")
        self.running = patch.object(install_local, "game_running", return_value=False)
        self.running.start()
        self.addCleanup(self.running.stop)

    def test_install_repeat_restore_and_reinstall(self):
        call = lambda action: install_local.operation(action, self.game, self.build, self.baseline)
        self.assertIn("已安装", call("install"))
        self.assertIn("已经安装", call("install"))
        self.assertIn("还原", call("restore"))
        for name, raw in self.originals.items():
            self.assertEqual((self.game / name).read_bytes(), raw)
        self.assertIn("已安装", call("install"))

    def test_wrong_version_writes_no_game_files(self):
        target = self.game / self.names[-1]
        target.write_bytes(b"another mod")
        with self.assertRaises(ValueError):
            install_local.operation("install", self.game, self.build, self.baseline)
        self.assertEqual((self.game / self.names[1]).read_bytes(), self.originals[self.names[1]])
        self.assertEqual(target.read_bytes(), b"another mod")

    def test_mid_install_failure_rolls_back_every_file(self):
        real = install_local.atomic_copy
        injected = [False]
        def fail_once(source, target):
            if source.is_relative_to(self.build) and target.name == "archive.bin" and not injected[0]:
                injected[0] = True
                raise OSError("simulated write failure")
            return real(source, target)
        with patch.object(install_local, "atomic_copy", side_effect=fail_once):
            with self.assertRaises(OSError):
                install_local.operation("install", self.game, self.build, self.baseline)
        for name, raw in self.originals.items():
            self.assertEqual((self.game / name).read_bytes(), raw)

    def test_restore_refuses_to_overwrite_another_mod(self):
        install_local.operation("install", self.game, self.build, self.baseline)
        target = self.game / self.names[-1]
        target.write_bytes(b"another mod")
        with self.assertRaises(ValueError):
            install_local.operation("restore", self.game, self.build, self.baseline)
        self.assertEqual(target.read_bytes(), b"another mod")

    def test_temp_collision_does_not_delete_existing_file(self):
        target = self.game / self.names[-1]
        temp = target.with_name(target.name + ".mcowh-zh-tmp")
        temp.write_bytes(b"existing partial file")
        with self.assertRaises(FileExistsError):
            install_local.atomic_copy(self.build / self.names[-1], target)
        self.assertEqual(temp.read_bytes(), b"existing partial file")

    def test_running_game_is_rejected(self):
        with patch.object(install_local, "game_running", return_value=True):
            with self.assertRaises(ValueError):
                install_local.operation("install", self.game, self.build, self.baseline)

    def test_escape_paths_are_rejected(self):
        for name in ["../outside", "/absolute", "C:/outside", "a\\b"]:
            with self.assertRaises(ValueError):
                install_local.safe_path(self.game, name)


if __name__ == "__main__":
    unittest.main()
