#!/usr/bin/env python3
"""
Tests for MuJoCo adapter
"""

import unittest
import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))

from adapters.mujoco_adapter import MuJoCoAdapter


class TestMuJoCoAdapter(unittest.TestCase):
    """Test cases for MuJoCo adapter"""
    
    def setUp(self):
        """Set up test configuration"""
        self.config = {
            'model_path': 'robot_control_system/assets/robots/arm/ur5e.xml',
            'render': False,
            'physics_timestep': 0.001,
            'control_timestep': 0.01,
            'joint_names': [
                'shoulder_pan_joint', 'shoulder_lift_joint', 'elbow_joint',
                'wrist_1_joint', 'wrist_2_joint', 'wrist_3_joint'
            ],
            'gripper_joint': None
        }
    
    def test_adapter_initialization(self):
        """Test adapter initialization"""
        adapter = MuJoCoAdapter(self.config)
        
        self.assertEqual(adapter.model_path, self.config['model_path'])
        self.assertEqual(adapter.render_enabled, False)
        self.assertEqual(adapter.physics_timestep, 0.001)
        self.assertEqual(adapter.control_timestep, 0.01)
        self.assertFalse(adapter.connected)
    
    def test_adapter_connection(self):
        """Test adapter connection and disconnection"""
        adapter = MuJoCoAdapter(self.config)
        
        # Test connection
        result = adapter.connect()
        self.assertTrue(result, "Adapter should connect successfully")
        self.assertTrue(adapter.connected, "Adapter should be marked as connected")
        self.assertIsNotNone(adapter.model, "Model should be loaded")
        self.assertIsNotNone(adapter.data, "Data should be initialized")
        
        # Test disconnection
        adapter.disconnect()
        self.assertFalse(adapter.connected, "Adapter should be marked as disconnected")
    
    def test_joint_commands(self):
        """Test joint command execution"""
        adapter = MuJoCoAdapter(self.config)
        adapter.connect()
        
        try:
            # Test valid joint positions
            joint_names = self.config['joint_names']
            positions = [0.0, -1.5708, 1.5708, -1.5708, -1.5708, 0.0]
            
            result = adapter.send_joint_command(joint_names, positions)
            self.assertTrue(result, "Valid joint command should succeed")
            
            # Test invalid joint count
            result = adapter.send_joint_command(joint_names, [0.0, 0.0])  # Too few positions
            self.assertFalse(result, "Invalid joint command should fail")
            
            # Test invalid joint names
            result = adapter.send_joint_command(['invalid_joint'], [0.0])
            self.assertFalse(result, "Command with invalid joint names should fail")
            
        finally:
            adapter.disconnect()
    
    def test_cartesian_commands(self):
        """Test Cartesian command execution"""
        adapter = MuJoCoAdapter(self.config)
        adapter.connect()
        
        try:
            # Test valid Cartesian position
            position = [0.5, 0.0, 0.5]  # x, y, z
            orientation = [1.0, 0.0, 0.0, 0.0]  # quaternion w, x, y, z
            
            result = adapter.send_cartesian_command(position, orientation)
            self.assertTrue(result, "Valid Cartesian command should succeed")
            
            # Test invalid position (too few coordinates)
            result = adapter.send_cartesian_command([0.5, 0.0], orientation)
            self.assertFalse(result, "Invalid Cartesian command should fail")
            
        finally:
            adapter.disconnect()
    
    def test_simulation_step(self):
        """Test simulation stepping"""
        adapter = MuJoCoAdapter(self.config)
        adapter.connect()
        
        try:
            initial_time = adapter.data.time
            
            # Step simulation
            adapter.step_simulation()
            
            # Time should advance
            self.assertGreater(adapter.data.time, initial_time, "Simulation time should advance")
            
        finally:
            adapter.disconnect()
    
    def test_joint_limits(self):
        """Test joint limit enforcement"""
        adapter = MuJoCoAdapter(self.config)
        adapter.connect()
        
        try:
            joint_names = self.config['joint_names']
            
            # Test positions within limits
            valid_positions = [0.0, -1.0, 1.0, -1.0, -1.0, 0.0]
            result = adapter.send_joint_command(joint_names, valid_positions)
            self.assertTrue(result, "Positions within limits should succeed")
            
            # Test positions beyond limits (very large values)
            extreme_positions = [10.0, -10.0, 10.0, -10.0, -10.0, 10.0]
            result = adapter.send_joint_command(joint_names, extreme_positions)
            # Should still succeed but positions will be clamped
            self.assertTrue(result, "Extreme positions should be clamped and succeed")
            
        finally:
            adapter.disconnect()
    
    def test_error_handling(self):
        """Test error handling for invalid operations"""
        adapter = MuJoCoAdapter(self.config)
        
        # Test operations without connection
        result = adapter.send_joint_command(['joint1'], [0.0])
        self.assertFalse(result, "Commands should fail when not connected")
        
        result = adapter.send_cartesian_command([0.0, 0.0, 0.0], [1.0, 0.0, 0.0, 0.0])
        self.assertFalse(result, "Commands should fail when not connected")
        
        # Test with invalid model path
        invalid_config = self.config.copy()
        invalid_config['model_path'] = 'nonexistent/path.xml'
        
        invalid_adapter = MuJoCoAdapter(invalid_config)
        result = invalid_adapter.connect()
        self.assertFalse(result, "Connection should fail with invalid model path")


if __name__ == '__main__':
    unittest.main()