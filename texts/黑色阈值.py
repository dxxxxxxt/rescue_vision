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
COLOR_NAME = 'black'
COLOR_DISPLAY_NAME = '黑色小球(核心球)'

# 定义一个空函数，用于创建轨迹栏
def nothing(x):
    pass

# 默认黑色阈值预设 - 针对比赛黑色核心球优化
# 黑色主要关注V通道低值，H和S范围较宽
DEFAULT_THRESHOLDS = {'H Min': 0, 'S Min': 0, 'V Min': 0, 'H Max': 180, 'S Max': 255, 'V Max': 80}

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
    logger.info(f"开始调整{COLOR_DISPLAY_NAME}阈值")
except Exception as e:
    logger.error(f"初始化摄像头时出错: {e}")
    exit(1)

# 添加配置文件保存路径
config_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'config')
os.makedirs(config_dir, exist_ok=True)

# 创建一个窗口和轨迹栏（滑动条）用于调整阈值
window_name = f'{COLOR_DISPLAY_NAME}阈值调整'
cv2.namedWindow(window_name)

# 创建滑块，参数分别是：滑块名，窗口名，最小值，最大值，空函数
cv2.createTrackbar('H Min', window_name, DEFAULT_THRESHOLDS['H Min'], 179, nothing) # H: 0-179
cv2.createTrackbar('S Min', window_name, DEFAULT_THRESHOLDS['S Min'], 255, nothing) # S: 0-255
cv2.createTrackbar('V Min', window_name, DEFAULT_THRESHOLDS['V Min'], 255, nothing) # V: 0-255
cv2.createTrackbar('H Max', window_name, DEFAULT_THRESHOLDS['H Max'], 179, nothing)
cv2.createTrackbar('S Max', window_name, DEFAULT_THRESHOLDS['S Max'], 255, nothing)
cv2.createTrackbar('V Max', window_name, DEFAULT_THRESHOLDS['V Max'], 255, nothing)

def load_thresholds():
    """加载保存的阈值配置"""
    config_file = os.path.join(config_dir, f"hsv_thresholds_{COLOR_NAME}.json")
    try:
        if os.path.exists(config_file):
            with open(config_file, 'r') as f:
                config_data = json.load(f)
            
            if COLOR_NAME in config_data:
                lower = config_data[COLOR_NAME]['lower']
                upper = config_data[COLOR_NAME]['upper']
                
                # 设置轨迹栏位置
                cv2.setTrackbarPos('H Min', window_name, lower[0])
                cv2.setTrackbarPos('S Min', window_name, lower[1])
                cv2.setTrackbarPos('V Min', window_name, lower[2])
                cv2.setTrackbarPos('H Max', window_name, upper[0])
                cv2.setTrackbarPos('S Max', window_name, upper[1])
                cv2.setTrackbarPos('V Max', window_name, upper[2])
                
                logger.info(f"已加载{COLOR_DISPLAY_NAME}保存的阈值配置: {config_file}")
                print(f"已加载{COLOR_DISPLAY_NAME}保存的阈值配置")
                return True
        logger.info(f"未找到{COLOR_DISPLAY_NAME}保存的阈值配置，使用默认值")
    except Exception as e:
        logger.error(f"加载{COLOR_DISPLAY_NAME}阈值配置失败: {e}")
        print(f"错误: 加载失败 - {e}")
    return False

# 尝试加载保存的阈值配置
load_thresholds()

