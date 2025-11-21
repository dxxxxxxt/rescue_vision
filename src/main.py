import os
import sys
import time
import cv2
from vision_core import VisionCore
from vision_serial import VisionSerial  

# 获取项目根目录
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))

def main():
    hsv_config_path = os.path.join(PROJECT_ROOT, 'config', 'hsv_thresholds.json')
    strategy_config_path = os.path.join(PROJECT_ROOT, 'config', 'game_strategy.json')
    
    # 设置队伍颜色（根据抽签结果修改这一行！）
    team_color = 'red'  # 比赛抽签后：改为 'red' 或 'blue'
    
    print("启动智能救援小车视觉与控制系统...")
    print(f"设置队伍颜色: {team_color}")
    
    # 初始化视觉核心
    vision_core = VisionCore(hsv_config_path, strategy_config_path)
    # 更新视觉核心的队伍颜色
    vision_core.team_color = team_color
    vision_core.enemy_color = 'blue' if team_color == 'red' else 'red'
    
    # 初始化串口通信 - 使用新的VisionSerial类
    # Windows系统使用COM端口，根据实际连接的端口进行修改（COM1, COM2, COM3等）
    serial = VisionSerial(port='COM1', baudrate=115200, team_color=team_color)
    
    # 机器人状态机
    state = 0 # 0: 寻找球, 1: 接近球, 2: 抓取, 3: 寻找区域, 4: 放置
    claw_state = "open"
    
    print("队伍颜色:", vision_core.team_color)
    print("敌方颜色:", vision_core.enemy_color)
    print("按 'q' 键退出")

    try:
        while True:
            # 获取帧并处理
            try:
                vision_result = vision_core.process_frame(vision_core.get_frame())
                annotated_frame = vision_result['frame']
                best_target = vision_result['best_target']
            except RuntimeError as e:
                print(f"获取帧失败: {e}")
                time.sleep(0.5)
                continue

            # 显示图像
            cv2.imshow('Rescue Vision', annotated_frame)
            if cv2.waitKey(1) & 0xFF == ord('q'):
                break

            # 新的通信方式：直接发送小球数据
            if best_target and best_target['color'] in [vision_core.team_color, 'black', 'yellow']:
                # 将小球数据转换为VisionSerial需要的格式
                ball_data = {
                    'color': best_target['color'],
                    'x': best_target['x'],
                    'y': best_target['y'],
                    'radius': best_target.get('radius', 20)  # 假设有半径信息
                }
                
                # 发送给电控系统（自动处理优先级和敌方目标过滤）
                serial.send_ball_detection(ball_data)
                
                print(f"发送目标: {best_target['color']}球 at ({best_target['x']}, {best_target['y']})")
            else:
                print("没有合适目标或都是敌方目标")
                # 可以发送停止指令
                serial.send_stop()

            # 原有的状态机逻辑可以简化或保留作为备份
            # 因为现在VisionSerial会自动处理目标选择
            
            # 从电控接收状态信息（如果需要）
            received_data = serial.receive_data()
            if received_data:
                print(f"📥 收到电控数据: {received_data.hex()}")

            time.sleep(0.05) # 控制循环频率

    except KeyboardInterrupt:
        print("程序被用户中断")
    except Exception as e:
        print(f"发生错误: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
    finally:
        serial.close()
        cv2.destroyAllWindows()
        print("系统已关闭")

if __name__ == "__main__":
    main()