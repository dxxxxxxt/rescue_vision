import cv2
import numpy as np
import json
import os
from utils.logger_utils import get_logger

# 获取日志记录器
logger = get_logger(__name__)

class ColorDetector:
    """
    颜色检测器类，支持HSV阈值检测和光照自适应功能
    
    主要功能：
    - 加载和管理HSV颜色阈值配置
    - 检测特定颜色或所有配置的颜色
    - 光照自适应：根据环境光照变化动态调整HSV阈值
    
    光照自适应工作原理：
    1. 计算图像的平均亮度作为当前光照水平
    2. 检测光照水平是否发生显著变化（超过设定阈值）
    3. 当光照发生显著变化时，动态调整HSV阈值的V通道（亮度）和S通道（饱和度）
    4. 在光线变暗时降低V的下限，在光线变亮时提高V的上限
    5. 同时调整S通道以保持检测稳定性
    """
    
    def __init__(self, config_path):
        """
        颜色检测器初始化
        :param config_path: HSV阈值配置文件路径
        """
        if not config_path:
            logger.warning("未提供配置文件路径")
        self.config_path = config_path
        # 加载基础阈值（保持不变的原始阈值）
        self.base_hsv_thresholds = self.load_hsv_thresholds()
        # 当前使用的阈值（可能是调整后的）
        self.hsv_thresholds = json.loads(json.dumps(self.base_hsv_thresholds))
        
        # 光照自适应参数
        self.light_adaptation_enabled = True  # 是否启用光照自适应
        self.last_light_level = None  # 上一次检测的光照水平
        self.adaptation_factor = 0.1  # 自适应调整因子（0.0-1.0），值越大调整越灵敏
        self.light_change_threshold = 10.0  # 光照变化阈值，超过此值才进行调整
        self.update_counter = 0  # 用于跟踪更新次数
        
    def set_adaptation_factor(self, factor):
        """
        设置光照自适应因子
        
        参数调整建议：
        - factor = 0.0: 完全不调整
        - factor = 0.1-0.3: 轻微调整，适合变化缓慢的环境
        - factor = 0.4-0.7: 中等调整，适合一般室内环境
        - factor = 0.8-1.0: 强烈调整，适合光照变化较大的环境
        
        :param factor: 自适应因子（0.0-1.0）
        """
        self.adaptation_factor = max(0.0, min(1.0, factor))
        logger.info(f"光照自适应因子设置为: {self.adaptation_factor}")
    
    def calculate_light_level(self, image):
        """
        计算图像的光照水平（亮度）
        :param image: 输入BGR图像
        :return: 光照水平值（0-255）
        """
        # 将图像转换为灰度图
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        # 计算平均亮度
        light_level = np.mean(gray)
        logger.debug(f"当前图像光照水平: {light_level}")
        return light_level
    
    def adjust_hsv_thresholds(self, base_thresholds, light_level):
        """
        根据光照水平动态调整HSV阈值
        
        调整策略：
        - 以标准光照水平128为基准
        - 光线变暗时：降低V通道下限，使更多较暗的像素被检测到
        - 光线变亮时：提高V通道上限，但调整幅度较小以避免过曝
        - 同时调整S通道（饱和度）的下限，使检测更加稳定
        
        :param base_thresholds: 基础HSV阈值
        :param light_level: 当前光照水平
        :return: 调整后的HSV阈值
        """
        # 标准光照水平参考值（可以根据实际情况调整）
        standard_light_level = 128.0
        # 计算光照偏差比例
        light_ratio = light_level / standard_light_level
        
        # 复制原始阈值以避免修改原始数据
        adjusted_thresholds = json.loads(json.dumps(base_thresholds))
        
        # 对每个颜色的阈值进行调整
        for color_name, color_configs in adjusted_thresholds.items():
            for config in color_configs:
                # 调整V通道（亮度）阈值
                # 光线暗时，降低V的下限
                # 光线亮时，提高V的上限
                if light_level < standard_light_level:
                    # 光线变暗，降低V通道的下限
                    config['lower'][2] = max(0, int(config['lower'][2] * (1 - (standard_light_level - light_level) / standard_light_level * self.adaptation_factor)))
                else:
                    # 光线变亮，适当提高V通道的上限
                    config['upper'][2] = min(255, int(config['upper'][2] * (1 + (light_level - standard_light_level) / standard_light_level * self.adaptation_factor * 0.5)))
                
                # 调整S通道（饱和度）阈值，在光照变化时保持稳定性
                config['lower'][1] = max(0, int(config['lower'][1] * (1 - abs(1 - light_ratio) * self.adaptation_factor * 0.3)))
        
        logger.debug(f"根据光照水平 {light_level} 调整HSV阈值")
        return adjusted_thresholds
    
    def is_light_changed_significantly(self, current_light_level):
        """
        检测光照是否发生显著变化
        
        为避免频繁调整，只有当光照水平的变化超过设定阈值时才认为是显著变化
        
        :param current_light_level: 当前光照水平
        :return: 是否显著变化
        """
        if self.last_light_level is None:
            # 首次检测，认为是显著变化
            return True
        
        # 计算光照变化量
        light_diff = abs(current_light_level - self.last_light_level)
        logger.debug(f"光照变化量: {light_diff}, 阈值: {self.light_change_threshold}")
        
        # 当变化超过阈值时认为是显著变化
        return light_diff >= self.light_change_threshold
    
    def update_thresholds_if_needed(self, image):
        """
        根据需要更新阈值
        
        这是光照自适应的核心方法，会在每次颜色检测前被调用
        1. 检查光照自适应是否启用
        2. 计算当前图像的光照水平
        3. 判断光照是否发生显著变化
        4. 如需要，更新HSV阈值
        
        :param image: 当前图像
        :return: 是否更新了阈值
        """
        if not self.light_adaptation_enabled:
            return False
        
        try:
            # 计算当前光照水平
            current_light_level = self.calculate_light_level(image)
            
            # 检查光照是否显著变化
            if self.is_light_changed_significantly(current_light_level):
                # 更新阈值
                self.hsv_thresholds = self.adjust_hsv_thresholds(self.base_hsv_thresholds, current_light_level)
                # 更新上次光照水平
                self.last_light_level = current_light_level
                # 增加更新计数器
                self.update_counter += 1
                logger.info(f"阈值已更新，更新次数: {self.update_counter}")
                return True
            
            return False
        except Exception as e:
            logger.error(f"更新阈值时出错: {e}")
            return False
    
    def set_light_change_threshold(self, threshold):
        """
        设置光照变化阈值
        
        参数调整建议：
        - 较小的值（5-10）：对光照变化敏感，频繁调整
        - 中等的值（10-20）：平衡的设置，适合一般场景
        - 较大的值（20-50）：减少不必要的调整，适合相对稳定的环境
        
        :param threshold: 光照变化阈值（0-255）
        """
        self.light_change_threshold = max(0.0, min(255.0, threshold))
        logger.info(f"光照变化阈值设置为: {self.light_change_threshold}")
    
    def enable_light_adaptation(self, enable=True):
        """
        启用或禁用光照自适应功能
        
        禁用时会自动重置为原始基础阈值
        
        :param enable: 是否启用
        """
        self.light_adaptation_enabled = enable
        status = "启用" if enable else "禁用"
        logger.info(f"光照自适应功能已{status}")
        # 如果禁用，重置为基础阈值
        if not enable:
            self.hsv_thresholds = json.loads(json.dumps(self.base_hsv_thresholds))
            logger.info("已重置为基础阈值")
    
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
            # 根据当前图像更新阈值（如果需要）
            self.update_thresholds_if_needed(image)
            
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
            
        # 根据当前图像更新阈值（如果需要）
        self.update_thresholds_if_needed(image)
            
        results = {}
        for color_name in self.hsv_thresholds:
            mask = self.detect_color(image, color_name)
            if mask is not None:
                results[color_name] = mask
            else:
                logger.warning(f"无法检测颜色: {color_name}")
        
        logger.info(f"成功检测到 {len(results)} 种颜色")
        return results