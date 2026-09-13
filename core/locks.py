import os
import threading
from contextlib import contextmanager

try:
    import fcntl
except ImportError:
    fcntl = None

_guard = threading.Lock()
_locks = {}


def _thread_lock(path):
    key = os.path.abspath(str(path))
    with _guard:
        lock = _locks.get(key)
        if lock is None:
            lock = threading.Lock()
            _locks[key] = lock
        return lock


@contextmanager
def file_lock(path):
    with _thread_lock(path):
        fh = None
        if fcntl is not None:
            try:
                fh = open(str(path) + '.lock', 'a+')
                fcntl.flock(fh.fileno(), fcntl.LOCK_EX)
            except Exception:
                if fh is not None:
                    try:
                        fh.close()
                    except Exception:
                        pass
                fh = None
        try:
            yield
        finally:
            if fh is not None:
                try:
                    fcntl.flock(fh.fileno(), fcntl.LOCK_UN)
                except Exception:
                    pass
                try:
                    fh.close()
                except Exception:
                    pass
