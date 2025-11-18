import cv2
import json
import os

class CameraManager:
    def __init__(self, camera_id=0, load_presets=True):
        """
        初始化摄像头管理器
        :param camera_id: 摄像头ID
        :param load_presets: 是否从配置文件加载预设
        """
        self.camera_id = camera_id
        self.cap = None
        self.is_open = False
        self.presets = {
            'bright': {
                'exposure': -6, 'brightness': 0.1, 'contrast': 0.3, 'saturation': 0.5,
                'gain': 0, 'sharpness': 0.5
            },
            'normal': {
                'exposure': -4, 'brightness': 0.2, 'contrast': 0.5, 'saturation': 0.7,
                'gain': 0, 'sharpness': 0.7
            },
            'dim': {
                'exposure': -2, 'brightness': 0.3, 'contrast': 0.7, 'saturation': 0.9,
                'gain': 0, 'sharpness': 0.5
            },
            'dark': {
                'exposure': 0, 'brightness': 0.4, 'contrast': 0.8, 'saturation': 1.0,
                'gain': 1, 'sharpness': 0.3
            }
        }
        
        # 加载配置文件中的预设
        if load_presets:
            self._load_presets_from_config()
        
        # 打开摄像头
        self._open_camera()
    
    def _open_camera(self):
        """打开摄像头并初始化参数"""
        try:
            self.cap = cv2.VideoCapture(self.camera_id)
            if not self.cap.isOpened():
                raise Exception(f"无法打开摄像头 {self.camera_id}")
            
            self.is_open = True
            self.set_optimal_exposure()
            print(f"成功打开摄像头 {self.camera_id}")
        except Exception as e:
            print(f"摄像头初始化失败: {str(e)}")
            self.is_open = False
    
    def _load_presets_from_config(self):
        """从配置文件加载曝光预设"""
        config_path = os.path.join(os.path.dirname(__file__), '../config/exposure_presets.json')
        try:
            if os.path.exists(config_path):
                with open(config_path, 'r', encoding='utf-8') as f:
                    config_presets = json.load(f)
                    # 更新预设参数
                    for env_type, params in config_presets.items():
                        if env_type in self.presets:
                            self.presets[env_type].update(params)
                        else:
                            self.presets[env_type] = params
                    print("成功加载曝光预设配置")
        except Exception as e:
            print(f"加载曝光预设失败: {str(e)}")
    
    def set_optimal_exposure(self):
        """设置最佳曝光参数"""
        if not self.is_open:
            return False
            
        try:
            # 使用normal环境的预设作为默认值
            self.adjust_for_environment('normal')
            return True
        except Exception as e:
            print(f"设置最佳曝光失败: {str(e)}")
            return False
    
    def adjust_for_environment(self, environment_type):
        """
        根据环境类型调整摄像头参数
        :param environment_type: 环境类型 ('bright', 'normal', 'dim', 'dark')
        :return: 是否调整成功
        """
        if not self.is_open or environment_type not in self.presets:
            return False
        
        try:
            preset = self.presets[environment_type]
            for param_name, value in preset.items():
                # 将参数名称映射到cv2的常量
                param_constant = self._get_param_constant(param_name)
                if param_constant is not None:
                    self.cap.set(param_constant, value)
            
            print(f"成功调整到{environment_type}环境设置")
            return True
        except Exception as e:
            print(f"调整环境参数失败: {str(e)}")
            return False
    
    def _get_param_constant(self, param_name):
        """将参数名称映射到cv2的常量"""
        param_map = {
            'exposure': cv2.CAP_PROP_EXPOSURE,
            'brightness': cv2.CAP_PROP_BRIGHTNESS,
            'contrast': cv2.CAP_PROP_CONTRAST,
            'saturation': cv2.CAP_PROP_SATURATION,
            'gain': cv2.CAP_PROP_GAIN,
            'sharpness': cv2.CAP_PROP_SHARPNESS,
            'focus': cv2.CAP_PROP_FOCUS,
            'white_balance': cv2.CAP_PROP_WB_TEMPERATURE
        }
        return param_map.get(param_name.lower())
    
    def get_parameter(self, param_name):
        """
        获取摄像头参数值
        :param param_name: 参数名称
        :return: 参数值或None
        """
        if not self.is_open:
            return None
            
        param_constant = self._get_param_constant(param_name)
        if param_constant is None:
            return None
            
        try:
            return self.cap.get(param_constant)
        except Exception as e:
            print(f"获取参数{param_name}失败: {str(e)}")
            return None
    
    def set_parameter(self, param_name, value):
        """
        设置摄像头参数值
        :param param_name: 参数名称
        :param value: 参数值
        :return: 是否设置成功
        """
        if not self.is_open:
            return False
            
        param_constant = self._get_param_constant(param_name)
        if param_constant is None:
            return False
            
        try:
            result = self.cap.set(param_constant, value)
            if result:
                print(f"成功设置{param_name}为{value}")
            else:
                print(f"警告: 设置{param_name}为{value}可能未生效")
            return result
        except Exception as e:
            print(f"设置参数{param_name}失败: {str(e)}")
            return False
    
    def read_frame(self):
        """
        读取一帧图像
        :return: (ret, frame) 元组，ret为是否成功，frame为图像数据
        """
        if not self.is_open:
            return False, None
            
        try:
            ret, frame = self.cap.read()
            if not ret:
                print("读取摄像头帧失败")
            return ret, frame
        except Exception as e:
            print(f"读取帧时发生错误: {str(e)}")
            return False, None
    
    def get_status(self):
        """
        获取摄像头状态
        :return: 包含摄像头状态的字典
        """
        return {
            'is_open': self.is_open,
            'camera_id': self.camera_id,
            'available_presets': list(self.presets.keys()),
            'current_parameters': {
                'exposure': self.get_parameter('exposure'),
                'brightness': self.get_parameter('brightness'),
                'contrast': self.get_parameter('contrast'),
                'saturation': self.get_parameter('saturation'),
                'gain': self.get_parameter('gain')
            }
        }
    
    def release(self):
        """释放摄像头资源"""
        if self.cap is not None:
            self.cap.release()
            self.is_open = False
            print(f"已释放摄像头 {self.camera_id}")
    
    def __del__(self):
        """析构函数，确保资源释放"""
        self.release()