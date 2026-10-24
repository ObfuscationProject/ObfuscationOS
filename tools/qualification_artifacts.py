"""Resolve qualification artifacts only against explicit retained input roots."""
from pathlib import Path


def preserved_artifact_path(source, kernel, osrepo, output, musl_probes=None, clock_set_probes=None,
                            maintained_time_probes=None):
    source = Path(source).resolve()
    for root in (kernel, osrepo):
        root = Path(root).resolve()
        if source.is_relative_to(root):
            return Path(root.name)/source.relative_to(root)
    for label, root in (('maintained-time-probe', maintained_time_probes),
                        ('clock-set-probe', clock_set_probes), ('musl-probe', musl_probes),
                        ('qualification', output)):
        if root is not None:
            root = Path(root).resolve()
            if source.is_relative_to(root):
                return Path(label)/source.relative_to(root)
    raise ValueError('artifact is outside every explicit qualification input root: '+str(source))
