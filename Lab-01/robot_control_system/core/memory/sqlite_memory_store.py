"""SQLite-based memory store for robot control system"""

import sqlite3
import threading
import json
import time
import pickle
from typing import Any, Dict, Optional, Callable, List
from collections import defaultdict
from pathlib import Path
import logging

class SQLiteMemoryStore:
    """SQLite-based persistent memory store with real-time capabilities"""
    
    _instance = None
    _lock = threading.Lock()
    
    def __new__(cls, db_path: str = "robot_memory.db"):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance._initialized = False
        return cls._instance
    
    def __init__(self, db_path: str = "robot_memory.db"):
        if self._initialized:
            return
            
        self._initialized = True
        self.db_path = db_path
        self.logger = logging.getLogger("SQLiteMemory")
        
        # Thread-local connections for thread safety
        self._thread_local = threading.local()
        self._write_lock = threading.RLock()
        
        # In-memory cache for frequently accessed data
        self._cache = {}
        self._cache_lock = threading.RLock()
        self._cache_ttl = 0.1  # 100ms cache TTL for real-time performance
        
        # Observers for real-time notifications
        self._namespace_observers = defaultdict(list)
        self._global_observers = []
        
        # Initialize database
        self._init_database()
        
    def _get_connection(self) -> sqlite3.Connection:
        """Get thread-local database connection"""
        if not hasattr(self._thread_local, 'conn'):
            self._thread_local.conn = sqlite3.connect(
                self.db_path,
                timeout=10.0,
                isolation_level=None,  # Autocommit mode for real-time
                check_same_thread=False
            )
            # Enable WAL mode for better concurrency
            self._thread_local.conn.execute("PRAGMA journal_mode=WAL")
            self._thread_local.conn.execute("PRAGMA synchronous=NORMAL")
            # Speed optimizations
            self._thread_local.conn.execute("PRAGMA temp_store=MEMORY")
            self._thread_local.conn.execute("PRAGMA cache_size=10000")
        return self._thread_local.conn
    
    def _init_database(self):
        """Initialize database schema"""
        conn = self._get_connection()
        cursor = conn.cursor()
        
        # Main memory table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS memory (
                namespace TEXT NOT NULL,
                key TEXT NOT NULL,
                value BLOB,
                value_type TEXT,
                timestamp REAL,
                PRIMARY KEY (namespace, key)
            )
        """)
        
        # Create indexes for fast lookups
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_namespace 
            ON memory(namespace)
        """)
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_timestamp 
            ON memory(timestamp)
        """)
        
        # Heartbeat table for module monitoring
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS heartbeats (
                module_name TEXT PRIMARY KEY,
                last_heartbeat REAL,
                status TEXT,
                metadata TEXT
            )
        """)
        
        # Command history table for debugging
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS command_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp REAL,
                command_type TEXT,
                command_data TEXT,
                source_module TEXT,
                status TEXT
            )
        """)
        
        # System metrics table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS system_metrics (
                timestamp REAL PRIMARY KEY,
                cpu_usage REAL,
                memory_usage REAL,
                latency_ms REAL,
                active_modules INTEGER,
                metrics_json TEXT
            )
        """)
        
        conn.commit()
        
        # Initialize default namespaces
        self._init_default_namespaces()
        
    def _init_default_namespaces(self):
        """Initialize default namespaces"""
        default_namespaces = [
            'input_buffer',
            'sensor_state', 
            'planned_trajectory',
            'action_commands',
            'output_signals',
            'system_status',
            'health_status',
            'module_heartbeats',
            'robot_commands',
            'robot_state_history'
        ]
        
        conn = self._get_connection()
        cursor = conn.cursor()
        
        for namespace in default_namespaces:
            # Create namespace entry if not exists
            cursor.execute("""
                INSERT OR IGNORE INTO memory (namespace, key, value, value_type, timestamp)
                VALUES (?, '__namespace_created__', ?, 'float', ?)
            """, (namespace, time.time(), time.time()))
        
        conn.commit()
    
    @classmethod
    def get_instance(cls, db_path: str = "robot_memory.db") -> 'SQLiteMemoryStore':
        """Get singleton instance"""
        return cls(db_path)
    
    def update(self, namespace: str, key: str, value: Any):
        """Update a value in the memory store"""
        with self._write_lock:
            try:
                # Serialize complex objects
                value_type = type(value).__name__
                if isinstance(value, (str, int, float, bool, type(None))):
                    serialized_value = json.dumps(value)
                else:
                    # Use pickle for complex objects
                    serialized_value = pickle.dumps(value)
                    value_type = f"pickle:{value_type}"
                
                conn = self._get_connection()
                cursor = conn.cursor()
                
                cursor.execute("""
                    INSERT OR REPLACE INTO memory 
                    (namespace, key, value, value_type, timestamp)
                    VALUES (?, ?, ?, ?, ?)
                """, (namespace, key, serialized_value, value_type, time.time()))
                
                # Update cache
                with self._cache_lock:
                    cache_key = f"{namespace}:{key}"
                    self._cache[cache_key] = {
                        'value': value,
                        'timestamp': time.time()
                    }
                
                # Notify observers
                self._notify_observers(namespace, key, value)
                
            except Exception as e:
                self.logger.error(f"Error updating {namespace}:{key}: {e}")
                raise
    
    def get(self, namespace: str, key: str, default: Any = None) -> Any:
        """Get a value from the memory store"""
        # Check cache first
        cache_key = f"{namespace}:{key}"
        with self._cache_lock:
            if cache_key in self._cache:
                cached = self._cache[cache_key]
                if time.time() - cached['timestamp'] < self._cache_ttl:
                    return cached['value']
        
        try:
            conn = self._get_connection()
            cursor = conn.cursor()
            
            cursor.execute("""
                SELECT value, value_type FROM memory
                WHERE namespace = ? AND key = ?
            """, (namespace, key))
            
            row = cursor.fetchone()
            if row is None:
                return default
            
            serialized_value, value_type = row
            
            # Deserialize value
            if value_type.startswith("pickle:"):
                value = pickle.loads(serialized_value)
            else:
                value = json.loads(serialized_value)
            
            # Update cache
            with self._cache_lock:
                self._cache[cache_key] = {
                    'value': value,
                    'timestamp': time.time()
                }
            
            return value
            
        except Exception as e:
            self.logger.error(f"Error getting {namespace}:{key}: {e}")
            return default
    
    def get_namespace(self, namespace: str) -> Dict[str, Any]:
        """Get all key-value pairs in a namespace"""
        try:
            conn = self._get_connection()
            cursor = conn.cursor()
            
            cursor.execute("""
                SELECT key, value, value_type FROM memory
                WHERE namespace = ? AND key != '__namespace_created__'
            """, (namespace,))
            
            result = {}
            for key, serialized_value, value_type in cursor.fetchall():
                try:
                    if value_type.startswith("pickle:"):
                        value = pickle.loads(serialized_value)
                    else:
                        value = json.loads(serialized_value)
                    result[key] = value
                except:
                    continue
            
            return result
            
        except Exception as e:
            self.logger.error(f"Error getting namespace {namespace}: {e}")
            return {}
    
    def delete(self, namespace: str, key: str):
        """Delete a key from the memory store"""
        with self._write_lock:
            try:
                conn = self._get_connection()
                cursor = conn.cursor()
                
                cursor.execute("""
                    DELETE FROM memory
                    WHERE namespace = ? AND key = ?
                """, (namespace, key))
                
                # Remove from cache
                cache_key = f"{namespace}:{key}"
                with self._cache_lock:
                    self._cache.pop(cache_key, None)
                
            except Exception as e:
                self.logger.error(f"Error deleting {namespace}:{key}: {e}")
    
    def clear_namespace(self, namespace: str):
        """Clear all data in a namespace"""
        with self._write_lock:
            try:
                conn = self._get_connection()
                cursor = conn.cursor()
                
                cursor.execute("""
                    DELETE FROM memory
                    WHERE namespace = ? AND key != '__namespace_created__'
                """, (namespace,))
                
                # Clear cache for this namespace
                with self._cache_lock:
                    keys_to_remove = [k for k in self._cache if k.startswith(f"{namespace}:")]
                    for key in keys_to_remove:
                        del self._cache[key]
                
            except Exception as e:
                self.logger.error(f"Error clearing namespace {namespace}: {e}")
    
    def update_heartbeat(self, module_name: str, status: str = "active", metadata: Dict = None):
        """Update module heartbeat"""
        try:
            conn = self._get_connection()
            cursor = conn.cursor()
            
            metadata_json = json.dumps(metadata) if metadata else "{}"
            
            cursor.execute("""
                INSERT OR REPLACE INTO heartbeats
                (module_name, last_heartbeat, status, metadata)
                VALUES (?, ?, ?, ?)
            """, (module_name, time.time(), status, metadata_json))
            
        except Exception as e:
            self.logger.error(f"Error updating heartbeat for {module_name}: {e}")
    
    def get_heartbeats(self) -> Dict[str, Dict]:
        """Get all module heartbeats"""
        try:
            conn = self._get_connection()
            cursor = conn.cursor()
            
            cursor.execute("""
                SELECT module_name, last_heartbeat, status, metadata
                FROM heartbeats
            """)
            
            heartbeats = {}
            for module_name, last_heartbeat, status, metadata_json in cursor.fetchall():
                heartbeats[module_name] = {
                    'last_heartbeat': last_heartbeat,
                    'status': status,
                    'metadata': json.loads(metadata_json)
                }
            
            return heartbeats
            
        except Exception as e:
            self.logger.error(f"Error getting heartbeats: {e}")
            return {}
    
    def log_command(self, command_type: str, command_data: Any, 
                    source_module: str, status: str = "pending"):
        """Log a command to history"""
        try:
            conn = self._get_connection()
            cursor = conn.cursor()
            
            command_json = json.dumps(command_data) if not isinstance(command_data, str) else command_data
            
            cursor.execute("""
                INSERT INTO command_history
                (timestamp, command_type, command_data, source_module, status)
                VALUES (?, ?, ?, ?, ?)
            """, (time.time(), command_type, command_json, source_module, status))
            
        except Exception as e:
            self.logger.error(f"Error logging command: {e}")
    
    def get_command_history(self, limit: int = 100) -> List[Dict]:
        """Get recent command history"""
        try:
            conn = self._get_connection()
            cursor = conn.cursor()
            
            cursor.execute("""
                SELECT timestamp, command_type, command_data, source_module, status
                FROM command_history
                ORDER BY id DESC
                LIMIT ?
            """, (limit,))
            
            history = []
            for row in cursor.fetchall():
                history.append({
                    'timestamp': row[0],
                    'command_type': row[1],
                    'command_data': json.loads(row[2]) if row[2] else None,
                    'source_module': row[3],
                    'status': row[4]
                })
            
            return history
            
        except Exception as e:
            self.logger.error(f"Error getting command history: {e}")
            return []
    
    def log_system_metrics(self, metrics: Dict):
        """Log system metrics"""
        try:
            conn = self._get_connection()
            cursor = conn.cursor()
            
            cursor.execute("""
                INSERT INTO system_metrics
                (timestamp, cpu_usage, memory_usage, latency_ms, active_modules, metrics_json)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (
                time.time(),
                metrics.get('cpu_usage', 0.0),
                metrics.get('memory_usage', 0.0),
                metrics.get('latency_ms', 0.0),
                metrics.get('active_modules', 0),
                json.dumps(metrics)
            ))
            
        except Exception as e:
            self.logger.error(f"Error logging system metrics: {e}")
    
    def subscribe_to_namespace(self, namespace: str, callback: Callable):
        """Subscribe to changes in a namespace"""
        self._namespace_observers[namespace].append(callback)
    
    def unsubscribe_from_namespace(self, namespace: str, callback: Callable):
        """Unsubscribe from namespace changes"""
        if callback in self._namespace_observers[namespace]:
            self._namespace_observers[namespace].remove(callback)
    
    def subscribe_global(self, callback: Callable):
        """Subscribe to all memory changes"""
        self._global_observers.append(callback)
    
    def _notify_observers(self, namespace: str, key: str, value: Any):
        """Notify observers of changes"""
        # Notify namespace-specific observers
        for observer in self._namespace_observers.get(namespace, []):
            try:
                observer(namespace, key, value)
            except Exception as e:
                self.logger.error(f"Error notifying namespace observer: {e}")
        
        # Notify global observers
        for observer in self._global_observers:
            try:
                observer(namespace, key, value)
            except Exception as e:
                self.logger.error(f"Error notifying global observer: {e}")
    
    def cleanup_old_data(self, older_than_seconds: float = 3600):
        """Clean up old data from the database"""
        try:
            conn = self._get_connection()
            cursor = conn.cursor()
            
            cutoff_time = time.time() - older_than_seconds
            
            # Clean old command history
            cursor.execute("""
                DELETE FROM command_history
                WHERE timestamp < ?
            """, (cutoff_time,))
            
            # Clean old system metrics
            cursor.execute("""
                DELETE FROM system_metrics
                WHERE timestamp < ?
            """, (cutoff_time,))
            
            conn.commit()
            
        except Exception as e:
            self.logger.error(f"Error cleaning up old data: {e}")
    
    def close(self):
        """Close database connections"""
        if hasattr(self._thread_local, 'conn'):
            self._thread_local.conn.close()
    
    def get_stats(self) -> Dict:
        """Get memory store statistics"""
        try:
            conn = self._get_connection()
            cursor = conn.cursor()
            
            # Count entries
            cursor.execute("SELECT COUNT(*) FROM memory")
            total_entries = cursor.fetchone()[0]
            
            cursor.execute("SELECT COUNT(DISTINCT namespace) FROM memory")
            total_namespaces = cursor.fetchone()[0]
            
            cursor.execute("SELECT COUNT(*) FROM command_history")
            total_commands = cursor.fetchone()[0]
            
            cursor.execute("SELECT COUNT(*) FROM heartbeats")
            active_modules = cursor.fetchone()[0]
            
            # Get database file size
            db_size = Path(self.db_path).stat().st_size if Path(self.db_path).exists() else 0
            
            return {
                'total_entries': total_entries,
                'total_namespaces': total_namespaces,
                'total_commands': total_commands,
                'active_modules': active_modules,
                'cache_size': len(self._cache),
                'db_size_bytes': db_size,
                'db_size_mb': db_size / (1024 * 1024)
            }
            
        except Exception as e:
            self.logger.error(f"Error getting stats: {e}")
            return {}