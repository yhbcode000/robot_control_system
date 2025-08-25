from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional
from enum import Enum
import time


class SignalFormat(Enum):
    JSON = "json"
    BINARY = "binary"
    ROS = "ros"
    XML = "xml"
    PROTOBUF = "protobuf"


class OutputStatus(Enum):
    IDLE = "idle"
    ACTIVE = "active"
    ERROR = "error"
    DISCONNECTED = "disconnected"


@dataclass
class OutputState:
    """Current state of the output module"""
    status: OutputStatus = OutputStatus.IDLE
    is_active: bool = False
    adapter_connected: bool = False
    emergency_active: bool = False
    
    # Signal processing
    pending_signals: List[Dict[str, Any]] = field(default_factory=list)
    signals_in_queue: int = 0
    last_send_time: float = 0.0
    
    # Emergency handling
    emergency_signal: Optional[Dict[str, Any]] = None
    
    # Connection info
    adapter_info: Dict[str, Any] = field(default_factory=dict)
    
    # Timing
    last_update_time: float = field(default_factory=time.time)
    last_trajectory_completion: float = 0.0
    
    def has_pending_signals(self) -> bool:
        """Check if there are pending signals to send"""
        return len(self.pending_signals) > 0
    
    def is_sending_regularly(self, threshold: float = 2.0) -> bool:
        """Check if module is sending signals regularly"""
        return (time.time() - self.last_send_time) < threshold
    
    def get_queue_size(self) -> int:
        """Get current queue size"""
        return self.signals_in_queue


@dataclass
class OutputStats:
    """Statistics for output module performance"""
    # Command processing
    total_commands_processed: int = 0
    commands_sent_to_adapter: int = 0
    successful_sends: int = 0
    failed_sends: int = 0
    
    # Error tracking
    formatting_errors: int = 0
    adapter_errors: int = 0
    timeout_errors: int = 0
    
    # Command filtering
    duplicate_commands: int = 0
    stale_commands: int = 0
    
    # Emergency handling
    emergency_commands_sent: int = 0
    emergency_response_time: float = 0.0
    
    # Performance metrics
    success_rate: float = 1.0
    average_send_time: float = 0.0
    throughput: float = 0.0  # commands per second
    
    # Timing
    last_stats_update: float = field(default_factory=time.time)
    
    def update_success_rate(self):
        """Update success rate calculation"""
        total_attempts = self.successful_sends + self.failed_sends
        if total_attempts > 0:
            self.success_rate = self.successful_sends / total_attempts
        else:
            self.success_rate = 1.0
    
    def get_error_rate(self) -> float:
        """Get overall error rate"""
        total_commands = self.total_commands_processed
        total_errors = self.formatting_errors + self.adapter_errors + self.timeout_errors
        
        if total_commands > 0:
            return total_errors / total_commands
        return 0.0
    
    def get_efficiency(self) -> float:
        """Get command processing efficiency (sent vs processed)"""
        if self.total_commands_processed > 0:
            return self.commands_sent_to_adapter / self.total_commands_processed
        return 1.0


@dataclass
class SignalQueueItem:
    """Individual item in the signal queue"""
    signal: Dict[str, Any]
    priority: int = 1  # 1=low, 2=normal, 3=high, 4=critical
    created_time: float = field(default_factory=time.time)
    retry_count: int = 0
    max_retries: int = 3
    
    def is_expired(self, timeout: float = 5.0) -> bool:
        """Check if signal has expired"""
        return (time.time() - self.created_time) > timeout
    
    def can_retry(self) -> bool:
        """Check if signal can be retried"""
        return self.retry_count < self.max_retries
    
    def increment_retry(self):
        """Increment retry count"""
        self.retry_count += 1


@dataclass
class AdapterInterface:
    """Interface definition for adapters"""
    adapter_type: str
    connection_status: bool = False
    last_heartbeat: float = 0.0
    
    # Supported capabilities
    supports_joint_control: bool = True
    supports_cartesian_control: bool = True
    supports_gripper_control: bool = True
    supports_emergency_stop: bool = True
    
    # Performance metrics
    command_latency: float = 0.0  # seconds
    throughput: float = 0.0  # commands per second
    error_count: int = 0
    
    # Configuration
    max_command_rate: float = 100.0  # Hz
    timeout: float = 1.0  # seconds
    
    def is_connected(self) -> bool:
        """Check if adapter is connected"""
        if not self.connection_status:
            return False
        
        # Check if heartbeat is recent
        return (time.time() - self.last_heartbeat) < (self.timeout * 2)
    
    def update_heartbeat(self):
        """Update heartbeat timestamp"""
        self.last_heartbeat = time.time()
    
    def record_command_sent(self, latency: float = 0.0):
        """Record that a command was sent"""
        if latency > 0:
            # Update running average of latency
            if self.command_latency == 0:
                self.command_latency = latency
            else:
                self.command_latency = (self.command_latency * 0.9) + (latency * 0.1)


