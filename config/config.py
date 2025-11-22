import os
import json
from typing import Tuple, Dict, Any, List
from pathlib import Path

# ==================== 配置文件路径管理 ====================
# 获取配置文件根目录
CONFIG_ROOT = Path(__file__).parent

# 配置文件路径
STRATEGY_CONFIG_PATH = CONFIG_ROOT / "game_strategy.json"
HSV_THRESHOLDS_PATH = CONFIG_ROOT / "hsv_thresholds.json"
EXPOSURE_PRESETS_PATH = CONFIG_ROOT / "exposure_presets.json"

# 输出目录
VIDEO_OUTPUT_DIR = Path("./videos")
os.makedirs(VIDEO_OUTPUT_DIR, exist_ok=True)

# ==================== 核心硬件配置 ====================
# 队伍颜色配置
TEAM: str = ["blue", "red"][1]  # 1: red, 0: blue
ENEMY_TEAM: str = "blue" if TEAM == "red" else "red"

# 区域坐标（像素）
CATCH_AREA: Tuple[int, int, int, int] = (150, 400, 500, 470)     # 夹取区域
READY_AREA: Tuple[int, int, int, int] = (100, 150, 550, 400)     # 准备区域
HOLDING_AREA: Tuple[int, int, int, int] = (250, 350, 400, 470)   # 持有区域

# 视觉系统配置
UART_PORT: str = "/dev/ttyUSB0" if os.name != "nt" else "COM1"  # 串口端口（跨平台兼容）

# ==================== 电控系统相关参数（由电控负责人配置）====================
# 注意：以下参数由电控系统负责，视觉系统不直接使用
# CATCH_ANGLE: Tuple[int, int] = (90, 90)       # 夹取角度
# RELEASE_ANGLE: Tuple[int, int] = (0, 0)       # 释放角度

