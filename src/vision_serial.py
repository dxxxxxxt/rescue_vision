import serial
import time
import struct
from serial import TimeoutException
from utils.logger_utils import get_logger

class VisionSerial:
    """
    视觉串口通信类 - 支持队伍颜色配置
    专为智能救援比赛设计
    """
    
    def __init__(self, port='/dev/ttyUSB0', baudrate=115200, team_color=None):
        """
        初始化串口通信
        :param port: 串口设备路径
        :param baudrate: 波特率
        :param team_color: 己方队伍颜色 ('red' 或 'blue')，如果为None需要后续设置
        """
        self.logger = get_logger(__name__)
        self.port = port
        self.baudrate = baudrate  # 使用传入的波特率参数
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
        
        # 图像参数
        self.image_width = 640
        self.image_height = 480
        self.center_x = self.image_width // 2
        self.center_y = self.image_height // 2
        
        # 距离估算参数
        self.actual_diameter_mm = 40
        self.reference_pixel_radius = 20
        self.reference_distance_mm = 500
        
        # 初始化队伍颜色
        self.team_color = None
        self.opponent_color = None
        self.priorities = {}
        
        if team_color:
            self.set_team_color(team_color)
        else:
            self.logger.warning("未设置队伍颜色，请在使用前调用 set_team_color()")
        
        self.connect()

    def set_team_color(self, team_color):
        """
        设置己方队伍颜色（比赛抽签后必须调用）
        :param team_color: 'red' 或 'blue'
        :return: 是否设置成功
        """
        if team_color not in ['red', 'blue']:
            self.logger.error("无效的队伍颜色，请输入 'red' 或 'blue'")
            return False
            
        self.team_color = team_color
        self.opponent_color = 'blue' if team_color == 'red' else 'red'
        
        # 根据己方颜色设置优先级
        if self.team_color == 'red':
            # 己方红色队：收集红、黄、黑；忽略蓝
            self.priorities = {
                'black': 30,   # 核心目标 - 最高优先级
                'yellow': 20,  # 危险目标
                'red': 10,     # 己方普通目标
                'blue': 0,     # 敌方目标 - 不收集
            }
        else:
            # 己方蓝色队：收集蓝、黄、黑；忽略红
            self.priorities = {
                'black': 30,   # 核心目标 - 最高优先级
                'yellow': 20,  # 危险目标
                'blue': 10,    # 己方普通目标
                'red': 0,      # 敌方目标 - 不收集
            }
        
        self.logger.info(f"队伍颜色设置: 己方{self.team_color.upper()}队")
        self.logger.info("当前优先级设置:")
        for color, priority in sorted(self.priorities.items(), key=lambda x: x[1], reverse=True):
            action = "收集" if priority > 0 else "忽略"
            score = {30: "核心球", 20: "危险球", 10: "普通球", 0: "0分"}[priority]
            self.logger.info(f"   {color.upper()}球: 优先级{priority} ({action}) - {score}")
        
        return True

    def connect(self):
        """
        连接串口
        """
        try:
            # 参数验证
            if not isinstance(self.port, str) or not self.port:
                self.logger.error("无效的串口端口号")
                self.is_connected = False
                return False
            
            if not isinstance(self.baudrate, int) or self.baudrate <= 0:
                self.logger.error("无效的波特率")
                self.is_connected = False
                return False
            
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
                write_timeout=0.5  # 添加写入超时
            )
            
            if self.ser.is_open:
                self.is_connected = True
                self.logger.info(f"串口连接成功: {self.port} 波特率: {self.baudrate}")
                return True
            else:
                self.logger.error(f"串口打开失败: {self.port}")
                self.is_connected = False
                return False
            
        except serial.SerialException as e:
            self.logger.error(f"串口通信异常: {e}")
            self.is_connected = False
            return False
        except Exception as e:
            self.logger.error(f"连接串口时发生未知错误: {e}")
            self.is_connected = False
            return False
            
    def disconnect(self):
        """断开并关闭串口连接"""
        try:
            if self.ser and self.ser.is_open:
                self.ser.close()
                self.logger.info(f"串口已关闭: {self.port}")
            self.is_connected = False
            return True
        except Exception as e:
            self.logger.error(f"关闭串口时发生错误: {e}")
            return False
            
    def check_connection(self):
        """检查串口连接是否正常"""
        try:
            if self.ser and self.ser.is_open:
                # 尝试发送一个简单的命令或检查状态
                return True
            return False
        except Exception:
            return False
            
    def ensure_connected(self):
        """确保串口连接"""
        # 检查当前连接状态
        if not self.is_connected or not self.ser or not self.ser.is_open:
            return self.connect()
        return True
        
    def receive_feedback(self):
        """
        接收电控系统的反馈数据
        
        返回格式:
        {"type": 反馈类型代码,
         "state": 状态数据,
         "raw_data": 原始字节数据}
         
        如果未接收到有效数据或发生错误，返回None
        """
        if not self.ensure_connected():
            self.logger.error("未连接到串口，无法接收反馈")
            return None
            
        try:
            # 等待接收数据
            if self.ser.in_waiting > 0:
                # 读取至少6字节（最小数据包大小）
                available_bytes = self.ser.in_waiting
                data = self.ser.read(min(available_bytes, 128))  # 限制最大读取量
                
                # 寻找起始字节
                start_index = -1
                for i in range(len(data)):
                    if data[i] == self.START_BYTE:
                        start_index = i
                        break
                
                if start_index == -1:
                    self.logger.debug("未找到起始字节")
                    return None
                
                # 检查剩余数据是否足够
                remaining_data = data[start_index:]
                if len(remaining_data) < 6:  # 最小数据包大小: 起始字节 + 反馈类型 + 状态数据(2字节) + 校验和 + 结束字节
                    self.logger.debug("数据不完整，等待更多数据")
                    return None
                
                # 提取数据包
                packet = remaining_data[:6]  # 提取最小数据包
                
                # 验证结束字节
                if packet[5] != self.END_BYTE:
                    self.logger.debug("结束字节验证失败")
                    return None
                
                # 验证校验和
                checksum = sum(packet[1:4]) & 0xFF  # 反馈类型 + 状态数据(2字节)
                if checksum != packet[4]:
                    self.logger.debug(f"校验和验证失败: 计算={checksum:02X}, 接收={packet[4]:02X}")
                    return None
                
                # 解析数据
                feedback_type = packet[1]
                state_data = int.from_bytes(packet[2:4], byteorder='little', signed=True)
                
                self.logger.info(f"收到电控反馈: 类型={feedback_type}, 状态={state_data}")
                
                return {
                    "type": feedback_type,
                    "state": state_data,
                    "raw_data": packet
                }
            
        except Exception as e:
            self.logger.error(f"接收电控反馈时发生错误: {e}")
            # 断开连接，下次发送时会自动重连
            self.disconnect()
        
        return None

    def send_ball_data(self, dx, dy, ball_color, distance):
        """
        发送小球数据给电控系统
        """
        if not self.ensure_connected():
            self.logger.error("未连接到串口")
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
            packet = bytearray()
            packet.append(self.START_BYTE)  # 起始字节
            
            # dx, dy, ball_id, distance
            dx_bytes = dx.to_bytes(2, byteorder='little', signed=True)
            packet.extend(dx_bytes)
            
            dy_bytes = dy.to_bytes(2, byteorder='little', signed=True)
            packet.extend(dy_bytes)
            
            packet.append(ball_id)
            
            distance_bytes = distance.to_bytes(2, byteorder='little', signed=False)
            packet.extend(distance_bytes)
            
            # 计算校验和
            checksum = sum(packet[1:]) & 0xFF
            packet.append(checksum)
            
            packet.append(self.END_BYTE)  # 结束字节
            
            # 发送数据
            self.ser.write(packet)
            self.logger.info(f"发送: {ball_color}球, 偏移({dx},{dy}), 距离{distance}mm")
            return True
            
        except TimeoutException:
            self.logger.error("串口发送超时")
            # 断开连接，下次发送时会自动重连
            self.disconnect()
            return False
        except Exception as e:
            self.logger.error(f"发送小球数据失败: {e}")
            # 断开连接，下次发送时会自动重连
            self.disconnect()
            return False

    def send_ball_detection(self, ball_data):
        """
        发送小球检测结果
        :param ball_data: {'color': 'red', 'x': 400, 'y': 300, 'radius': 25}
        """
        if not self.ensure_connected():
            return False
        
        if not self.team_color:
            self.logger.error("请先设置队伍颜色！调用 set_team_color('red') 或 set_team_color('blue')")
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
                self.logger.info(f"忽略{color}球（敌方目标）")
                return False
            
            # 计算坐标和距离
            dx = ball_data['x'] - self.center_x
            dy = self.center_y - ball_data['y']
            distance = self.estimate_distance(ball_data.get('radius', 0))
            
            return self.send_ball_data(dx, dy, color, distance)
            
        except KeyError as e:
            self.logger.error(f"数据字典缺少键: {e}")
            return False
        except TypeError as e:
            self.logger.error(f"数据类型错误: {e}")
            return False
        except Exception as e:
            self.logger.error(f"处理小球检测数据失败: {e}")
            return False

    def estimate_distance(self, pixel_radius):
        """估算距离"""
        try:
            if pixel_radius <= 0:
                self.logger.debug("无效的像素半径，返回默认距离")
                return 1000
            pixel_diameter = pixel_radius * 2
            distance_mm = (self.actual_diameter_mm * self.reference_distance_mm) / pixel_diameter
            result = int(max(100, min(distance_mm, 2000)))
            self.logger.debug(f"估算距离: 像素半径={pixel_radius}, 估算距离={result}mm")
            return result
        except (ValueError, TypeError) as e:
            self.logger.error(f"距离估算计算错误: {e}")
            return 1000

    def send_multiple_balls(self, balls_list):
        """
        发送多个小球，自动选择优先级最高的
        """
        try:
            if not balls_list:
                self.logger.info("没有检测到小球")
                return False
            
            if not isinstance(balls_list, list):
                self.logger.error("balls_list必须是列表格式")
                return False
            
            if not self.team_color:
                self.logger.error("请先设置队伍颜色！")
                return False
            
            # 过滤可收集的小球
            collectable_balls = []
            for idx, ball in enumerate(balls_list):
                if not isinstance(ball, dict):
                    self.logger.warning(f"小球数据格式错误 (索引{idx})")
                    continue
                    
                color = ball.get('color', '')
                if self.priorities.get(color, 0) > 0:
                    collectable_balls.append(ball)
            
            if not collectable_balls:
                self.logger.info("没有可收集的小球（都是敌方目标）")
                return False
            
            # 按优先级排序
            sorted_balls = sorted(collectable_balls, 
                                key=lambda ball: self.priorities.get(ball.get('color', ''), 0), 
                                reverse=True)
            
            target_ball = sorted_balls[0]
            priority = self.priorities[target_ball['color']]
            self.logger.info(f"选择{target_ball['color']}球 (优先级: {priority})")
            
            return self.send_ball_detection(target_ball)
            
        except Exception as e:
            self.logger.error(f"处理多球数据失败: {e}")
            return False

    # 停止功能已移除，电控系统不再需要命令数据

    def test_communication(self):
        """测试通信"""
        if not self.ensure_connected():
            return False
        
        self.logger.info("开始通信测试...")
        
        # 测试数据（包含各种颜色）
        test_balls = [
            {'color': 'red', 'x': 400, 'y': 200, 'radius': 25},
            {'color': 'blue', 'x': 300, 'y': 150, 'radius': 30},
            {'color': 'yellow', 'x': 350, 'y': 250, 'radius': 28},
            {'color': 'black', 'x': 280, 'y': 180, 'radius': 32},
        ]
        
        success_count = 0
        for ball in test_balls:
            success = self.send_ball_detection(ball)
            if success:
                success_count += 1
            time.sleep(0.2)
        
        self.logger.info(f"测试完成: {success_count}/{len(test_balls)} 通过")
        return success_count > 0

    def report_failure(self, message):
        """报告失败信息
        
        Args:
            message: 失败信息描述
        """
        self.logger.error(message)
            
    def close(self):
        """关闭串口"""
        try:
            if self.ser and self.ser.is_open:
                self.ser.close()
                self.is_connected = False
                self.logger.info("串口已关闭")
            else:
                self.logger.debug("串口未打开，无需关闭")
        except Exception as e:
            self.logger.error(f"关闭串口时发生错误: {e}")


# 使用示例
if __name__ == "__main__":
    # 创建串口对象（不指定颜色）
    vision_serial = VisionSerial('/dev/ttyUSB0', 115200)
    
    try:
        # 必须先设置队伍颜色！
        vision_serial.logger.info("=== 设置队伍颜色 ===")
        vision_serial.set_team_color('red')  # 或者 'blue'
        
        # 测试通信
        vision_serial.logger.info("\n=== 通信测试 ===")
        vision_serial.test_communication()
        
        # 模拟比赛场景
        vision_serial.logger.info("\n=== 模拟比赛 ===")
        detected_balls = [
            {'color': 'red', 'x': 350, 'y': 220, 'radius': 28},    # 己方目标
            {'color': 'blue', 'x': 400, 'y': 300, 'radius': 25},   # 敌方目标（被忽略）
            {'color': 'yellow', 'x': 280, 'y': 180, 'radius': 32}, # 危险目标（最高优先级）
        ]
        
        vision_serial.send_multiple_balls(detected_balls)
        
    except KeyboardInterrupt:
        vision_serial.logger.info("\n用户中断")
    finally:
        vision_serial.close()
