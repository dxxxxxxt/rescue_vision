import cv2
import numpy as np
from utils.logger_utils import get_logger

class ColorDetector:
    def __init__(self, config=None):
        self.logger = get_logger(__name__)
        
        # 默认HSV阈值配置
        self.default_hsv_config = {
            'red': {'lower': [0, 100, 100], 'upper': [10, 255, 255]},
            'blue': {'lower': [100, 100, 100], 'upper': [130, 255, 255]},
            'yellow': {'lower': [20, 100, 100], 'upper': [30, 255, 255]},
            'black': {'lower': [0, 0, 0], 'upper': [180, 255, 70]},
            'purple': {'lower': [120, 100, 100], 'upper': [160, 255, 255]}
        }
        
        # 使用传入的配置或默认配置
        self.hsv_config = config.copy() if config else self.default_hsv_config.copy()
    
    def update_thresholds_if_needed(self, frame):
        # 简化版本，不再进行光照自适应调整
        pass
    
    def detect_color(self, frame, color):
        # 更新光照自适应阈值
        self.update_thresholds_if_needed(frame)
        
        # 检查颜色是否有效
        if color not in self.hsv_config:
            return None
        
        try:
            # 转换为HSV色彩空间
            hsv = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)
            
            # 获取该颜色的HSV阈值
            lower = np.array(self.hsv_config[color]['lower'])
            upper = np.array(self.hsv_config[color]['upper'])
            
            # 对于红色，需要特殊处理（因为红色在HSV环中跨越0点）
            if color == 'red':
                lower1 = lower
                upper1 = np.array([10, 255, 255])
                lower2 = np.array([160, lower[1], lower[2]])
                upper2 = np.array([180, upper[1], upper[2]])
                
                # 创建两个掩码并合并
                mask1 = cv2.inRange(hsv, lower1, upper1)
                mask2 = cv2.inRange(hsv, lower2, upper2)
                mask = cv2.bitwise_or(mask1, mask2)
            elif color == 'purple':
                # 对于紫色，也需要特殊处理以捕获完整的紫色范围
                lower1 = lower
                upper1 = np.array([140, upper[1], upper[2]])  # 中间点140度作为分界
                lower2 = np.array([140, lower[1], lower[2]])
                upper2 = upper
                
                # 创建两个掩码并合并
                mask1 = cv2.inRange(hsv, lower1, upper1)
                mask2 = cv2.inRange(hsv, lower2, upper2)
                mask = cv2.bitwise_or(mask1, mask2)
            else:
                # 创建单一掩码
                mask = cv2.inRange(hsv, lower, upper)
            
            # 形态学操作，去除噪声
            kernel = np.ones((5, 5), np.uint8)
            mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, kernel)
            mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, kernel)
            
            return mask
            
        except Exception as e:
            self.logger.error(f"检测{color}色时出错: {e}")
            return None
    
    def find_contours(self, mask, min_area=50):
        # 从掩码中查找轮廓
        if mask is None:
            return []
        
        contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        
        # 过滤太小的轮廓
        return [c for c in contours if cv2.contourArea(c) > min_area]
    
    def get_ball_position(self, contour):
        # 计算轮廓的中心和半径
        if len(contour) < 5:  # cv2.minEnclosingCircle需要至少5个点
            return None
        
        (x, y), radius = cv2.minEnclosingCircle(contour)
        return {
            'x': int(x),
            'y': int(y),
            'radius': int(radius)
        }
    
    def detect_balls(self, frame, colors=None, min_area=50):
        # 检测所有指定颜色的小球
        if colors is None:
            colors = list(self.hsv_config.keys())
        
        detected_balls = []
        
        for color in colors:
            # 检测特定颜色
            mask = self.detect_color(frame, color)
            if mask is None:
                continue
            
            # 查找轮廓
            contours = self.find_contours(mask, min_area)
            
            # 处理每个轮廓
            for contour in contours:
                ball_info = self.get_ball_position(contour)
                if ball_info:
                    ball_info['color'] = color
                    detected_balls.append(ball_info)
        
        return detected_balls