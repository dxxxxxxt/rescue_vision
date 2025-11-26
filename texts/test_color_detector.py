import unittest
import cv2
import numpy as np
import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))

from src.color_detector import ColorDetector

class TestColorDetector(unittest.TestCase):
    
    def setUp(self):
        """测试前置设置"""
        # 获取正确的配置文件路径
        config_path = os.path.join(os.path.dirname(__file__), '..', 'config', 'hsv_thresholds.json')
        self.detector = ColorDetector(config_path)
        
        # 定义所有基础颜色的BGR值
        self.base_colors = {
            'red': [0, 0, 255],        # BGR红色
            'yellow': [0, 255, 255],   # BGR黄色
            'blue': [255, 0, 0],       # BGR蓝色
            'black': [0, 0, 0]         # BGR黑色
        }
        
    def test_red_ball_detection(self):
        """测试红色球检测"""
        # 创建纯红色测试图像
        test_image = np.zeros((100, 100, 3), dtype=np.uint8)
        test_image[:, :] = [0, 0, 255]  # 纯红色(BGR)
        
        mask = self.detector.detect_color(test_image, 'red')
        red_pixel_count = np.sum(mask > 0)
        
        self.assertGreater(red_pixel_count, 0, "红色球检测失败")
        print(f"红色球检测通过，检测到 {red_pixel_count} 个红色像素")
    
    def test_black_ball_detection(self):
        """测试黑色球检测"""
        test_image = np.ones((100, 100, 3), dtype=np.uint8) * 128  # 灰色背景
        cv2.circle(test_image, (50, 50), 20, (0, 0, 0), -1)  # 黑色球
        
        mask = self.detector.detect_color(test_image, 'black')
        contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        
        self.assertEqual(len(contours), 1, "应该检测到1个黑色球")
        print("黑色球检测通过")
    
    def test_empty_image(self):
        """测试空图像处理"""
        empty_image = np.zeros((100, 100, 3), dtype=np.uint8)
        
        mask = self.detector.detect_color(empty_image, 'red')
        red_pixel_count = np.sum(mask > 0)
        
        self.assertEqual(red_pixel_count, 0, "空图像不应该检测到红色")
        print("空图像处理通过")
    

    
    def test_all_base_colors(self):
        """测试所有基础颜色检测"""
        for color_name, bgr_value in self.base_colors.items():
            with self.subTest(color=color_name):
                # 创建纯颜色测试图像
                test_image = np.zeros((100, 100, 3), dtype=np.uint8)
                test_image[:, :] = bgr_value
                
                # 检测颜色
                mask = self.detector.detect_color(test_image, color_name)
                color_pixel_count = np.sum(mask > 0)
                
                # 验证检测结果
                self.assertGreater(color_pixel_count, 0, f"{color_name}颜色检测失败")
                print(f"{color_name}颜色检测通过，检测到 {color_pixel_count} 个像素")
    
    def test_yellow_ball_detection(self):
        """测试黄色球检测"""
        test_image = np.zeros((100, 100, 3), dtype=np.uint8)
        test_image[:, :] = [0, 255, 255]  # 纯黄色(BGR)
        
        mask = self.detector.detect_color(test_image, 'yellow')
        yellow_pixel_count = np.sum(mask > 0)
        
        self.assertGreater(yellow_pixel_count, 0, "黄色球检测失败")
        print(f"黄色球检测通过，检测到 {yellow_pixel_count} 个黄色像素")
    
    def test_blue_ball_detection(self):
        """测试蓝色球检测"""
        test_image = np.zeros((100, 100, 3), dtype=np.uint8)
        test_image[:, :] = [255, 0, 0]  # 纯蓝色(BGR)
        
        mask = self.detector.detect_color(test_image, 'blue')
        blue_pixel_count = np.sum(mask > 0)
        
        self.assertGreater(blue_pixel_count, 0, "蓝色球检测失败")
        print(f"蓝色球检测通过，检测到 {blue_pixel_count} 个蓝色像素")
    
    def test_all_colors_in_one_image(self):
        """测试在同一图像中检测所有颜色"""
        # 创建测试图像
        test_image = np.ones((200, 200, 3), dtype=np.uint8) * 128  # 灰色背景
        
        # 在不同位置绘制不同颜色的正方形
        positions = [(50, 50), (150, 50), (50, 150), (150, 150)]
        
        for i, (color_name, bgr_value) in enumerate(self.base_colors.items()):
            x, y = positions[i]
            cv2.rectangle(test_image, (x-30, y-30), (x+30, y+30), bgr_value, -1)
        
        # 测试每种颜色检测
        for color_name in self.base_colors.keys():
            mask = self.detector.detect_color(test_image, color_name)
            pixel_count = np.sum(mask > 0)
            
            self.assertGreater(pixel_count, 0, f"{color_name}在混合图像中检测失败")
            print(f"{color_name}在混合图像中检测通过，检测到 {pixel_count} 个像素")

if __name__ == '__main__':
    unittest.main()