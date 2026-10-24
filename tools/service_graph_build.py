"""Admit only the explicitly sealed production service graph, never its test init."""
from pathlib import Path
import hashlib
import json
import re
from stage_rootfs import inspect_managed_init_elf
from service_manifest_config import snapshot, parse

PROFILE = 'bounded-boot-manifest-noargs-v2'
SOURCES = ('apps/init/service_manager.c', 'apps/init/service_graph.h', 'apps/init/pid1_policy.h',
           'apps/init/service_manifest.h', 'apps/init/service_manifest_load.h')
ADDITIONS = {'project_source_dependencies', 'service_graph_sysroot_dependencies',
             'project_dependency_command', 'service_graph_profile',
             'original_manifest_sha256', 'service_graph_sealer_sha256', 'service_manifest_sha256'}


def sha(path): return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def admit(build: Path, expected: str, arch: str, project: Path, *, configuration: bytes | None = None) -> Path:
    build, project = build.resolve(), project.resolve()
    # Packaging supplies the same immutable trusted snapshot it will install.
    # Legacy callers still take a trusted snapshot; neither path skips grammar.
    if configuration is None:
        configuration = snapshot(project / 'config/services.conf')
    parse(configuration)
    configuration_digest = hashlib.sha256(configuration).hexdigest()
    manifest_path = build / 'manifest.json'
    if not isinstance(expected, str) or not re.fullmatch('[0-9a-f]{64}', expected) or sha(manifest_path) != expected:
        raise ValueError('service graph manifest hash mismatch')
    manifest = json.loads(manifest_path.read_text())
    original = build / 'unsealed-manifest.json'
    if (manifest.get('schema_version') != 1 or manifest.get('status') != 'built-not-executed' or
            manifest.get('executed') is not False or manifest.get('architecture') != arch or
            manifest.get('source_mode') != 'debug' or manifest.get('mode') != 'debug' or
            manifest.get('service_graph_profile') != PROFILE or
            manifest.get('service_manifest_sha256') != configuration_digest or
            manifest.get('probe_sha256') != sha(project / SOURCES[0]) or
            manifest.get('linker_script_sha256') != sha(project / 'tests/musl/bootstrap.ld') or
            manifest.get('project_source_dependencies') != {name: sha(project / name) for name in SOURCES} or
            manifest.get('service_graph_sealer_sha256') != sha(project / 'tools/seal_service_graph_build.py') or
            manifest.get('original_manifest_sha256') != sha(original)):
        raise ValueError('service graph is not the pinned production source/architecture/musl profile')
    if {key: value for key, value in manifest.items() if key not in ADDITIONS} != json.loads(original.read_text()):
        raise ValueError('service graph sealing altered the original build record')
    elf = build / 'bootstrap.elf'
    payload = elf.read_bytes()
    if sha(elf) != manifest.get('elf_sha256'):
        raise ValueError('service graph ELF differs from its sealed build')
    if inspect_managed_init_elf(payload, arch) != manifest.get('elf'):
        raise ValueError('service graph ELF identity differs from its sealed build')
    return elf
