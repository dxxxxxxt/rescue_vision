import cv2
import json
import os
import numpy as np
from color_detector import ColorDetector
from ball_tracker import BallTracker

class VisionCore:
    def __init__(self, hsv_config_path, strategy_config_path):
        """
        视觉核心初始化
        :param hsv_config_path: HSV阈值配置文件路径
        :param strategy_config_path: 游戏策略配置文件路径
        """
        # 加载配置
        self.strategy_config = self.load_strategy_config(strategy_config_path)
        
        # 初始化摄像头
        vision_params = self.strategy_config.get('vision_params', {})
        self.camera_id = vision_params.get('camera_id', 0)
        self.image_width = vision_params.get('image_width', 640)
        self.image_height = vision_params.get('image_height', 480)
        
        # 初始化组件
        self.color_detector = ColorDetector(hsv_config_path)
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
        # 新规则：第一个夹取必须是己方球
        self.first_pick = True  # 标记是否为第一次夹取
        
        # 安全区配置 - 为600*300的长方形
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
        
    def load_strategy_config(self, config_path):
        """
        加载游戏策略配置
        :param config_path: 配置文件路径
        :return: 策略配置字典
        """
        if not os.path.exists(config_path):
            raise FileNotFoundError(f"策略配置文件不存在: {config_path}")
        
        with open(config_path, 'r', encoding='utf-8') as f:
            return json.load(f)
    
    def init_camera(self):
        """
        初始化摄像头
        
        Raises:
            RuntimeError: 当无法初始化摄像头时抛出异常
        
        Returns:
            camera: 初始化好的摄像头对象
        """
        try:
            camera = cv2.VideoCapture(self.camera_id)
            # 设置摄像头参数
            vision_params = self.strategy_config.get('vision_params', {})
            width = vision_params.get('image_width', 640)
            height = vision_params.get('image_height', 480)
            
            camera.set(cv2.CAP_PROP_FRAME_WIDTH, width)
            camera.set(cv2.CAP_PROP_FRAME_HEIGHT, height)
            
            if not camera.isOpened():
                raise RuntimeError(f"无法打开摄像头 {self.camera_id}，请检查设备连接")
                
            print(f"摄像头已成功初始化，ID: {self.camera_id}")
            return camera
            
        except Exception as e:
            raise RuntimeError(f"初始化摄像头失败: {str(e)}")
    
    def get_frame(self):
        """
        获取摄像头当前帧
        
        Returns:
            frame: 摄像头图像帧
            
        Raises:
            RuntimeError: 当无法获取有效帧时抛出异常
        """
        import time
        
        if not self.camera.isOpened():
            # 尝试重新打开摄像头
            try:
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
                    raise RuntimeError("摄像头无法打开，请检查设备连接")
                
            except Exception as e:
                raise RuntimeError(f"重新打开摄像头失败: {str(e)}")
        
        # 获取帧
        ret, frame = self.camera.read()
        if not ret or frame is None:
            raise RuntimeError("无法获取摄像头帧，请检查摄像头")
        
        return frame
    
    def detect_all_balls(self, frame):
        """
        检测所有小球
        :param frame: BGR图像
        :return: 检测到的小球列表
        """
        # 检测所有颜色
        color_masks = self.color_detector.detect_all_colors(frame)
        
        # 跟踪小球
        balls = self.ball_tracker.track_balls(color_masks)
        
        return balls
    
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
                print(f"小球 (颜色: {ball['color']}, 坐标: ({ball['x']}, {ball['y']})) 在安全区内，将被过滤掉")
        
        if not filtered_balls:
            print("所有检测到的小球都在安全区内")
            return None
        
        prioritized_balls = self.get_prioritized_balls(filtered_balls)
        
        # 由于每次只夹取一个小球，且已排除对方球，直接返回最高优先级的球
        # 黄色球单独转运规则在每次只夹一个的情况下自动满足
        return prioritized_balls[0] if prioritized_balls[0]['priority'] > 0 else None
    
    def set_first_pick_done(self):
        """
        标记第一次夹取已完成
        """
        self.first_pick = False
        print("第一次夹取已完成，现在按照正常优先级选择目标")
    
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
        # 黄色球必须单独转运
        if target_ball['color'] == 'yellow':
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
        if not self.safety_zone.get('enabled', False):
            return
        
        try:
            points = self.safety_zone.get('points', [])
            self.safety_zone['pixel_points'] = []
            
            for point in points:
                # 将比例坐标转换为像素坐标
                pixel_x = int(point['x'] * self.image_width)
                pixel_y = int(point['y'] * self.image_height)
                self.safety_zone['pixel_points'].append((pixel_x, pixel_y))
            
            print(f"安全区配置: {self.safety_zone['type']}")
            print(f"安全区像素坐标: {self.safety_zone['pixel_points']}")
            
        except Exception as e:
            print(f"转换安全区坐标失败: {e}")
            self.safety_zone['enabled'] = False
    
    def is_ball_in_safety_zone(self, ball):
        """
        检测小球是否在安全区内
        :param ball: 小球对象，包含x, y坐标
        :return: True表示在安全区内，False表示不在
        """
        if not self.safety_zone.get('enabled', False):
            return False
        
        try:
            ball_point = (ball['x'], ball['y'])
            points = self.safety_zone['pixel_points']
            
            # 检查小球是否在长方形安全区内
            if self.safety_zone['type'] == 'rectangle' and len(points) >= 2:
                # 矩形由左上角和右下角两个点定义
                top_left = points[0]
                bottom_right = points[1]
                
                # 检查点是否在矩形范围内
                return (top_left[0] <= ball_point[0] <= bottom_right[0]) and \
                       (top_left[1] <= ball_point[1] <= bottom_right[1])
            
            return False
            
        except Exception as e:
            print(f"检测安全区失败: {e}")
            return False
    
    def draw_safety_zone(self, frame):
        """
        在图像上绘制安全区
        :param frame: 输入图像
        :return: 绘制了安全区的图像
        """
        if not self.safety_zone.get('enabled', False) or 'pixel_points' not in self.safety_zone:
            return frame
        
        try:
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
            print(f"绘制安全区失败: {e}")
        
        return frame
    
    def process_frame(self, frame):
        """
        处理单帧图像
        :param frame: BGR图像
        :return: 处理结果（带标注的图像、检测到的小球、最佳目标）
        """
        # 检测小球
        balls = self.detect_all_balls(frame)
        
        # 获取最佳目标
        best_target = self.get_best_target(balls)
        
        # 绘制结果
        annotated_frame = self.ball_tracker.draw_balls(frame, balls)
        
        # 绘制安全区
        annotated_frame = self.draw_safety_zone(annotated_frame)
        
        # 标记最佳目标
        if best_target:
            center = (best_target['x'], best_target['y'])
            radius = best_target['radius']
            # 绘制红色边框表示最佳目标
            cv2.circle(annotated_frame, center, radius + 5, (0, 0, 255), 3)
            cv2.putText(annotated_frame, "TARGET", (center[0] - 30, center[1] + radius + 20),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 0, 255), 2)
        
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
        
        try:
            while True:
                # 获取帧
                frame = self.get_frame()
                
                # 处理帧
                result = self.process_frame(frame)
                
                # 保存视频
                if save_video:
                    if self.video_writer is None:
                        # 创建视频写入器
                        fourcc = cv2.VideoWriter_fourcc(*'XVID')
                        fps = self.camera.get(cv2.CAP_PROP_FPS)
                        size = (result['frame'].shape[1], result['frame'].shape[0])
                        self.video_writer = cv2.VideoWriter(output_path, fourcc, fps, size)
                    self.video_writer.write(result['frame'])
                
                # 显示图像
                if display:
                    cv2.imshow('Rescue Vision', result['frame'])
                    
                    # 按下'q'键退出
                    if cv2.waitKey(1) & 0xFF == ord('q'):
                        break
                
                # 输出检测结果
                print(f"检测到 {len(result['balls'])} 个小球")
                if result['best_target']:
                    print(f"最佳目标: {result['best_target']['color']} 球 - 位置 ({result['best_target']['x']}, {result['best_target']['y']})")
        
        except KeyboardInterrupt:
            print("视觉系统已停止")
        
        finally:
            # 释放资源
            self.camera.release()
            if video_writer:
                video_writer.release()
            if display:
                cv2.destroyAllWindows()
    
    def release(self):
        """
        释放资源
        """
        try:
            if hasattr(self, 'camera') and self.camera is not None:
                self.camera.release()
                print("摄像头资源已释放")
            
            if hasattr(self, 'video_writer') and self.video_writer is not None:
                self.video_writer.release()
                self.video_writer = None
                print("视频保存完成")
            
            cv2.destroyAllWindows()
        except Exception as e:
            print(f"释放资源时发生错误: {str(e)}")
    
    def __del__(self):
        """
        析构函数，释放摄像头资源
        """
        if hasattr(self, 'camera'):
            self.camera.release()