#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
测试安全区相关功能的脚本
验证动态安全区检测、紫色围栏处理和小球优先级逻辑
"""

import sys
import os
import cv2
import numpy as np

# 添加项目根目录到Python路径
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from src.vision_core import VisionCore
from src.color_detector import ColorDetector

def create_test_frame():
    """创建测试图像，包含紫色围栏、红蓝安全区和不同颜色的小球"""
    # 创建一个800x600的黑色背景
    frame = np.zeros((600, 800, 3), dtype=np.uint8)
    
    # 绘制紫色围栏（未知形状）
    # 创建一个不规则的闭合路径作为围栏
    fence_points = np.array([
        [50, 50], [100, 40], [200, 60], [300, 40], [400, 70], 
        [500, 30], [600, 60], [700, 40], [750, 100], [730, 200],
        [750, 300], [730, 400], [750, 500], [700, 550], [600, 530],
        [500, 560], [400, 530], [300, 560], [200, 530], [100, 550],
        [50, 500], [70, 400], [50, 300], [70, 200], [50, 100], [50, 50]
    ])
    cv2.fillPoly(frame, [fence_points], (150, 0, 150))  # 紫色围栏 BGR: (150, 0, 150)
    
    # 绘制红色安全区
    cv2.rectangle(frame, (100, 100), (250, 200), (0, 0, 255), -1)  # 红色 BGR: (0, 0, 255)
    
    # 绘制蓝色安全区
    cv2.rectangle(frame, (550, 350), (700, 450), (255, 0, 0), -1)  # 蓝色 BGR: (255, 0, 0)
    
    # 绘制不同颜色的小球（在围栏内）
    # 红色小球（应优先运输到红色安全区）
    cv2.circle(frame, (300, 200), 30, (0, 0, 255), -1)  # 红色
    # 蓝色小球（应优先运输到蓝色安全区）
    cv2.circle(frame, (400, 300), 25, (255, 0, 0), -1)  # 蓝色
    # 黄色小球（中性颜色）
    cv2.circle(frame, (500, 200), 20, (0, 255, 255), -1)  # 黄色
    # 绿色小球（中性颜色）
    cv2.circle(frame, (350, 400), 22, (0, 255, 0), -1)  # 绿色
    
    # 在安全区内的小球（应降低优先级）
    cv2.circle(frame, (150, 150), 15, (0, 0, 255), -1)  # 红色小球在红色安全区
    cv2.circle(frame, (600, 400), 15, (255, 0, 0), -1)  # 蓝色小球在蓝色安全区
    
    return frame

def test_safety_zone_detection():
    """测试安全区检测功能"""
    print("测试安全区检测功能...")
    
    # 创建测试图像
    frame = create_test_frame()
    
    # 初始化VisionCore
    vision_core = VisionCore()
    vision_core.set_team_color('red')  # 设置队伍颜色为红色
    
    # 检测安全区
    safety_zones = vision_core.detect_safety_zones(frame)
    
    # 验证检测结果
    print(f"检测到的安全区: {safety_zones.keys()}")
    for color, zone_info in safety_zones.items():
        if zone_info and 'contour' in zone_info:
            area = cv2.contourArea(zone_info['contour'])
            print(f"{color}安全区面积: {area:.2f} 像素")
    
    return frame, vision_core

def test_ball_in_safety_zone(frame, vision_core):
    """测试小球是否在安全区内的判断"""
    print("\n测试小球安全区判断功能...")
    
    # 检测安全区
    safety_zones = vision_core.detect_safety_zones(frame)
    
    # 创建测试小球
    balls = [
        {'x': 300, 'y': 200, 'radius': 30, 'color': 'red'},
        {'x': 150, 'y': 150, 'radius': 15, 'color': 'red'},
        {'x': 400, 'y': 300, 'radius': 25, 'color': 'blue'},
        {'x': 600, 'y': 400, 'radius': 15, 'color': 'blue'},
        {'x': 500, 'y': 200, 'radius': 20, 'color': 'yellow'}
    ]
    
    # 测试每个小球
    for ball in balls:
        in_safety, zone_color = vision_core.is_ball_in_safety_zone(ball, safety_zones)
        status = "在安全区内" if in_safety else "不在安全区内"
        zone_info = f"，位于{zone_color}安全区" if zone_color else ""
        print(f"{ball['color']}色小球 ({ball['x']}, {ball['y']}): {status}{zone_info}")

def test_ball_priority(frame, vision_core):
    """测试小球优先级逻辑"""
    print("\n测试小球优先级逻辑...")
    
    # 检测安全区
    safety_zones = vision_core.detect_safety_zones(frame)
    
    # 创建测试小球
    balls = [
        {'x': 300, 'y': 200, 'radius': 30, 'color': 'red'},
        {'x': 150, 'y': 150, 'radius': 15, 'color': 'red'},
        {'x': 400, 'y': 300, 'radius': 25, 'color': 'blue'},
        {'x': 600, 'y': 400, 'radius': 15, 'color': 'blue'},
        {'x': 500, 'y': 200, 'radius': 20, 'color': 'yellow'},
        {'x': 350, 'y': 400, 'radius': 22, 'color': 'green'}
    ]
    
    # 计算每个小球的优先级
    for ball in balls:
        priority = vision_core.calculate_ball_priority(ball, safety_zones)
        print(f"{ball['color']}色小球优先级: {priority}")
    
    # 获取优先级排序后的小球
    prioritized_balls = vision_core.get_prioritized_balls(balls, safety_zones)
    print("\n优先级排序后的小球:")
    for i, ball in enumerate(prioritized_balls):
        print(f"{i+1}. {ball['color']}色小球")
    
    # 获取最佳目标
    best_target = vision_core.get_best_target(balls, safety_zones)
    if best_target:
        print(f"\n最佳目标: {best_target['color']}色小球")

def test_frame_processing(frame, vision_core):
    """测试完整的帧处理流程"""
    print("\n测试完整的帧处理流程...")
    
    # 处理帧
    result = vision_core.process_frame(frame)
    
    # 显示处理后的图像
    if result['frame'] is not None:
        # 保存处理后的图像用于检查
        output_path = os.path.join(os.path.dirname(__file__), 'test_output.jpg')
        cv2.imwrite(output_path, result['frame'])
        print(f"处理后的图像已保存到: {output_path}")
        
        # 显示处理结果信息
        print(f"检测到的小球数量: {len(result['balls'])}")
        print(f"检测到的安全区: {result['safety_zones'].keys()}")
        if result['best_target']:
            print(f"选择的最佳目标: {result['best_target']['color']}色小球")

def main():
    """主函数"""
    print("开始测试安全区相关功能...")
    
    try:
        # 测试安全区检测
        frame, vision_core = test_safety_zone_detection()
        
        # 测试小球安全区判断
        test_ball_in_safety_zone(frame, vision_core)
        
        # 测试小球优先级逻辑
        test_ball_priority(frame, vision_core)
        
        # 测试完整的帧处理流程
        test_frame_processing(frame, vision_core)
        
        print("\n所有测试完成！")
    except Exception as e:
        print(f"测试过程中出现错误: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()
