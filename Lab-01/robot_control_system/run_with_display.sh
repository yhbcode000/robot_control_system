#!/bin/bash
# Script to run the robot control system with proper display settings

# Try to detect display
if [ -z "$DISPLAY" ]; then
    echo "DISPLAY not set, trying to detect..."
    
    # Check for X11 sockets
    if [ -e /tmp/.X11-unix/X1 ]; then
        export DISPLAY=:1
        echo "Using DISPLAY=:1"
    elif [ -e /tmp/.X11-unix/X0 ]; then
        export DISPLAY=:0
        echo "Using DISPLAY=:0"
    else
        echo "Warning: No X11 display detected, MuJoCo viewer may not work"
        echo "Running in headless mode..."
    fi
else
    echo "Using existing DISPLAY=$DISPLAY"
fi

# Run the robot control system
echo "Starting Robot Control System..."
echo "Press Ctrl+C to stop"
echo ""
echo "Keyboard Controls:"
echo "  W/S: Forward/Backward"
echo "  A/D: Left/Right"
echo "  Q/E: Up/Down"
echo "  Arrow Keys: Rotation"
echo "  Space: Toggle Gripper"
echo "  ESC: Emergency Stop"
echo ""

# Run with timeout if specified
if [ "$1" = "--timeout" ] && [ -n "$2" ]; then
    echo "Running with timeout: $2 seconds"
    timeout "$2" uv run main.py
else
    uv run main.py
fi