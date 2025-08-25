from .base_adapter import BaseAdapter, AdapterType
from .mujoco_adapter import MuJoCoAdapter
from .models import ConnectionState, AdapterStatus, AdapterCapabilities

def create_adapter(config):
    """Factory function to create appropriate adapter"""
    adapter_type = config.get('type', 'mujoco').lower()
    
    if adapter_type == 'mujoco':
        return MuJoCoAdapter(config)
    else:
        raise ValueError(f"Unknown adapter type: {adapter_type}")

__all__ = ['BaseAdapter', 'MuJoCoAdapter', 'AdapterType', 'ConnectionState', 'AdapterStatus', 'create_adapter']