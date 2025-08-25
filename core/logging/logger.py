import logging
import colorlog
from typing import Optional
from .formatters import get_console_formatter, get_file_formatter, ModuleFormatter


def setup_logging(config: dict):
    """Setup logging with error resilience and fallback options"""
    level = getattr(logging, config.get('level', 'INFO').upper())
    
    # Root logger configuration
    root_logger = logging.getLogger()
    root_logger.setLevel(level)
    
    # Remove existing handlers
    for handler in root_logger.handlers[:]:
        root_logger.removeHandler(handler)
    
    try:
        # Console handler with color
        if config.get('colorful', True):
            console_handler = colorlog.StreamHandler()
            console_handler.setFormatter(get_console_formatter())
        else:
            console_handler = logging.StreamHandler()
            console_handler.setFormatter(get_file_formatter())
        
        console_handler.setLevel(level)
        root_logger.addHandler(console_handler)
        
    except Exception as e:
        # Fallback to basic logging if colorlog fails
        print(f"Warning: Colored logging failed ({e}), falling back to basic logging")
        console_handler = logging.StreamHandler()
        console_handler.setFormatter(get_file_formatter())
        console_handler.setLevel(level)
        root_logger.addHandler(console_handler)
    
    try:
        # Optional file handler
        if config.get('file'):
            file_handler = logging.FileHandler(config['file'])
            file_handler.setFormatter(get_file_formatter())
            file_handler.setLevel(level)
            root_logger.addHandler(file_handler)
    except Exception as e:
        print(f"Warning: File logging failed ({e}), continuing without file logging")
    
    return root_logger


def get_module_logger(module_name: str, color: Optional[str] = None) -> logging.Logger:
    """Get module-specific logger with error resilience"""
    logger = logging.getLogger(module_name)
    
    # Don't add handlers if they already exist
    if not logger.handlers:
        try:
            # Create module-specific console handler
            console_handler = colorlog.StreamHandler()
            
            # Define colors for different modules
            module_colors = {
                'Watchdog': 'red',
                'Input': 'blue',
                'Sense': 'cyan',
                'Plan': 'green',
                'Act': 'yellow',
                'Output': 'purple',
            }
            
            color = color or module_colors.get(module_name, 'white')
            formatter = ModuleFormatter(module_name, color)
            console_handler.setFormatter(formatter)
            
            logger.addHandler(console_handler)
            logger.setLevel(logging.DEBUG)
            logger.propagate = False
            
        except Exception as e:
            # Fallback to basic logging if colored logging fails
            print(f"Warning: Colored logging failed for {module_name} ({e}), using basic logging")
            console_handler = logging.StreamHandler()
            basic_formatter = logging.Formatter(
                f'%(asctime)s - [{module_name:^10}] - %(levelname)s - %(message)s',
                datefmt='%H:%M:%S'
            )
            console_handler.setFormatter(basic_formatter)
            logger.addHandler(console_handler)
            logger.setLevel(logging.DEBUG)
            logger.propagate = False
    
    return logger