import serial
import time
ser = None
is_connected = False
port = '/dev/ttyS3'
baudrate = 115200

START_BYTE = 0xAA
END_BYTE = 0xBB

color_id_map = {
    'red_ball': 0,     # 红色小球
    'blue_ball': 1,    # 蓝色小球  
    'yellow_ball': 2,  # 黄色小球（危险目标）
    'black_ball': 3,   # 黑色小球（核心目标）
    'red_zone': 4,     # 红色安全区
    'blue_zone': 5     # 蓝色安全区
}