# ==================== 从JSON加载配置 ====================
class ConfigLoader:
    """配置加载器类，统一管理所有配置文件的加载"""
    
    def __init__(self):
        self.strategy_config = self._load_strategy_config()
        self.hsv_thresholds = self._load_hsv_thresholds()
        self.exposure_presets = self._load_exposure_presets()
        self._setup_derived_configs()
    
    def _load_strategy_config(self) -> Dict[str, Any]:
        """加载比赛策略配置"""
        if STRATEGY_CONFIG_PATH.exists():
            with open(STRATEGY_CONFIG_PATH, 'r', encoding='utf-8') as f:
                return json.load(f)
        else:
            # 默认策略配置
            return {
                "team_color": "red",
                "ball_priorities": {"black": 200, "yellow": 150, "team": 100, "enemy": 0},
                "ball_counts": {"red": 4, "blue": 4, "black": 4, "yellow": 2},
                "movement_strategy": "avoid_collision",
                "auto_mode_duration": 30,
                "yellow_rules": {
                    "max_count": 2,
                    "cannot_hold_other": True
                },
                "vision_params": {
                    "camera_id": 0,
                    "image_width": 640,
                    "image_height": 480,
                    "detection_confidence": 0.8,
                    "tracking_window": 30,
                    "min_ball_radius": 10,
                    "max_ball_radius": 40
                },
                "safety_zones": [
                    {
                        "name": "blue_safety_zone",
                        "color": [255, 0, 0],
                        "enabled": True,
                        "type": "rectangle",
                        "position": {
                            "x": 0.7,
                            "y": 0.1,
                            "width": 0.3,
                            "height": 0.4
                        }
                    },
                    {
                        "name": "red_safety_zone",
                        "color": [0, 0, 255],
                        "enabled": True,
                        "type": "rectangle",
                        "position": {
                            "x": 0.7,
                            "y": 0.5,
                            "width": 0.3,
                            "height": 0.4
                        }
                    }
                ]
            }
    
    def _load_hsv_thresholds(self) -> Dict[str, Any]:
        """加载HSV颜色阈值配置"""
        if HSV_THRESHOLDS_PATH.exists():
            with open(HSV_THRESHOLDS_PATH, 'r', encoding='utf-8') as f:
                return json.load(f)
        else:
            # 默认HSV阈值
            return {
                "red": [
                    {"lower": [0, 120, 70], "upper": [10, 255, 255]},
                    {"lower": [170, 120, 70], "upper": [180, 255, 255]}
                ],
                "yellow": [
                    {"lower": [20, 100, 100], "upper": [30, 255, 255]}
                ],
                "blue": [
                    {"lower": [90, 100, 100], "upper": [130, 255, 255]}
                ],
                "black": [
                    {"lower": [0, 0, 0], "upper": [180, 255, 40]}
                ]
            }
    
    def _load_exposure_presets(self) -> Dict[str, Any]:
        """加载摄像头曝光预设配置"""
        if EXPOSURE_PRESETS_PATH.exists():
            with open(EXPOSURE_PRESETS_PATH, 'r', encoding='utf-8') as f:
                return json.load(f)
        else:
            # 默认曝光预设
            return {
                "competition": {
                    "exposure": -3,
                    "brightness": 0.25,
                    "contrast": 0.7,
                    "saturation": 0.8,
                    "gain": 0,
                    "sharpness": 0.6
                },
                "competition_bright": {
                    "exposure": -5,
                    "brightness": 0.15,
                    "contrast": 0.8,
                    "saturation": 0.7,
                    "gain": 0,
                    "sharpness": 0.7
                },
                "competition_dim": {
                    "exposure": -1,
                    "brightness": 0.35,
                    "contrast": 0.9,
                    "saturation": 0.9,
                    "gain": 1,
                    "sharpness": 0.5
                },
                "competition_dark": {
                    "exposure": 0,
                    "brightness": 0.45,
                    "contrast": 1.0,
                    "saturation": 1.0,
                    "gain": 2,
                    "sharpness": 0.4
                },
                "match_urgent": {
                    "exposure": -4,
                    "brightness": 0.2,
                    "contrast": 0.75,
                    "saturation": 0.85,
                    "gain": 0,
                    "sharpness": 0.7
                }
            }
    
    def _setup_derived_configs(self):
        """设置派生配置"""
        pass
    
    def get_ball_priority(self, ball_color: str) -> int:
        """获取球体优先级"""
        
        color = ball_color.lower()
        
        # 根据队伍颜色确定优先级
        if color == self.get_team_color():
            return self.strategy_config["ball_priorities"]["team"]
        elif color == self.get_enemy_color():
            return self.strategy_config["ball_priorities"]["enemy"]
        else:
            return self.strategy_config["ball_priorities"].get(color, 0)
    
    def get_camera_profile(self, lighting_condition: str = "competition") -> Dict[str, float]:
        """获取相机参数配置"""
        return self.exposure_presets.get(lighting_condition, self.exposure_presets["competition"])
    
    def get_vision_params(self) -> Dict[str, Any]:
        """获取视觉参数配置"""
        return self.strategy_config.get("vision_params", {})
    
    def get_safety_zones(self) -> List[Dict[str, Any]]:
        """获取安全区配置"""
        return self.strategy_config.get("safety_zones", [])
    
    def get_all_exposure_profiles(self) -> Dict[str, Any]:
        """获取所有相机曝光配置"""
        return self.exposure_presets

    def get_available_exposure_profiles(self) -> List[str]:
        """获取可用的曝光配置名称列表"""
        return list(self.exposure_presets.keys())
        
    def get_team_color(self) -> str:
        """获取当前队伍颜色"""
        return self.strategy_config.get("team_color", TEAM)

    def get_enemy_color(self) -> str:
        """获取对手队伍颜色"""
        team_color = self.get_team_color()
        return "blue" if team_color == "red" else "red"
        
    def get_yellow_ball_rules(self) -> Dict[str, Any]:
        """获取黄球规则配置"""
        return self.strategy_config.get("yellow_rules", {
            "max_count": 2,
            "cannot_hold_other": True
        })

# 初始化配置加载器
config_loader = ConfigLoader()

# 暴露全局配置访问
STRATEGY_CONFIG = config_loader.strategy_config
HSV_THRESHOLDS = config_loader.hsv_thresholds
EXPOSURE_PRESETS = config_loader.exposure_presets

# 暴露便捷方法
get_ball_priority = config_loader.get_ball_priority
get_camera_profile = config_loader.get_camera_profile
get_vision_params = config_loader.get_vision_params
get_safety_zones = config_loader.get_safety_zones

# ==================== 初始化验证 ====================
def _validate():
    """参数安全检查"""
    assert TEAM in ("blue", "red"), "队伍必须是 'blue' 或 'red'"
    
    # 验证相机配置
    assert 0 <= STRATEGY_CONFIG.get("vision_params", {}).get("camera_id", 0) <= 10, "相机ID无效"
    
    print(f"配置验证通过！")
    print(f"队伍: {TEAM}")
    print(f"相机ID: {STRATEGY_CONFIG.get('vision_params', {}).get('camera_id', 0)}")
    print(f"图像尺寸: {STRATEGY_CONFIG.get('vision_params', {}).get('image_width', 640)}x{STRATEGY_CONFIG.get('vision_params', {}).get('image_height', 480)}")
    print(f"安全区数量: {len(config_loader.get_safety_zones())}")

_validate()