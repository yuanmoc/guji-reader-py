import logging
from logging.handlers import RotatingFileHandler

# 日志目录和文件
from core.utils.path_util import get_user_store_path

LOG_FILE = get_user_store_path('logs', 'app.log')

# 日志格式
LOG_FORMAT = '[%(asctime)s] [%(levelname)s] %(filename)s:%(lineno)d - %(message)s'
# LOG_FORMAT = '[%(asctime)s] [%(levelname)s] - %(message)s'
DATE_FORMAT = '%Y-%m-%d %H:%M:%S'

# 创建logger
logger = logging.getLogger('guji_reader')
logger.setLevel(logging.INFO)

# 文件日志处理器，最大5MB，保留3个历史文件
file_handler = RotatingFileHandler(LOG_FILE, maxBytes=5*1024*1024, backupCount=3, encoding='utf-8')
file_handler.setFormatter(logging.Formatter(LOG_FORMAT, datefmt=DATE_FORMAT))

# 控制台日志（可选）
console_handler = logging.StreamHandler()
console_handler.setFormatter(logging.Formatter(LOG_FORMAT, datefmt=DATE_FORMAT))

# 避免重复添加handler
if not logger.hasHandlers():
    logger.addHandler(file_handler)
    logger.addHandler(console_handler)

# 便捷方法
info = logger.info
warning = logger.warning
error = logger.error
exception = logger.exception 