import unittest
import cv2
import numpy as np
import os
import sys
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))

from src.color_detector import ColorDetector

class TestAdvancedColorDetection(unittest.TestCase):
    
    def setUp(self):
        config_path = os.path.join(os.path.dirname(__file__), '..', 'config', 'hsv_thresholds.json')
        self.detector = ColorDetector(config_path)
    
    def test_blue_ball_detection(self):
        """测试蓝色球检测"""
        test_image = np.zeros((100, 100, 3), dtype=np.uint8)
        test_image[:, :] = [255, 0, 0]  # 纯蓝色(BGR)
        
        mask = self.detector.detect_color(test_image, "blue")
        blue_pixel_count = np.sum(mask > 0)
        
        self.assertGreater(blue_pixel_count, 0, "蓝色球检测失败")
        print(f"✅ 蓝色球检测通过，检测到 {blue_pixel_count} 个蓝色像素")
    
    def test_yellow_ball_detection(self):
        """测试黄色球检测"""
        test_image = np.zeros((100, 100, 3), dtype=np.uint8)
        test_image[:, :] = [0, 255, 255]  # 纯黄色(BGR)
        
        mask = self.detector.detect_color(test_image, "yellow")
        yellow_pixel_count = np.sum(mask > 0)
        
        self.assertGreater(yellow_pixel_count, 0, "黄色球检测失败")
        print(f"✅ 黄色球检测通过，检测到 {yellow_pixel_count} 个黄色像素")
    
    def test_multiple_colors_same_image(self):
        """测试同一图像中多颜色检测"""
        test_image = np.ones((200, 200, 3), dtype=np.uint8) * 128
        
        # 添加不同颜色的球
        cv2.circle(test_image, (50, 50), 20, (0, 0, 255), -1)   # 红球
        cv2.circle(test_image, (150, 50), 20, (255, 0, 0), -1)  # 蓝球
        cv2.circle(test_image, (50, 150), 20, (0, 255, 255), -1) # 黄球
        cv2.circle(test_image, (150, 150), 20, (0, 0, 0), -1)   # 黑球
        
        # 测试每种颜色检测
        for color_name in ["red", "blue", "yellow", "black"]:
            mask = self.detector.detect_color(test_image, color_name)
            pixel_count = np.sum(mask > 0)
            self.assertGreater(pixel_count, 0, f"{color_name} 在多颜色图像中检测失败")
            print(f"✅ {color_name} 在多颜色图像中检测到 {pixel_count} 像素")

if __name__ == '__main__':
    unittest.main()