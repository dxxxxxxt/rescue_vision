#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
紫色围栏测试脚本
用于测试紫色围栏检测和过滤功能
"""

import cv2
import numpy as np
import sys
import os

# 添加项目根目录到Python路径
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

# 导入视觉核心模块
from rescue_vision.src.vision_core import VisionCore
from rescue_vision.src.utils.logger_utils import get_logger

# 获取日志记录器
logger = get_logger(__name__)

def test_purple_fence(display_fence=True):
    """
    测试紫色围栏检测功能
    
    Args:
        display_fence: 是否在界面上显示紫色围栏区域
    """
    try:
        # 初始化视觉核心
        logger.info("初始化视觉系统...")
        vision = VisionCore()
        
        # 修改vision_core的process_frame方法以显示围栏（如果需要）
        original_process_frame = vision.process_frame
        
        def custom_process_frame(frame):
            result = original_process_frame(frame)
            if display_fence and 'frame' in result and result['frame'] is not None:
                # 重新检测围栏并显示
                fence_mask = vision.detect_purple_fence(frame)
                if fence_mask is not None:
                    result['frame'] = vision.draw_purple_fence(result['frame'], fence_mask)
            return result
        
        if display_fence:
            vision.process_frame = custom_process_frame
        
        logger.info("紫色围栏测试开始！")
        logger.info("按键说明:")
        logger.info("  - 'q': 退出程序")
        logger.info("  - 'f': 切换围栏显示/隐藏")
        logger.info("  - 'r': 重置系统")
        
        # 运行视觉系统
        vision.run(display=True)
        
    except KeyboardInterrupt:
        logger.info("测试被用户中断")
    except Exception as e:
        logger.error(f"测试过程中发生错误: {e}")
    finally:
        if 'vision' in locals():
            vision.release()
        logger.info("测试结束，资源已释放")


def create_test_image():
    """
    创建一个带有紫色围栏和不同颜色小球的测试图像
    用于离线测试
    """
    # 创建一个640x480的白色背景图像
    test_image = np.ones((480, 640, 3), dtype=np.uint8) * 255
    
    # 绘制紫色围栏（左侧和右侧）
    cv2.rectangle(test_image, (0, 0), (50, 480), (128, 0, 128), -1)  # 左侧围栏
    cv2.rectangle(test_image, (590, 0), (640, 480), (128, 0, 128), -1)  # 右侧围栏
    
    # 在围栏内绘制一些小球（这些应该被过滤掉）
    cv2.circle(test_image, (25, 100), 30, (0, 0, 255), -1)  # 红色球（围栏内）
    cv2.circle(test_image, (615, 400), 25, (255, 0, 0), -1)  # 蓝色球（围栏内）
    
    # 在围栏外绘制一些小球（这些应该被检测到）
    cv2.circle(test_image, (200, 200), 40, (0, 0, 255), -1)  # 红色球
    cv2.circle(test_image, (400, 150), 35, (255, 0, 0), -1)  # 蓝色球
    cv2.circle(test_image, (300, 350), 30, (0, 255, 255), -1)  # 黄色球
    cv2.circle(test_image, (500, 300), 45, (0, 0, 0), -1)  # 黑色球
    
    # 保存测试图像
    test_image_path = "test_purple_fence_image.jpg"
    cv2.imwrite(test_image_path, test_image)
    logger.info(f"测试图像已保存到: {test_image_path}")
    
    return test_image

def test_with_image(image_path=None):
    """
    使用图像测试紫色围栏功能
    
    Args:
        image_path: 图像路径，如果为None则创建测试图像
    """
    try:
        # 加载或创建测试图像
        if image_path and os.path.exists(image_path):
            test_image = cv2.imread(image_path)
            logger.info(f"加载测试图像: {image_path}")
        else:
            logger.info("创建测试图像...")
            test_image = create_test_image()
        
        # 初始化视觉核心
        vision = VisionCore()
        
        # 处理图像
        result = vision.process_frame(test_image)
        
        # 显示原始图像和处理后的图像
        cv2.imshow("Original Image", test_image)
        cv2.imshow("Processed Image", result['frame'])
        
        # 显示检测到的小球信息
        logger.info(f"检测到 {len(result['balls'])} 个小球")
        for i, ball in enumerate(result['balls']):
            logger.info(f"小球 {i+1}: 颜色={ball.get('color')}, 位置=({ball.get('x')}, {ball.get('y')}), 半径={ball.get('radius')}")
        
        logger.info("按任意键退出...")
        cv2.waitKey(0)
        cv2.destroyAllWindows()
        
    except Exception as e:
        logger.error(f"图像测试过程中发生错误: {e}")


import argparse

if __name__ == "__main__":
    # 解析命令行参数
    parser = argparse.ArgumentParser(description='紫色围栏测试工具')
    parser.add_argument('-m', '--mode', type=int, choices=[1,2,3,4], 
                        help='测试模式: 1=实时摄像头(显示围栏), 2=实时摄像头(隐藏围栏), 3=图像测试, 4=创建测试图像')
    parser.add_argument('-i', '--image', type=str, help='测试图像路径')
    parser.add_argument('-a', '--auto', action='store_true', help='自动测试模式')
    args = parser.parse_args()
    
    # 自动测试模式
    if args.auto:
        logger.info("执行自动测试...")
        # 创建测试图像
        create_test_image()
        # 使用测试图像进行测试（无需显示界面）
        # 这里我们需要修改test_with_image函数以支持无界面模式
        sys.exit(0)
    
    # 使用命令行参数指定模式
    if args.mode:
        choice = str(args.mode)
    else:
        # 交互式选择
        print("===== 紫色围栏测试工具 =====")
        print("1. 实时摄像头测试（显示围栏）")
        print("2. 实时摄像头测试（隐藏围栏）")
        print("3. 使用测试图像测试")
        print("4. 创建测试图像")
        
        choice = input("请选择测试模式 (1-4): ")
    
    if choice == '1':
        test_purple_fence(display_fence=True)
    elif choice == '2':
        test_purple_fence(display_fence=False)
    elif choice == '3':
        image_path = args.image or input("请输入图像路径（直接回车使用默认测试图像）: ").strip()
        test_with_image(image_path if image_path else None)
    elif choice == '4':
        create_test_image()
    else:
        print("无效选择，退出程序")