@dataclass
class OutputConfiguration:
    """Configuration for output module"""
    # Output format settings
    default_format: SignalFormat = SignalFormat.JSON
    supported_formats: List[SignalFormat] = field(default_factory=lambda: [SignalFormat.JSON, SignalFormat.ROS])
    
    # Queue settings
    max_queue_size: int = 1000
    queue_timeout: float = 5.0
    
    # Retry settings
    max_retries: int = 3
    retry_delay: float = 0.1
    
    # Performance settings
    max_send_rate: float = 100.0  # Hz
    batch_size: int = 10
    
    # Logging settings
    enable_command_logging: bool = False
    log_file_path: str = "output.log"
    log_level: str = "INFO"
    
    # Safety settings
    emergency_timeout: float = 0.1  # Max time to process emergency stop
    duplicate_filter_timeout: float = 0.1  # seconds
    
    def validate(self) -> bool:
        """Validate configuration values"""
        if self.max_queue_size <= 0:
            return False
        if self.queue_timeout <= 0:
            return False
        if self.max_send_rate <= 0:
            return False
        if self.emergency_timeout <= 0:
            return False
        
        return True


@dataclass
class CommandMetrics:
    """Metrics for individual command types"""
    command_type: str
    total_sent: int = 0
    successful: int = 0
    failed: int = 0
    average_latency: float = 0.0
    last_sent_time: float = 0.0
    
    def record_send(self, success: bool, latency: float = 0.0):
        """Record a command send attempt"""
        self.total_sent += 1
        self.last_sent_time = time.time()
        
        if success:
            self.successful += 1
        else:
            self.failed += 1
        
        # Update average latency
        if latency > 0:
            if self.average_latency == 0:
                self.average_latency = latency
            else:
                self.average_latency = (self.average_latency * 0.9) + (latency * 0.1)
    
    def get_success_rate(self) -> float:
        """Get success rate for this command type"""
        if self.total_sent == 0:
            return 1.0
        return self.successful / self.total_sent


@dataclass
class OutputLog:
    """Log entry for output operations"""
    timestamp: float = field(default_factory=time.time)
    level: str = "INFO"  # DEBUG, INFO, WARNING, ERROR, CRITICAL
    message: str = ""
    command_type: Optional[str] = None
    success: Optional[bool] = None
    latency: Optional[float] = None
    error_details: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization"""
        return {
            'timestamp': self.timestamp,
            'level': self.level,
            'message': self.message,
            'command_type': self.command_type,
            'success': self.success,
            'latency': self.latency,
            'error_details': self.error_details
        }


@dataclass
class SystemHealth:
    """System health metrics for output module"""
    cpu_usage: float = 0.0
    memory_usage: float = 0.0
    queue_utilization: float = 0.0  # percentage of queue filled
    
    # Connection health
    adapter_connection_health: float = 1.0  # 0.0 to 1.0
    communication_latency: float = 0.0
    
    # Error rates
    recent_error_rate: float = 0.0  # errors in last minute
    overall_error_rate: float = 0.0
    
    # Performance indicators
    throughput_health: float = 1.0  # current vs expected throughput
    response_time_health: float = 1.0  # current vs target response time
    
    def get_overall_health_score(self) -> float:
        """Calculate overall health score (0.0 to 1.0)"""
        scores = [
            1.0 - min(self.cpu_usage / 100.0, 1.0),  # Invert CPU usage
            1.0 - min(self.memory_usage / 100.0, 1.0),  # Invert memory usage
            1.0 - min(self.queue_utilization, 1.0),  # Invert queue utilization
            self.adapter_connection_health,
            1.0 - min(self.recent_error_rate, 1.0),  # Invert error rate
            self.throughput_health,
            self.response_time_health
        ]
        
        return sum(scores) / len(scores)