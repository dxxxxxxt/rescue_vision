import serial
import time

# 全局变量
ser = None
is_connected = False
port = None
baudrate = None

# 协议定义
START_BYTE = 0xAA
END_BYTE = 0xBB

# 颜色映射
color_id_map = {
    'red_ball': 0,     # 红色小球
    'blue_ball': 1,    # 蓝色小球  
    'yellow_ball': 2,  # 黄色小球（危险目标）
    'black_ball': 3,   # 黑色小球（核心目标）
    'red_zone': 4,     # 红色安全区
    'blue_zone': 5     # 蓝色安全区
}

# 图像和距离参数
image_width = 640
image_height = 480
center_x = image_width // 2
center_y = image_height // 2
actual_diameter_mm = 40
reference_distance_mm = 500
team_color = None

def connect_serial(port_name, baud_rate):
    """简单的串口连接函数"""
    global ser, is_connected, port, baudrate
    
    port = port_name
    baudrate = baud_rate
    
    try:
        # 关闭之前的连接
        if ser and ser.is_open:
            ser.close()
            
        # 连接串口
        ser = serial.Serial(
            port=port,
            baudrate=baudrate,
            bytesize=serial.EIGHTBITS,
            parity=serial.PARITY_NONE,
            stopbits=serial.STOPBITS_ONE,
            timeout=0.1,
            write_timeout=0.5
        )
        
        is_connected = ser.is_open
        if is_connected:
            pass
        return is_connected
        
    except Exception as e:
        pass
        is_connected = False
        return False

def send_serial_data(dx, dy, color_id, distance):
    """发送数据到串口的核心函数"""
    if not is_connected or not ser or not ser.is_open:
        return False
    
    try:
        # 边界检查
        dx = max(-32768, min(dx, 32767))
        dy = max(-32768, min(dy, 32767))
        distance = max(0, min(distance, 65535))
        
        # 构建数据包
        packet = bytearray([START_BYTE])
        packet.extend(dx.to_bytes(2, byteorder='little', signed=True))
        packet.extend(dy.to_bytes(2, byteorder='little', signed=True))
        packet.append(color_id)
        packet.extend(distance.to_bytes(2, byteorder='little', signed=False))
        
        # 计算校验和并发送
        packet.append(sum(packet[1:]) & 0xFF)
        packet.append(END_BYTE)
        ser.write(packet)
        return True
        
    except Exception as e:
            return False

def handle_ball_data(ball_data):
    """处理单个小球数据并发送"""
    # 简单检查数据有效性
    if not isinstance(ball_data, dict) or not all(k in ball_data for k in ['color', 'x', 'y']):
        return False
    
    color = ball_data['color']
    ball_color_key = f'{color}_ball'
    
    # 检查颜色有效性
    if ball_color_key not in color_id_map:
        return False
    
    # 计算坐标偏移
    dx = ball_data['x'] - center_x
    dy = center_y - ball_data['y']
    
    # 估算距离
    radius = ball_data.get('radius', 0)
    if radius <= 0:
        distance = 1000  # 默认距离
    else:
        distance = int(max(100, min((actual_diameter_mm * reference_distance_mm) / (radius * 2), 2000)))
    
    # 发送安全区信息（如果需要）
    if ball_data.get('in_safety_zone', False) and team_color and f'{team_color}_zone' in color_id_map:
        send_serial_data(0, 0, color_id_map[f'{team_color}_zone'], 0)
    
    # 发送小球数据
    return send_serial_data(dx, dy, color_id_map[ball_color_key], distance)

def process_balls_list(balls_list):
    """处理多个小球数据列表"""
    if not isinstance(balls_list, list):
        return False
    
    # 检查是否有小球在安全区
    safety_zone_needed = False
    for ball in balls_list:
        if isinstance(ball, dict) and ball.get('in_safety_zone', False):
            safety_zone_needed = True
            break
    
    # 发送安全区信息
    if safety_zone_needed and team_color and f'{team_color}_zone' in color_id_map:
        send_serial_data(0, 0, color_id_map[f'{team_color}_zone'], 0)
    
    # 处理每个小球
    for ball in balls_list:
        handle_ball_data(ball)
    
    return True

def set_team(team):
    """设置队伍颜色"""
    global team_color
    if team in ['red', 'blue']:
        team_color = team
        return True
    return False

def disconnect_serial():
    """断开串口连接"""
    global ser, is_connected
    try:
        if ser and ser.is_open:
            ser.close()

        is_connected = False
    except Exception as e:
        pass

