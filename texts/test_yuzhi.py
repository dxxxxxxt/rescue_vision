import cv2
import numpy as np
import json
import os
import time
# 添加日志记录
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from src.utils.logger_utils import setup_logging, get_logger

# 初始化日志
setup_logging()
logger = get_logger(__name__)

# 全局配置
VIDEO_WIDTH = 640
VIDEO_HEIGHT = 480
FPS_TARGET = 30
VIDEO_SOURCE = 0  

# 定义一个空函数，用于创建轨迹栏
def nothing(x):
    pass

# 默认颜色预设 - 针对比赛球颜色优化
COLOR_PRESETS = {
    'red': {'H Min': 0, 'S Min': 100, 'V Min': 100, 'H Max': 10, 'S Max': 255, 'V Max': 255},  # 普通球/对方球
    'blue': {'H Min': 90, 'S Min': 100, 'V Min': 100, 'H Max': 120, 'S Max': 255, 'V Max': 255}, # 普通球/本方球
    'yellow': {'H Min': 20, 'S Min': 100, 'V Min': 100, 'H Max': 40, 'S Max': 255, 'V Max': 255}, # 危险球
    'black': {'H Min': 0, 'S Min': 0, 'V Min': 0, 'H Max': 179, 'S Max': 255, 'V Max': 50}    # 核心球
}

# 初始化视频流 - 只使用摄像头模式
try:
    # 打开摄像头
    cap = cv2.VideoCapture(VIDEO_SOURCE)
    
    # 设置摄像头参数
    cap.set(cv2.CAP_PROP_FRAME_WIDTH, VIDEO_WIDTH)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, VIDEO_HEIGHT)
    cap.set(cv2.CAP_PROP_FPS, FPS_TARGET)
    
    if not cap.isOpened():
        logger.error("无法打开摄像头")
        exit(1)
    
    logger.info(f"成功打开摄像头，分辨率: {VIDEO_WIDTH}x{VIDEO_HEIGHT}")
    logger.info("开始处理比赛现场视频流")
except Exception as e:
    logger.error(f"初始化摄像头时出错: {e}")
    exit(1)

# 应用默认红色预设
set_preset('red')
logger.info("已自动应用红色球检测预设")

# 创建一个窗口和轨迹栏（滑动条）用于调整阈值
cv2.namedWindow('Threshold Adjustment')

# 创建滑块，参数分别是：滑块名，窗口名，最小值，最大值，空函数
cv2.createTrackbar('H Min', 'Threshold Adjustment', 0, 179, nothing) # H: 0-179
cv2.createTrackbar('S Min', 'Threshold Adjustment', 0, 255, nothing) # S: 0-255
cv2.createTrackbar('V Min', 'Threshold Adjustment', 0, 255, nothing) # V: 0-255
cv2.createTrackbar('H Max', 'Threshold Adjustment', 179, 179, nothing)
cv2.createTrackbar('S Max', 'Threshold Adjustment', 255, 255, nothing)
cv2.createTrackbar('V Max', 'Threshold Adjustment', 255, 255, nothing)

# 添加预设选择
cv2.createTrackbar('Preset', 'Threshold Adjustment', 0, len(COLOR_PRESETS), nothing)

# 添加配置文件保存路径
config_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'config')
os.makedirs(config_dir, exist_ok=True)
def set_preset(preset_name):
    """设置预设颜色值"""
    if preset_name in COLOR_PRESETS:
        preset = COLOR_PRESETS[preset_name]
        cv2.setTrackbarPos('H Min', 'Threshold Adjustment', preset['H Min'])
        cv2.setTrackbarPos('S Min', 'Threshold Adjustment', preset['S Min'])
        cv2.setTrackbarPos('V Min', 'Threshold Adjustment', preset['V Min'])
        cv2.setTrackbarPos('H Max', 'Threshold Adjustment', preset['H Max'])
        cv2.setTrackbarPos('S Max', 'Threshold Adjustment', preset['S Max'])
        cv2.setTrackbarPos('V Max', 'Threshold Adjustment', preset['V Max'])
        logger.info(f"已应用预设: {preset_name}")

