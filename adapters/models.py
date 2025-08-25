from dataclasses import dataclass, field
from typing import Dict, Any, List, Optional
from enum import Enum
import time


class ConnectionState(Enum):
    DISCONNECTED = "disconnected"
    CONNECTING = "connecting"
    CONNECTED = "connected"
    ERROR = "error"
    RECONNECTING = "reconnecting"


class AdapterStatus(Enum):
    IDLE = "idle"
    ACTIVE = "active"
    ERROR = "error"
    EMERGENCY = "emergency"
    MAINTENANCE = "maintenance"


@dataclass
class AdapterCapabilities:
    """Capabilities supported by an adapter"""
    joint_control: bool = True
    cartesian_control: bool = False
    gripper_control: bool = False
    force_control: bool = False
    impedance_control: bool = False
    trajectory_following: bool = False
    real_time_control: bool = False
    
    # Advanced capabilities
    collision_detection: bool = False
    self_collision_detection: bool = False
    workspace_monitoring: bool = False
    joint_limit_monitoring: bool = False
    
    # Simulation specific
    physics_simulation: bool = False
    visualization: bool = False
    sensor_simulation: bool = False
    
    # Communication
    low_latency_control: bool = False
    high_frequency_control: bool = False  # >1kHz
    batch_commands: bool = False


@dataclass
class ConnectionConfig:
    """Configuration for adapter connection"""
    host: str = "localhost"
    port: int = 12345
    timeout: float = 5.0
    retry_attempts: int = 3
    retry_delay: float = 1.0
    heartbeat_interval: float = 1.0
    
    # Authentication
    username: Optional[str] = None
    password: Optional[str] = None
    api_key: Optional[str] = None
    
    # Connection options
    use_ssl: bool = False
    verify_certificate: bool = True
    
    def validate(self) -> bool:
        """Validate connection configuration"""
        if self.timeout <= 0:
            return False
        if self.retry_attempts < 0:
            return False
        if self.port < 1 or self.port > 65535:
            return False
        return True


@dataclass
class AdapterMetrics:
    """Performance metrics for adapter"""
    # Command statistics
    total_commands: int = 0
    successful_commands: int = 0
    failed_commands: int = 0
    
    # Timing statistics
    average_latency: float = 0.0
    max_latency: float = 0.0
    min_latency: float = 0.0
    
    # Connection statistics
    total_connections: int = 0
    failed_connections: int = 0
    reconnections: int = 0
    total_uptime: float = 0.0
    
    # Error statistics
    timeout_errors: int = 0
    communication_errors: int = 0
    protocol_errors: int = 0
    
    # Performance indicators
    commands_per_second: float = 0.0
    bytes_sent: int = 0
    bytes_received: int = 0
    
    # Last update
    last_update: float = field(default_factory=time.time)
    
    def get_success_rate(self) -> float:
        """Calculate command success rate"""
        if self.total_commands == 0:
            return 1.0
        return self.successful_commands / self.total_commands
    
    def get_connection_reliability(self) -> float:
        """Calculate connection reliability"""
        if self.total_connections == 0:
            return 1.0
        return (self.total_connections - self.failed_connections) / self.total_connections
    
    def update_command_stats(self, success: bool, latency: float = 0.0):
        """Update command statistics"""
        self.total_commands += 1
        
        if success:
            self.successful_commands += 1
        else:
            self.failed_commands += 1
        
        if latency > 0:
            # Update latency statistics
            if self.average_latency == 0:
                self.average_latency = latency
            else:
                # Exponential moving average
                self.average_latency = 0.9 * self.average_latency + 0.1 * latency
            
            self.max_latency = max(self.max_latency, latency)
            if self.min_latency == 0:
                self.min_latency = latency
            else:
                self.min_latency = min(self.min_latency, latency)
        
        self.last_update = time.time()


@dataclass
class RobotConfiguration:
    """Robot-specific configuration"""
    robot_type: str = "generic"
    dof: int = 6  # Degrees of freedom
    
    # Joint configuration
    joint_names: List[str] = field(default_factory=list)
    joint_limits_min: List[float] = field(default_factory=list)
    joint_limits_max: List[float] = field(default_factory=list)
    joint_velocity_limits: List[float] = field(default_factory=list)
    joint_acceleration_limits: List[float] = field(default_factory=list)
    
    # Workspace configuration
    workspace_min: List[float] = field(default_factory=lambda: [0.1, -0.5, 0.1])
    workspace_max: List[float] = field(default_factory=lambda: [0.8, 0.5, 0.8])
    
    # End effector configuration
    has_gripper: bool = False
    gripper_joint_name: Optional[str] = None
    end_effector_frame: str = "end_effector"
    
    # Safety configuration
    max_velocity: float = 0.5  # m/s
    max_acceleration: float = 1.0  # m/s²
    emergency_stop_deceleration: float = 5.0  # m/s²
    
    # Control configuration
    default_control_mode: str = "position"
    supported_control_modes: List[str] = field(default_factory=lambda: ["position", "velocity"])
    control_frequency: float = 100.0  # Hz
    
    def validate(self) -> bool:
        """Validate robot configuration"""
        if self.dof <= 0:
            return False
        
        if len(self.joint_names) != self.dof:
            return False
        
        if len(self.joint_limits_min) != self.dof or len(self.joint_limits_max) != self.dof:
            return False
        
        # Check joint limits are valid
        for i in range(self.dof):
            if self.joint_limits_min[i] >= self.joint_limits_max[i]:
                return False
        
        if len(self.workspace_min) != 3 or len(self.workspace_max) != 3:
            return False
        
        return True