def save_thresholds():
    """保存当前阈值配置"""
    thresholds = {
        'H Min': cv2.getTrackbarPos('H Min', window_name),
        'S Min': cv2.getTrackbarPos('S Min', window_name),
        'V Min': cv2.getTrackbarPos('V Min', window_name),
        'H Max': cv2.getTrackbarPos('H Max', window_name),
        'S Max': cv2.getTrackbarPos('S Max', window_name),
        'V Max': cv2.getTrackbarPos('V Max', window_name)
    }
    
    # 转换为配置文件格式
    config_data = {
        COLOR_NAME: {
            'lower': [thresholds['H Min'], thresholds['S Min'], thresholds['V Min']],
            'upper': [thresholds['H Max'], thresholds['S Max'], thresholds['V Max']]
        }
    }
    
    # 保存到文件
    output_file = os.path.join(config_dir, f"hsv_thresholds_{COLOR_NAME}.json")
    try:
        with open(output_file, 'w') as f:
            json.dump(config_data, f, indent=2)
        logger.info(f"{COLOR_DISPLAY_NAME}阈值配置已保存到: {output_file}")
        print(f"{COLOR_DISPLAY_NAME}阈值配置已保存到: {output_file}")
    except Exception as e:
        logger.error(f"保存{COLOR_DISPLAY_NAME}阈值配置失败: {e}")
        print(f"错误: 保存失败 - {e}")
    """加载保存的阈值配置"""
    config_file = os.path.join(config_dir, f"hsv_thresholds_{COLOR_NAME}.json")
    try:
        if os.path.exists(config_file):
            with open(config_file, 'r') as f:
                config_data = json.load(f)
            
            if COLOR_NAME in config_data:
                lower = config_data[COLOR_NAME]['lower']
                upper = config_data[COLOR_NAME]['upper']
                
                # 设置轨迹栏位置
                cv2.setTrackbarPos('H Min', window_name, lower[0])
                cv2.setTrackbarPos('S Min', window_name, lower[1])
                cv2.setTrackbarPos('V Min', window_name, lower[2])
                cv2.setTrackbarPos('H Max', window_name, upper[0])
                cv2.setTrackbarPos('S Max', window_name, upper[1])
                cv2.setTrackbarPos('V Max', window_name, upper[2])
                
                logger.info(f"已加载{COLOR_DISPLAY_NAME}保存的阈值配置: {config_file}")
                print(f"已加载{COLOR_DISPLAY_NAME}保存的阈值配置")
                return True
        logger.info(f"未找到{COLOR_DISPLAY_NAME}保存的阈值配置，使用默认值")
    except Exception as e:
        logger.error(f"加载{COLOR_DISPLAY_NAME}阈值配置失败: {e}")
        print(f"错误: 加载失败 - {e}")
    return False

def print_current_thresholds():
    """打印当前阈值"""
    h_min = cv2.getTrackbarPos('H Min', window_name)
    s_min = cv2.getTrackbarPos('S Min', window_name)
    v_min = cv2.getTrackbarPos('V Min', window_name)
    h_max = cv2.getTrackbarPos('H Max', window_name)
    s_max = cv2.getTrackbarPos('S Max', window_name)
    v_max = cv2.getTrackbarPos('V Max', window_name)
    
    print(f"当前{COLOR_DISPLAY_NAME}HSV阈值设置:")
    print(f"Lower: [{h_min}, {s_min}, {v_min}]")
    print(f"Upper: [{h_max}, {s_max}, {v_max}]")
    print("注: 黑色小球识别主要关注V通道的低值设置")

# 打印使用说明
print(f"==== {COLOR_DISPLAY_NAME}阈值调整工具 ====")
print("使用说明:")
print("- 调整滑动条来设置HSV阈值")
print("- 黑色识别提示: 主要调整V Max(亮度上限)，降低此值可提高黑色识别率")
print("- 按 's' 键保存当前阈值配置")
print("- 按 'p' 键打印当前阈值设置")
print("- 按 'r' 键恢复默认阈值")
print("- 按 'q' 键退出")

# 性能监控变量
fps_start_time = time.time()
fps_count = 0
current_fps = 0

