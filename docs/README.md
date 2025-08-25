# Documentation

Welcome to the Robot Control System documentation.

## 📚 Documentation Structure

### 📖 [API Reference](./api/)
Complete API documentation for all modules and classes.

### 📝 [Guides](./guides/)
Step-by-step guides for common tasks and configurations.

### 🎓 [Tutorials](./tutorials/)
Comprehensive tutorials for getting started and advanced usage.

## 🚀 Quick Links

- [Installation Guide](../README.md#installation)
- [Configuration Guide](./guides/configuration.md)
- [API Documentation](./api/index.md)
- [Performance Tuning](./guides/performance.md)

## 📋 Available Documentation

### Core System
- [Memory System](./api/memory.md) - Thread-safe memory management
- [Module Architecture](./api/modules.md) - Modular system design
- [Observer Pattern](./api/observer.md) - Event notification system

### Modules
- [Watchdog Module](./api/watchdog.md) - Health monitoring and alerts
- [Input Module](./api/input.md) - Keyboard and mouse handling
- [Sense Module](./api/sense.md) - Input parsing and validation
- [Plan Module](./api/plan.md) - Trajectory planning and generation
- [Act Module](./api/act.md) - Command execution and control
- [Output Module](./api/output.md) - Signal formatting and output

### Adapters
- [MuJoCo Adapter](./api/mujoco.md) - Physics simulation interface
- [Robot Models](./api/models.md) - Data structures and types

### Utilities
- [Configuration](./guides/configuration.md) - System configuration management
- [Logging](./guides/logging.md) - Structured logging system
- [Testing](./guides/testing.md) - Test suite and validation

## 🔧 Building Documentation

To build the full documentation locally:

```bash
# Install documentation dependencies
uv install --group docs

# Build documentation
sphinx-build -b html docs/ docs/_build/
```

## 🤝 Contributing to Documentation

We welcome contributions to improve our documentation:

1. **Fix typos and errors** - Simple corrections are always appreciated
2. **Add examples** - Real-world usage examples help everyone
3. **Expand guides** - More detailed explanations for complex topics
4. **API documentation** - Keep code documentation up-to-date

See our [Contributing Guide](../CONTRIBUTING.md) for more details.