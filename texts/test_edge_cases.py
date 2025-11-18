import unittest
import cv2
import numpy as np
import os
import sys
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))

from src.color_detector import ColorDetector

class TestEdgeCases(unittest.TestCase):
    
    def setUp(self):
        """测试前置设置"""
        config_path = os.path.join(os.path.dirname(__file__), '..', 'config', 'hsv_thresholds.json')
        self.detector = ColorDetector(config_path)
    
    def test_partial_balls(self):
        """测试部分球体（被遮挡）"""
        test_image = np.ones((100, 100, 3), dtype=np.uint8) * 128
        # 绘制半个红色球
        cv2.circle(test_image, (10, 50), 20, (0, 0, 255), -1)
        
        mask = self.detector.detect_color(test_image, "red")
        red_pixel_count = np.sum(mask > 0)
        
        # 部分球体应该也能检测到
        self.assertGreater(red_pixel_count, 0, "部分球体检测失败")
        print("✅ 部分球体检测通过")
    
    def test_small_balls(self):
        """测试小尺寸球体"""
        test_image = np.ones((100, 100, 3), dtype=np.uint8) * 128
        # 绘制小红色球（半径5像素）
        cv2.circle(test_image, (50, 50), 5, (0, 0, 255), -1)
        
        mask = self.detector.detect_color(test_image, "red")
        red_pixel_count = np.sum(mask > 0)
        
        self.assertGreater(red_pixel_count, 0, "小尺寸球体检测失败")
        print("✅ 小尺寸球体检测通过")

if __name__ == '__main__':
    unittest.main()