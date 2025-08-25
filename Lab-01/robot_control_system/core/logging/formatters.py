import colorlog
import logging


def get_console_formatter():
    return colorlog.ColoredFormatter(
        "%(log_color)s%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        datefmt='%H:%M:%S',
        reset=True,
        log_colors={
            'DEBUG': 'cyan',
            'INFO': 'green',
            'WARNING': 'yellow',
            'ERROR': 'red',
            'CRITICAL': 'red,bg_white',
        },
        secondary_log_colors={},
        style='%'
    )


def get_file_formatter():
    return logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )


class ModuleFormatter(logging.Formatter):
    def __init__(self, module_name: str, color: str = 'white'):
        super().__init__()
        self.module_name = module_name
        self.color = color
        self._setup_formatter()
    
    def _setup_formatter(self):
        self.formatter = colorlog.ColoredFormatter(
            f"%(log_color)s%(asctime)s - [{self.module_name:^10}] - %(levelname)s - %(message)s",
            datefmt='%H:%M:%S',
            reset=True,
            log_colors={
                'DEBUG': 'cyan',
                'INFO': self.color,
                'WARNING': 'yellow', 
                'ERROR': 'red',
                'CRITICAL': 'red,bg_white',
            }
        )
    
    def format(self, record):
        return self.formatter.format(record)