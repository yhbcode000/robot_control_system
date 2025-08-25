# Installation Guide

This guide covers different ways to install and set up the Robot Control System.

## 📋 Prerequisites

- **Python**: 3.11 or higher
- **Operating System**: Linux, macOS, or Windows
- **Package Manager**: [uv](https://docs.astral.sh/uv/) (recommended) or pip

## 🚀 Quick Installation

### Using uv (Recommended)

```bash
# Clone the repository
git clone https://github.com/your-username/robot-control-system.git
cd robot-control-system

# Install dependencies
uv sync

# Run the system
uv run python main.py
```

### Using pip

```bash
# Clone the repository
git clone https://github.com/your-username/robot-control-system.git
cd robot-control-system

# Create virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Run the system
python main.py
```

## 🔧 Development Installation

For development work, install with development dependencies:

```bash
# Using uv
uv sync --group dev

# Using pip
pip install -r requirements.txt
pip install pytest black flake8 mypy pre-commit
```

## 🖥️ System Requirements

### Minimum Requirements
- **RAM**: 2GB available memory
- **CPU**: Dual-core processor
- **Storage**: 1GB free space
- **Graphics**: OpenGL 3.3 support (for MuJoCo visualization)

### Recommended Requirements
- **RAM**: 8GB+ for optimal performance
- **CPU**: Quad-core processor or better
- **Storage**: 5GB+ free space
- **Graphics**: Dedicated GPU (for complex simulations)

## 🎮 Hardware Support

### Input Devices
- Standard keyboard (required)
- Mouse (optional, for advanced control)
- Game controllers (future support planned)

### Display
- Monitor with 1920x1080 resolution or higher
- OpenGL 3.3+ compatible graphics driver

## 🔍 Verifying Installation

Test your installation:

```bash
# Run system tests
uv run python run_tests.py

# Quick performance check
uv run python scripts/simple_perf_check.py

# Test with viewer
uv run python scripts/test_with_viewer.py
```

Expected output:
- All tests should pass (green checkmarks)
- Performance metrics should show "EXCELLENT" rating
- MuJoCo viewer should display the robot arm

## ❗ Troubleshooting

### Common Issues

#### MuJoCo Installation Problems
```bash
# Update MuJoCo
pip install --upgrade mujoco

# On Linux, you may need additional packages
sudo apt-get install libglew-dev libglfw3-dev
```

#### Permission Errors
```bash
# On Linux/macOS, ensure proper permissions
chmod +x run_with_display.sh
```

#### Import Errors
```bash
# Verify Python path
export PYTHONPATH="${PYTHONPATH}:/path/to/robot_control_system"
```

### Platform-Specific Notes

#### Linux
- Install system dependencies:
  ```bash
  sudo apt-get update
  sudo apt-get install python3-dev build-essential
  ```

#### macOS
- Install Xcode command line tools:
  ```bash
  xcode-select --install
  ```

#### Windows
- Install Microsoft Visual C++ Build Tools
- Use PowerShell or Command Prompt (not Git Bash)

## 🚀 Next Steps

After successful installation:

1. **Read the [Configuration Guide](./configuration.md)**
2. **Try the [Quick Start Tutorial](../tutorials/quickstart.md)**
3. **Explore the [Examples](../../examples/)**
4. **Check the [API Documentation](../api/index.md)**

## 💡 Tips

- Use `uv` for faster dependency management
- Create isolated environments for different projects
- Keep dependencies up-to-date with `uv sync --upgrade`
- Use the provided test scripts to verify functionality

## 🆘 Getting Help

If you encounter issues:

1. **Check the [FAQ](./faq.md)**
2. **Search existing [GitHub Issues](https://github.com/your-username/robot-control-system/issues)**
3. **Create a new issue** with detailed error information
4. **Join our community discussions**