#!/usr/bin/env python3
"""Bind exact compiler dependencies of the bounded service-manager artifacts."""
from pathlib import Path
import argparse
import hashlib
import json
import os
import shlex
import subprocess
import sys
from service_manifest_config import snapshot

SOURCES = {
    'apps/init/service_manager.c': {'apps/init/service_manager.c', 'apps/init/service_graph.h', 'apps/init/pid1_policy.h',
                                  'apps/init/service_manifest.h', 'apps/init/service_manifest_load.h'},
    'tests/musl/service_graph_init.c': {'tests/musl/service_graph_init.c', 'apps/init/service_manager.c', 'apps/init/service_graph.h', 'apps/init/pid1_policy.h',
                                     'apps/init/service_manifest.h', 'apps/init/service_manifest_load.h'},
    'tests/musl/service_graph_child.c': {'tests/musl/service_graph_child.c', 'tests/musl/service_generation.h'},
}
SAFE_ENV = dict(PATH='/usr/bin:/bin', LC_ALL='C', TZ='UTC', PYTHONDONTWRITEBYTECODE='1')
sha = lambda path: hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    assert __debug__ and sys.dont_write_bytecode and os.environ.get('PYTHONDONTWRITEBYTECODE') == '1'
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--build', type=Path, required=True)
    parser.add_argument('--project', type=Path, required=True)
    parser.add_argument('--source', type=Path, required=True)
    args = parser.parse_args()
    build, project, source = args.build.resolve(), args.project.resolve(), args.source.resolve()
    if not source.is_file() or not source.is_relative_to(project):
        raise ValueError('service source must be inside the explicit OS project')
    relative = str(source.relative_to(project))
    if relative not in SOURCES: raise ValueError('unsupported service source contract')
    config_digest = hashlib.sha256(snapshot(project / 'config/services.conf')).hexdigest()
    manifest = build / 'manifest.json'
    record = json.loads(manifest.read_text())
    if (record.get('schema_version') != 1 or record.get('status') != 'built-not-executed' or
        record.get('executed') is not False or record.get('probe_sha256') != sha(source) or
        record.get('elf_sha256') != sha(build / 'bootstrap.elf')):
        raise ValueError('unadmitted service build')
    compile_command = record['commands'][0]
    at = compile_command.index('-c')
    command = [*compile_command[:at], '-M', '-MT', 'service-graph', str(source)]
    output = subprocess.check_output(command, text=True, env=SAFE_ENV)
    if not output.startswith('service-graph:'): raise ValueError('unexpected compiler dependency output')
    include = Path(compile_command[compile_command.index('-isystem') + 1]).resolve()
    found, sysroot = {}, {}
    for token in shlex.split(output.replace('\\\n', '').split(':', 1)[1]):
        path = Path(token).resolve()
        if not path.is_file(): raise ValueError('compiler dependency disappeared')
        if path.is_relative_to(project): found[str(path.relative_to(project))] = sha(path)
        elif path.is_relative_to(include): sysroot[str(path.relative_to(include))] = sha(path)
        else: raise ValueError('compiler dependency is outside project and admitted musl headers')
    if set(found) != SOURCES[relative]: raise ValueError('service compiler dependency closure mismatch')
    backup, temporary = build / 'unsealed-manifest.json', build / 'manifest.service-graph.tmp'
    if backup.exists() or temporary.exists() or 'service_graph_profile' in record:
        raise ValueError('service build sealing is one-shot')
    with backup.open('xb') as stream: stream.write(manifest.read_bytes())
    record.update(project_source_dependencies=found, service_graph_sysroot_dependencies=sysroot,
                  project_dependency_command=command, service_graph_profile='bounded-boot-manifest-noargs-v2',
                  service_manifest_sha256=config_digest,
                  original_manifest_sha256=sha(backup), service_graph_sealer_sha256=sha(Path(__file__)))
    with temporary.open('x') as stream:
        json.dump(record, stream, indent=2, sort_keys=True); stream.write('\n')
    temporary.replace(manifest)
    print('SERVICE GRAPH ARTIFACT SEALED', relative, sha(manifest), flush=True)


if __name__ == '__main__': main()
