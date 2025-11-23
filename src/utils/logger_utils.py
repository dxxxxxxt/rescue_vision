import logging
import os
import sys
import time
from datetime import datetime, timedelta
from logging.handlers import RotatingFileHandler
from logging import Formatter

# 确保日志目录存在
LOG_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'logs')
os.makedirs(LOG_DIR, exist_ok=True)

# 彩色日志格式类
class ColoredFormatter(Formatter):
    # ANSI颜色代码
    COLORS = {
        'DEBUG': '\033[36m',       # 青色
        'INFO': '\033[32m',        # 绿色
        'WARNING': '\033[33m',     # 黄色
        'ERROR': '\033[31m',       # 红色
        'CRITICAL': '\033[41m\033[37m',  # 红底白字
        'RESET': '\033[0m'         # 重置
    }
    
    def format(self, record):
        # 为Windows系统简化处理
        if os.name == 'nt':
            # Windows命令提示符不支持完整的ANSI颜色，使用基本格式
            formatter = Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
            return formatter.format(record)
        
        # 为支持ANSI颜色的终端添加颜色
        levelname = record.levelname
        color = self.COLORS.get(levelname, self.COLORS['RESET'])
        reset = self.COLORS['RESET']
        
        # 带有颜色的格式
        colored_format = f'{color}%(asctime)s - %(name)s - %(levelname)s - %(message)s{reset}'
        formatter = Formatter(colored_format)
        return formatter.format(record)

# 清理旧日志文件
def clean_old_logs(days_to_keep=7):
    """
    清理指定天数之前的日志文件
    :param days_to_keep: 保留的天数
    """
    try:
        cutoff_date = datetime.now() - timedelta(days=days_to_keep)
        for filename in os.listdir(LOG_DIR):
            if filename.endswith('.log'):
                file_path = os.path.join(LOG_DIR, filename)
                try:
                    # 获取文件修改时间
                    file_mtime = datetime.fromtimestamp(os.path.getmtime(file_path))
                    # 删除过期文件
                    if file_mtime < cutoff_date:
                        os.remove(file_path)
                        print(f"已删除过期日志: {filename}")
                except Exception as e:
                    print(f"清理日志文件 {filename} 时出错: {e}")
    except Exception as e:
        print(f"清理旧日志过程中出错: {e}")

# 统一的日志配置
def setup_logging(level=logging.INFO, log_name_prefix="rescue_vision"):
    """
    设置统一的日志配置
    :param level: 日志级别
    :param log_name_prefix: 日志文件名前缀
    """
    # 清理根日志记录器的所有处理器
    root_logger = logging.getLogger()
    root_logger.handlers.clear()
    root_logger.setLevel(level)
    
    # 生成日志文件名（包含日期但不包含时间，便于轮转）
    base_log_filename = f"{log_name_prefix}_{datetime.now().strftime('%Y%m%d')}.log"
    log_file_path = os.path.join(LOG_DIR, base_log_filename)
    
    # 设置文件处理器（带轮转功能）
    # 每个文件最大10MB，最多保留5个备份文件
    file_handler = RotatingFileHandler(
        log_file_path,
        maxBytes=10*1024*1024,  # 10MB
        backupCount=5,
        encoding='utf-8'
    )
    file_formatter = Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    file_handler.setFormatter(file_formatter)
    root_logger.addHandler(file_handler)
    
    # 设置控制台处理器（带颜色）
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(ColoredFormatter())
    root_logger.addHandler(console_handler)
    
    # 清理旧日志
    clean_old_logs()
    
    root_logger.info(f"日志系统初始化完成，日志文件路径: {log_file_path}")
    root_logger.info(f"日志级别: {logging.getLevelName(level)}")

# 获取日志记录器的便捷函数
def get_logger(name=__name__):
    """
    获取指定名称的日志记录器
    :param name: 记录器名称
    :return: 日志记录器实例
    """
    logger = logging.getLogger(name)
    # 如果根日志记录器还没有设置处理器，则自动初始化
    if not logging.getLogger().handlers:
        setup_logging()
    return logger

# 自动初始化日志系统
# 当模块被导入时，预先设置基本配置
if not logging.getLogger().handlers:
    setup_logging()

# 导出常用的日志级别常量，便于其他模块使用
DEBUG = logging.DEBUG
INFO = logging.INFO
WARNING = logging.WARNING
ERROR = logging.ERROR
CRITICAL = logging.CRITICAL
