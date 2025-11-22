# -*- coding: utf-8 -*-

"""
串口调试工具 - 用于救援机器人视觉系统与电控系统的通信调试
功能：
1. 列出系统可用串口
2. 连接/断开串口
3. 发送各种控制命令（停止、抓取、放置等）
4. 发送测试数据
5. 接收并解析电控反馈数据
6. 实时监控串口通信

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
                # Windows特有的设置
                xonxoff=False,
                rtscts=False,
                dsrdtr=False
            )
            
            if self.ser.is_open:
                self.is_connected = True
                print(f"串口连接成功: {port}")
                
                # 启动接收线程
                self.running = True
                self.receive_thread = threading.Thread(target=self.receive_loop)
                self.receive_thread.daemon = True
                self.receive_thread.start()
                
                return True
            else:
                print(f"串口打开失败: {port}")
                return False
        
        except serial.SerialException as e:
            print(f"串口连接错误: {e}")
            return False
        except Exception as e:
            print(f"连接串口时发生未知错误: {e}")
            return False
    
    def disconnect(self):
        """断开串口连接"""
        try:
            self.running = False
            if self.receive_thread:
                self.receive_thread.join(timeout=1.0)
            
            if self.ser and self.ser.is_open:
                self.ser.close()
                print(f"串口已关闭: {self.ser.port}")
            
            self.is_connected = False
            return True
        except Exception as e:
            print(f"关闭串口时发生错误: {e}")
            return False
    
    def receive_loop(self):
        """接收数据的循环线程"""
        print("接收线程已启动，等待数据...")
        
        while self.running:
            try:
                if self.ser and self.ser.is_open and self.ser.in_waiting > 0:
                    with self.lock:
                        data = self.ser.read_all()
                        
                    if data:
                        print("\n[接收]")
                        print(f"原始数据 (十六进制): {data.hex()}")
                        self._parse_received_data(data)
                
                time.sleep(0.01)
            except Exception as e:
                print(f"接收数据异常: {e}")
                time.sleep(0.1)
    
    def _parse_received_data(self, data):
        """解析接收到的数据"""
        try:
            # 尝试解析为标准格式 [0xAA, 命令类型, 参数, 校验和, 0xBB]
            if len(data) >= 5 and data[0] == self.START_BYTE and data[-1] == self.END_BYTE:
                cmd_type = data[1]
                checksum = data[-2]
                params = data[2:-2]
                
                # 校验和验证
                calculated_checksum = sum(data[1:-2]) & 0xFF
                
                print(f"命令类型: 0x{cmd_type:02X}")
                print(f"参数: {params.hex() if params else '无'}")
                print(f"校验和: 0x{checksum:02X}", end=" ")
                
                if calculated_checksum == checksum:
                    print("(验证通过)")
                else:
                    print(f"(验证失败，计算值: 0x{calculated_checksum:02X})")
                
                # 根据命令类型解析
                if cmd_type == self.CMD_GRAB:
                    print("命令说明: 抓取/释放反馈")
                elif cmd_type == self.CMD_PLACE:
                    print("命令说明: 放置反馈")
                else:
                    print(f"命令说明: 未知命令 0x{cmd_type:02X}")
            else:
                print("数据格式不匹配标准协议")
        
        except Exception as e:
            print(f"解析数据失败: {e}")
    
    def send_data(self, data):
        """发送原始数据"""
        try:
            if not self.is_connected or not self.ser or not self.ser.is_open:
                print("错误: 未连接到串口")
                return False
            
            with self.lock:
                bytes_sent = self.ser.write(data)
            
            print(f"\n[发送]")
            print(f"原始数据 (十六进制): {data.hex()}")
            print(f"发送字节数: {bytes_sent}")
            
            # 记录命令历史
            timestamp = time.strftime("%H:%M:%S")
            self.command_history.append((timestamp, "send_raw", data.hex()))
            
            return True
        
        except Exception as e:
            print(f"发送数据失败: {e}")
            return False
    
    def send_stop_command(self):
        """发送停止命令"""
        # 使用与VisionSerial类相同的停止命令实现
        dx = 0
        dy = 0
        ball_color = "red"
        distance = 1000
        
        # 构建数据包
        packet = bytearray()
        packet.append(0xAA)  # 起始字节
        
        # 添加dx, dy
        dx_bytes = dx.to_bytes(2, byteorder='little', signed=True)
        dy_bytes = dy.to_bytes(2, byteorder='little', signed=True)
        packet.extend(dx_bytes)
        packet.extend(dy_bytes)
        
        # 添加球颜色 (0=red)
        color_id = 0 if ball_color == "red" else 1
        packet.append(color_id)
        
        # 添加距离
        distance_bytes = distance.to_bytes(2, byteorder='little', signed=False)
        packet.extend(distance_bytes)
        
        # 计算校验和
        checksum = sum(packet[1:]) & 0xFF
        packet.append(checksum)
        
        # 添加结束字节
        packet.append(0xBB)
        
        print("发送停止命令...")
        return self.send_data(packet)
    
    def send_grab_command(self, grab=True):
        """发送抓取命令"""
        flag = 1 if grab else 0
        checksum = (0x01 + flag) & 0xFF
        command = bytes([0xAA, 0x01, flag, checksum, 0xBB])
        
        print(f"发送抓取命令: {'抓取' if grab else '释放'}")
        return self.send_data(command)
    
    def send_place_command(self, position=0):
        """发送放置命令"""
        checksum = (0x02 + position) & 0xFF
        command = bytes([0xAA, 0x02, position, checksum, 0xBB])
        
        print(f"发送放置命令，位置: {position}")
        return self.send_data(command)
    
    def send_test_ball_data(self, color="red", x=320, y=240, radius=20):
        """发送测试的球数据"""
        # 计算dx, dy (相对中心的偏移)
        center_x, center_y = 320, 240
        dx = x - center_x
        dy = y - center_y
        
        # 估算距离
        actual_diameter_mm = 40
        reference_pixel_radius = 20
        reference_distance_mm = 500
        distance = int(reference_distance_mm * reference_pixel_radius / radius)
        
        # 颜色ID映射
        color_to_id = {"red": 0, "blue": 1, "yellow": 2, "black": 3}
        color_id = color_to_id.get(color, 0)
        
        # 构建数据包
        packet = bytearray()
        packet.append(0xAA)  # 起始字节
        
        # 添加dx, dy
        dx_bytes = max(-32768, min(dx, 32767)).to_bytes(2, byteorder='little', signed=True)
        dy_bytes = max(-32768, min(dy, 32767)).to_bytes(2, byteorder='little', signed=True)
        packet.extend(dx_bytes)
        packet.extend(dy_bytes)
        
        # 添加球颜色
        packet.append(color_id)
        
        # 添加距离
        distance_bytes = max(0, min(distance, 65535)).to_bytes(2, byteorder='little', signed=False)
        packet.extend(distance_bytes)
        
        # 计算校验和
        checksum = sum(packet[1:]) & 0xFF
        packet.append(checksum)
        
        # 添加结束字节
        packet.append(0xBB)
        
        print(f"发送测试球数据: {color}球, 位置({x},{y}), 半径{radius}")
        return self.send_data(packet)
    
    def run_test_sequence(self):
        """运行测试序列"""
        if not self.is_connected:
            print("错误: 未连接到串口")
            return
        
        print("\n开始运行测试序列...")
        
        # 测试各种颜色的球数据
        test_balls = [
            {"color": "red", "x": 400, "y": 200, "radius": 25},
            {"color": "blue", "x": 300, "y": 150, "radius": 30},
            {"color": "yellow", "x": 350, "y": 250, "radius": 28},
            {"color": "black", "x": 280, "y": 180, "radius": 32},
        ]
        
        success_count = 0
        for ball in test_balls:
            success = self.send_test_ball_data(**ball)
            if success:
                success_count += 1
            time.sleep(0.5)
        
        # 测试控制命令
        self.send_stop_command()
        time.sleep(0.5)
        
        self.send_grab_command(True)
        time.sleep(0.5)
        
        self.send_place_command(1)
        time.sleep(0.5)
        
        print(f"\n测试完成: {success_count}/{len(test_balls)} 个球数据发送成功")
    
    def print_menu(self):
        """打印菜单"""
        print("\n" + "="*50)
        print("          串口调试工具 v1.0")
        print("="*50)
        print(f"当前状态: {'已连接到 ' + self.ser.port if self.is_connected else '未连接'}")
        print("\n命令列表:")
        print("1. 列出可用串口")
        print("2. 连接串口")
        print("3. 断开连接")
        print("4. 发送停止命令")
        print("5. 发送抓取命令")
        print("6. 发送放置命令")
        print("7. 发送测试球数据")
        print("8. 运行测试序列")
        print("9. 发送自定义数据")
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
            color = input("请输入球颜色 (red/blue/yellow/black, 默认red): ").lower() or "red"
            if color not in ["red", "blue", "yellow", "black"]:
                color = "red"
            
            try:
                x = int(input("请输入X坐标 (默认320): ") or "320")
                y = int(input("请输入Y坐标 (默认240): ") or "240")
                radius = int(input("请输入半径 (默认20): ") or "20")
                
                self.send_test_ball_data(color, x, y, radius)
            except ValueError:
                print("请输入有效的数字")
        
        elif cmd == "8":
            self.run_test_sequence()
        
        elif cmd == "9":
            try:
                # 输入格式: AA 01 02 BB (空格分隔的十六进制字节)
                hex_str = input("请输入要发送的十六进制数据 (空格分隔，如 'AA 01 02 BB'): ")
                data = bytes.fromhex(hex_str)
                self.send_data(data)
            except Exception as e:
                print(f"数据格式错误: {e}")
        
        elif cmd == "0":
            print("感谢使用串口调试工具，再见!")
            return False
        
        else:
            print("无效的命令，请重新输入")
        
        return True
    
    def run(self):
        """运行调试工具主循环"""
        try:
            print("欢迎使用救援机器人串口调试工具!")
            self.list_ports()  # 启动时自动列出可用串口
            
            while True:
                self.print_menu()
                cmd = input("请输入命令 (0-9): ")
                if not self.handle_command(cmd):
                    break
        
        except KeyboardInterrupt:
            print("\n程序被用户中断")
        except Exception as e:
            print(f"发生错误: {e}")
        finally:
            self.disconnect()

if __name__ == "__main__":
    debugger = SerialDebugger()
    debugger.run()
