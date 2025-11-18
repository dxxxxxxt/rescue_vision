import cv2
import sys
import os

# 添加项目根目录到Python路径
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from camera_manager import CameraManager


class CameraExposureTuner:
    """
    摄像头曝光和参数调整工具类
    提供滑动条和键盘两种控制方式
    """
    
    def __init__(self, camera_id=0):
        """初始化摄像头调整工具"""
        # 窗口名称
        self.main_window = "Camera Exposure Tuner"
        self.ctrl_window = "Controls"
        
        # 初始化摄像头管理器
        self.camera = CameraManager(camera_id=camera_id)
        
        # 控制参数
        self.controls = {
            'exposure': {'name': 'Exposure', 'min': -10, 'max': 0, 'step': 0.5, 'default': -4.0},
            'brightness': {'name': 'Brightness', 'min': 0, 'max': 1, 'step': 0.05, 'default': 0.2},
            'contrast': {'name': 'Contrast', 'min': 0, 'max': 1, 'step': 0.05, 'default': 0.5},
            'saturation': {'name': 'Saturation', 'min': 0, 'max': 1, 'step': 0.05, 'default': 0.7},
            'gain': {'name': 'Gain', 'min': 0, 'max': 1, 'step': 0.05, 'default': 0},
            'sharpness': {'name': 'Sharpness', 'min': 0, 'max': 1, 'step': 0.05, 'default': 0.7}
        }
        
        # 创建窗口
        self._create_windows()
        
        # 创建控制滑动条
        self._create_trackbars()
        
        # 显示使用说明
        self._show_usage()
    
    def _create_windows(self):
        """创建显示窗口"""
        cv2.namedWindow(self.main_window, cv2.WINDOW_AUTOSIZE)
        cv2.namedWindow(self.ctrl_window, cv2.WINDOW_NORMAL)
        cv2.resizeWindow(self.ctrl_window, 300, 400)
    
    def _create_trackbars(self):
        """创建控制滑动条"""
        # 空回调函数
        def nothing(x):
            pass
        
        # 创建每个参数的滑动条
        for param_name, param_info in self.controls.items():
            # 计算滑动条的范围和步长（转换为整数）
            slider_min = 0
            slider_max = int((param_info['max'] - param_info['min']) / param_info['step'])
            
            # 计算默认值对应的滑动条位置
            default_pos = int((param_info['default'] - param_info['min']) / param_info['step'])
            
            # 创建滑动条
            cv2.createTrackbar(
                param_info['name'],
                self.ctrl_window,
                default_pos,
                slider_max,
                nothing
            )
    
    def _get_trackbar_values(self):
        """获取滑动条的当前值并转换为实际参数值"""
        values = {}
        
        for param_name, param_info in self.controls.items():
            # 获取滑动条位置
            pos = cv2.getTrackbarPos(param_info['name'], self.ctrl_window)
            
            # 转换为实际参数值
            actual_value = param_info['min'] + (pos * param_info['step'])
            values[param_name] = actual_value
        
        return values
    
    def _set_trackbar_values(self, values):
        """根据参数值设置滑动条位置"""
        for param_name, param_value in values.items():
            if param_name in self.controls:
                param_info = self.controls[param_name]
                # 计算滑动条位置
                pos = int((param_value - param_info['min']) / param_info['step'])
                # 设置滑动条
                cv2.setTrackbarPos(param_info['name'], self.ctrl_window, pos)
    
    def _show_usage(self):
        """显示使用说明"""
        print("=" * 60)
        print("摄像头曝光和参数调整工具")
        print("=" * 60)
        print("键盘控制:")
        print("  +/-  : 调整曝光值")
        print("  b/d  : 调整亮度")
        print("  c/v  : 调整对比度")
        print("  s/w  : 调整饱和度")
        print("  g/h  : 调整增益")
        print("  p/o  : 调整锐度")
        print("  1-4  : 快速应用预设 (1:明亮, 2:正常, 3:较暗, 4:黑暗)")
        print("  r    : 重置到默认值")
        print("  q    : 退出程序")
        print("\n滑动条控制:")
        print("  在 Controls 窗口中使用滑动条精确调整参数")
        print("=" * 60)
    
    def _draw_info(self, frame):
        """在图像上绘制参数信息"""
        # 获取当前参数值
        values = {}
        for param_name in self.controls.keys():
            values[param_name] = self.camera.get_parameter(param_name)
        
        # 绘制参数信息
        y_pos = 30
        font = cv2.FONT_HERSHEY_SIMPLEX
        font_scale = 0.6
        color = (0, 255, 0)
        thickness = 2
        
        for param_name, value in values.items():
            if value is not None:
                info_text = f"{param_name.capitalize()}: {value:.2f}"
                cv2.putText(frame, info_text, (10, y_pos), font, font_scale, color, thickness)
                y_pos += 25
        
        # 绘制键盘提示
        tips = ["Keys: +/- (exp), b/d (bright), c/v (contrast), s/w (sat)",
                "g/h (gain), p/o (sharp), 1-4 (presets), r (reset), q (quit)"]
        
        for tip in tips:
            cv2.putText(frame, tip, (10, y_pos), font, font_scale, (255, 0, 0), 1)
            y_pos += 20
    
    def _handle_keyboard(self, key):
        """处理键盘输入"""
        param_changes = {}
        
        # 参数调整键
        if key in [ord('+'), ord('=')]:
            # 增加曝光
            exp = self.camera.get_parameter('exposure')
            if exp is not None:
                param_changes['exposure'] = min(exp + 0.5, 0)
        elif key in [ord('-'), ord('_')]:
            # 减少曝光
            exp = self.camera.get_parameter('exposure')
            if exp is not None:
                param_changes['exposure'] = max(exp - 0.5, -10)
        elif key == ord('b'):
            # 增加亮度
            bright = self.camera.get_parameter('brightness')
            if bright is not None:
                param_changes['brightness'] = min(bright + 0.05, 1.0)
        elif key == ord('d'):
            # 减少亮度
            bright = self.camera.get_parameter('brightness')
            if bright is not None:
                param_changes['brightness'] = max(bright - 0.05, 0.0)
        elif key == ord('c'):
            # 增加对比度
            contrast = self.camera.get_parameter('contrast')
            if contrast is not None:
                param_changes['contrast'] = min(contrast + 0.05, 1.0)
        elif key == ord('v'):
            # 减少对比度
            contrast = self.camera.get_parameter('contrast')
            if contrast is not None:
                param_changes['contrast'] = max(contrast - 0.05, 0.0)
        elif key == ord('s'):
            # 增加饱和度
            sat = self.camera.get_parameter('saturation')
            if sat is not None:
                param_changes['saturation'] = min(sat + 0.05, 1.0)
        elif key == ord('w'):
            # 减少饱和度
            sat = self.camera.get_parameter('saturation')
            if sat is not None:
                param_changes['saturation'] = max(sat - 0.05, 0.0)
        elif key == ord('g'):
            # 增加增益
            gain = self.camera.get_parameter('gain')
            if gain is not None:
                param_changes['gain'] = min(gain + 0.05, 1.0)
        elif key == ord('h'):
            # 减少增益
            gain = self.camera.get_parameter('gain')
            if gain is not None:
                param_changes['gain'] = max(gain - 0.05, 0.0)
        elif key == ord('p'):
            # 增加锐度
            sharp = self.camera.get_parameter('sharpness')
            if sharp is not None:
                param_changes['sharpness'] = min(sharp + 0.05, 1.0)
        elif key == ord('o'):
            # 减少锐度
            sharp = self.camera.get_parameter('sharpness')
            if sharp is not None:
                param_changes['sharpness'] = max(sharp - 0.05, 0.0)
        # 预设键
        elif key == ord('1'):
            self.camera.adjust_for_environment('bright')
        elif key == ord('2'):
            self.camera.adjust_for_environment('normal')
        elif key == ord('3'):
            self.camera.adjust_for_environment('dim')
        elif key == ord('4'):
            self.camera.adjust_for_environment('dark')
        # 重置键
        elif key == ord('r'):
            # 重置到默认值
            for param_name, param_info in self.controls.items():
                self.camera.set_parameter(param_name, param_info['default'])
        
        # 应用参数变化
        for param_name, value in param_changes.items():
            self.camera.set_parameter(param_name, value)
            print(f"Set {param_name}: {value:.2f}")
        
        # 更新滑动条位置
        if param_changes or key in [ord('1'), ord('2'), ord('3'), ord('4'), ord('r')]:
            current_values = {}
            for param_name in self.controls.keys():
                current_values[param_name] = self.camera.get_parameter(param_name)
            self._set_trackbar_values(current_values)
    
    def run(self):
        """运行调整工具"""
        try:
            while True:
                # 获取滑动条值并应用到摄像头
                trackbar_values = self._get_trackbar_values()
                for param_name, value in trackbar_values.items():
                    self.camera.set_parameter(param_name, value)
                
                # 读取摄像头帧
                ret, frame = self.camera.read_frame()
                if not ret:
                    print("无法读取摄像头帧")
                    break
                
                # 绘制信息
                self._draw_info(frame)
                
                # 显示图像
                cv2.imshow(self.main_window, frame)
                
                # 处理键盘输入
                key = cv2.waitKey(1) & 0xFF
                if key == ord('q'):
                    break
                elif key != 255:  # 不是无按键输入
                    self._handle_keyboard(key)
        
        except KeyboardInterrupt:
            print("程序被中断")
        
        finally:
            # 释放资源
            self.camera.release()
            cv2.destroyAllWindows()
            print("程序已退出")


if __name__ == "__main__":
    # 创建并运行摄像头调整工具
    tuner = CameraExposureTuner(camera_id=0)
    tuner.run()