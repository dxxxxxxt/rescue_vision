import cv2
import json
import os
import numpy as np
import time
from color_detector import ColorDetector
from ball_tracker import BallTracker
from utils.logger_utils import get_logger

# 获取日志记录器
logger = get_logger(__name__)

class VisionCore:
    def __init__(self, config_loader):
        """
        视觉核心初始化
        :param config_loader: 配置加载器实例
        """
        # 使用统一的配置加载器
        self.config_loader = config_loader
        self.strategy_config = config_loader.strategy_config
        
        # 初始化摄像头
        vision_params = self.strategy_config.get('vision_params', {})
        self.camera_id = vision_params.get('camera_id', 0)
        self.image_width = vision_params.get('image_width', 640)
        self.image_height = vision_params.get('image_height', 480)
        
        # 初始化组件
        # 使用配置加载器中的HSV配置路径
        self.color_detector = ColorDetector(config_loader.get_hsv_config_path())
        # 使用配置文件中的小球半径参数
        min_radius = vision_params.get('min_ball_radius', 10)
        max_radius = vision_params.get('max_ball_radius', 100)
        self.ball_tracker = BallTracker(min_radius=min_radius, max_radius=max_radius)
        self.camera = self.init_camera()
        
        # 初始化视频编写器
        self.video_writer = None
        
        # 游戏策略参数
        self.team_color = self.strategy_config.get('team_color', 'red')
        self.enemy_color = 'blue' if self.team_color == 'red' else 'red'
        self.ball_priorities = self.strategy_config.get('ball_priorities', {})
        self.ball_counts = self.strategy_config.get('ball_counts', {})
        # 第一个夹取必须是己方球
        self.first_pick = True  # 标记是否为第一次夹取
        
        # 优先使用safety_zones数组配置
        safety_zones = self.strategy_config.get('safety_zones', [])
        
        # 初始化安全区
        self.safety_zones = []
        self.active_safety_zone = None
        
        # 处理safety_zones数组配置
        if safety_zones and isinstance(safety_zones, list):
            logger.info(f"找到{len(safety_zones)}个安全区配置")
            # 将safety_zones转换为程序可用的格式
            for zone_config in safety_zones:
                if zone_config.get('enabled', False):
                    zone = {
                        'name': zone_config.get('name', 'unnamed_zone'),
                        'enabled': True,
                        'type': zone_config.get('type', 'rectangle'),
                        'priority': zone_config.get('priority', 0),
                        'pixel_points': []
                    }
                    
                    # 处理position格式的配置
                    position = zone_config.get('position', {})
                    if position:
                        # 计算实际像素坐标
                        x = position.get('x', 0) * self.image_width
                        y = position.get('y', 0) * self.image_height
                        width = position.get('width', 0) * self.image_width
                        height = position.get('height', 0) * self.image_height
                        
                        zone['pixel_points'] = [
                            (int(x), int(y)),  # 左上角
                            (int(x + width), int(y + height))  # 右下角
                        ]
                        self.safety_zones.append(zone)
                        logger.info(f"添加安全区: {zone['name']}, 类型: {zone['type']}, 优先级: {zone['priority']}, 坐标: {zone['pixel_points']}")
        
        # 设置默认活动安全区
        if self.safety_zones:
            self.active_safety_zone = self.safety_zones[0]
            logger.info(f"默认活动安全区设置为: {self.active_safety_zone['name']}")
        
        # 兼容旧的safety_zone配置
        if not self.safety_zones:
            logger.warning("未找到有效的safety_zones配置，尝试使用旧的safety_zone配置")
            self.safety_zone = self.strategy_config.get('safety_zone', {
                'enabled': True,
                'type': 'rectangle',
                'points': [
                    {'x': 0.0, 'y': 0.0},  # 左上角 (相对于图像尺寸的比例)
                    {'x': 600/self.image_width, 'y': 300/self.image_height}  # 右下角 (固定600*300像素)
                ]
            })
            # 转换比例坐标为实际像素坐标
            self._convert_safety_zone_points()
            if hasattr(self, 'safety_zone') and self.safety_zone.get('enabled', False):
                self.safety_zones.append({
                    'name': 'legacy_safety_zone',
                    'enabled': True,
                    'type': self.safety_zone.get('type', 'rectangle'),
                    'pixel_points': self.safety_zone.get('pixel_points', [])
                })
        
    def load_strategy_config(self, config_path):
        """
        加载游戏策略配置
        :param config_path: 配置文件路径
        :return: 策略配置字典
        """
        # 默认配置模板
        default_config = {
            "team_color": "red",
            "ball_priority": ["red", "black", "yellow"],
            "auto_mode_duration": 300,
            "yellow_ball_rule": "collect",
            "ball_counts": {
                "red": 4,
                "blue": 4,
                "yellow": 2,
                "black": 2
            },
            "safety_zones": []
        }
        
        # 检查文件是否存在
        if not os.path.exists(config_path):
            logger.error(f"策略配置文件不存在: {config_path}")
            return default_config
        
        try:
            # 读取配置文件
            with open(config_path, 'r', encoding='utf-8') as f:
                config = json.load(f)
        except json.JSONDecodeError as e:
            logger.error(f"策略配置文件格式错误 (JSON解析失败): {str(e)}")
            return default_config
        except PermissionError as e:
            logger.error(f"没有权限读取策略配置文件: {str(e)}")
            return default_config
        
        # 验证必要配置项
        required_fields = ['team_color', 'ball_priority']
        for field in required_fields:
            if field not in config:
                logger.warning(f"策略配置缺少必要字段: {field}，使用默认值")
                if field == 'team_color':
                    config[field] = 'red'
                elif field == 'ball_priority':
                    config[field] = ['red', 'black', 'yellow']
        
        # 验证队伍颜色格式
        if config['team_color'] not in ['red', 'blue']:
            logger.warning(f"无效的队伍颜色: {config['team_color']}，使用默认值'red'")
            config['team_color'] = 'red'
        
        logger.info(f"策略配置文件加载成功: {config_path}")
        return config
    
    def init_camera(self):
        """
        初始化摄像头
        
        Returns:
            camera: 初始化好的摄像头对象，失败时返回None
        """
        try:
            logger.info(f"正在初始化摄像头，ID: {self.camera_id}")
            camera = cv2.VideoCapture(self.camera_id)
            
            # 设置摄像头参数
            vision_params = self.strategy_config.get('vision_params', {})
            width = vision_params.get('image_width', 640)
            height = vision_params.get('image_height', 480)
            
            camera.set(cv2.CAP_PROP_FRAME_WIDTH, width)
            camera.set(cv2.CAP_PROP_FRAME_HEIGHT, height)
            
            if not camera.isOpened():
                logger.error(f"无法打开摄像头 {self.camera_id}，请检查设备连接")
                return None
                
            # 尝试捕获一帧，确保摄像头正常工作
            ret, _ = camera.read()
            if not ret:
                camera.release()
                logger.error(f"摄像头 {self.camera_id} 无法捕获图像")
                return None
                
            logger.info(f"摄像头已成功初始化，ID: {self.camera_id}")
            return camera
            
        except Exception as e:
            logger.error(f"初始化摄像头失败: {str(e)}")
            return None
    
    def get_frame(self):
        """
        获取摄像头当前帧
        
        Returns:
            frame: 摄像头图像帧，失败时返回None
        """
        
        if not self.camera or not self.camera.isOpened():
            # 尝试重新打开摄像头
            try:
                logger.warning(f"摄像头未打开，尝试重新初始化，ID: {self.camera_id}")
                if self.camera:
                    self.camera.release()
                self.camera = cv2.VideoCapture(self.camera_id)
                # 设置摄像头参数
                vision_params = self.strategy_config.get('vision_params', {})
                width = vision_params.get('image_width', 640)
                height = vision_params.get('image_height', 480)
                self.camera.set(cv2.CAP_PROP_FRAME_WIDTH, width)
                self.camera.set(cv2.CAP_PROP_FRAME_HEIGHT, height)
                time.sleep(0.2)  # 给摄像头一些初始化时间
                
                if not self.camera.isOpened():
                    logger.error("摄像头无法打开，请检查设备连接")
                    return None
                
            except Exception as e:
                logger.error(f"重新打开摄像头失败: {str(e)}")
                return None
        
        # 设置获取帧的超时
        timeout = time.time() + 2.0  # 2秒超时
        retry_count = 0
        max_retries = 3
        
        while time.time() < timeout:
            ret, frame = self.camera.read()
            if ret and frame is not None and frame.size > 0:
                return frame
            
            retry_count += 1
            if retry_count > max_retries:
                break
                
            logger.warning("获取帧失败，重试...")
            time.sleep(0.1)
        
        # 尝试重新初始化摄像头
        if self.camera:
            self.camera.release()
            self.camera = self.init_camera()
            
        # 重新初始化后再次尝试获取帧
        if self.camera and self.camera.isOpened():
            ret, frame = self.camera.read()
            if ret and frame is not None and frame.size > 0:
                return frame
        
        logger.error("无法获取有效图像帧，请检查摄像头连接")
        return None
        
    def detect_all_balls(self, frame):
        """
        检测所有小球
        :param frame: BGR图像
        :return: 检测到的小球列表，失败时返回空列表
        """
        # 验证输入
        if frame is None or frame.size == 0:
            logger.error("输入图像为空或无效")
            return []
        
        # 检测所有颜色
        try:
            color_masks = self.color_detector.detect_all_colors(frame)
            if color_masks is None or not isinstance(color_masks, dict):
                logger.error("颜色检测器返回的结果类型不正确")
                return []
        except Exception as color_err:
            logger.error(f"颜色检测失败: {str(color_err)}")
            return []
        
        # 跟踪小球
        try:
            balls = self.ball_tracker.track_balls(color_masks)
            if balls is None or not isinstance(balls, list):
                logger.error("小球跟踪器返回的结果类型不正确")
                return []
            return balls
        except Exception as track_err:
            logger.error(f"小球跟踪失败: {str(track_err)}")
            return []
    
    def calculate_ball_priority(self, ball):
        """
        计算小球优先级
        :param ball: 小球对象
        :return: 优先级分数
        """
        color = ball['color']
        
        # 不能夹取对方小球
        if color == self.enemy_color:
            return 0  # 对方球优先级为0，不被选择
        
        # 第一个夹取必须是己方球
        if self.first_pick:
            if color == self.team_color:
                return 1000  # 给予极高优先级
            else:
                return 0  # 其他颜色优先级为0
        
        # 正常优先级计算
        if color == self.team_color:
            return self.ball_priorities.get('team', 100)
        else:
            return self.ball_priorities.get(color, 0)
    
    def get_prioritized_balls(self, balls):
        """
        获取按优先级排序的小球列表
        :param balls: 检测到的小球列表
        :return: 按优先级排序的小球列表
        """
        # 计算每个小球的优先级
        for ball in balls:
            ball['priority'] = self.calculate_ball_priority(ball)
        
        # 按优先级降序排序
        sorted_balls = sorted(balls, key=lambda x: x['priority'], reverse=True)
        
        return sorted_balls
    
    def get_best_target(self, balls, current_balls=[]):
        """
        获取最佳目标小球
        :param balls: 检测到的小球列表
        :param current_balls: 当前已夹取的小球列表（由于每次只夹一个，该参数实际无用，但保留兼容）
        :return: 最佳目标小球，若没有符合条件的则返回None
        """
        if not balls:
            return None
        
        # 过滤掉安全区内的小球
        filtered_balls = []
        for ball in balls:
            if not self.is_ball_in_safety_zone(ball):
                filtered_balls.append(ball)
            else:
                logger.debug(f"小球 (颜色: {ball['color']}, 坐标: ({ball['x']}, {ball['y']})) 在安全区内，将被过滤掉")
        
        if not filtered_balls:
            logger.debug("所有检测到的小球都在安全区内")
            return None
        
        prioritized_balls = self.get_prioritized_balls(filtered_balls)
        
        # 检查黄色球限制
        for ball in prioritized_balls:
            if ball['priority'] <= 0:
                continue
                
            # 检查黄色球限制条件
            yellow_allowed, reason = self.check_yellow_ball_restriction(current_balls, ball)
            if not yellow_allowed:
                logger.debug(f"跳过黄色球: {reason}")
                continue
                
            # 检查转运数量限制
            transfer_allowed, reason = self.check_transfer_limit(current_balls, ball)
            if not transfer_allowed:
                logger.debug(f"跳过小球: {reason}")
                continue
                
            # 黄色球数量限制已在check_yellow_ball_restriction方法中检查
            # 不需要在此处重复检查
                
            logger.info(f"选择目标: {ball['color']} 球 - 优先级: {ball['priority']}")
            return ball
            
        logger.debug("没有找到符合条件的目标小球")
        return None
    
    def set_first_pick_done(self):
        """
        标记第一次夹取已完成
        """
        self.first_pick = False
        logger.info("第一次夹取已完成，现在按照正常优先级选择目标")
    
    def check_transfer_limit(self, balls, target_ball):
        """
        检查一次转移的数量限制（普通球 + 核心球不能超过4个）
        :param balls: 当前已夹取的小球列表
        :param target_ball: 目标小球
        :return: (是否允许夹取, 原因)
        """
        # 黄色球单独计算，不参与数量限制
        if target_ball['color'] == 'yellow' or any(ball['color'] == 'yellow' for ball in balls):
            return True, ""
        
        # 计算当前已夹取的普通球和核心球数量
        current_count = len([ball for ball in balls if ball['color'] in [self.team_color, 'black']])
        
        # 如果目标球是普通球或核心球，检查数量限制
        if target_ball['color'] in [self.team_color, 'black']:
            if current_count >= 4:
                return False, "一次转移不能超过4个普通球+核心球"
        
        return True, ""
    
    def calculate_score(self, balls, mode='autonomous'):
        """
        根据比赛规则计算得分
        :param balls: 转运的小球列表
        :param mode: 模式（'autonomous'或'remote'）
        :return: 得分
        """
        score = 0
        
        # 得分规则矩阵
        scores = {
            'autonomous': {
                'team': 5,    # 己方普通球
                'black': 10,  # 核心球
                'yellow': -5, # 危险球
                'enemy': -10  # 对方球
            },
            'remote': {
                'team': 2,    # 己方普通球
                'black': 6,   # 核心球
                'yellow': -2, # 危险球
                'enemy': -5   # 对方球
            }
        }
        
        for ball in balls:
            color = ball['color']
            if color == self.team_color:
                score += scores[mode]['team']
            elif color == 'black':
                score += scores[mode]['black']
            elif color == 'yellow':
                score += scores[mode]['yellow']
            elif color == self.enemy_color:
                score += scores[mode]['enemy']
        
        return score
    
    def check_yellow_ball_restriction(self, balls, target_ball):
        """
        检查黄色球（危险球）的限制条件
        :param balls: 当前已夹取的小球列表
        :param target_ball: 目标小球
        :return: (是否允许夹取, 原因)
        """
        # 统计当前已夹取的黄色球数量
        yellow_count = sum(1 for b in balls if b['color'] == 'yellow')
        
        # 黄色球必须单独转运
        if target_ball['color'] == 'yellow':
            # 检查数量限制
            if yellow_count >= 1:
                return False, "黄色球数量已达上限（1个）"
            # 检查单独转运规则
            if len(balls) > 0:
                return False, "黄色球必须单独转运，当前已夹取其他小球"
            return True, ""
        
        # 已夹取黄色球时不能夹取其他小球
        if any(ball['color'] == 'yellow' for ball in balls):
            return False, "已夹取黄色球，不能同时夹取其他小球"
        
        return True, ""
    
    def _convert_safety_zone_points(self):
        """
        将安全区的比例坐标转换为实际像素坐标
        """
        if not hasattr(self, 'safety_zone') or not self.safety_zone.get('enabled', False):
            return
        
        try:
            points = self.safety_zone.get('points', [])
            self.safety_zone['pixel_points'] = []
            
            for point in points:
                # 将比例坐标转换为像素坐标
                pixel_x = int(point['x'] * self.image_width)
                pixel_y = int(point['y'] * self.image_height)
                self.safety_zone['pixel_points'].append((pixel_x, pixel_y))
            
            logger.info(f"安全区配置: {self.safety_zone['type']}")
            logger.info(f"安全区像素坐标: {self.safety_zone['pixel_points']}")
            
        except Exception as e:
            logger.error(f"转换安全区坐标失败: {e}")
            self.safety_zone['enabled'] = False
    
    def is_ball_in_safety_zone(self, ball):
        """
        检测小球是否在安全区内
        :param ball: 小球对象，包含x, y坐标
        :return: True表示在安全区内，False表示不在
        """
        if not self.safety_zones:
            # 兼容旧的safety_zone配置
            if hasattr(self, 'safety_zone') and self.safety_zone.get('enabled', False):
                try:
                    ball_point = (ball['x'], ball['y'])
                    points = self.safety_zone['pixel_points']
                    
                    # 检查小球是否在长方形安全区内
                    if self.safety_zone['type'] == 'rectangle' and len(points) >= 2:
                        # 矩形由左上角和右下角两个点定义
                        top_left = points[0]
                        bottom_right = points[1]
                        
                        # 检查点是否在矩形范围内
                        result = (top_left[0] <= ball_point[0] <= bottom_right[0]) and \
                               (top_left[1] <= ball_point[1] <= bottom_right[1])
                        if result:
                            logger.debug(f"小球 (颜色: {ball['color']}, 坐标: ({ball['x']}, {ball['y']})) 在旧格式安全区内")
                        return result
                    return False
                except Exception as e:
                    logger.error(f"检测旧格式安全区失败: {e}")
            return False
        
        # 检查所有启用的安全区
        try:
            ball_point = (ball['x'], ball['y'])
            
            for zone in self.safety_zones:
                if zone.get('enabled', False) and zone.get('pixel_points'):
                    points = zone['pixel_points']
                    
                    # 检查小球是否在长方形安全区内
                    if zone['type'] == 'rectangle' and len(points) >= 2:
                        # 矩形由左上角和右下角两个点定义
                        top_left = points[0]
                        bottom_right = points[1]
                        
                        # 检查点是否在矩形范围内
                        if (top_left[0] <= ball_point[0] <= bottom_right[0]) and \
                           (top_left[1] <= ball_point[1] <= bottom_right[1]):
                            logger.debug(f"小球 (颜色: {ball['color']}, 坐标: ({ball['x']}, {ball['y']})) 在安全区 {zone['name']} 内")
                            return True
            
            return False
            
        except Exception as e:
            logger.error(f"检测安全区失败: {e}")
            return False
    
    def draw_safety_zone(self, frame):
        """
        在图像上绘制安全区
        :param frame: 输入图像
        :return: 绘制了安全区的图像
        """
        try:
            # 优先绘制新的safety_zones配置
            for zone in self.safety_zones:
                if zone.get('enabled', False) and zone.get('pixel_points'):
                    points = zone['pixel_points']
                    
                    # 绘制长方形安全区
                    if zone['type'] == 'rectangle' and len(points) >= 2:
                        # 矩形由左上角和右下角两个点定义
                        top_left = points[0]
                        bottom_right = points[1]
                        
                        # 绘制半透明矩形
                        overlay = frame.copy()
                        cv2.rectangle(overlay, top_left, bottom_right, (0, 0, 255), -1)
                        frame = cv2.addWeighted(overlay, 0.3, frame, 0.7, 0)
                        
                        # 绘制矩形边框
                        cv2.rectangle(frame, top_left, bottom_right, (0, 0, 255), 2)
                        
                        # 添加安全区文字说明
                        zone_name = zone.get('name', "SAFETY ZONE")
                        cv2.putText(frame, zone_name, (top_left[0] + 10, top_left[1] - 10),
                                   cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 0, 255), 2)
            
            # 兼容旧的safety_zone配置
            if not self.safety_zones and hasattr(self, 'safety_zone') and self.safety_zone.get('enabled', False) and 'pixel_points' in self.safety_zone:
                points = self.safety_zone['pixel_points']
                
                # 绘制长方形安全区
                if self.safety_zone['type'] == 'rectangle' and len(points) >= 2:
                    # 矩形由左上角和右下角两个点定义
                    top_left = points[0]
                    bottom_right = points[1]
                    
                    # 绘制半透明矩形
                    overlay = frame.copy()
                    cv2.rectangle(overlay, top_left, bottom_right, (0, 0, 255), -1)
                    frame = cv2.addWeighted(overlay, 0.3, frame, 0.7, 0)
                    
                    # 绘制矩形边框
                    cv2.rectangle(frame, top_left, bottom_right, (0, 0, 255), 2)
                    
                    # 添加安全区文字说明
                    cv2.putText(frame, "SAFETY ZONE", (top_left[0] + 10, top_left[1] - 10),
                               cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 0, 255), 2)
        
        except Exception as e:
            logger.error(f"绘制安全区失败: {e}")
        
        return frame
    
    def process_frame(self, frame):
        """
        处理单帧图像
        :param frame: BGR图像
        :return: 处理结果（带标注的图像、检测到的小球、最佳目标），如果输入无效返回None, [], None
        """
        # 验证输入
        if frame is None or frame.size == 0:
            logger.error("输入图像为空或无效")
            return None, [], None
        
        # 确保图像可修改
        try:
            if frame.flags.writeable:
                annotated_frame = frame.copy()
            else:
                logger.warning("输入图像不可写，创建可写副本")
                annotated_frame = frame.copy()
        except Exception as e:
            logger.error(f"创建图像副本失败: {str(e)}")
            return None, [], None
        
        # 检测小球
        balls = []
        try:
            balls = self.detect_all_balls(frame)
            if not isinstance(balls, list):
                logger.error("detect_all_balls返回的结果类型不正确")
                balls = []
        except Exception as detect_err:
            # 记录错误但继续执行，不中断处理流程
            logger.error(f"小球检测失败: {detect_err}")
            balls = []
        
        # 获取最佳目标
        best_target = None
        try:
            best_target = self.get_best_target(balls)
        except Exception as target_err:
            # 记录错误但继续执行
            logger.error(f"获取最佳目标失败: {target_err}")
        
        # 绘制结果
        try:
            if hasattr(self, 'ball_tracker'):
                annotated_frame = self.ball_tracker.draw_balls(annotated_frame, balls)
            else:
                logger.warning("ball_tracker未初始化，跳过绘制")
        except Exception as draw_err:
            logger.error(f"绘制小球失败: {draw_err}")
        
        # 绘制安全区
        try:
            annotated_frame = self.draw_safety_zone(annotated_frame)
        except Exception as safety_err:
            logger.error(f"绘制安全区失败: {safety_err}")
        
        # 标记最佳目标
        if best_target:
            try:
                # 验证最佳目标数据
                if all(k in best_target for k in ['x', 'y', 'radius']):
                    center = (best_target['x'], best_target['y'])
                    radius = best_target['radius']
                    # 确保坐标有效
                    h, w = annotated_frame.shape[:2]
                    if 0 <= center[0] < w and 0 <= center[1] < h:
                        # 绘制红色边框表示最佳目标
                        cv2.circle(annotated_frame, center, radius + 5, (0, 0, 255), 3)
                        cv2.putText(annotated_frame, "TARGET", (center[0] - 30, center[1] + radius + 20),
                                   cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 0, 255), 2)
                    else:
                        logger.warning(f"最佳目标坐标超出图像范围: {center}")
                else:
                    logger.warning("最佳目标数据不完整")
            except Exception as mark_err:
                logger.error(f"标记最佳目标失败: {mark_err}")
        
        return {
            'frame': annotated_frame,
            'balls': balls,
            'best_target': best_target
        }
    
    def run(self, display=True, save_video=False, output_path=None):
        """
        运行视觉系统
        :param display: 是否显示图像
        :param save_video: 是否保存视频
        :param output_path: 视频保存路径
        """
        self.video_writer = None
        restart_count = 0
        max_restarts = 5
        
        try:
            while True:
                try:
                    # 获取帧
                    frame = self.get_frame()
                    
                    # 处理帧
                    result = self.process_frame(frame)
                    
                    # 保存视频
                    if save_video and result['frame'] is not None:
                        try:
                            if self.video_writer is None:
                                # 创建视频写入器
                                fourcc = cv2.VideoWriter_fourcc(*'XVID')
                                fps = self.camera.get(cv2.CAP_PROP_FPS)
                                size = (result['frame'].shape[1], result['frame'].shape[0])
                                self.video_writer = cv2.VideoWriter(output_path, fourcc, fps, size)
                                logger.info(f"视频写入器已初始化，保存路径: {output_path}")
                            self.video_writer.write(result['frame'])
                        except Exception as e:
                            logger.error(f"保存视频帧失败: {e}")
                            # 尝试重新初始化视频写入器
                            if self.video_writer:
                                self.video_writer.release()
                                self.video_writer = None
                    
                    # 显示图像
                    if display and result['frame'] is not None:
                        cv2.imshow('Rescue Vision', result['frame'])
                        
                        # 按下'q'键退出
                        if cv2.waitKey(1) & 0xFF == ord('q'):
                            logger.info("用户按q键退出")
                            break
                    
                    # 输出检测结果
                    logger.debug(f"检测到 {len(result['balls'])} 个小球")
                    if result['best_target']:
                        logger.info(f"最佳目标: {result['best_target']['color']} 球 - 位置 ({result['best_target']['x']}, {result['best_target']['y']})")
                
                except Exception as e:
                    # 处理摄像头错误，尝试重新初始化
                    logger.error(f"摄像头错误: {e}")
                    restart_count += 1
                    
                    if restart_count < max_restarts:
                        logger.info(f"尝试重新初始化摄像头，重启计数: {restart_count}/{max_restarts}")
                        # 释放旧的摄像头资源
                        if hasattr(self, 'camera') and self.camera:
                            self.camera.release()
                            self.camera = None
                        
                        # 等待一段时间后重试
                        time.sleep(1)
                        try:
                            self.camera = self.init_camera()
                        except Exception as init_error:
                            logger.error(f"重新初始化摄像头失败: {init_error}")
                    else:
                        logger.error(f"达到最大重启次数，程序退出")
                        break
                    
                    # 短暂暂停避免CPU占用过高
                    time.sleep(0.01)
        
        except KeyboardInterrupt:
            logger.info("视觉系统已停止")
        except Exception as e:
            logger.error(f"运行时发生严重错误: {e}")
        finally:
            # 释放资源
            self.release()
    
    def release(self):
        """
        释放资源
        """
        try:
            if hasattr(self, 'camera') and self.camera is not None:
                self.camera.release()
                logger.info("摄像头资源已释放")
            
            if hasattr(self, 'video_writer') and self.video_writer is not None:
                self.video_writer.release()
                self.video_writer = None
                logger.info("视频保存完成")
            
            cv2.destroyAllWindows()
        except Exception as e:
            logger.error(f"释放资源时发生错误: {str(e)}")
    
    def __del__(self):
        """
        析构函数，释放摄像头资源
        """
        try:
            if hasattr(self, 'camera') and self.camera is not None:
                self.camera.release()
        except Exception as e:
            # 析构函数中不应抛出异常
            pass