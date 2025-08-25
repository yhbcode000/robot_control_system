"""Inverse Kinematics solver for end-effector control"""

import numpy as np
from typing import Optional, Tuple, List
from scipy.optimize import minimize
import time

class InverseKinematics:
    """Inverse kinematics solver for 6-DOF robot arm"""
    
    def __init__(self, config: dict = None):
        self.config = config or {}
        
        # Robot parameters (UR5e-like configuration)
        # Link lengths in meters
        self.d1 = 0.1625    # Base to shoulder
        self.a2 = -0.425    # Shoulder to elbow
        self.a3 = -0.3922   # Elbow to wrist 1
        self.d4 = 0.1333    # Wrist 1 to wrist 2
        self.d5 = 0.0997    # Wrist 2 to wrist 3
        self.d6 = 0.0996    # Wrist 3 to end-effector
        
        # Joint limits (radians)
        self.joint_limits = [
            (-np.pi, np.pi),      # Joint 1: Base rotation
            (-np.pi, np.pi),      # Joint 2: Shoulder
            (-np.pi, np.pi),      # Joint 3: Elbow
            (-np.pi, np.pi),      # Joint 4: Wrist 1
            (-np.pi, np.pi),      # Joint 5: Wrist 2
            (-np.pi, np.pi),      # Joint 6: Wrist 3
        ]
        
        # Workspace limits (meters) - expanded for UR5e-like robot
        self.workspace_limits = {
            'x': (-1.2, 1.2),
            'y': (-1.2, 1.2), 
            'z': (-0.2, 1.5)
        }
        
        # Solver parameters
        self.max_iterations = 100
        self.position_tolerance = 0.001  # 1mm
        self.orientation_tolerance = 0.01  # ~0.57 degrees
        
    def forward_kinematics(self, joint_angles: np.ndarray) -> Tuple[np.ndarray, np.ndarray]:
        """
        Compute forward kinematics: joint angles -> end-effector pose
        
        Args:
            joint_angles: Array of 6 joint angles (radians)
            
        Returns:
            position: 3D position vector [x, y, z]
            orientation: Quaternion [x, y, z, w]
        """
        q = joint_angles
        
        # DH parameters for UR5e
        # [theta, d, a, alpha]
        dh_params = np.array([
            [q[0],           self.d1,    0,         np.pi/2],
            [q[1] - np.pi/2, 0,          self.a2,   0],
            [q[2],           0,          self.a3,   0],
            [q[3] - np.pi/2, self.d4,    0,         np.pi/2],
            [q[4],           self.d5,    0,         -np.pi/2],
            [q[5],           self.d6,    0,         0]
        ])
        
        # Build transformation matrices
        T = np.eye(4)
        
        for i in range(6):
            theta, d, a, alpha = dh_params[i]
            
            # DH transformation matrix
            ct = np.cos(theta)
            st = np.sin(theta)
            ca = np.cos(alpha)
            sa = np.sin(alpha)
            
            Ti = np.array([
                [ct,    -st*ca,  st*sa,   a*ct],
                [st,     ct*ca, -ct*sa,   a*st],
                [0,      sa,     ca,      d],
                [0,      0,      0,       1]
            ])
            
            T = T @ Ti
        
        # Extract position
        position = T[:3, 3]
        
        # Extract orientation as quaternion
        R = T[:3, :3]
        orientation = self._rotation_matrix_to_quaternion(R)
        
        return position, orientation
    
    def inverse_kinematics(self, target_position: np.ndarray, 
                          target_orientation: Optional[np.ndarray] = None,
                          initial_guess: Optional[np.ndarray] = None) -> Tuple[Optional[np.ndarray], bool]:
        """
        Solve inverse kinematics: end-effector pose -> joint angles
        
        Args:
            target_position: Target 3D position [x, y, z]
            target_orientation: Target quaternion [x, y, z, w] (optional)
            initial_guess: Initial joint angles for optimization
            
        Returns:
            joint_angles: Solution joint angles (None if no solution found)
            success: Whether solution was found
        """
        # Check workspace limits
        if not self._check_workspace_limits(target_position):
            return None, False
        
        # Use current pose as initial guess if not provided
        if initial_guess is None:
            initial_guess = np.zeros(6)
        
        # Default orientation (pointing down)
        if target_orientation is None:
            target_orientation = np.array([0, 1, 0, 0])  # Pointing down
        
        def objective_function(q):
            """Objective function to minimize"""
            try:
                # Ensure joint limits
                for i, (q_min, q_max) in enumerate(self.joint_limits):
                    if q[i] < q_min or q[i] > q_max:
                        return 1e6  # Large penalty for joint limit violation
                
                # Forward kinematics
                pos, ori = self.forward_kinematics(q)
                
                # Position error
                pos_error = np.linalg.norm(pos - target_position)
                
                # Orientation error (simplified - just use quaternion distance)
                ori_error = 1.0 - np.abs(np.dot(ori, target_orientation))
                
                # Combined error with weights
                total_error = pos_error + 0.1 * ori_error
                
                return total_error
                
            except Exception as e:
                return 1e6  # Return large error if computation fails
        
        # Set up optimization bounds
        bounds = [(q_min, q_max) for q_min, q_max in self.joint_limits]
        
        # Solve using multiple methods/initial guesses for robustness
        best_solution = None
        best_error = float('inf')
        
        # Try different initial guesses
        initial_guesses = [
            initial_guess,
            np.zeros(6),
            np.array([0, -np.pi/4, np.pi/2, -np.pi/4, np.pi/2, 0]),  # Common pose
            np.array([np.pi/2, -np.pi/3, np.pi/3, -np.pi/3, np.pi/2, 0]),  # Another pose
        ]
        
        for guess in initial_guesses:
            try:
                # Scipy optimization
                result = minimize(
                    objective_function,
                    guess,
                    method='L-BFGS-B',
                    bounds=bounds,
                    options={'maxiter': self.max_iterations}
                )
                
                if result.success and result.fun < best_error:
                    best_solution = result.x
                    best_error = result.fun
                    
                    # If error is small enough, we're done
                    if best_error < self.position_tolerance:
                        break
                        
            except Exception as e:
                continue
        
        # Check if solution is good enough
        if best_solution is not None and best_error < 0.01:  # 1cm tolerance
            return best_solution, True
        
        return None, False
    
    def solve_position_ik(self, target_position: np.ndarray,
                         current_joints: Optional[np.ndarray] = None) -> Tuple[Optional[np.ndarray], bool]:
        """
        Solve IK for position only (orientation-free)
        
        Args:
            target_position: Target 3D position [x, y, z]
            current_joints: Current joint configuration for initial guess
            
        Returns:
            joint_angles: Solution joint angles
            success: Whether solution was found
        """
        return self.inverse_kinematics(
            target_position, 
            target_orientation=None,
            initial_guess=current_joints
        )
    
    def jacobian_ik(self, target_position: np.ndarray, 
                   current_joints: np.ndarray,
                   max_iterations: int = 50,
                   step_size: float = 0.1) -> Tuple[Optional[np.ndarray], bool]:
        """
        Jacobian-based iterative IK solver (faster but less robust)
        
        Args:
            target_position: Target 3D position
            current_joints: Current joint configuration
            max_iterations: Maximum iterations
            step_size: Step size for updates
            
        Returns:
            joint_angles: Solution joint angles
            success: Whether solution was found
        """
        q = current_joints.copy()
        
        for iteration in range(max_iterations):
            # Forward kinematics
            current_pos, _ = self.forward_kinematics(q)
            
            # Position error
            error = target_position - current_pos
            error_magnitude = np.linalg.norm(error)
            
            # Check convergence
            if error_magnitude < self.position_tolerance:
                return q, True
            
            # Compute Jacobian numerically
            J = self._compute_jacobian(q)
            
            # Pseudo-inverse for joint updates
            try:
                # Damped least squares to avoid singularities
                damping = 0.01
                J_pinv = J.T @ np.linalg.inv(J @ J.T + damping * np.eye(3))
                
                # Update joint angles
                dq = step_size * J_pinv @ error
                q += dq
                
                # Enforce joint limits
                for i, (q_min, q_max) in enumerate(self.joint_limits):
                    q[i] = np.clip(q[i], q_min, q_max)
                    
            except np.linalg.LinAlgError:
                # Singular configuration
                return None, False
        
        return None, False
    
    def _compute_jacobian(self, joint_angles: np.ndarray, epsilon: float = 1e-6) -> np.ndarray:
        """Compute numerical Jacobian matrix"""
        J = np.zeros((3, 6))  # 3D position, 6 joints
        
        # Current position
        pos0, _ = self.forward_kinematics(joint_angles)
        
        # Numerical differentiation
        for i in range(6):
            q_plus = joint_angles.copy()
            q_plus[i] += epsilon
            
            pos_plus, _ = self.forward_kinematics(q_plus)
            
            # Partial derivative
            J[:, i] = (pos_plus - pos0) / epsilon
        
        return J
    
    def _check_workspace_limits(self, position: np.ndarray) -> bool:
        """Check if position is within workspace limits"""
        x, y, z = position
        
        x_min, x_max = self.workspace_limits['x']
        y_min, y_max = self.workspace_limits['y']
        z_min, z_max = self.workspace_limits['z']
        
        return (x_min <= x <= x_max and 
                y_min <= y <= y_max and 
                z_min <= z <= z_max)
    
    def _rotation_matrix_to_quaternion(self, R: np.ndarray) -> np.ndarray:
        """Convert rotation matrix to quaternion [x, y, z, w]"""
        trace = np.trace(R)
        
        if trace > 0:
            s = np.sqrt(trace + 1.0) * 2  # s = 4 * qw
            qw = 0.25 * s
            qx = (R[2, 1] - R[1, 2]) / s
            qy = (R[0, 2] - R[2, 0]) / s
            qz = (R[1, 0] - R[0, 1]) / s
        elif R[0, 0] > R[1, 1] and R[0, 0] > R[2, 2]:
            s = np.sqrt(1.0 + R[0, 0] - R[1, 1] - R[2, 2]) * 2  # s = 4 * qx
            qw = (R[2, 1] - R[1, 2]) / s
            qx = 0.25 * s
            qy = (R[0, 1] + R[1, 0]) / s
            qz = (R[0, 2] + R[2, 0]) / s
        elif R[1, 1] > R[2, 2]:
            s = np.sqrt(1.0 + R[1, 1] - R[0, 0] - R[2, 2]) * 2  # s = 4 * qy
            qw = (R[0, 2] - R[2, 0]) / s
            qx = (R[0, 1] + R[1, 0]) / s
            qy = 0.25 * s
            qz = (R[1, 2] + R[2, 1]) / s
        else:
            s = np.sqrt(1.0 + R[2, 2] - R[0, 0] - R[1, 1]) * 2  # s = 4 * qz
            qw = (R[1, 0] - R[0, 1]) / s
            qx = (R[0, 2] + R[2, 0]) / s
            qy = (R[1, 2] + R[2, 1]) / s
            qz = 0.25 * s
        
        return np.array([qx, qy, qz, qw])
    
    def get_workspace_center(self) -> np.ndarray:
        """Get center of workspace"""
        x_center = np.mean(self.workspace_limits['x'])
        y_center = np.mean(self.workspace_limits['y'])
        z_center = np.mean(self.workspace_limits['z'])
        return np.array([x_center, y_center, z_center])
    
    def get_reachable_position(self, position: np.ndarray) -> np.ndarray:
        """Clamp position to reachable workspace"""
        x, y, z = position
        
        x = np.clip(x, *self.workspace_limits['x'])
        y = np.clip(y, *self.workspace_limits['y'])
        z = np.clip(z, *self.workspace_limits['z'])
        
        return np.array([x, y, z])