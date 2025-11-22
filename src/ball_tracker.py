import cv2
import numpy as np
from typing import List, Dict, Tuple, Optional
from utils.logger_utils import get_logger

# 获取日志记录器
logger = get_logger(__name__)

class BallTracker:
    def __init__(self, min_radius=10, max_radius=100):
        """
        小球跟踪器初始化
        :param min_radius: 最小球半径
        :param max_radius: 最大球半径
        """
        self.min_radius = min_radius
        self.max_radius = max_radius
        self.min_circularity = 0.7  # 最小圆形度阈值
    
    def find_balls(self, mask, color_name):
        """
        在掩码中找到小球
        :param mask: 二值化掩码
        :param color_name: 小球颜色
        :return: 小球列表，每个元素包含(x, y, radius, color)
        """
        # 输入验证
        if mask is None or mask.size == 0:
            logger.error("输入掩码无效")
            return []
            
        if not color_name or not isinstance(color_name, str):
            logger.error("颜色名称无效")
            return []
        
        try:
            # 寻找轮廓
            contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
            
            balls = []
            
            for contour in contours:
                try:
                    # 计算轮廓的最小外接圆
                    (x, y), radius = cv2.minEnclosingCircle(contour)
                    center = (int(x), int(y))
                    radius = int(radius)
                    
                    # 筛选出符合大小的圆形
                    if self.min_radius < radius < self.max_radius:
                        # 计算轮廓的面积和圆形度
                        area = cv2.contourArea(contour)
                        circle_area = np.pi * radius * radius
                        circularity = area / circle_area if circle_area > 0 else 0
                        
                        # 只有圆形度足够高的才认为是小球
                        if circularity > self.min_circularity:
                            balls.append({
                                'x': center[0],
                                'y': center[1],
                                'radius': radius,
                                'color': color_name,
                                'area': area,
                                'circularity': circularity
                            })
                except Exception as e:
                    logger.warning(f"处理轮廓时出错: {e}")
                    continue
            
            logger.info(f"在{color_name}掩码中找到{len(balls)}个小球")
            return balls
        except Exception as e:
            logger.error(f"查找小球时出错: {e}")
            return []
    
    def track_balls(self, color_masks):
        """
        跟踪所有颜色的小球
        :param color_masks: 颜色掩码字典，键为颜色名称
        :return: 所有检测到的小球列表
        """
        # 输入验证
        if not isinstance(color_masks, dict):
            logger.error("颜色掩码参数必须是字典类型")
            return []
        
        try:
            all_balls = []
            
            for color_name, mask in color_masks.items():
                if mask is not None and mask.size > 0:
                    balls = self.find_balls(mask, color_name)
                    all_balls.extend(balls)
                else:
                    logger.warning(f"跳过无效的{color_name}掩码")
            
            logger.info(f"总共跟踪到{len(all_balls)}个小球")
            return all_balls
        except Exception as e:
            logger.error(f"跟踪小球时出错: {e}")
            return []
    
    def draw_balls(self, image, balls):
        """
        在图像上绘制检测到的小球
        :param image: 输入BGR图像
        :param balls: 小球列表
        :return: 绘制后的图像
        """
        # 输入验证
        if image is None or image.size == 0:
            logger.error("输入图像无效")
            return None
            
        if balls is None:
            logger.warning("没有小球数据")
            return image.copy()
        
        try:
            result = image.copy()
            
            # 颜色映射
            color_map = {
                'red': (0, 0, 255),      # BGR格式，红色
                'yellow': (0, 255, 255),  # 黄色
                'blue': (255, 0, 0),      # 蓝色
                'black': (0, 0, 0)        # 黑色
            }
            
            for ball in balls:
                try:
                    # 验证小球数据
                    if not isinstance(ball, dict) or 'x' not in ball or 'y' not in ball or 'radius' not in ball or 'color' not in ball:
                        logger.warning("小球数据格式无效")
                        continue
                        
                    color = color_map.get(ball['color'], (255, 255, 255))
                    center = (ball['x'], ball['y'])
                    radius = ball['radius']
                    
                    # 确保中心点在图像范围内
                    h, w = image.shape[:2]
                    if not (0 <= center[0] < w and 0 <= center[1] < h):
                        logger.warning(f"小球中心({center})超出图像范围")
                        continue
                    
                    # 绘制圆圈
                    cv2.circle(result, center, radius, color, 2)
                    
                    # 绘制中心点
                    cv2.circle(result, center, 2, color, -1)
                    
                    # 标注信息
                    text = f"{ball['color']} ({ball['x']}, {ball['y']})"
                    # 确保文本位置在图像范围内
                    text_x = max(10, min(center[0] - 50, w - 100))
                    text_y = max(30, center[1] - radius - 10)
                    cv2.putText(result, text, (text_x, text_y), 
                                cv2.FONT_HERSHEY_SIMPLEX, 0.5, color, 2)
                except Exception as e:
                    logger.warning(f"绘制小球时出错: {e}")
                    continue
            
            return result
        except Exception as e:
            logger.error(f"绘制小球过程出错: {e}")
            return image.copy()