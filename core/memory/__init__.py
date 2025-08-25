try:
    # Try SQLite memory store first
    from .sqlite_memory_wrapper import GlobalMemory
    print("[Memory] Using SQLite-based memory store")
except ImportError as e:
    # Fallback to original memory store
    from .memory_store import GlobalMemory
    print(f"[Memory] SQLite unavailable ({e}), using in-memory store")

from .memory_types import *

__all__ = ['GlobalMemory', 'MemoryNamespace', 'HeartbeatInfo', 'ThreadHealth', 'ModuleMetrics', 'SystemMetrics', 'HealthStatus', 'ModuleStatus']