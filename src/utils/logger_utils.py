import logging
import os
from datetime import datetime

# 确保日志目录存在
LOG_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'logs')
os.makedirs(LOG_DIR, exist_ok=True)

# 生成日志文件名
log_filename = datetime.now().strftime('%Y%m%d_%H%M%S.log')
log_file_path = os.path.join(LOG_DIR, log_filename)

# 统一的日志配置
def setup_logging(level=logging.INFO):
    """
    设置统一的日志配置
    :param level: 日志级别
    """
    # 基本配置
    logging.basicConfig(
        level=level,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            # 控制台输出
            logging.StreamHandler(),
            # 文件输出
            logging.FileHandler(log_file_path, encoding='utf-8')
        ]
    )
    logging.info(f"日志系统初始化完成，日志文件路径: {log_file_path}")

# 获取日志记录器的便捷函数
def get_logger(name=__name__):
    """
    获取指定名称的日志记录器
    :param name: 记录器名称
    :return: 日志记录器实例
    """
    return logging.getLogger(name)
