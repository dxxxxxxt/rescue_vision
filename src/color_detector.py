import cv2
import numpy as np
import json
import os

class ColorDetector:
    def __init__(self, config_path):
        """
        颜色检测器初始化
        :param config_path: HSV阈值配置文件路径
        """
        self.config_path = config_path
        self.hsv_thresholds = self.load_hsv_thresholds()
    
    def load_hsv_thresholds(self):
        """
        加载HSV颜色阈值配置
        :return: 包含各颜色HSV阈值的字典
        """
        if not os.path.exists(self.config_path):
            raise FileNotFoundError(f"配置文件不存在: {self.config_path}")
        
        with open(self.config_path, 'r', encoding='utf-8') as f:
            return json.load(f)
    
    def preprocess_image(self, image):
        """
        图像预处理
        :param image: 输入BGR图像
        :return: 预处理后的图像
        """
        # 高斯模糊去除噪声
        blurred = cv2.GaussianBlur(image, (5, 5), 0)
        return blurred
    
    def detect_color(self, image, color_name):
        """
        检测特定颜色
        :param image: 输入BGR图像
        :param color_name: 颜色名称（red, yellow, blue, black）
        :return: 二值化掩码，包含检测到的颜色区域
        """
        if color_name not in self.hsv_thresholds:
            raise ValueError(f"不支持的颜色: {color_name}")
        
        # 图像预处理
        processed = self.preprocess_image(image)
        
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
    
    def detect_all_colors(self, image):
        """
        检测所有配置的颜色
        :param image: 输入BGR图像
        :return: 字典，键为颜色名称，值为对应的二值化掩码
        """
        results = {}
        for color_name in self.hsv_thresholds:
            results[color_name] = self.detect_color(image, color_name)
        return results