"""Stage explicit login test executables in a retained qualification consumer."""
from pathlib import Path
import argparse
import shutil


def stage(build):
    root = build / 'rootfs'
    if not (root / 'init').is_file() or not (root / 'bin/oksh').is_file():
        raise ValueError('normal distribution stage must run first')
    for source, target in [(build / 'apps/login.elf', root / 'bin/login'),
            (build / 'apps/oksh.elf', root / 'bin/oksh-real'),
            (build / 'fixtures/native-login-session.elf', root / 'bin/oksh'),
            (build / 'fixtures/native-login-cut.elf', root / 'bin/login-cut')]:
        shutil.copy2(source, target)
        target.chmod(0o755)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--build', type=Path, required=True)
    stage(parser.parse_args().build)
