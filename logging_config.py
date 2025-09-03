import logging
import sys
import json

from config import config

# 日志格式化器
class JsonFormatter(logging.Formatter):
    def format(self, record):
        log_object = {
            "timestamp": self.formatTime(record, self.datefmt),
            "level": record.levelname,
            "message": record.getMessage(),
            "name": record.name,
        }
        if record.exc_info:
            log_object['exc_info'] = self.formatException(record.exc_info)
        return json.dumps(log_object, ensure_ascii=False)

# 日志配置字典
LOGGING_CONFIG = {
    'version': 1,
    'disable_existing_loggers': False,
    'formatters': {
        'default': {
            'format': '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        },
        'json': {
            '()': JsonFormatter,
        },
        'detailed': {
            'format': '%(asctime)s - %(name)s - %(levelname)s - [%(filename)s:%(lineno)d] - %(message)s',
        },
    },
    'handlers': {
        'console': {
            'class': 'logging.StreamHandler',
            'stream': sys.stdout,
            'formatter': 'detailed',
        },
    },
    'loggers': {
        'uvicorn': {
            'handlers': ['console'],
            'level': 'INFO',
            'propagate': False,
        },
        'fastapi': {
            'handlers': ['console'],
            'level': 'INFO',
            'propagate': False,
        },
        'app': {
            'handlers': ['console'],
            'level': 'DEBUG',
            'propagate': False,
        }
    },
    'root': {
        'level': 'INFO',
        'handlers': ['console'],
    },
}

def setup_logging():
    """根据环境配置日志"""
    env = config.APP_ENV
    
    if env == 'production':
        LOGGING_CONFIG['handlers']['console']['formatter'] = 'default'
        LOGGING_CONFIG['loggers']['app']['handlers'] = ['console', 'file']
        LOGGING_CONFIG['loggers']['uvicorn']['handlers'] = ['console', 'file']
        LOGGING_CONFIG['loggers']['fastapi']['handlers'] = ['console', 'file']
    else: # development
        # 开发环境使用详细格式，便于调试
        LOGGING_CONFIG['handlers']['console']['formatter'] = 'detailed'
        LOGGING_CONFIG['loggers']['app']['handlers'] = ['console']
        LOGGING_CONFIG['loggers']['uvicorn']['handlers'] = ['console']
        LOGGING_CONFIG['loggers']['fastapi']['handlers'] = ['console']
        
    logging.config.dictConfig(LOGGING_CONFIG)

__all__ = ['setup_logging', 'LOGGING_CONFIG'] 