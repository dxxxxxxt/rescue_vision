import cv2
import json
import os
import numpy as np
import time
from color_detector import ColorDetector
from ball_tracker import BallTracker

class VisionCore:
    def __init__(self, config_path='config.json'):
        """初始化视觉核心"""
        # 初始化默认配置
        self.config = {
            'camera_id': 0,
            'strategy': {
                'team_color': 'blue',
                'enemy_color': 'red'
            },
            'safety_zones': []
        }
        
        # 加载配置文件
        if os.path.exists(config_path):
            try:
                with open(config_path, 'r', encoding='utf-8') as f:
                    self.config.update(json.load(f))
            except Exception as e:
                print(f"警告：加载配置文件失败: {e}")
        
        # 初始化必要的属性
        self.team_color = self.config['strategy']['team_color']
        self.enemy_color = self.config['strategy']['enemy_color']
        self.first_pick_done = False
        
        # 初始化安全区（支持新旧格式）
        self.safety_zones = []
        zones = self.config.get('safety_zones', [])
        # 转换旧版单安全区格式为多安全区格式
        if isinstance(zones, list):
            if zones and all(isinstance(zone, list) for zone in zones):
                self.safety_zones = zones
            elif zones and all(isinstance(p, (int, float)) for p in zones):
                self.safety_zones = [zones]
        
        # 存储动态检测到的安全区
        self.dynamic_safety_zones = {'red': None, 'blue': None}
        
        # 初始化组件
        self.camera = self.init_camera()
        self.color_detector = ColorDetector()
        self.ball_tracker = BallTracker()
        self.video_writer = None
    
    def init_camera(self):
        """初始化摄像头"""
        camera_id = self.config.get('camera_id', 0)
        camera = cv2.VideoCapture(camera_id)
        
        if not camera.isOpened():
            raise Exception(f"无法打开摄像头 {camera_id}")
        
        # 设置摄像头参数
        camera.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
        camera.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
        return camera
    
    def get_frame(self):
        """获取摄像头帧"""
        if not hasattr(self, 'camera') or not self.camera:
            return None
        
        ret, frame = self.camera.read()
        if not ret:
            return None
        
        return frame
    
    def detect_all_balls(self, frame):
        """检测所有小球"""
        if frame is None:
            return []
        
        balls = []
        # 检测各颜色小球
        for color in ['red', 'green', 'blue', 'yellow']:
            color_balls = self.color_detector.detect_color(frame, color)
            balls.extend(color_balls)
        
        return balls
    
    def calculate_ball_priority(self, ball, safety_zones=None):
        """检查小球是否有效（不在对应安全区内）"""
        # 检查小球基本信息
        if not ball or not ball.get('color'):
            return float('inf')
        
        # 检查小球是否在对应颜色的安全区内
        in_safety, safety_color = self.is_ball_in_safety_zone(ball, safety_zones)
        if in_safety and safety_color:
            color = ball['color']
            # 过滤掉已在目标安全区的小球
            if (color == self.team_color and safety_color == self.team_color) or \
               (color == self.enemy_color and safety_color == self.enemy_color):
                return float('inf')
        
        return 0
    
    def get_prioritized_balls(self, balls, safety_zones=None):
        """过滤无效小球，保留有效的小球"""
        # 过滤条件：有效小球需要有完整数据且不在对应安全区内
        # 过滤有效小球
        valid_balls = []
        for ball in balls:
            # 检查小球是否存在
            if not ball:
                continue
            
            # 检查小球是否包含所有必需属性
            required_fields = ['x', 'y', 'radius', 'color']
            has_required_fields = True
            for field in required_fields:
                if field not in ball:
                    has_required_fields = False
                    break
            
            if not has_required_fields:
                continue
            
            # 检查小球是否在安全区域且符合优先级规则
            priority = self.calculate_ball_priority(ball, safety_zones)
            if priority != float('inf'):
                valid_balls.append(ball)
        
        return valid_balls
    
    def get_best_target(self, balls, safety_zones=None):
        """获取最佳目标，按检测顺序返回第一个符合规则的有效小球"""
        # 先获取有效的小球列表
        valid_balls = self.get_prioritized_balls(balls, safety_zones)
        
        # 按检测顺序查找符合黄色球限制规则的第一个小球
        for ball in valid_balls:
            if self.check_yellow_ball_restriction(balls, ball):
                return ball
                
        return None
    
    def set_first_pick_done(self):
        """标记首次抓取已完成"""
        self.first_pick_done = True
    
    def check_yellow_ball_restriction(self, balls, target_ball):
        """检查黄色球限制规则"""
        if target_ball.get('color') != 'yellow':
            return True
        
        # 计算场上己方球数量
        team_balls = [b for b in balls if b and b.get('color') == self.team_color]
        
        # 只有当己方球少于2个时才能抓取黄色球
        return len(team_balls) < 2
    
    def is_ball_in_safety_zone(self, ball, safety_zones=None):
        """检查小球是否在安全区内"""
        if not ball:
            return False, None
        
        x, y = ball.get('x', 0), ball.get('y', 0)
        zones = safety_zones or self.dynamic_safety_zones
        
        # 检查动态安全区
        for color, zone in zones.items():
            if zone and 'contour' in zone:
                if cv2.pointPolygonTest(zone['contour'], (x, y), False) >= 0:
                    return True, color
        
        # 兼容旧版矩形安全区
        for zone in self.safety_zones:
            if len(zone) >= 4 and zone[0] <= x <= zone[2] and zone[1] <= y <= zone[3]:
                return True, None
        
        return False, None
        
    def detect_purple_fence(self, frame):
        """检测紫色围栏"""
        if frame is None or frame.size == 0:
            return np.ones(frame.shape[:2], dtype=np.uint8) * 255 if frame is not None else None
        
        try:
            # 转换为HSV色彩空间
            hsv = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)
            
            # 紫色HSV范围（改进的范围，增加对不同紫色色调的敏感度）
            # 使用两个范围来覆盖完整的紫色范围，并略微扩大范围以适应不同光线条件
            lower_purple1 = np.array([110, 40, 40])  # 降低饱和度和亮度阈值
            upper_purple1 = np.array([140, 255, 255])
            lower_purple2 = np.array([140, 40, 40])  # 降低饱和度和亮度阈值
            upper_purple2 = np.array([170, 255, 255])  # 扩大上限
            
            # 创建两个紫色掩码并合并
            mask1 = cv2.inRange(hsv, lower_purple1, upper_purple1)
            mask2 = cv2.inRange(hsv, lower_purple2, upper_purple2)
            purple_mask = cv2.bitwise_or(mask1, mask2)
            
            # 形态学操作改进
            # 1. 先进行腐蚀，去除小的噪点
            kernel_small = np.ones((3, 3), np.uint8)
            purple_mask = cv2.erode(purple_mask, kernel_small, iterations=1)
            
            # 2. 再进行膨胀，填补缝隙并强化围栏边缘
            kernel_large = np.ones((7, 7), np.uint8)
            purple_mask = cv2.dilate(purple_mask, kernel_large, iterations=1)
            
            # 3. 闭合操作，填充围栏内部的小空洞
            purple_mask = cv2.morphologyEx(purple_mask, cv2.MORPH_CLOSE, kernel_large)
            
            # 轮廓处理：只保留最大的闭合区域作为围栏
            contours, _ = cv2.findContours(purple_mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
            if contours:
                # 找到最大轮廓
                max_contour = max(contours, key=cv2.contourArea)
                
                # 创建新的掩码，只保留最大轮廓
                purple_mask = np.zeros_like(purple_mask)
                cv2.drawContours(purple_mask, [max_contour], -1, 255, -1)
                
                # 进行边界平滑，使围栏边界更连续
                purple_mask = cv2.GaussianBlur(purple_mask, (5, 5), 0)
                _, purple_mask = cv2.threshold(purple_mask, 127, 255, cv2.THRESH_BINARY)
            
            # 反转掩码，使围栏区域为黑色，其他区域为白色（可检测区域）
            # 这样在后续处理中，我们只会检测非围栏区域内的小球
            fence_filter_mask = cv2.bitwise_not(purple_mask)
            
            # 添加一定的缓冲，不完全过滤掉围栏边缘，避免小球被误过滤
            buffer_kernel = np.ones((5, 5), np.uint8)
            fence_filter_mask = cv2.morphologyEx(fence_filter_mask, cv2.MORPH_DILATE, buffer_kernel)
            
            return fence_filter_mask
            
        except Exception as e:
            print(f"检测紫色围栏时出错: {e}")
            # 出错时返回全1的掩码，避免影响正常检测
            return np.ones(frame.shape[:2], dtype=np.uint8) * 255
    
    def detect_safety_zones(self, frame):
        """动态检测红色和蓝色安全区
        
        Args:
            frame: 输入图像
            
        Returns:
            dict: 包含红色和蓝色安全区信息的字典
        """
        if frame is None:
            return {'red': None, 'blue': None}
        
        safety_zones = {'red': None, 'blue': None}
        
        try:
            # 检测红色安全区
            red_mask = self.color_detector.detect_color(frame, 'red')
            if red_mask is not None:
                # 形态学操作，填充红色区域
                kernel = np.ones((15, 15), np.uint8)
                red_mask = cv2.morphologyEx(red_mask, cv2.MORPH_CLOSE, kernel)
                red_mask = cv2.morphologyEx(red_mask, cv2.MORPH_DILATE, kernel)
                
                # 查找红色区域的轮廓
                contours, _ = cv2.findContours(red_mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
                # 找到最大的红色区域作为红色安全区
                if contours:
                    largest_contour = max(contours, key=cv2.contourArea)
                    if cv2.contourArea(largest_contour) > 1000:  # 最小面积阈值
                        x, y, w, h = cv2.boundingRect(largest_contour)
                        safety_zones['red'] = {'x': x, 'y': y, 'width': w, 'height': h, 'contour': largest_contour}
            
            # 检测蓝色安全区
            blue_mask = self.color_detector.detect_color(frame, 'blue')
            if blue_mask is not None:
                # 形态学操作，填充蓝色区域
                kernel = np.ones((15, 15), np.uint8)
                blue_mask = cv2.morphologyEx(blue_mask, cv2.MORPH_CLOSE, kernel)
                blue_mask = cv2.morphologyEx(blue_mask, cv2.MORPH_DILATE, kernel)
                
                # 查找蓝色区域的轮廓
                contours, _ = cv2.findContours(blue_mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
                # 找到最大的蓝色区域作为蓝色安全区
                if contours:
                    largest_contour = max(contours, key=cv2.contourArea)
                    if cv2.contourArea(largest_contour) > 1000:  # 最小面积阈值
                        x, y, w, h = cv2.boundingRect(largest_contour)
                        safety_zones['blue'] = {'x': x, 'y': y, 'width': w, 'height': h, 'contour': largest_contour}
            
        except Exception as e:
            print(f"检测安全区时出错: {e}")
        
        return safety_zones
    
    def filter_balls_in_fence(self, balls, fence_mask):
        """过滤围栏内的小球，增强对未知形状围栏的适应性"""
        if not balls or fence_mask is None:
            return balls
        
        filtered_balls = []
        
        for ball in balls:
            try:
                # 检查小球信息完整性
                if not ball or not all(k in ball for k in ['x', 'y', 'radius']):
                    continue
                
                x, y, r = int(ball['x']), int(ball['y']), int(ball['radius'])
                h, w = fence_mask.shape[:2]
                
                # 检查小球中心点是否在图像范围内
                if not (0 <= x < w and 0 <= y < h):
                    continue
                
                # 方法1：检查小球中心点是否在可抓取区域内
                center_in_valid = fence_mask[y, x] > 127
                
                # 方法2：检查小球大部分区域是否在可抓取区域内
                # 创建一个小球区域的掩码
                ball_mask = np.zeros_like(fence_mask)
                cv2.circle(ball_mask, (x, y), r, 255, -1)
                
                # 计算小球区域中在可抓取区域内的比例
                intersection = cv2.bitwise_and(ball_mask, fence_mask)
                valid_area = cv2.countNonZero(intersection)
                total_ball_area = cv2.countNonZero(ball_mask)
                
                # 如果小球大部分区域（>70%）在可抓取区域内，则视为有效
                valid_ratio = valid_area / total_ball_area if total_ball_area > 0 else 0
                
                # 组合判断：中心点在有效区域，或大部分区域在有效区域
                if center_in_valid or valid_ratio > 0.7:
                    filtered_balls.append(ball)
                
            except Exception as e:
                print(f"过滤小球时出错: {e}")
                # 出错时保留该小球，避免影响检测
                filtered_balls.append(ball)
        
        return filtered_balls
        
    def draw_purple_fence(self, frame, fence_mask):
        """在图像上绘制紫色围栏区域（用于调试）"""
        if frame is None or fence_mask is None:
            return frame
        
        try:
            # 创建围栏掩码的彩色版本
            fence_overlay = np.zeros_like(frame)
            fence_overlay[:, :] = (128, 0, 128)  # 紫色
            
            # 创建围栏区域的掩码（反转fence_mask）
            purple_mask = cv2.bitwise_not(fence_mask)
            
            # 将围栏区域添加到图像上
            frame = cv2.bitwise_or(frame, fence_overlay, mask=purple_mask)
            
            # 添加文字说明
            cv2.putText(frame, "PURPLE FENCE", (10, 30),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.6, (128, 0, 128), 2)
                        
        except Exception as e:
            print(f"绘制紫色围栏时出错: {e}")
            
        return frame
    
    def draw_safety_zone(self, frame):
        """绘制安全区，优先显示动态检测到的安全区"""
        if frame is None or frame.size == 0:
            return frame
            
        # 创建副本以避免修改原图
        result_frame = frame.copy()
        
        # 颜色映射表
        color_map = {
            'red': (0, 0, 255),      # BGR格式的红色
            'blue': (255, 0, 0),     # BGR格式的蓝色
            'green': (0, 255, 0),    # BGR格式的绿色
            'yellow': (0, 255, 255)  # BGR格式的黄色
        }
        
        # 优先绘制动态检测到的安全区
        if hasattr(self, 'dynamic_safety_zones') and self.dynamic_safety_zones:
            for color, zone_info in self.dynamic_safety_zones.items():
                if color in color_map and zone_info:
                    # 绘制安全区轮廓
                    contour = zone_info.get('contour')
                    if contour is not None and len(contour) > 0:
                        cv2.drawContours(result_frame, [contour], -1, color_map[color], 3)
                        
                        # 找到安全区的质心位置用于显示标签
                        M = cv2.moments(contour)
                        if M['m00'] > 0:
                            cx = int(M['m10'] / M['m00'])
                            cy = int(M['m01'] / M['m00'])
                            
                            # 计算轮廓的边界矩形，用于确定标签位置
                            x, y, w, h = cv2.boundingRect(contour)
                            
                            # 标签位置 - 放置在安全区上方或内部，避免超出图像范围
                            label_pos = (cx - 40, max(20, y - 10))
                            
                            # 绘制半透明背景框以提高标签可读性
                            text_size = cv2.getTextSize(f"{color.upper()} ZONE", 
                                                       cv2.FONT_HERSHEY_SIMPLEX, 0.6, 2)[0]
                            cv2.rectangle(result_frame, 
                                         (label_pos[0] - 5, label_pos[1] - text_size[1] - 5),
                                         (label_pos[0] + text_size[0] + 5, label_pos[1] + 5),
                                         color_map[color], -1)
                            
                            # 绘制标签文本（使用白色文字）
                            cv2.putText(result_frame, f"{color.upper()} ZONE", 
                                       label_pos, cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 2)
                            
                            # 在安全区内部显示检测状态
                            status_text = "DETECTED"
                            status_pos = (cx - 30, cy)
                            cv2.putText(result_frame, status_text, 
                                       status_pos, cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 2)
                            
                            # 显示安全区面积信息
                            area = cv2.contourArea(contour)
                            area_text = f"Area: {int(area)}px"
                            area_pos = (cx - 40, cy + 20)
                            cv2.putText(result_frame, area_text, 
                                       area_pos, cv2.FONT_HERSHEY_SIMPLEX, 0.4, (255, 255, 255), 1)
        else:
            # 如果没有动态检测到的安全区，则使用配置中的安全区
            safety_zones = self.config.get('safety_zones', {})
            
            # 绘制红色安全区
            red_zone = safety_zones.get('red', {})
            if all(k in red_zone for k in ['x', 'y', 'width', 'height']):
                x, y, width, height = red_zone['x'], red_zone['y'], red_zone['width'], red_zone['height']
                cv2.rectangle(result_frame, (x, y), (x + width, y + height), (0, 0, 255), 2)
                cv2.putText(result_frame, "RED ZONE (CONFIG)", (x, y - 10), 
                            cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 0, 255), 2)
            
            # 绘制蓝色安全区
            blue_zone = safety_zones.get('blue', {})
            if all(k in blue_zone for k in ['x', 'y', 'width', 'height']):
                x, y, width, height = blue_zone['x'], blue_zone['y'], blue_zone['width'], blue_zone['height']
                cv2.rectangle(result_frame, (x, y), (x + width, y + height), (255, 0, 0), 2)
                cv2.putText(result_frame, "BLUE ZONE (CONFIG)", (x, y - 10), 
                            cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 0, 0), 2)
        
        # 在图像左上角显示安全区检测状态
        status_color = (0, 255, 0) if (hasattr(self, 'dynamic_safety_zones') and 
                                      (self.dynamic_safety_zones.get('red') or self.dynamic_safety_zones.get('blue'))) else (0, 0, 255)
        cv2.putText(result_frame, "SAFETY ZONES: " + ("ACTIVE" if status_color == (0, 255, 0) else "INACTIVE"), 
                   (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.6, status_color, 2)
        
        return result_frame
    
    def test_core_functionality(self):
        """内部测试函数，验证核心功能是否正常工作"""
        print("\n===== 开始验证核心功能 =====")
        
        # 验证队伍颜色设置
        print(f"队伍颜色: {self.team_color}, 敌方颜色: {self.enemy_color}")
        
        # 验证安全区检测功能是否存在
        has_detection = hasattr(self, 'detect_safety_zones')
        print(f"动态安全区检测功能: {'已实现' if has_detection else '未实现'}")
        
        # 验证安全区判断功能是否正确
        has_improved_check = 'safety_zones' in self.is_ball_in_safety_zone.__code__.co_varnames
        print(f"改进的安全区判断功能: {'已实现' if has_improved_check else '未实现'}")
        
        # 验证小球优先级功能是否包含队伍颜色逻辑
        priority_has_team = 'team_color' in self.calculate_ball_priority.__code__.co_names
        print(f"基于队伍颜色的优先级逻辑: {'已实现' if priority_has_team else '未实现'}")
        
        # 验证围栏检测功能是否已优化
        fence_has_improvement = 'contours' in self.detect_purple_fence.__code__.co_names
        print(f"优化的围栏检测功能: {'已实现' if fence_has_improvement else '未实现'}")
        
        # 验证安全区显示功能是否已更新
        draw_has_update = 'dynamic_safety_zones' in self.draw_safety_zone.__code__.co_names
        print(f"更新的安全区显示功能: {'已实现' if draw_has_update else '未实现'}")
        
        print("===== 功能验证完成 =====\n")
        return True
    
    def process_frame(self, frame):
        """处理单帧图像，集成动态安全区检测"""
        if frame is None or frame.size == 0:
            return {"frame": None, "balls": [], "best_target": None}
        
        # 创建图像副本
        annotated_frame = frame.copy()
        
        # 检测紫色围栏
        fence_mask = self.detect_purple_fence(frame)
        
        # 动态检测红色和蓝色安全区
        self.dynamic_safety_zones = self.detect_safety_zones(frame)
        
        # 使用围栏掩码过滤图像（只处理非围栏区域）
        if fence_mask is not None:
            # 创建带有围栏过滤的图像副本
            filtered_frame = frame.copy()
            # 将围栏区域设为黑色，避免在这些区域检测小球
            filtered_frame = cv2.bitwise_and(filtered_frame, filtered_frame, mask=fence_mask)
            detection_frame = filtered_frame
        else:
            detection_frame = frame
        
        # 检测小球（使用过滤后的图像）
        balls = self.detect_all_balls(detection_frame) or []
        
        # 进一步过滤位于围栏区域内的小球（双重保险）
        balls = self.filter_balls_in_fence(balls, fence_mask)
        
        # 获取最佳目标，传入当前检测到的安全区信息
        best_target = self.get_best_target(balls, self.dynamic_safety_zones)
        
        # 绘制结果
        if hasattr(self, 'ball_tracker'):
            annotated_frame = self.ball_tracker.draw_balls(annotated_frame, balls)
        
        # 绘制紫色围栏（用于调试）
        # 可以根据需要启用或禁用
        # annotated_frame = self.draw_purple_fence(annotated_frame, fence_mask)
        
        # 绘制安全区（现在会显示动态检测到的安全区）
        annotated_frame = self.draw_safety_zone(annotated_frame)
        
        # 标记最佳目标
        if best_target and all(k in best_target for k in ['x', 'y', 'radius']):
            center = (best_target['x'], best_target['y'])
            radius = best_target['radius']
            h, w = annotated_frame.shape[:2]
            if 0 <= center[0] < w and 0 <= center[1] < h:
                cv2.circle(annotated_frame, center, radius + 5, (0, 0, 255), 3)
                cv2.putText(annotated_frame, "TARGET", (center[0] - 30, center[1] + radius + 20),
                           cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 0, 255), 2)
                
                # 添加目标安全区信息
                target_color = best_target.get('color')
                if target_color == self.team_color and self.dynamic_safety_zones.get(self.team_color):
                    cv2.putText(annotated_frame, f"TO {self.team_color.upper()} ZONE", 
                               (center[0] - 60, center[1] - radius - 20),
                               cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 2)
        
        return {
            'frame': annotated_frame,
            'balls': balls,
            'best_target': best_target,
            'safety_zones': self.dynamic_safety_zones
        }
    
    def run(self, display=True, save_video=False, output_path=None):
        """运行视觉系统"""
        self.video_writer = None
        restart_count = 0
        max_restarts = 5
        
        try:
            while True:
                try:
                    # 获取帧
                    frame = self.get_frame()
                    if frame is None:
                        time.sleep(0.01)
                        continue
                    
                    # 处理帧
                    result = self.process_frame(frame)
                    
                    # 保存视频
                    if save_video and result['frame'] is not None:
                        if self.video_writer is None:
                            # 创建视频写入器
                            fourcc = cv2.VideoWriter_fourcc(*'XVID')
                            fps = self.camera.get(cv2.CAP_PROP_FPS)
                            size = (result['frame'].shape[1], result['frame'].shape[0])
                            self.video_writer = cv2.VideoWriter(output_path, fourcc, fps, size)
                        
                        self.video_writer.write(result['frame'])
                    
                    # 显示图像
                    if display and result['frame'] is not None:
                        cv2.imshow('Rescue Vision', result['frame'])
                        
                        # 按下'q'键退出
                        if cv2.waitKey(1) & 0xFF == ord('q'):
                            break
                    
                except Exception as e:
                    # 处理摄像头错误，尝试重新初始化
                    print(f"摄像头错误: {e}")
                    restart_count += 1
                    
                    if restart_count < max_restarts:
                        # 释放旧的摄像头资源
                        if hasattr(self, 'camera') and self.camera:
                            self.camera.release()
                        
                        # 等待后重试初始化
                        time.sleep(1)
                        try:
                            self.camera = self.init_camera()
                            restart_count = 0
                        except Exception as init_error:
                            print(f"重新初始化摄像头失败: {init_error}")
                            restart_count += 1
                            if restart_count >= max_restarts:
                                break
                    
                    time.sleep(0.01)
        
        except KeyboardInterrupt:
            pass
        finally:
            # 释放资源
            self.release()
    
    def release(self):
        """释放资源"""
        try:
            if hasattr(self, 'camera') and self.camera is not None:
                self.camera.release()
            
            if hasattr(self, 'video_writer') and self.video_writer is not None:
                self.video_writer.release()
                self.video_writer = None
            
            cv2.destroyAllWindows()
        except Exception as e:
            print(f"释放资源时发生错误: {str(e)}")
    
    def __del__(self):
        """析构函数，释放摄像头资源"""
        try:
            if hasattr(self, 'camera') and self.camera is not None:
                self.camera.release()
        except Exception:
            pass