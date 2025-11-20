import serial
import time
import struct

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
        self.port = port
        self.baudrate = baudrate
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
            print("⚠️ 未设置队伍颜色，请在使用前调用 set_team_color()")
        
        self.connect()

    def set_team_color(self, team_color):
        """
        设置己方队伍颜色（比赛抽签后必须调用）
        :param team_color: 'red' 或 'blue'
        :return: 是否设置成功
        """
        if team_color not in ['red', 'blue']:
            print("❌ 无效的队伍颜色，请输入 'red' 或 'blue'")
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
        
        print(f"✅ 队伍颜色设置: 己方{self.team_color.upper()}队")
        print("🎯 当前优先级设置:")
        for color, priority in sorted(self.priorities.items(), key=lambda x: x[1], reverse=True):
            action = "收集" if priority > 0 else "忽略"
            score = {30: "15分", 20: "10分", 10: "5分", 0: "0分"}[priority]
            print(f"   {color.upper()}球: 优先级{priority} ({action}) - {score}")
        
        return True

    def connect(self):
        """连接串口"""
        try:
            if self.ser and self.ser.is_open:
                self.ser.close()
            
            self.ser = serial.Serial(
                port=self.port,
                baudrate=self.baudrate,
                bytesize=serial.EIGHTBITS,
                parity=serial.PARITY_NONE,
                stopbits=serial.STOPBITS_ONE,
                timeout=0.1
            )
            
            self.is_connected = True
            print(f"✅ 串口连接成功: {self.port} 波特率: {self.baudrate}")
            return True
            
        except Exception as e:
            print(f"❌ 串口连接失败: {e}")
            self.is_connected = False
            return False

    def ensure_connected(self):
        """确保串口连接"""
        if not self.is_connected or not self.ser or not self.ser.is_open:
            return self.connect()
        return True

    def send_ball_data(self, dx, dy, ball_color, distance):
        """
        发送小球数据给电控系统
        """
        if not self.ensure_connected():
            return False

        try:
            # 数据验证
            if ball_color not in self.color_to_id:
                print(f"❌ 无效的颜色: {ball_color}")
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
            print(f"🎯 发送: {ball_color}球, 偏移({dx},{dy}), 距离{distance}mm")
            return True
            
        except Exception as e:
            print(f"❌ 发送失败: {e}")
            return False

    def send_ball_detection(self, ball_data):
        """
        发送小球检测结果
        :param ball_data: {'color': 'red', 'x': 400, 'y': 300, 'radius': 25}
        """
        if not self.ensure_connected():
            return False
        
        if not self.team_color:
            print("❌ 请先设置队伍颜色！调用 set_team_color('red') 或 set_team_color('blue')")
            return False
        
        try:
            # 验证数据
            required_fields = ['color', 'x', 'y']
            for field in required_fields:
                if field not in ball_data:
                    print(f"❌ 缺少字段: {field}")
                    return False
            
            color = ball_data['color']
            
            # 检查是否应该收集这个小球
            if self.priorities.get(color, 0) == 0:
                print(f"⏭️ 忽略{color}球（敌方目标）")
                return False
            
            # 计算坐标和距离
            dx = ball_data['x'] - self.center_x
            dy = self.center_y - ball_data['y']
            distance = self.estimate_distance(ball_data.get('radius', 0))
            
            return self.send_ball_data(dx, dy, color, distance)
            
        except Exception as e:
            print(f"❌ 处理失败: {e}")
            return False

    def estimate_distance(self, pixel_radius):
        """估算距离"""
        if pixel_radius <= 0:
            return 1000
        pixel_diameter = pixel_radius * 2
        distance_mm = (self.actual_diameter_mm * self.reference_distance_mm) / pixel_diameter
        return int(max(100, min(distance_mm, 2000)))

    def send_multiple_balls(self, balls_list):
        """
        发送多个小球，自动选择优先级最高的
        """
        if not balls_list:
            print("⚠️ 没有检测到小球")
            return False
        
        if not self.team_color:
            print("❌ 请先设置队伍颜色！")
            return False
        
        # 过滤可收集的小球
        collectable_balls = []
        for ball in balls_list:
            color = ball.get('color', '')
            if self.priorities.get(color, 0) > 0:
                collectable_balls.append(ball)
        
        if not collectable_balls:
            print("⚠️ 没有可收集的小球（都是敌方目标）")
            return False
        
        # 按优先级排序
        sorted_balls = sorted(collectable_balls, 
                             key=lambda ball: self.priorities.get(ball['color'], 0), 
                             reverse=True)
        
        target_ball = sorted_balls[0]
        priority = self.priorities[target_ball['color']]
        print(f"🎯 选择{target_ball['color']}球 (优先级: {priority})")
        
        return self.send_ball_detection(target_ball)

    def send_stop(self):
        """发送停止指令"""
        print("🛑 发送停止指令")
        return self.send_ball_data(0, 0, 'red', 1000)

    def test_communication(self):
        """测试通信"""
        if not self.ensure_connected():
            return False
        
        print("🧪 开始通信测试...")
        
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
        
        print(f"📊 测试完成: {success_count}/{len(test_balls)} 通过")
        return success_count > 0

    def close(self):
        """关闭串口"""
        if self.ser and self.ser.is_open:
            self.ser.close()
            self.is_connected = False
            print("🔌 串口已关闭")


# 使用示例
if __name__ == "__main__":
    # 创建串口对象（不指定颜色）
    vision_serial = VisionSerial('/dev/ttyUSB0', 115200)
    
    try:
        # 必须先设置队伍颜色！
        print("=== 设置队伍颜色 ===")
        vision_serial.set_team_color('red')  # 或者 'blue'
        
        # 测试通信
        print("\n=== 通信测试 ===")
        vision_serial.test_communication()
        
        # 模拟比赛场景
        print("\n=== 模拟比赛 ===")
        detected_balls = [
            {'color': 'red', 'x': 350, 'y': 220, 'radius': 28},    # 己方目标
            {'color': 'blue', 'x': 400, 'y': 300, 'radius': 25},   # 敌方目标（被忽略）
            {'color': 'yellow', 'x': 280, 'y': 180, 'radius': 32}, # 危险目标（最高优先级）
        ]
        
        vision_serial.send_multiple_balls(detected_balls)
        
    except KeyboardInterrupt:
        print("\n⏹️ 用户中断")
    finally:
        vision_serial.close()
