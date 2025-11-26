# -*- coding: utf-8 -*-

"""
串口调试工具 - 用于救援机器人视觉系统与电控系统的通信调试
功能：
1. 列出系统可用串口
2. 连接/断开串口
3. 发送各种控制命令（停止、抓取、放置等）
4. 发送测试数据（小球数据、安全区信息等）
5. 接收并解析电控反馈数据
6. 实时监控串口通信
7. 队伍颜色设置和优先级管理
8. 多球测试和智能选择

Windows兼容版本
"""

import serial
import serial.tools.list_ports
import time
import threading
import json
import sys
import os

# 添加项目根目录到Python路径（Windows兼容方式）
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

# 尝试导入日志工具，如果失败则创建简单的日志记录器
try:
    from src.utils.logger_utils import get_logger
    logger_available = True
except ImportError:
    # 如果无法导入日志工具，创建一个简单的日志记录器
    logger_available = False
    import logging
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    def get_logger(name):
        return logging.getLogger(name)

class SerialDebugger:
    def __init__(self):
        self.logger = get_logger("serial_debugger")
        self.ser = None
        self.is_connected = False
        self.receive_thread = None
        self.running = False
        self.lock = threading.Lock()
        # Windows系统标识
        self.is_windows = sys.platform.startswith('win')
        
        # 通信协议常量
        self.START_BYTE = 0xAA
        self.END_BYTE = 0xBB
        self.CMD_GRAB = 0x01
        self.CMD_PLACE = 0x02
        self.CMD_ROTATION = 0x03
        
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
        
        # 队伍颜色和优先级
        self.team_color = None
        self.opponent_color = None
        self.priorities = {}
        
        # 命令历史记录
        self.command_history = []
    
    def list_ports(self):
        """列出所有可用的串口（Windows兼容）"""
        try:
            ports = serial.tools.list_ports.comports()
            if not ports:
                print("未找到可用的串口设备")
                return []
            
            print("可用的串口设备:")
            for i, port in enumerate(ports, 1):
                # Windows系统上显示更友好的串口信息
                if self.is_windows:
                    print(f"{i}. {port.device} - {port.description} (VID:{port.vid if port.vid else 'N/A'}, PID:{port.pid if port.pid else 'N/A'})")
                else:
                    print(f"{i}. {port.device} - {port.description}")
            
            return ports
        except Exception as e:
            print(f"列出串口时发生错误: {e}")
            return []
    
    def connect(self, port, baudrate=115200):
        """连接到指定串口（Windows兼容）"""
        try:
            # 确保之前的连接已关闭
            if self.ser and self.ser.is_open:
                self.ser.close()
            
            # Windows系统上可能需要处理串口名称格式
            if self.is_windows and not port.startswith('COM'):
                # 如果在Windows上没有指定COM前缀，自动添加
                if port.isdigit():
                    port = f"COM{port}"
            
            print(f"正在连接串口: {port}，波特率: {baudrate}...")
            self.ser = serial.Serial(
                port=port,
                baudrate=baudrate,
                bytesize=serial.EIGHTBITS,
                parity=serial.PARITY_NONE,
                stopbits=serial.STOPBITS_ONE,
                timeout=0.1,
                write_timeout=0.5
            )
            
            # 检查连接是否成功
            if self.ser.is_open:
                self.is_connected = True
                self.running = True
                print(f"成功连接到串口: {port}")
                
                # 启动接收线程
                self.receive_thread = threading.Thread(target=self.receive_loop, daemon=True)
                self.receive_thread.start()
                print("接收线程已启动")
                return True
            else:
                print(f"连接串口失败: 无法打开 {port}")
                return False
                
        except serial.SerialException as e:
            print(f"连接串口时发生错误: {e}")
            return False
        except Exception as e:
            print(f"连接串口时发生未知错误: {e}")
            return False
    
    def disconnect(self):
        """断开串口连接"""
        try:
            self.running = False
            time.sleep(0.1)  # 给接收线程一些时间来退出
            
            if self.ser and self.ser.is_open:
                self.ser.close()
                print(f"已断开串口连接: {self.ser.port}")
            
            self.ser = None
            self.is_connected = False
            return True
            
        except Exception as e:
            print(f"断开串口连接时发生错误: {e}")
            return False
    
    def receive_loop(self):
        """接收数据循环"""
        buffer = bytearray()
        
        while self.running:
            try:
                if self.ser and self.ser.is_open:
                    # 读取数据
                    data = self.ser.read(1024)
                    if data:
                        buffer.extend(data)
                        # 处理接收到的数据
                        self._parse_received_data(buffer)
                else:
                    time.sleep(0.01)
                    
            except Exception as e:
                print(f"接收数据时发生错误: {e}")
                # 如果发生错误，等待一段时间后重试
                time.sleep(0.1)
    
    def _parse_received_data(self, buffer):
        """解析接收到的数据"""
        try:
            # 简单实现：寻找开始和结束字节
            start_idx = buffer.find(self.START_BYTE)
            end_idx = buffer.find(self.END_BYTE, start_idx + 1)
            
            if start_idx >= 0 and end_idx > start_idx:
                # 提取完整的数据包
                packet = buffer[start_idx:end_idx + 1]
                # 从缓冲区中移除已处理的数据包
                del buffer[0:end_idx + 1]
                
                # 验证数据包长度和校验和
                if len(packet) >= 5:  # 最小数据包长度：起始字节 + 数据 + 校验和 + 结束字节
                    data_part = packet[1:-2]  # 去除起始字节和结束字节，以及校验和
                    received_checksum = packet[-2]  # 校验和是结束字节前的字节
                    
                    # 计算校验和
                    calculated_checksum = sum(data_part) & 0xFF
                    
                    if received_checksum == calculated_checksum:
                        # 校验和正确，处理数据包
                        print(f"接收到有效数据包: {packet.hex()}")
                        # 这里可以添加更详细的数据包解析逻辑
                        
                        # 如果是控制命令的响应
                        if len(data_part) > 0:
                            cmd_id = data_part[0]
                            # 根据命令ID处理不同的响应
                            if cmd_id == self.CMD_GRAB:
                                status = "成功" if len(data_part) > 1 and data_part[1] == 0x01 else "失败"
                                print(f"抓取命令响应: {status}")
                            elif cmd_id == self.CMD_PLACE:
                                status = "成功" if len(data_part) > 1 and data_part[1] == 0x01 else "失败"
                                print(f"放置命令响应: {status}")
                            elif cmd_id == self.CMD_ROTATION:
                                status = "成功" if len(data_part) > 1 and data_part[1] == 0x01 else "失败"
                                print(f"旋转命令响应: {status}")
                    else:
                        print(f"校验和错误: 收到 {received_checksum:02X}, 计算 {calculated_checksum:02X}")
        except Exception as e:
            print(f"解析数据时发生错误: {e}")
    
    def send_data(self, data):
        """发送数据到串口"""
        try:
            if not self.is_connected or not self.ser:
                print("错误: 未连接到串口")
                return False
            
            with self.lock:
                # 发送数据
                bytes_sent = self.ser.write(data)
                # 确保数据被发送
                self.ser.flush()
                
                if bytes_sent == len(data):
                    print(f"成功发送 {bytes_sent} 字节: {data.hex()}")
                    return True
                else:
                    print(f"发送数据失败: 只发送了 {bytes_sent}/{len(data)} 字节")
                    return False
                    
        except serial.SerialException as e:
            print(f"发送数据时发生串口错误: {e}")
            # 尝试重新连接
            self.disconnect()
            return False
        except Exception as e:
            print(f"发送数据时发生错误: {e}")
            return False
    
    def send_stop_command(self):
        """发送停止命令"""
        if not self.is_connected:
            print("错误: 未连接到串口")
            return False
        
        try:
            # 停止命令的格式
            # 0xAA - 起始字节
            # 0x00 - 停止命令ID
            # 0x00 - 校验和
            # 0xBB - 结束字节
            command = bytes([0xAA, 0x00, 0x00, 0xBB])
            
            print("发送停止命令")
            return self.send_data(command)
            
        except Exception as e:
            print(f"发送停止命令时发生错误: {e}")
            return False
    
    def send_grab_command(self, grab=True):
        """发送抓取命令"""
        if not self.is_connected:
            print("错误: 未连接到串口")
            return False
        
        try:
            # 抓取命令的格式
            # 0xAA - 起始字节
            # 0x01 - 抓取命令ID
            # 0x01 - 抓取 / 0x00 - 松开
            # 校验和
            # 0xBB - 结束字节
            action = 0x01 if grab else 0x00
            checksum = (self.CMD_GRAB + action) & 0xFF
            command = bytes([0xAA, self.CMD_GRAB, action, checksum, 0xBB])
            
            action_text = "抓取" if grab else "松开"
            print(f"发送{action_text}命令")
            return self.send_data(command)
            
        except Exception as e:
            print(f"发送抓取命令时发生错误: {e}")
            return False
    
    def send_place_command(self, position=0):
        """发送放置命令"""
        if not self.is_connected:
            print("错误: 未连接到串口")
            return False
        
        try:
            # 确保位置在有效范围内
            position = max(0, min(4, position))
            
            # 放置命令的格式
            # 0xAA - 起始字节
            # 0x02 - 放置命令ID
            # 位置值 (0-4)
            # 校验和
            # 0xBB - 结束字节
            checksum = (self.CMD_PLACE + position) & 0xFF
            command = bytes([0xAA, self.CMD_PLACE, position, checksum, 0xBB])
            
            print(f"发送放置命令，位置: {position}")
            return self.send_data(command)
            
        except Exception as e:
            print(f"发送放置命令时发生错误: {e}")
            return False
    
    def send_rotation_command(self, speed=0):
        """发送旋转命令"""
        if not self.is_connected:
            print("错误: 未连接到串口")
            return False
        
        try:
            # 限制速度范围
            speed_value = max(-100, min(100, speed))
            # 映射到0-255的范围 (0=逆时针, 128=停止, 255=顺时针)
            mapped_value = 128 + int(speed_value * 1.27)
            
            # 旋转命令的格式
            # 0xAA - 起始字节
            # 0x03 - 旋转命令ID
            # 旋转速度 (0-255)
            # 校验和
            # 0xBB - 结束字节
            checksum = (self.CMD_ROTATION + mapped_value) & 0xFF
            command = bytes([0xAA, self.CMD_ROTATION, mapped_value, checksum, 0xBB])
            
            direction = "顺时针" if speed_value > 0 else "逆时针" if speed_value < 0 else "停止"
            print(f"发送旋转命令: {direction}，速度: {abs(speed_value)}%")
            return self.send_data(command)
            
        except Exception as e:
            print(f"发送旋转命令时发生错误: {e}")
            return False
    
    def set_team_color(self, team_color):
        """设置队伍颜色"""
        if team_color not in ['red', 'blue']:
            print(f"错误: 无效的队伍颜色 '{team_color}'，请输入 'red' 或 'blue'")
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
        
        print(f"队伍颜色设置完成: 己方{self.team_color.upper()}队")
        print(f"优先级设置: 黑色(30) > 黄色(20) > {team_color}(10) > {self.opponent_color}(0)")
        return True
    
    def estimate_distance(self, pixel_radius):
        """估算距离"""
        try:
            if pixel_radius <= 0:
                return 1000
            
            pixel_diameter = pixel_radius * 2
            distance_mm = (self.actual_diameter_mm * self.reference_distance_mm) / pixel_diameter
            return int(max(100, min(distance_mm, 2000)))
            
        except Exception as e:
            print(f"距离估算错误: {e}")
            return 1000
    
    def send_safety_zone_info(self, safety_zone_color):
        """发送安全区信息"""
        if not self.is_connected:
            print("错误: 未连接到串口")
            return False
        
        try:
            # 数据验证
            if safety_zone_color not in self.safety_zone_color_to_id:
                print(f"错误: 无效的安全区颜色: {safety_zone_color}")
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
            print(f"发送安全区信息: {safety_zone_color}安全区 (ID: {safety_zone_id})")
            return self.send_data(packet)
            
        except Exception as e:
            print(f"发送安全区信息失败: {e}")
            return False
    
    def send_ball_data(self, dx, dy, ball_color, distance):
        """发送小球数据"""
        if not self.is_connected:
            print("错误: 未连接到串口")
            return False

        try:
            # 数据验证
            if ball_color not in self.color_to_id:
                print(f"错误: 无效的颜色: {ball_color}")
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
            print(f"发送: {ball_color}球, 偏移({dx},{dy}), 距离{distance}mm")
            return self.send_data(packet)
            
        except Exception as e:
            print(f"发送小球数据失败: {e}")
            return False
    
    def send_test_ball_data(self, color="red", x=320, y=240, radius=20, in_safety_zone=False):
        """发送测试的球数据"""
        # 计算dx, dy (相对中心的偏移)
        dx = x - self.center_x
        dy = y - self.center_y
        
        # 估算距离
        distance = self.estimate_distance(radius)
        
        # 如果球在安全区内且设置了队伍颜色，发送安全区信息
        if in_safety_zone and self.team_color:
            self.send_safety_zone_info(self.team_color)
        
        # 发送球数据
        result = self.send_ball_data(dx, dy, color, distance)
        
        if result:
            print(f"测试球数据发送成功: {color}球, 位置({x},{y}), 半径{radius}")
            if in_safety_zone:
                print(f"该球位于{self.team_color}安全区内")
        return result
    
    def send_multiple_balls(self, balls_list):
        """发送多个小球，自动选择优先级最高的"""
        try:
            if not balls_list or not isinstance(balls_list, list):
                print("错误: 无效的小球列表")
                return False
            
            if not self.team_color:
                print("错误: 请先设置队伍颜色")
                return False
            
            # 过滤可收集的小球
            collectable_balls = []
            for ball in balls_list:
                if isinstance(ball, dict) and self.priorities.get(ball.get('color', ''), 0) > 0:
                    collectable_balls.append(ball)
            
            if not collectable_balls:
                print("没有可收集的小球")
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
            print(f"选择{target_ball['color']}球 (优先级: {priority})")
            
            # 计算dx, dy
            dx = target_ball['x'] - self.center_x
            dy = target_ball['y'] - self.center_y
            distance = self.estimate_distance(target_ball.get('radius', 20))
            
            return self.send_ball_data(dx, dy, target_ball['color'], distance)
            
        except Exception as e:
            print(f"处理多球数据失败: {e}")
            return False
    
    def run_test_sequence(self):
        """运行测试序列"""
        if not self.is_connected:
            print("错误: 未连接到串口")
            return
        
        print("\n开始运行测试序列...")
        
        # 如果未设置队伍颜色，默认设置为红色
        if not self.team_color:
            print("未设置队伍颜色，默认设置为红色")
            self.set_team_color('red')
        
        # 测试单个小球
        print("\n1. 测试单个小球数据发送:")
        for color in ['red', 'blue', 'yellow', 'black']:
            self.send_test_ball_data(color=color, x=320, y=240, radius=20)
            time.sleep(0.5)
        
        # 测试多球优先级
        print("\n2. 测试多球优先级选择:")
        test_balls = [
            {'color': 'red', 'x': 400, 'y': 200, 'radius': 25, 'in_safety_zone': True},
            {'color': 'blue', 'x': 300, 'y': 150, 'radius': 30, 'in_safety_zone': False},
            {'color': 'yellow', 'x': 350, 'y': 250, 'radius': 28, 'in_safety_zone': True},
            {'color': 'black', 'x': 280, 'y': 180, 'radius': 32, 'in_safety_zone': False},
        ]
        self.send_multiple_balls(test_balls)
        
        # 测试安全区
        print("\n3. 测试安全区信息:")
        self.send_safety_zone_info(self.team_color)
        
        print("\n测试序列完成!")
    
    def print_menu(self):
        """打印菜单"""
        print("\n" + "="*50)
        print("          串口调试工具 v1.0")
        print("="*50)
        print(f"当前状态: {'已连接到 ' + self.ser.port if self.is_connected else '未连接'}")
        print(f"队伍颜色: {self.team_color if self.team_color else '未设置'}")
        print("\n命令列表:")
        print("1. 列出可用串口")
        print("2. 连接串口")
        print("3. 断开连接")
        print("4. 发送停止命令")
        print("5. 发送抓取命令")
        print("6. 发送放置命令")
        print("7. 设置队伍颜色")
        print("8. 发送测试球数据")
        print("9. 发送安全区信息")
        print("10. 运行测试序列")
        print("11. 发送自定义数据")
        print("0. 退出")
        print("="*50)
    
    def handle_command(self, cmd):
        """处理用户命令"""
        if cmd == "1":
            self.list_ports()
            
        elif cmd == "2":
            ports = self.list_ports()
            if ports:
                try:
                    print("\n请选择连接方式:")
                    print("1. 从上面列表中选择串口")
                    print("2. 手动输入串口名称")
                    
                    conn_type = input("请选择 (1-2): ")
                    
                    if conn_type == "1":
                        choice = int(input("请选择串口 (输入序号): ")) - 1
                        if 0 <= choice < len(ports):
                            port = ports[choice].device
                        else:
                            print("无效的选择")
                            return True
                    elif conn_type == "2":
                        # 手动输入模式，在Windows上提示输入COM端口
                        if self.is_windows:
                            port = input("请输入串口名称 (如 COM3): ")
                            # 自动补全COM前缀
                            if port.isdigit():
                                port = f"COM{port}"
                        else:
                            port = input("请输入串口名称: ")
                    else:
                        print("无效的选择")
                        return True
                    
                    baudrate = input("请输入波特率 (默认115200): ")
                    baudrate = int(baudrate) if baudrate else 115200
                    self.connect(port, baudrate)
                except ValueError:
                    print("请输入有效的数字")
        
        elif cmd == "3":
            self.disconnect()
        
        elif cmd == "4":
            self.send_stop_command()
        
        elif cmd == "5":
            grab = input("抓取还是释放? (g/r, 默认g): ").lower() != "r"
            self.send_grab_command(grab)
        
        elif cmd == "6":
            try:
                position = int(input("请输入放置位置 (0-4, 默认0): ") or "0")
                if 0 <= position <= 4:
                    self.send_place_command(position)
                else:
                    print("位置必须在0-4之间")
            except ValueError:
                print("请输入有效的数字")
        
        elif cmd == "7":
            color = input("请输入队伍颜色 (red/blue): ").strip().lower()
            self.set_team_color(color)
        
        elif cmd == "8":
            color = input("请输入球颜色 (red/blue/yellow/black, 默认red): ").lower() or "red"
            if color not in ["red", "blue", "yellow", "black"]:
                color = "red"
            
            try:
                x = int(input("请输入X坐标 (默认320): ") or "320")
                y = int(input("请输入Y坐标 (默认240): ") or "240")
                radius = int(input("请输入半径 (默认20): ") or "20")
                
                in_safety = input("是否在安全区内？(y/n，默认n): ").strip().lower()
                in_safety_zone = in_safety == 'y'
                
                self.send_test_ball_data(color, x, y, radius, in_safety_zone)
            except ValueError:
                print("请输入有效的数字")
        
        elif cmd == "9":
            if not self.team_color:
                color = input("请输入安全区颜色 (red/blue): ").strip().lower()
                if color in ['red', 'blue']:
                    self.send_safety_zone_info(color)
                else:
                    print("错误: 无效的安全区颜色")
            else:
                # 使用已设置的队伍颜色
                self.send_safety_zone_info(self.team_color)
        
        elif cmd == "10":
            self.run_test_sequence()
        
        elif cmd == "11":
            try:
                # 输入格式: AA 01 02 BB (空格分隔的十六进制字节)
                hex_input = input("请输入要发送的十六进制数据 (空格分隔): ")
                # 分割并转换为字节
                byte_values = [int(x, 16) for x in hex_input.split()]
                data = bytes(byte_values)
                
                print(f"发送自定义数据: {data.hex()}")
                self.send_data(data)
            except ValueError:
                print("错误: 无效的十六进制数据格式")
        
        elif cmd == "0" or cmd.lower() == "q":
            return False
        
        else:
            print("未知命令，请重新输入")
        
        return True
    
    def run(self):
        """运行调试工具"""
        print("欢迎使用救援机器人串口调试工具!")
        
        try:
            # 初始列出可用串口
            self.list_ports()
            
            while True:
                self.print_menu()
                cmd = input("请输入命令 (0-11): ")
                if not self.handle_command(cmd):
                    break
                    
        except KeyboardInterrupt:
            print("\n程序被用户中断")
        except Exception as e:
            print(f"运行时发生错误: {e}")
        finally:
            # 确保断开连接
            self.disconnect()
            print("程序已退出")

if __name__ == "__main__":
    debugger = SerialDebugger()
    debugger.run()