def save_thresholds(color_name='custom'):
    """保存当前阈值配置"""
    thresholds = {
        'H Min': cv2.getTrackbarPos('H Min', 'Threshold Adjustment'),
        'S Min': cv2.getTrackbarPos('S Min', 'Threshold Adjustment'),
        'V Min': cv2.getTrackbarPos('V Min', 'Threshold Adjustment'),
        'H Max': cv2.getTrackbarPos('H Max', 'Threshold Adjustment'),
        'S Max': cv2.getTrackbarPos('S Max', 'Threshold Adjustment'),
        'V Max': cv2.getTrackbarPos('V Max', 'Threshold Adjustment')
    }
    
    # 转换为配置文件格式
    config_data = {
        color_name: {
            'lower': [thresholds['H Min'], thresholds['S Min'], thresholds['V Min']],
            'upper': [thresholds['H Max'], thresholds['S Max'], thresholds['V Max']]
        }
    }
    
    # 保存到文件
    output_file = os.path.join(config_dir, f"hsv_thresholds_{color_name}.json")
    try:
        with open(output_file, 'w') as f:
            json.dump(config_data, f, indent=2)
        logger.info(f"阈值配置已保存到: {output_file}")
        print(f"阈值配置已保存到: {output_file}")
    except Exception as e:
        logger.error(f"保存阈值配置失败: {e}")
        print(f"错误: 保存失败 - {e}")

def print_current_thresholds():
    """打印当前阈值"""
    h_min = cv2.getTrackbarPos('H Min', 'Threshold Adjustment')
    s_min = cv2.getTrackbarPos('S Min', 'Threshold Adjustment')
    v_min = cv2.getTrackbarPos('V Min', 'Threshold Adjustment')
    h_max = cv2.getTrackbarPos('H Max', 'Threshold Adjustment')
    s_max = cv2.getTrackbarPos('S Max', 'Threshold Adjustment')
    v_max = cv2.getTrackbarPos('V Max', 'Threshold Adjustment')
    
    print("当前HSV阈值设置:")
    print(f"Lower: [{h_min}, {s_min}, {v_min}]")
    print(f"Upper: [{h_max}, {s_max}, {v_max}]")

# 打印使用说明
print("==== 比赛现场HSV阈值调整工具 ====")
print("使用说明:")
print("- 调整滑动条来设置HSV阈值")
print("- 按 's' 键保存当前阈值配置")
print("- 按 'p' 键打印当前阈值设置")
print("- 按 '1' 键使用红色预设 (普通球/对方球)")
print("- 按 '2' 键使用蓝色预设 (普通球/本方球)")
print("- 按 '3' 键使用黄色预设 (危险球)")
print("- 按 '4' 键使用黑色预设 (核心球)")
print("- 按 'q' 键退出")

# 性能监控变量
fps_start_time = time.time()
fps_count = 0
current_fps = 0

# 比赛场景优化参数
ENABLE_MORPHOLOGY = True  # 启用形态学操作进行去噪

