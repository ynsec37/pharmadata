"""Shared helpers for the data-raw build scripts."""

from __future__ import annotations

import inspect
import logging
import os
import shutil
import stat
import time
from typing import TYPE_CHECKING, TypeVar

if TYPE_CHECKING:
    from collections.abc import Callable
    from pathlib import Path

# Retry knobs for transient filesystem hiccups (locked handles, antivirus scans).
_RETRY_ATTEMPTS = 3
_RETRY_DELAY = 0.1

_T = TypeVar("_T")
_log = logging.getLogger(__name__)


def _retry(
    action: Callable[[], _T], *, exceptions: type[BaseException] = OSError
) -> _T:
    """Run *action* up to _RETRY_ATTEMPTS times, retrying on *exceptions*.

    The final attempt runs outside the retry loop: no sleep, no catch, so its
    exception propagates to the caller.
    """
    for attempt in range(1, _RETRY_ATTEMPTS):
        try:
            return action()
        except exceptions as exc:
            _log.debug("attempt %d/%d failed: %s", attempt, _RETRY_ATTEMPTS, exc)
            time.sleep(_RETRY_DELAY)
    return action()


def _on_rm_error(func: Callable[[str], None], fpath: str, _exc_info: object) -> None:
    """Make a path writable, then retry the failed remove operation."""
    os.chmod(fpath, stat.S_IWRITE)  # noqa: PTH101
    func(fpath)


_RMTREE_ONEXC = "onexc" in inspect.signature(shutil.rmtree).parameters


def _rmtree(path: Path) -> None:
    """``shutil.rmtree`` with the supported error callback.

    ``onexc`` replaced ``onerror`` in Python 3.12, but some 3.12+ builds
    (e.g. uv's CPython 3.14 on Windows) ship ``_robust_rmtree`` without it.
    """
    if _RMTREE_ONEXC:
        shutil.rmtree(path, onexc=_on_rm_error)  # type: ignore[unexpected-keyword]
    else:  # pragma: no cover
        shutil.rmtree(path, onerror=_on_rm_error)


def rmtree(path: Path) -> None:
    """Remove a directory tree, retrying through transient filesystem delays.

    Read-only files are made writable before retrying; a persistent failure
    surfaces instead of being swallowed.
    """
    if not path.exists():
        return
    _retry(lambda: _rmtree(path))
