"""Stage only the explicit boot archive permission execution fixture."""
from pathlib import Path
import argparse
import shutil


def stage(build):
    root = build / 'rootfs'
    if not root.is_dir() or not (root / 'init').is_file():
        raise ValueError('normal distribution staging must run first')
    for name, mode in (('archive-sticky', 0o1777), ('archive-sgid', 0o2777),
                       ('archive-sgid/imported', 0o755)):
        path = root / name
        path.mkdir()
        path.chmod(mode)
    path = root / 'archive-sgid/imported-file'
    path.write_bytes(b'root-owned archive fixture\n')
    path.chmod(0o444)
    path = root / 'bin/archive-permissions-probe'
    shutil.copy2(build / 'fixtures/native-archive-permissions-probe.elf', path)
    path.chmod(0o755)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--build', type=Path, required=True)
    stage(parser.parse_args().build)
