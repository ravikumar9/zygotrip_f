import json
import logging
from datetime import datetime


class JSONFormatter(logging.Formatter):
    """
    Custom JSON formatter for structured logging.
    Converts log records to JSON format for better parsing and analysis.
    """
    
    def format(self, record):
        """Convert log record to JSON"""
        log_data = {
            'timestamp': datetime.utcnow().isoformat(),
            'level': record.levelname,
            'logger': record.name,
            'message': record.getMessage(),
            'module': record.module,
            'function': record.funcName,
            'line': record.lineno,
        }
        
        # Add exception info if present
        if record.exc_info:
            log_data['exception'] = self.formatException(record.exc_info)
        
        # Add custom fields from extra dict
        if hasattr(record, '__dict__'):
            for key, value in record.__dict__.items():
                # Skip standard logging fields
                if not key.startswith('_') and \
                   key not in ('name', 'msg', 'args', 'created', 'filename',
                               'funcName', 'levelname', 'levelno', 'lineno',
                               'module', 'msecs', 'message', 'pathname', 'process',
                               'processName', 'relativeCreated', 'thread', 'threadName',
                               'exc_info', 'exc_text', 'stack_info'):
                    log_data[key] = value
        
        return json.dumps(log_data, default=str)