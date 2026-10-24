"""Stage only the explicit native console lease execution fixture."""
from pathlib import Path
import argparse
import shutil


def stage(build):
    root = build / 'rootfs'
    if not root.is_dir() or not (root / 'init').is_file():
        raise ValueError('normal distribution staging must run first')
    path = root / 'bin/console-lease-probe'
    shutil.copy2(build / 'fixtures/native-console-lease-probe.elf', path)
    path.chmod(0o755)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--build', type=Path, required=True)
    stage(parser.parse_args().build)