# 比赛场景优化参数
ENABLE_MORPHOLOGY = True  # 启用形态学操作进行去噪
BLACK_DETECTION_MODE = True  # 针对黑色检测的特殊优化

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
        
        # 获取帧
        ret, frame = cap.read()
        if not ret:
            logger.warning("无法读取摄像头帧，重试...")
            time.sleep(0.1)  # 短暂休眠后重试
            continue

        # 转换为HSV颜色空间，比RGB更易区分颜色
        hsv = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)

        # 从轨迹栏获取当前阈值
        h_min = cv2.getTrackbarPos('H Min', window_name)
        s_min = cv2.getTrackbarPos('S Min', window_name)
        v_min = cv2.getTrackbarPos('V Min', window_name)
        h_max = cv2.getTrackbarPos('H Max', window_name)
        s_max = cv2.getTrackbarPos('S Max', window_name)
        v_max = cv2.getTrackbarPos('V Max', window_name)

        # 定义阈值范围
        lower_bound = np.array([h_min, s_min, v_min])
        upper_bound = np.array([h_max, s_max, v_max])

        # 根据阈值创建掩膜，在范围内的变为白色，不在的变为黑色
        mask = cv2.inRange(hsv, lower_bound, upper_bound)
        
        # 应用形态学操作减少噪声 - 针对黑色球检测优化
        if ENABLE_MORPHOLOGY:
            if BLACK_DETECTION_MODE:
                # 黑色小球检测的特殊形态学处理
                # 使用更小的内核以保留核心球的细节
                kernel_small = np.ones((2, 2), np.uint8)
                # 先腐蚀去除小的噪声点
                mask = cv2.erode(mask, kernel_small, iterations=1)
                # 再膨胀保留小球轮廓
                mask = cv2.dilate(mask, kernel_small, iterations=2)
                
                # 使用开运算进一步优化
                kernel = np.ones((3, 3), np.uint8)
                mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, kernel)
            else:
                # 标准形态学操作
                kernel = np.ones((3, 3), np.uint8)
                mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, kernel)
                mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, kernel)
        else:
            # 简单的腐蚀膨胀操作
            kernel = np.ones((3, 3), np.uint8)
            mask = cv2.erode(mask, kernel, iterations=1)
            mask = cv2.dilate(mask, kernel, iterations=1)

        # 创建结果图像（可视化阈值效果）
        result = cv2.bitwise_and(frame, frame, mask=mask)

        # 在原图上显示当前配置信息和FPS
        info_text = f"FPS: {current_fps:.1f} | {COLOR_DISPLAY_NAME}"
        
        # 在图像上显示信息
        cv2.putText(frame, info_text, (10, 30), 
                    cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 2)
        
        # 在图像底部显示HSV阈值范围
        threshold_text = f"HSV范围: [{h_min},{s_min},{v_min}] to [{h_max},{s_max},{v_max}]"
        cv2.putText(frame, threshold_text, (10, frame.shape[0] - 20), 
                    cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 0), 1)
        
        # 将原图、掩膜和结果显示出来
        cv2.imshow('比赛现场视频', frame)
        cv2.imshow('颜色掩码', mask)
        cv2.imshow('检测结果', result)

        # 处理按键
        key = cv2.waitKey(1) & 0xFF
        if key == ord('q'):
            logger.info("用户退出程序")
            break
        elif key == ord('s'):
            # 保存阈值配置
            save_thresholds()
        elif key == ord('p'):
            # 打印当前阈值
            print_current_thresholds()
        elif key == ord('r'):
            # 恢复默认阈值
            cv2.setTrackbarPos('H Min', window_name, DEFAULT_THRESHOLDS['H Min'])
            cv2.setTrackbarPos('S Min', window_name, DEFAULT_THRESHOLDS['S Min'])
            cv2.setTrackbarPos('V Min', window_name, DEFAULT_THRESHOLDS['V Min'])
            cv2.setTrackbarPos('H Max', window_name, DEFAULT_THRESHOLDS['H Max'])
            cv2.setTrackbarPos('S Max', window_name, DEFAULT_THRESHOLDS['S Max'])
            cv2.setTrackbarPos('V Max', window_name, DEFAULT_THRESHOLDS['V Max'])
            logger.info(f"已恢复{COLOR_DISPLAY_NAME}默认阈值")
            print(f"已恢复{COLOR_DISPLAY_NAME}默认阈值")
        elif key == ord('b'):
            # 切换黑色检测模式
            BLACK_DETECTION_MODE = not BLACK_DETECTION_MODE
            mode_text = "开启" if BLACK_DETECTION_MODE else "关闭"
            logger.info(f"黑色小球特殊检测模式: {mode_text}")
            print(f"黑色小球特殊检测模式已{mode_text}")
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
    logger.info(f"{COLOR_DISPLAY_NAME}阈值调整工具已成功关闭")
except Exception as e:
    logger.error(f"清理资源时出错: {e}")
