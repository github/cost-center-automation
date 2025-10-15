"""
Logger setup and configuration.
"""

import logging
import logging.config
import sys
from pathlib import Path
import yaml


class BrokenPipeHandler(logging.StreamHandler):
    """Custom logging handler that gracefully handles broken pipe errors."""
    
    def emit(self, record):
        """Emit a record, handling broken pipe errors gracefully."""
        try:
            super().emit(record)
        except BrokenPipeError:
            # Pipe was closed (e.g., output piped to head), exit gracefully
            sys.exit(0)
        except OSError as e:
            if e.errno == 32:  # Broken pipe
                sys.exit(0)
            else:
                raise


def setup_logging(level=logging.INFO, config_file=None):
    """Setup logging configuration."""
    
    # Create logs directory
    log_dir = Path("logs")
    log_dir.mkdir(exist_ok=True)
    
    if config_file and Path(config_file).exists():
        # Load logging config from file
        with open(config_file, 'r') as f:
            config = yaml.safe_load(f)
        logging.config.dictConfig(config)
    else:
        # Default logging configuration
        logging_config = {
            'version': 1,
            'disable_existing_loggers': False,
            'formatters': {
                'standard': {
                    'format': '%(asctime)s [%(levelname)s] %(name)s: %(message)s',
                    'datefmt': '%Y-%m-%d %H:%M:%S'
                },
                'detailed': {
                    'format': '%(asctime)s [%(levelname)s] %(name)s:%(lineno)d: %(message)s',
                    'datefmt': '%Y-%m-%d %H:%M:%S'
                }
            },
            'handlers': {
                'console': {
                    'level': 'INFO',
                    'class': 'src.logger_setup.BrokenPipeHandler',
                    'formatter': 'standard',
                    'stream': 'ext://sys.stdout'
                },
                'file': {
                    'level': 'DEBUG',
                    'class': 'logging.handlers.RotatingFileHandler',
                    'formatter': 'detailed',
                    'filename': 'logs/copilot_manager.log',
                    'maxBytes': 10485760,  # 10MB
                    'backupCount': 5,
                    'encoding': 'utf-8'
                }
            },
            'loggers': {
                '': {  # root logger
                    'handlers': ['console', 'file'],
                    'level': level,
                    'propagate': False
                },
                'requests.packages.urllib3': {
                    'level': 'WARNING'
                }
            }
        }
        
        logging.config.dictConfig(logging_config)
    
    # Set the console handler level based on the parameter
    root_logger = logging.getLogger()
    for handler in root_logger.handlers:
        if isinstance(handler, logging.StreamHandler) and handler.stream.name == '<stdout>':
            handler.setLevel(level)


def get_logger(name):
    """Get a logger instance."""
    return logging.getLogger(name)