while True:
    try:
        # 计算FPS
        fps_count += 1
        if fps_count % 10 == 0:
            current_time = time.time()
            current_fps = fps_count / (current_time - fps_start_time)
            fps_start_time = current_time
            fps_count = 0
            logger.info(f"视频处理FPS: {current_fps:.2f}")
        
        # 只使用视频流模式获取帧
        ret, frame_to_use = cap.read()
        if not ret:
            logger.warning("无法读取摄像头帧，重试...")
            time.sleep(0.1)  # 短暂休眠后重试
            continue

        # 转换为HSV颜色空间，比RGB更易区分颜色
        hsv = cv2.cvtColor(frame_to_use, cv2.COLOR_BGR2HSV)

        # 从轨迹栏获取当前阈值
        h_min = cv2.getTrackbarPos('H Min', 'Threshold Adjustment')
        s_min = cv2.getTrackbarPos('S Min', 'Threshold Adjustment')
        v_min = cv2.getTrackbarPos('V Min', 'Threshold Adjustment')
        h_max = cv2.getTrackbarPos('H Max', 'Threshold Adjustment')
        s_max = cv2.getTrackbarPos('S Max', 'Threshold Adjustment')
        v_max = cv2.getTrackbarPos('V Max', 'Threshold Adjustment')
        preset_idx = cv2.getTrackbarPos('Preset', 'Threshold Adjustment')
        
        # 处理预设选择
        if preset_idx > 0 and preset_idx <= len(COLOR_PRESETS):
            preset_names = list(COLOR_PRESETS.keys())
            set_preset(preset_names[preset_idx - 1])
            cv2.setTrackbarPos('Preset', 'Threshold Adjustment', 0)  # 重置预设选择器

        # 定义阈值范围
        lower_bound = np.array([h_min, s_min, v_min])
        upper_bound = np.array([h_max, s_max, v_max])

        # 根据阈值创建掩膜，在范围内的变为白色，不在的变为黑色
        mask = cv2.inRange(hsv, lower_bound, upper_bound)
        
        # 应用形态学操作减少噪声 - 针对比赛现场优化
        if ENABLE_MORPHOLOGY:
            # 使用3x3内核以保留小球细节
            kernel = np.ones((3, 3), np.uint8)
            # 开运算：先腐蚀后膨胀，去除噪声点
            mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, kernel)
            # 闭运算：先膨胀后腐蚀，连接断开的区域
            mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, kernel)
        else:
            # 简单的腐蚀膨胀操作
            kernel = np.ones((3, 3), np.uint8)
            mask = cv2.erode(mask, kernel, iterations=1)
            mask = cv2.dilate(mask, kernel, iterations=1)

        # 创建结果图像（可视化阈值效果）
        result = cv2.bitwise_and(frame_to_use, frame_to_use, mask=mask)

        # 在原图上显示当前配置信息和FPS
        color_info = {
            'red': '红色 - 普通球/对方球',
            'blue': '蓝色 - 普通球/本方球',
            'yellow': '黄色 - 危险球',
            'black': '黑色 - 核心球'
        }
        
        # 获取当前应用的预设信息
        current_preset = None
        for color, preset in COLOR_PRESETS.items():
            if (preset['H Min'] == h_min and preset['H Max'] == h_max and 
                preset['S Min'] == s_min and preset['S Max'] == s_max and 
                preset['V Min'] == v_min and preset['V Max'] == v_max):
                current_preset = color_info[color]
                break
        
        info_text = f"FPS: {current_fps:.1f}"
        if current_preset:
            info_text += f" | 当前: {current_preset}"
        
        # 在图像上显示信息
        cv2.putText(frame_to_use, info_text, (10, 30), 
                    cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 2)
        
        # 在图像底部显示HSV阈值范围
        threshold_text = f"HSV范围: [{h_min},{s_min},{v_min}] to [{h_max},{s_max},{v_max}]"
        cv2.putText(frame_to_use, threshold_text, (10, frame_to_use.shape[0] - 20), 
                    cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 0), 1)
        
        # 将原图、掩膜和结果显示出来
        cv2.imshow('比赛现场视频', frame_to_use)
        cv2.imshow('颜色掩码', mask)
        cv2.imshow('检测结果', result)

        # 处理按键
        key = cv2.waitKey(1) & 0xFF
        if key == ord('q'):
            logger.info("用户退出程序")
            break
        elif key == ord('s'):
            # 保存阈值配置
            color_name = input("请输入颜色名称（默认: custom）: ").strip() or 'custom'
            save_thresholds(color_name)
        elif key == ord('p'):
            # 打印当前阈值
            print_current_thresholds()
        elif key == ord('1'):
            set_preset('red')
        elif key == ord('2'):
            set_preset('blue')
        elif key == ord('3'):
            set_preset('yellow')
        elif key == ord('4'):
            set_preset('black')
    except Exception as e:
        logger.error(f"主循环中出错: {e}")
        import traceback
        traceback.print_exc()
        # 继续运行而不是退出
        continue

# 清理资源
try:
    if cap is not None:
        cap.release()
    cv2.destroyAllWindows()
    logger.info("比赛现场HSV阈值调整工具已成功关闭")
except Exception as e:
    logger.error(f"清理资源时出错: {e}")
