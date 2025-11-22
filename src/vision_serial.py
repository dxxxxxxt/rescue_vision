import serial
import time
import struct
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
                'yellow': 30,  # 危险目标 - 最高优先级 (15分)
                'black': 20,   # 核心目标 (10分)
                'red': 10,     # 己方普通目标 (5分)
                'blue': 0,     # 敌方目标 - 不收集
            }
        else:
            # 己方蓝色队：收集蓝、黄、黑；忽略红
            self.priorities = {
                'yellow': 30,  # 危险目标 - 最高优先级 (15分)
                'black': 20,   # 核心目标 (10分)
                'blue': 10,    # 己方普通目标 (5分)
                'red': 0,      # 敌方目标 - 不收集
            }
        
        self.logger.info(f"队伍颜色设置: 己方{self.team_color.upper()}队")
        self.logger.info("当前优先级设置:")
        for color, priority in sorted(self.priorities.items(), key=lambda x: x[1], reverse=True):
            action = "收集" if priority > 0 else "忽略"
            score = {30: "15分", 20: "10分", 10: "5分", 0: "0分"}[priority]
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
                timeout=0.1
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
            packet.append(0xAA)  # 起始字节
            
            # dx, dy, ball_id, distance
            dx_bytes = dx.to_bytes(2, byteorder='little', signed=True)
            packet.extend(dx_bytes)
            
            dy_bytes = dy.to_bytes(2, byteorder='little', signed=True)
            packet.extend(dy_bytes)
            
            packet.append(ball_id)
            packet.append(0x00)  # 预留字节
            
            distance_bytes = distance.to_bytes(2, byteorder='little', signed=False)
            packet.extend(distance_bytes)
            
            packet.append(0xBB)  # 结束字节
            
            # 发送数据
            self.ser.write(packet)
            self.logger.info(f"发送: {ball_color}球, 偏移({dx},{dy}), 距离{distance}mm")
            return True
            
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

    def send_stop(self):
        """发送停止指令"""
        self.logger.info("发送停止指令")
        return self.send_ball_data(0, 0, 'red', 1000)

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

    def receive_data(self, timeout=0.1):
        """从串口接收数据
        
        Args:
            timeout: 接收超时时间，单位秒
            
        Returns:
            接收到的数据字典，包含命令类型和参数，或None表示未接收到有效数据
        """
        if not self.ser or not self.ser.is_open:
            self.logger.error("串口未打开，无法接收数据")
            return None
            
        try:
            # 设置超时
            self.ser.timeout = timeout
            
            # 检查是否有数据可读
            if self.ser.in_waiting > 0:
                # 读取所有可用数据
                data = self.ser.read_all()
                self.logger.debug(f"接收到原始数据: {data.hex()}")
                
                # 简单的数据解析逻辑
                # 假设数据格式: [0xAA, 命令类型, 参数1, 参数2, 校验和, 0xBB]
                if len(data) >= 6 and data[0] == 0xAA and data[-1] == 0xBB:
                    cmd_type = data[1]
                    params = data[2:-2]  # 排除起始、命令类型、校验和和结束字节
                    checksum = data[-2]
                    
                    # 简单校验
                    calculated_checksum = sum(data[1:-2]) & 0xFF
                    if calculated_checksum == checksum:
                        # 返回解析后的数据
                        return {
                            "cmd_type": cmd_type,
                            "params": params
                        }
                    else:
                        self.logger.warning(f"校验和错误，接收到: {checksum}, 计算: {calculated_checksum}")
                else:
                    self.logger.warning("接收到非标准格式数据")
                    
            return None
        except Exception as e:
            self.logger.error(f"接收数据异常: {e}")
            return None
    
    def send_grab_command(self, grab=True):
        """发送抓取命令给电控系统
        
        Args:
            grab: True表示抓取，False表示释放
        """
        if not self.ensure_connected():
            self.logger.error("未连接到串口")
            return False
            
        try:
            # 构建抓取命令数据包 [0xAA, 0x01, 抓取标志, 校验和, 0xBB]
            # 0x01: 抓取命令类型
            # 抓取标志: 1=抓取, 0=释放
            flag = 1 if grab else 0
            checksum = (0x01 + flag) & 0xFF
            
            command = bytes([0xAA, 0x01, flag, checksum, 0xBB])
            self.ser.write(command)
            self.logger.info(f"发送抓取命令: {'抓取' if grab else '释放'}")
            return True
        except Exception as e:
            self.logger.error(f"发送抓取命令异常: {e}")
            return False
    
    def send_place_command(self, position=None):
        """发送放置命令给电控系统
        
        Args:
            position: 放置位置信息，可为None表示使用默认位置
        """
        if not self.ensure_connected():
            self.report_failure("未连接到串口")
            return False
            
        try:
            # 构建放置命令数据包 [0xAA, 0x02, 位置信息, 校验和, 0xBB]
            # 0x02: 放置命令类型
            # 位置信息: 0=默认位置, 1-4=特定区域位置
            pos_value = 0 if position is None else position
            checksum = (0x02 + pos_value) & 0xFF
            
            command = bytes([0xAA, 0x02, pos_value, checksum, 0xBB])
            self.ser.write(command)
            self.logger.info(f"发送放置命令，位置: {pos_value}")
            return True
        except Exception as e:
            self.logger.error(f"发送放置命令异常: {e}")
            return False
            
    def send_rotation(self, rotation_speed):
        """
        发送旋转指令给电控系统
        
        Args:
            rotation_speed: 旋转速度百分比值，范围为-100到100
                           正数表示顺时针旋转，负数表示逆时针旋转
                           绝对值表示旋转速度的百分比
            
        Returns:
            bool: 命令发送成功返回True，否则返回False
        """
        if not self.ensure_connected():
            self.report_failure("未连接到串口")
            return False
            
        try:
            # 验证并处理旋转速度值
            speed_value = int(rotation_speed)
            # 确保速度值在有效范围内
            speed_value = max(-100, min(100, speed_value))
            
            # 将-100到100的范围映射到0-200
            # 0表示-100(逆时针最大速度)，100表示停止，200表示100(顺时针最大速度)
            mapped_value = speed_value + 100
            
            # 计算校验和
            checksum = (0x03 + mapped_value) & 0xFF
            
            # 构建命令包: 起始符(AA) + 命令类型(03) + 速度值 + 校验和 + 结束符(BB)
            command = bytes([0xAA, 0x03, mapped_value, checksum, 0xBB])
            self.ser.write(command)
            
            direction = "顺时针" if speed_value > 0 else "逆时针" if speed_value < 0 else "停止"
            self.logger.info(f"发送旋转命令: {direction}，速度: {abs(speed_value)}%")
            return True
        except Exception as e:
            self.logger.error(f"发送旋转命令时出错: {e}")
            return False
            
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
