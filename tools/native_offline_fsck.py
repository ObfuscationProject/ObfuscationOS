"""Keep offline filesystem failure authoritative after a guest has passed."""

from __future__ import annotations

from collections.abc import Callable


def require_final_fsck(record: dict, check: Callable[[], object], save: Callable[[], object]) -> None:
    prior_status = record["status"]
    try:
        check()
    except BaseException as error:
        record.update(status="failed", offline_error=repr(error))
        save()
        raise
    record["status"] = prior_status
    save()