@dataclass 
class AdapterState:
    """Current state of an adapter"""
    connection_state: ConnectionState = ConnectionState.DISCONNECTED
    adapter_status: AdapterStatus = AdapterStatus.IDLE
    
    # Connection info
    connected_since: Optional[float] = None
    last_heartbeat: float = 0.0
    heartbeat_interval: float = 1.0
    
    # Control state
    last_command_time: float = 0.0
    emergency_stop_active: bool = False
    
    # Error state
    last_error: Optional[str] = None
    error_count: int = 0
    consecutive_errors: int = 0
    
    # Performance state
    current_latency: float = 0.0
    command_queue_size: int = 0
    
    def is_healthy(self) -> bool:
        """Check if adapter is in healthy state"""
        if self.connection_state != ConnectionState.CONNECTED:
            return False
        
        if self.adapter_status == AdapterStatus.ERROR:
            return False
        
        if self.consecutive_errors > 5:
            return False
        
        # Check if heartbeat is recent
        if time.time() - self.last_heartbeat > self.heartbeat_interval * 3:
            return False
        
        return True
    
    def update_heartbeat(self):
        """Update heartbeat timestamp"""
        self.last_heartbeat = time.time()
    
    def record_error(self, error_message: str):
        """Record an error occurrence"""
        self.last_error = error_message
        self.error_count += 1
        self.consecutive_errors += 1
        
        if self.consecutive_errors > 3:
            self.adapter_status = AdapterStatus.ERROR
    
    def clear_errors(self):
        """Clear error state"""
        self.consecutive_errors = 0
        self.last_error = None
        if self.adapter_status == AdapterStatus.ERROR:
            self.adapter_status = AdapterStatus.IDLE


@dataclass
class CommandBuffer:
    """Buffer for storing commands to be sent"""
    commands: List[Dict[str, Any]] = field(default_factory=list)
    max_size: int = 1000
    created_time: float = field(default_factory=time.time)
    
    def add_command(self, command: Dict[str, Any]) -> bool:
        """Add command to buffer"""
        if len(self.commands) >= self.max_size:
            return False  # Buffer full
        
        command['timestamp'] = time.time()
        self.commands.append(command)
        return True
    
    def get_next_command(self) -> Optional[Dict[str, Any]]:
        """Get next command from buffer"""
        if not self.commands:
            return None
        return self.commands.pop(0)
    
    def clear(self):
        """Clear all commands"""
        self.commands.clear()
    
    def size(self) -> int:
        """Get current buffer size"""
        return len(self.commands)
    
    def is_empty(self) -> bool:
        """Check if buffer is empty"""
        return len(self.commands) == 0
    
    def is_full(self) -> bool:
        """Check if buffer is full"""
        return len(self.commands) >= self.max_size


@dataclass
class AdapterDiagnostics:
    """Comprehensive diagnostics for adapter"""
    adapter_info: Dict[str, Any] = field(default_factory=dict)
    connection_info: Dict[str, Any] = field(default_factory=dict)
    performance_metrics: Optional[AdapterMetrics] = None
    capabilities: Optional[AdapterCapabilities] = None
    robot_config: Optional[RobotConfiguration] = None
    current_state: Optional[AdapterState] = None
    
    # System resources
    cpu_usage: float = 0.0
    memory_usage: float = 0.0
    
    # Network stats (for networked adapters)
    network_latency: float = 0.0
    packet_loss: float = 0.0
    bandwidth_utilization: float = 0.0
    
    # Health indicators
    overall_health_score: float = 1.0
    warnings: List[str] = field(default_factory=list)
    errors: List[str] = field(default_factory=list)
    
    # Timestamp
    timestamp: float = field(default_factory=time.time)
    
    def add_warning(self, warning: str):
        """Add a warning message"""
        if warning not in self.warnings:
            self.warnings.append(warning)
    
    def add_error(self, error: str):
        """Add an error message"""
        if error not in self.errors:
            self.errors.append(error)
    
    def calculate_health_score(self) -> float:
        """Calculate overall health score"""
        score = 1.0
        
        # Reduce score for errors and warnings
        score -= len(self.errors) * 0.2
        score -= len(self.warnings) * 0.1
        
        # Consider connection state
        if self.current_state:
            if self.current_state.connection_state != ConnectionState.CONNECTED:
                score -= 0.5
            if self.current_state.adapter_status == AdapterStatus.ERROR:
                score -= 0.3
        
        # Consider performance metrics
        if self.performance_metrics:
            success_rate = self.performance_metrics.get_success_rate()
            score *= success_rate
        
        self.overall_health_score = max(0.0, score)
        return self.overall_health_score