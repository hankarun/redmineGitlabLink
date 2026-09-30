"""How work is taken off the request thread.

An abstraction mostly so tests can run the pipeline inline and assert on the
result instead of racing a thread.
"""

from __future__ import annotations

import threading
from typing import Any, Callable, Protocol, runtime_checkable


@runtime_checkable
class TaskRunner(Protocol):
    def submit(self, fn: Callable[..., Any], *args: Any) -> None: ...


class ThreadTaskRunner:
    """Answer the webhook immediately; do the Redmine calls in the background."""

    def submit(self, fn: Callable[..., Any], *args: Any) -> None:
        threading.Thread(target=fn, args=args, daemon=True).start()


class InlineTaskRunner:
    def submit(self, fn: Callable[..., Any], *args: Any) -> None:
        fn(*args)
