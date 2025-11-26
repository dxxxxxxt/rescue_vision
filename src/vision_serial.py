import serial
import time
from serial import TimeoutException
from utils.logger_utils import get_logger

class VisionSerial:
    def __init__(self, port='/dev/ttyUSB0', baudrate=115200, team_color=None):
        self.logger = get_logger(__name__)
        self.port = port
        self.baudrate = 115200
        self.ser = None
        self.is_connected = False
        
        # 通信协议常量
        self.START_BYTE = 0xAA
        self.END_BYTE = 0xBB
        
        # 小球颜色映射
        self.color_to_id = {
            'red': 0,     # 红色小球
            'blue': 1,    # 蓝色小球  
            'yellow': 2,  # 黄色小球（危险目标）
            'black': 3    # 黑色小球（核心目标）
        }
        
        # 安全区颜色映射 
        self.safety_zone_color_to_id = {
            'red': 4,     # 红色安全区
            'blue': 5     # 蓝色安全区
        }
        
        # 图像参数
        self.image_width = 640
        self.image_height = 480
        self.center_x = self.image_width // 2
        self.center_y = self.image_height // 2
        
        # 距离估算参数
        self.actual_diameter_mm = 40
        self.reference_pixel_radius = 20
        self.reference_distance_mm = 500
        
        # 初始化队伍颜色和优先级
        self.team_color = None
        self.opponent_color = None
        self.priorities = {}
        
        if team_color:
            self.set_team_color(team_color)
        
        self.connect()

    def set_team_color(self, team_color):
        # 设置己方队伍颜色
        if team_color not in ['red', 'blue']:
            self.logger.error(f"无效的队伍颜色: {team_color}，请输入 'red' 或 'blue'")
            return False
            
        self.team_color = team_color
        self.opponent_color = 'blue' if team_color == 'red' else 'red'
        
        # 根据己方颜色设置优先级
        self.priorities = {
            'black': 30,   # 核心目标 - 最高优先级
            'yellow': 20,  # 危险目标
            team_color: 10,     # 己方普通目标
            self.opponent_color: 0  # 敌方目标 - 不收集
        }
        
        self.logger.info(f"队伍颜色设置: 己方{self.team_color.upper()}队")
        return True

    def connect(self):
        # 连接串口
        try:
            # 确保之前的连接已关闭
            self.disconnect()
            
            self.logger.info(f"尝试连接串口: {self.port} 波特率: {self.baudrate}")
            self.ser = serial.Serial(
                port=self.port,
                baudrate=self.baudrate,
                bytesize=serial.EIGHTBITS,
                parity=serial.PARITY_NONE,
                stopbits=serial.STOPBITS_ONE,
                timeout=0.1,
                write_timeout=0.5
            )
            
            if self.ser.is_open:
                self.is_connected = True
                self.logger.info(f"串口连接成功: {self.port}")
                return True
        except serial.SerialException as e:
            self.logger.error(f"串口通信异常: {e}")
        except Exception as e:
            self.logger.error(f"连接串口时发生未知错误: {e}")
            
        self.is_connected = False
        return False
            
    def disconnect(self):
        # 断开并关闭串口连接
        try:
            if self.ser and self.ser.is_open:
                self.ser.close()
                self.logger.info(f"串口已关闭: {self.port}")
            self.is_connected = False
        except Exception as e:
            self.logger.error(f"关闭串口时发生错误: {e}")

    def ensure_connected(self):
        # 确保串口连接
        if not self.is_connected or not self.ser or not self.ser.is_open:
            return self.connect()
        return True
        
    def receive_feedback(self):
        # 接收电控系统的反馈数据
        if not self.ensure_connected():
            return None
            
        try:
            # 等待接收数据
            if self.ser.in_waiting > 0:
                # 读取可用数据
                data = self.ser.read(min(self.ser.in_waiting, 128))
                
                # 寻找起始字节
                start_index = data.find(self.START_BYTE)
                if start_index == -1:
                    return None
                
                # 检查剩余数据是否足够
                remaining_data = data[start_index:]
                if len(remaining_data) < 6:  # 最小数据包大小
                    return None
                
                # 提取数据包
                packet = remaining_data[:6]
                
                # 验证结束字节和校验和
                if packet[5] != self.END_BYTE:
                    return None
                
                checksum = sum(packet[1:4]) & 0xFF
                if checksum != packet[4]:
                    return None
                
                # 解析数据
                feedback_type = packet[1]
                state_data = int.from_bytes(packet[2:4], byteorder='little', signed=True)
                
                return {
                    "type": feedback_type,
                    "state": state_data,
                    "raw_data": packet
                }
                
        except Exception as e:
            self.logger.error(f"接收电控反馈时发生错误: {e}")
            self.disconnect()
        
        return None

    def send_ball_data(self, dx, dy, ball_color, distance):
        # 发送小球数据给电控系统
        if not self.ensure_connected():
            return False

        try:
            # 数据验证
            if ball_color not in self.color_to_id:
                self.logger.error(f"无效的颜色: {ball_color}")
                return False
                
            # 边界检查
            dx = max(-32768, min(dx, 32767))
            dy = max(-32768, min(dy, 32767))
            distance = max(0, min(distance, 65535))
            
            ball_id = self.color_to_id[ball_color]
            
            # 构建数据包
            packet = bytearray([self.START_BYTE])
            packet.extend(dx.to_bytes(2, byteorder='little', signed=True))
            packet.extend(dy.to_bytes(2, byteorder='little', signed=True))
            packet.append(ball_id)
            packet.extend(distance.to_bytes(2, byteorder='little', signed=False))
            
            # 计算校验和
            checksum = sum(packet[1:]) & 0xFF
            packet.append(checksum)
            packet.append(self.END_BYTE)
            
            # 发送数据
            self.ser.write(packet)
            self.logger.debug(f"发送: {ball_color}球, 偏移({dx},{dy}), 距离{distance}mm")
            return True
            
        except Exception as e:
            self.logger.error(f"发送小球数据失败: {e}")
            self.disconnect()
            return False
    
    def send_safety_zone_info(self, safety_zone_color):
        # 发送安全区信息 
        if not self.ensure_connected():
            return False
        
        try:
            # 数据验证
            if safety_zone_color not in self.safety_zone_color_to_id:
                self.logger.error(f"无效的安全区颜色: {safety_zone_color}")
                return False
                
            safety_zone_id = self.safety_zone_color_to_id[safety_zone_color]
            
            # 使用与小球数据包相同的格式，颜色ID为4或5
            packet = bytearray([self.START_BYTE])
            packet.extend(b'\x00\x00')  # dx=0
            packet.extend(b'\x00\x00')  # dy=0
            packet.append(safety_zone_id)  # 4=红色安全区, 5=蓝色安全区
            packet.extend(b'\x00\x00')  # distance=0
            
            # 计算校验和
            checksum = sum(packet[1:]) & 0xFF
            packet.append(checksum)
            packet.append(self.END_BYTE)
            
            # 发送数据
            self.ser.write(packet)
            self.logger.debug(f"发送安全区信息: {safety_zone_color}安全区 (ID: {safety_zone_id})")
            return True
            
        except Exception as e:
            self.logger.error(f"发送安全区信息失败: {e}")
            self.disconnect()
            return False

    def send_ball_detection(self, ball_data):
        # 发送小球检测结果
        if not self.ensure_connected() or not self.team_color:
            return False
        
        try:
            # 验证数据格式
            if not isinstance(ball_data, dict):
                self.logger.error("ball_data必须是字典格式")
                return False
            
            # 验证必要字段
            required_fields = ['color', 'x', 'y']
            for field in required_fields:
                if field not in ball_data:
                    self.logger.error(f"缺少字段: {field}")
                    return False
            
            color = ball_data['color']
            
            # 检查是否应该收集这个小球
            if self.priorities.get(color, 0) == 0:
                self.logger.debug(f"忽略{color}球（敌方目标）")
                return False
            
            # 计算坐标和距离
            dx = ball_data['x'] - self.center_x
            dy = self.center_y - ball_data['y']
            distance = self.estimate_distance(ball_data.get('radius', 0))
            
            # 如果小球在安全区内，同时发送安全区信息
            if ball_data.get('in_safety_zone', False) and self.team_color in self.safety_zone_color_to_id:
                self.send_safety_zone_info(self.team_color)
            
            return self.send_ball_data(dx, dy, color, distance)
            
        except Exception as e:
            self.logger.error(f"处理小球检测数据失败: {e}")
            return False

    def estimate_distance(self, pixel_radius):
        # 估算距离
        try:
            if pixel_radius <= 0:
                return 1000
            
            pixel_diameter = pixel_radius * 2
            distance_mm = (self.actual_diameter_mm * self.reference_distance_mm) / pixel_diameter
            return int(max(100, min(distance_mm, 2000)))
            
        except Exception as e:
            self.logger.error(f"距离估算计算错误: {e}")
            return 1000

    def send_multiple_balls(self, balls_list):
        # 发送多个小球，自动选择优先级最高的
        try:
            if not balls_list or not isinstance(balls_list, list) or not self.team_color:
                return False
            
            # 过滤可收集的小球
            collectable_balls = []
            for ball in balls_list:
                if isinstance(ball, dict) and self.priorities.get(ball.get('color', ''), 0) > 0:
                    collectable_balls.append(ball)
            
            if not collectable_balls:
                # 如果没有可收集的小球，但有安全区信息，发送安全区信息
                if self.team_color in self.safety_zone_color_to_id:
                    return self.send_safety_zone_info(self.team_color)
                return False
            
            # 检查是否有小球在安全区内
            has_ball_in_safety = any(ball.get('in_safety_zone', False) for ball in balls_list)
            
            # 如果有小球在安全区内，发送安全区信息
            if has_ball_in_safety and self.team_color in self.safety_zone_color_to_id:
                self.send_safety_zone_info(self.team_color)
            
            # 按优先级排序并选择第一个
            sorted_balls = sorted(collectable_balls, 
                                key=lambda ball: self.priorities.get(ball.get('color', ''), 0), 
                                reverse=True)
            
            target_ball = sorted_balls[0]
            priority = self.priorities[target_ball['color']]
            self.logger.debug(f"选择{target_ball['color']}球 (优先级: {priority})")
            
            return self.send_ball_detection(target_ball)
            
        except Exception as e:
            self.logger.error(f"处理多球数据失败: {e}")
            return False

    def test_communication(self):
        # 测试通信
        if not self.ensure_connected():
            return False
        
        self.logger.info("开始通信测试...")
        
        # 测试数据
        test_balls = [
            {'color': 'red', 'x': 400, 'y': 200, 'radius': 25, 'in_safety_zone': True},
            {'color': 'blue', 'x': 300, 'y': 150, 'radius': 30, 'in_safety_zone': False},
            {'color': 'yellow', 'x': 350, 'y': 250, 'radius': 28, 'in_safety_zone': True},
            {'color': 'black', 'x': 280, 'y': 180, 'radius': 32, 'in_safety_zone': False},
        ]
        
        success_count = 0
        
        # 测试发送小球数据
        for ball in test_balls:
            if self.send_ball_detection(ball):
                success_count += 1
            time.sleep(0.2)
        
        # 测试发送安全区信息
        if self.send_safety_zone_info('red'):
            success_count += 1
        time.sleep(0.2)
        
        if self.send_safety_zone_info('blue'):
            success_count += 1
        
        self.logger.info(f"测试完成: {success_count}/{len(test_balls) + 2} 通过")
        return success_count > 0

    def close(self):
        # 关闭串口
        try:
            if self.ser and self.ser.is_open:
                self.ser.close()
                self.is_connected = False
                self.logger.info("串口已关闭")
        except Exception as e:
            self.logger.error(f"关闭串口时发生错误: {e}")

# 使用示例
if __name__ == "__main__":
    # 创建串口对象
    vision_serial = VisionSerial('/dev/ttyUSB0', 115200)
    
    try:
        # 设置队伍颜色
        vision_serial.set_team_color('red')  # 或者 'blue'
        
        # 测试通信
        vision_serial.test_communication()
        
        # 模拟比赛场景
        detected_balls = [
            {'color': 'red', 'x': 350, 'y': 220, 'radius': 28},
            {'color': 'blue', 'x': 400, 'y': 300, 'radius': 25},
            {'color': 'yellow', 'x': 280, 'y': 180, 'radius': 32},
        ]
        
        vision_serial.send_multiple_balls(detected_balls)
        
    except KeyboardInterrupt:
        vision_serial.logger.info("用户中断")
    finally:
        vision_serial.close()