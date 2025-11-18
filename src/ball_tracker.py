import cv2
import numpy as np

class BallTracker:
    def __init__(self, min_radius=10, max_radius=100):
        """
        小球跟踪器初始化
        :param min_radius: 最小球半径
        :param max_radius: 最大球半径
        """
        self.min_radius = min_radius
        self.max_radius = max_radius
    
    def find_balls(self, mask, color_name):
        """
        在掩码中找到小球
        :param mask: 二值化掩码
        :param color_name: 小球颜色
        :return: 小球列表，每个元素包含(x, y, radius, color)
        """
        # 寻找轮廓
        contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        
        balls = []
        
        for contour in contours:
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
                if circularity > 0.7:
                    balls.append({
                        'x': center[0],
                        'y': center[1],
                        'radius': radius,
                        'color': color_name,
                        'area': area,
                        'circularity': circularity
                    })
        
        return balls
    
    def track_balls(self, color_masks):
        """
        跟踪所有颜色的小球
        :param color_masks: 颜色掩码字典，键为颜色名称
        :return: 所有检测到的小球列表
        """
        all_balls = []
        
        for color_name, mask in color_masks.items():
            balls = self.find_balls(mask, color_name)
            all_balls.extend(balls)
        
        return all_balls
    
    def draw_balls(self, image, balls):
        """
        在图像上绘制检测到的小球
        :param image: 输入BGR图像
        :param balls: 小球列表
        :return: 绘制后的图像
        """
        result = image.copy()
        
        # 颜色映射
        color_map = {
            'red': (0, 0, 255),      # BGR格式，红色
            'yellow': (0, 255, 255),  # 黄色
            'blue': (255, 0, 0),      # 蓝色
            'black': (0, 0, 0)        # 黑色
        }
        
        for ball in balls:
            color = color_map.get(ball['color'], (255, 255, 255))
            center = (ball['x'], ball['y'])
            radius = ball['radius']
            
            # 绘制圆圈
            cv2.circle(result, center, radius, color, 2)
            
            # 绘制中心点
            cv2.circle(result, center, 2, color, -1)
            
            # 标注信息
            text = f"{ball['color']} ({ball['x']}, {ball['y']})"
            cv2.putText(result, text, (center[0] - 50, center[1] - radius - 10), 
                        cv2.FONT_HERSHEY_SIMPLEX, 0.5, color, 2)
        
        return result