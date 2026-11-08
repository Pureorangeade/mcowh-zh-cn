"""Known executable profiles; localization never writes the executable.

The user 60 FPS patch v1.0.0 changes only offsets 0x2fe1c..0x2fe1e:
0f be 08 -> 6a 3c 59. Both complete-file hashes were checked against the
original build and the user's patch_core.py. This is not a general hash bypass.
"""
from resources import sha256

EXE_NAME = 'MC_OneWayHeroics.exe'
ORIGINAL_SHA256 = 'd0e7cb34119313a61bef149517d29b3adb886c37456d21b2c2301a38338f1e5e'
FPS60_SHA256 = '001ade6dde612c93968009ac71a62070b1222e69bbe07f6201c0d1c942211548'


def executable_state(path, original_hash):
    if not path.is_file():
        return {'state': 'missing', 'sha256': None, 'profile': None}
    digest = sha256(path)
    if digest == original_hash:
        return {'state': 'original', 'sha256': digest, 'profile': 'original'}
    if original_hash == ORIGINAL_SHA256 and digest == FPS60_SHA256:
        return {'state': 'compatible', 'sha256': digest, 'profile': 'user_60fps_v1.0.0'}
    return {'state': 'different', 'sha256': digest, 'profile': None}


def require_executable(path, original_hash):
    state = executable_state(path, original_hash)
    if state['state'] not in {'original', 'compatible'}:
        raise ValueError('不支持的游戏主程序版本。支持原版及已验证的60帧补丁1.0.0版。')
    return state
