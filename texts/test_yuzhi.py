import cv2
import numpy as np
import json
import os
# 添加日志记录
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from src.utils.logger_utils import setup_logging, get_logger

# 初始化日志
setup_logging()
logger = get_logger(__name__)

# 定义一个空函数，用于创建轨迹栏
def nothing(x):
    pass

# 默认颜色预设
COLOR_PRESETS = {
    'red': {'H Min': 0, 'S Min': 100, 'V Min': 100, 'H Max': 10, 'S Max': 255, 'V Max': 255},
    'blue': {'H Min': 90, 'S Min': 100, 'V Min': 100, 'H Max': 120, 'S Max': 255, 'V Max': 255},
    'yellow': {'H Min': 20, 'S Min': 100, 'V Min': 100, 'H Max': 40, 'S Max': 255, 'V Max': 255},
    'black': {'H Min': 0, 'S Min': 0, 'V Min': 0, 'H Max': 179, 'S Max': 255, 'V Max': 50}
}

# 读取一张来自比赛现场的照片，或者使用视频流
# frame = cv2.imread('competition_field.jpg')
# 使用默认摄像头
try:
    cap = cv2.VideoCapture(0)
    if not cap.isOpened():
        logger.error("无法打开摄像头")
        cap = None
        # 尝试使用图片模式
        image_path = input("请输入图片路径（留空退出）: ")
        if image_path and os.path.exists(image_path):
            frame = cv2.imread(image_path)
            if frame is None:
                logger.error("无法读取图片")
                exit(1)
            frame_mode = True
            logger.info(f"成功加载图片: {image_path}")
        else:
            logger.error("未提供有效图片路径，程序退出")
            exit(1)
    else:
        frame_mode = False
        logger.info("成功打开摄像头")
except Exception as e:
    logger.error(f"初始化输入源时出错: {e}")
    exit(1)

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
print("==== HSV阈值调整工具 ====")
print("使用说明:")
print("- 调整滑动条来设置HSV阈值")
print("- 按 's' 键保存当前阈值配置")
print("- 按 'p' 键打印当前阈值设置")
print("- 按 '1' 键使用红色预设")
print("- 按 '2' 键使用蓝色预设")
print("- 按 '3' 键使用黄色预设")
print("- 按 '4' 键使用黑色预设")
print("- 按 'q' 键退出")

while True:
    try:
        # 获取帧
        if frame_mode:
            frame_to_use = frame.copy()  # 使用图片模式
        else:
            ret, frame_to_use = cap.read()
            if not ret:
                logger.warning("无法读取摄像头帧，尝试重新初始化...")
                # 尝试重新打开摄像头
                cap.release()
                cap = cv2.VideoCapture(0)
                if not cap.isOpened():
                    logger.error("无法重新打开摄像头，切换到图片模式")
                    # 尝试使用图片模式
                    image_path = input("请输入图片路径（留空退出）: ")
                    if image_path and os.path.exists(image_path):
                        frame = cv2.imread(image_path)
                        if frame is None:
                            logger.error("无法读取图片")
                            break
                        frame_mode = True
                        logger.info(f"成功加载图片: {image_path}")
                        frame_to_use = frame.copy()
                    else:
                        logger.error("未提供有效图片路径，程序退出")
                        break
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
        
        # 应用形态学操作减少噪声
        kernel = np.ones((5, 5), np.uint8)
        mask = cv2.erode(mask, kernel, iterations=1)
        mask = cv2.dilate(mask, kernel, iterations=1)

        # 创建结果图像（可视化阈值效果）
        result = cv2.bitwise_and(frame_to_use, frame_to_use, mask=mask)

        # 将原图、掩膜和结果显示出来
        cv2.imshow('Original Frame', frame_to_use)
        cv2.imshow('Mask', mask)
        cv2.imshow('Result', result)

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
    if not frame_mode and cap is not None:
        cap.release()
    cv2.destroyAllWindows()
    logger.info("程序已成功关闭")
except Exception as e:
    logger.error(f"清理资源时出错: {e}")
