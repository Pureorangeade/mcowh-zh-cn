"""Both patch orders and independent removal preserve the other patch."""
import hashlib
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'tools'))
import bundle
import install_local
from audit_installation import installation_state
from game_compat import EXE_NAME, ORIGINAL_SHA256, FPS60_SHA256, executable_state, require_executable


class FpsCompatibilityTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.original = (ROOT/'work/clean-fixture'/EXE_NAME).read_bytes()
        assert hashlib.sha256(cls.original).hexdigest() == ORIGINAL_SHA256
        assert cls.original[0x2fe1c:0x2fe1f] == bytes.fromhex('0f be 08')
        fps = bytearray(cls.original)
        fps[0x2fe1c:0x2fe1f] = bytes.fromhex('6a 3c 59')
        cls.fps = bytes(fps)
        assert hashlib.sha256(cls.fps).hexdigest() == FPS60_SHA256

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.game = Path(self.temp.name)/'game'
        self.build = Path(self.temp.name)/'build'
        self.game.mkdir(); self.build.mkdir()
        self.exe = self.game/EXE_NAME
        self.exe.write_bytes(self.original)
        self.baseline = {'files':[{'path':EXE_NAME,'sha256':ORIGINAL_SHA256}]}
        report = {'files':[]}
        for name in ['D3D11/Data/archive.bin','D3D11/Data/data0000.bin']:
            for folder,raw in [(self.game,b'original resource'),(self.build,b'localized resource')]:
                p=folder/name;p.parent.mkdir(parents=True,exist_ok=True);p.write_bytes(raw)
            self.baseline['files'].append({'path':name,'sha256':hashlib.sha256(b'original resource').hexdigest()})
            report['files'].append({'path':name,'sha256':hashlib.sha256(b'localized resource').hexdigest()})
        (self.build/'build-report.json').write_text(json.dumps(report),encoding='utf8')
        self.guard = patch.object(install_local,'game_running',return_value=False)
        self.guard.start();self.addCleanup(self.guard.stop)

    def operation(self, action):
        return install_local.operation(action,self.game,self.build,self.baseline)

    def test_only_original_or_exact_known_fps_variant_is_accepted(self):
        for data,profile in [(self.original,'original'),(self.fps,'user_60fps_v1.0.0')]:
            self.exe.write_bytes(data)
            self.assertEqual(require_executable(self.exe,ORIGINAL_SHA256)['profile'],profile)
            self.assertEqual(self.exe.read_bytes(),data)
        for index in [100,0x2fe1c,0x2fe1d,0x2fe1e,len(self.original)-1]:
            foreign=bytearray(self.fps);foreign[index]^=1
            self.exe.write_bytes(foreign)
            with self.assertRaises(ValueError):self.operation('install')
            self.assertFalse((self.game/'.mcowh-zh-backup').exists())
            self.assertEqual(self.exe.read_bytes(),foreign)
        self.exe.write_bytes(self.fps)
        with self.assertRaises(ValueError):require_executable(self.exe,'different baseline')

    def test_fps_then_localization_and_independent_removal(self):
        self.exe.write_bytes(self.fps)
        self.operation('install');self.operation('install')
        self.assertEqual(self.exe.read_bytes(),self.fps)
        self.assertFalse((self.game/'.mcowh-zh-backup'/EXE_NAME).exists())
        # The user's FPS tool can restore the original executable independently.
        self.exe.write_bytes(self.original)
        self.assertEqual((self.game/'D3D11/Data/archive.bin').read_bytes(),b'localized resource')
        self.operation('restore')
        self.assertEqual(self.exe.read_bytes(),self.original)

    def test_localization_then_fps_and_restore_keeps_60fps(self):
        self.operation('install')
        self.exe.write_bytes(self.fps)
        self.operation('install')
        self.operation('restore')
        self.assertEqual(self.exe.read_bytes(),self.fps)
        self.assertEqual((self.game/'D3D11/Data/archive.bin').read_bytes(),b'original resource')
        self.operation('install')
        self.assertEqual(self.exe.read_bytes(),self.fps)

    def test_prepare_and_restore_still_reject_unknown_resource_changes(self):
        self.exe.write_bytes(self.fps)
        target=self.game/'D3D11/Data/data0000.bin'
        target.write_bytes(b'foreign resource')
        with patch.object(bundle,'metadata',return_value={'baseline':self.baseline}),patch.object(bundle,'Archive') as archive:
            with self.assertRaises(ValueError):bundle.prepare(Path('unused'),self.game,self.build)
            archive.assert_not_called()
        self.assertEqual(self.exe.read_bytes(),self.fps)
        target.write_bytes(b'original resource');self.operation('install')
        target.write_bytes(b'foreign resource')
        with self.assertRaises(ValueError):self.operation('restore')
        self.assertEqual(target.read_bytes(),b'foreign resource')
        self.assertEqual(self.exe.read_bytes(),self.fps)

    def test_audit_recognizes_fps_guard_without_accepting_missing_or_unknown_exe(self):
        self.exe.write_bytes(self.fps)
        status=executable_state(self.exe,ORIGINAL_SHA256)
        self.assertEqual(installation_state([dict(status,patch_target=False),{'patch_target':True,'state':'patched'}]),'installed')
        self.exe.unlink()
        self.assertEqual(executable_state(self.exe,ORIGINAL_SHA256)['state'],'missing')


if __name__ == '__main__':unittest.main()
