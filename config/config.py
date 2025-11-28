import os
import sys
import json
from typing import Tuple, Dict, Any, List, Optional
from pathlib import Path

# ==================== 配置文件路径管理 ====================
# 获取配置文件根目录
CONFIG_ROOT = Path(__file__).parent

# 配置文件路径
STRATEGY_CONFIG_PATH = CONFIG_ROOT / "game_strategy.json"
HSV_THRESHOLDS_PATH = CONFIG_ROOT / "hsv_thresholds.json"

# 输出目录
VIDEO_OUTPUT_DIR = Path("./videos")
os.makedirs(VIDEO_OUTPUT_DIR, exist_ok=True)

# ==================== 核心硬件配置 ====================
# 队伍颜色配置 (默认值，会被strategy_config中的值覆盖)
DEFAULT_TEAM: str = ["blue", "red"][1]  # 1: red, 0: blue

# 区域坐标（像素）
CATCH_AREA: Tuple[int, int, int, int] = (150, 400, 500, 470)     # 夹取区域
READY_AREA: Tuple[int, int, int, int] = (100, 150, 550, 400)     # 准备区域
HOLDING_AREA: Tuple[int, int, int, int] = (250, 350, 400, 470)   # 持有区域

# 视觉系统配置
# 兼容串口配置，同时定义UART_PORT和SERIAL_PORT以保持兼容性
SERIAL_PORT: str = "/dev/ttyUSB0" if os.name != "nt" else "COM1"  # 串口端口（跨平台兼容）
UART_PORT: str = SERIAL_PORT  # 保持向后兼容

# ==================== 从JSON加载配置 ====================
class ConfigLoader:
    """配置加载器类，统一管理所有配置文件的加载"""
    
    def __init__(self):
        """初始化配置加载器"""
        try:
            self.strategy_config = self._load_strategy_config()
            self.hsv_thresholds = self._load_hsv_thresholds()
            self._setup_derived_configs()
    
        except Exception as e:
    
            # 确保即使出错也有基本的配置可用
            self.strategy_config = {"team_color": DEFAULT_TEAM}
            self.hsv_thresholds = {}
    
    def _load_strategy_config(self) -> Dict[str, Any]:
        """加载比赛策略配置"""
        try:
            if STRATEGY_CONFIG_PATH.exists():
                with open(STRATEGY_CONFIG_PATH, 'r', encoding='utf-8') as f:
                    config = json.load(f)
    
                    return config
            else:

                # 默认策略配置
                return {
                    "team_color": DEFAULT_TEAM,
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
        except json.JSONDecodeError as e:
            
            return {"team_color": DEFAULT_TEAM}
        except Exception as e:
            pass
        return {"team_color": DEFAULT_TEAM}
    
    def _load_hsv_thresholds(self) -> Dict[str, Any]:
        """加载HSV颜色阈值配置"""
        try:
            if HSV_THRESHOLDS_PATH.exists():
                with open(HSV_THRESHOLDS_PATH, 'r', encoding='utf-8') as f:
                    thresholds = json.load(f)
    
                    return thresholds
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
        except json.JSONDecodeError as e:
            
            return {}
        except Exception as e:

            return {}
    

    
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
    
    def get_vision_params(self) -> Dict[str, Any]:
        """获取视觉参数配置"""
        return self.strategy_config.get("vision_params", {})
    
    def get_safety_zones(self) -> List[Dict[str, Any]]:
        """获取安全区配置"""
        return self.strategy_config.get("safety_zones", [])
    
    def get_hsv_config_path(self) -> Path:
        """获取HSV阈值配置文件路径"""
        return HSV_THRESHOLDS_PATH
    
    def get_strategy_config_path(self) -> Path:
        """获取策略配置文件路径"""
        return STRATEGY_CONFIG_PATH
        
    def get_team_color(self) -> str:
        """获取当前队伍颜色"""
        team_color = self.strategy_config.get("team_color", DEFAULT_TEAM)
        # 验证队伍颜色的有效性
        if team_color not in ("blue", "red"):

            return DEFAULT_TEAM
        return team_color

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

# 暴露便捷方法
get_ball_priority = config_loader.get_ball_priority
get_vision_params = config_loader.get_vision_params
get_safety_zones = config_loader.get_safety_zones

# ==================== 初始化验证 ====================
def _validate():
    """参数安全检查"""
    try:
        team_color = config_loader.get_team_color()
        assert team_color in ("blue", "red"), f"队伍必须是 'blue' 或 'red'，当前值: {team_color}"
        
        # 验证相机配置
        camera_id = STRATEGY_CONFIG.get("vision_params", {}).get("camera_id", 0)
        assert 0 <= camera_id <= 10, f"相机ID无效，当前值: {camera_id}"
        
        width = STRATEGY_CONFIG.get('vision_params', {}).get('image_width', 640)
        height = STRATEGY_CONFIG.get('vision_params', {}).get('image_height', 480)
        safety_zones_count = len(config_loader.get_safety_zones())
        
   
    except AssertionError as e:
        pass
    except Exception as e:
        pass


_validate()