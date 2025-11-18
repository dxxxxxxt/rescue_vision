import os
import sys
from vision_core import VisionCore

# 获取项目根目录
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))

def main():
    """
    主函数
    """
    # 配置文件路径
    hsv_config_path = os.path.join(PROJECT_ROOT, 'config', 'hsv_thresholds.json')
    strategy_config_path = os.path.join(PROJECT_ROOT, 'config', 'game_strategy.json')
    
    try:
        # 初始化视觉核心
        vision_core = VisionCore(hsv_config_path, strategy_config_path)
        
        # 运行视觉系统
        print("启动智能救援小车视觉系统...")
        print("队伍颜色:", vision_core.team_color)
        print("敌方颜色:", vision_core.enemy_color)
        print("按 'q' 键退出")
        
        vision_core.run(display=True)
        
    except Exception as e:
        print(f"错误: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()