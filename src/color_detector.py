import cv2
import numpy as np
import json
import os
from utils.logger_utils import get_logger

# 获取日志记录器
logger = get_logger(__name__)

class ColorDetector:
    def __init__(self, config_path):
        """
        颜色检测器初始化
        :param config_path: HSV阈值配置文件路径
        """
        if not config_path:
            logger.warning("未提供配置文件路径")
        self.config_path = config_path
        self.hsv_thresholds = self.load_hsv_thresholds()
    
    def load_hsv_thresholds(self):
        """
        加载HSV颜色阈值配置
        :return: 包含各颜色HSV阈值的字典
        """
        if not self.config_path:
            logger.warning("配置文件路径为空")
            return {}
            
        if not os.path.exists(self.config_path):
            logger.error(f"配置文件不存在: {self.config_path}")
            raise FileNotFoundError(f"配置文件不存在: {self.config_path}")
        
        try:
            with open(self.config_path, 'r', encoding='utf-8') as f:
                thresholds = json.load(f)
                logger.info(f"成功加载HSV阈值配置")
                return thresholds
        except json.JSONDecodeError as e:
            logger.error(f"配置文件格式错误: {e}")
            raise
        except Exception as e:
            logger.error(f"加载配置文件出错: {e}")
            raise
    
    def preprocess_image(self, image):
        """
        图像预处理
        :param image: 输入BGR图像
        :return: 预处理后的图像
        """
        # 输入验证
        if image is None or image.size == 0:
            logger.error("输入图像无效")
            return None
        
        try:
            # 高斯模糊去除噪声
            blurred = cv2.GaussianBlur(image, (5, 5), 0)
            return blurred
        except Exception as e:
            logger.error(f"图像预处理出错: {e}")
            return None
    
    def detect_color(self, image, color_name):
        """
        检测特定颜色
        :param image: 输入BGR图像
        :param color_name: 颜色名称（red, yellow, blue, black）
        :return: 二值化掩码，包含检测到的颜色区域
        """
        # 输入验证
        if image is None or image.size == 0:
            logger.error("输入图像无效")
            return None
            
        if not color_name or not isinstance(color_name, str):
            logger.error("颜色名称无效")
            return None
        
        if color_name not in self.hsv_thresholds:
            logger.warning(f"不支持的颜色: {color_name}")
            raise ValueError(f"不支持的颜色: {color_name}")
        
        try:
            # 图像预处理
            processed = self.preprocess_image(image)
            if processed is None:
                return None
            
            # 转换为HSV颜色空间
            hsv = cv2.cvtColor(processed, cv2.COLOR_BGR2HSV)
            
            # 获取颜色的HSV阈值
            color_config = self.hsv_thresholds[color_name]
            
            # 创建掩码（处理可能的多范围颜色，如红色）
            masks = []
            for range_config in color_config:
                lower = np.array(range_config['lower'], dtype=np.uint8)
                upper = np.array(range_config['upper'], dtype=np.uint8)
                mask = cv2.inRange(hsv, lower, upper)
                masks.append(mask)
            
            # 合并所有掩码
            combined_mask = np.bitwise_or.reduce(masks) if len(masks) > 1 else masks[0]
            
            # 形态学操作：开运算（去除噪声）和闭运算（填充孔洞）
            kernel = np.ones((5, 5), np.uint8)
            mask = cv2.morphologyEx(combined_mask, cv2.MORPH_OPEN, kernel)
            mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, kernel)
            
            return mask
        except Exception as e:
            logger.error(f"颜色检测出错: {e}")
            return None
    
    def detect_all_colors(self, image):
        """
        检测所有配置的颜色
        :param image: 输入BGR图像
        :return: 字典，键为颜色名称，值为对应的二值化掩码
        """
        # 输入验证
        if image is None or image.size == 0:
            logger.error("输入图像无效")
            return {}
            
        results = {}
        for color_name in self.hsv_thresholds:
            mask = self.detect_color(image, color_name)
            if mask is not None:
                results[color_name] = mask
            else:
                logger.warning(f"无法检测颜色: {color_name}")
        
        logger.info(f"成功检测到 {len(results)} 种颜色")
        return results