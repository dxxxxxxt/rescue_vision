import os
import sys
import json
from typing import Tuple, Dict, Any, List, Optional
from pathlib import Path
# 使用相对路径导入logger_utils
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from src.utils.logger_utils import get_logger

# 获取日志记录器
logger = get_logger(__name__)

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
            self.exposure_presets = self._load_exposure_presets()
            self._setup_derived_configs()
            logger.info("配置加载器初始化成功")
        except Exception as e:
            logger.error(f"配置加载器初始化失败: {e}")
            # 确保即使出错也有基本的配置可用
            self.strategy_config = {"team_color": DEFAULT_TEAM}
            self.hsv_thresholds = {}
            self.exposure_presets = {}
    
    def _load_strategy_config(self) -> Dict[str, Any]:
        """加载比赛策略配置"""
        try:
            if STRATEGY_CONFIG_PATH.exists():
                with open(STRATEGY_CONFIG_PATH, 'r', encoding='utf-8') as f:
                    config = json.load(f)
                    logger.info(f"成功加载策略配置文件: {STRATEGY_CONFIG_PATH}")
                    return config
            else:
                logger.warning(f"策略配置文件不存在: {STRATEGY_CONFIG_PATH}，使用默认配置")
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
            logger.error(f"策略配置文件格式错误: {STRATEGY_CONFIG_PATH}, {e}，使用默认配置")
            return {"team_color": DEFAULT_TEAM}
        except Exception as e:
            logger.error(f"加载策略配置失败: {e}，使用最小默认配置")
            return {"team_color": DEFAULT_TEAM}
    
    def _load_hsv_thresholds(self) -> Dict[str, Any]:
        """加载HSV颜色阈值配置"""
        try:
            if HSV_THRESHOLDS_PATH.exists():
                with open(HSV_THRESHOLDS_PATH, 'r', encoding='utf-8') as f:
                    thresholds = json.load(f)
                    logger.info(f"成功加载HSV阈值配置: {HSV_THRESHOLDS_PATH}")
                    return thresholds
            else:
                logger.warning(f"HSV阈值配置文件不存在: {HSV_THRESHOLDS_PATH}，使用默认配置")
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
            logger.error(f"HSV阈值配置文件格式错误: {HSV_THRESHOLDS_PATH}, {e}，使用默认配置")
            return {}
        except Exception as e:
            logger.error(f"加载HSV阈值配置失败: {e}，使用空配置")
            return {}
    
    def _load_exposure_presets(self) -> Dict[str, Any]:
        """加载摄像头曝光预设配置"""
        try:
            if EXPOSURE_PRESETS_PATH.exists():
                with open(EXPOSURE_PRESETS_PATH, 'r', encoding='utf-8') as f:
                    presets = json.load(f)
                    logger.info(f"成功加载曝光预设配置: {EXPOSURE_PRESETS_PATH}")
                    return presets
            else:
                logger.warning(f"曝光预设配置文件不存在: {EXPOSURE_PRESETS_PATH}，使用默认配置")
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
        except json.JSONDecodeError as e:
            logger.error(f"曝光预设配置文件格式错误: {EXPOSURE_PRESETS_PATH}, {e}，使用默认配置")
            return {}
        except Exception as e:
            logger.error(f"加载曝光预设配置失败: {e}，使用空配置")
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
            logger.warning(f"无效的队伍颜色: {team_color}，使用默认值: {DEFAULT_TEAM}")
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
EXPOSURE_PRESETS = config_loader.exposure_presets

# 暴露便捷方法
get_ball_priority = config_loader.get_ball_priority
get_camera_profile = config_loader.get_camera_profile
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
        
        logger.info(f"配置验证通过！")
        logger.info(f"队伍: {team_color}")
        logger.info(f"相机ID: {camera_id}")
        logger.info(f"图像尺寸: {width}x{height}")
        logger.info(f"安全区数量: {safety_zones_count}")
    except AssertionError as e:
        logger.error(f"配置验证失败: {e}")
    except Exception as e:
        logger.error(f"验证过程出错: {e}")

_validate()