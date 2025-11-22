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
    
    print("启动智能救援小车视觉与控制系统...")
    
    # 初始化视觉核心 - 队伍颜色直接从配置文件读取，无需在此处设置
    # 如需修改队伍颜色，请修改：config/game_strategy.json 中的 "team_color" 字段
    vision_core = VisionCore(hsv_config_path, strategy_config_path)
    team_color = vision_core.team_color
    print(f"从配置文件读取队伍颜色: {team_color}")
    # 敌方颜色自动根据队伍颜色设置
    vision_core.enemy_color = 'blue' if team_color == 'red' else 'red'
    
    # 初始化串口通信 - 使用新的VisionSerial类
    # Windows系统使用COM端口，根据实际连接的端口进行修改（COM1, COM2, COM3等）
    serial = VisionSerial(port='COM1', baudrate=115200, team_color=team_color)
    
    # 机器人状态机定义
    # 0: 寻找球, 1: 接近球, 2: 抓取, 3: 寻找区域, 4: 放置
    state_names = ['寻找球', '接近球', '抓取', '寻找区域', '放置']
    state = 0
    claw_state = "open"
    
    # 状态计时器和转换条件
    state_timer = 0
    state_duration = 0  # 当前状态的持续时间
    
    # 定义状态常量
    SEARCH_BALL = 0
    APPROACH_BALL = 1
    GRAB_BALL = 2
    SEARCH_AREA = 3
    PLACE_BALL = 4
    
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
                detected_areas = vision_result.get('detected_areas', [])  # 假设有区域检测结果
            except RuntimeError as e:
                print(f"获取帧失败: {e}")
                time.sleep(0.5)
                continue

            # 显示当前状态
            cv2.putText(annotated_frame, f'状态: {state_names[state]}', (10, 30), 
                        cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 255, 0), 2)
            cv2.imshow('Rescue Vision', annotated_frame)
            if cv2.waitKey(1) & 0xFF == ord('q'):
                break

            # 状态机逻辑实现
            if state == SEARCH_BALL:  # 寻找球状态
                print("[寻找球] 正在搜索目标球...")
                if best_target and best_target['color'] in [vision_core.team_color, 'black', 'yellow']:
                    print(f"[寻找球] 发现目标: {best_target['color']}球")
                    state = APPROACH_BALL  # 转换到接近球状态
                    state_timer = time.time()
                else:
                    # 发送旋转指令搜索目标
                    print("[寻找球] 未发现目标，继续搜索...")
                    # 发送旋转命令（假设有此方法）
                    # serial.send_rotation(50)  # 以50%速度旋转

            elif state == APPROACH_BALL:  # 接近球状态
                # 计算目标距离（假设基于半径估算）
                distance = best_target.get('radius', 20) if best_target else 0
                print(f"[接近球] 接近目标中，当前距离: {distance}")
                
                if best_target and best_target['color'] in [vision_core.team_color, 'black', 'yellow']:
                    # 将小球数据转换为VisionSerial需要的格式
                    ball_data = {
                        'color': best_target['color'],
                        'x': best_target['x'],
                        'y': best_target['y'],
                        'radius': best_target.get('radius', 20)
                    }
                    
                    # 发送给电控系统
                    serial.send_ball_detection(ball_data)
                    
                    # 判断是否足够接近目标
                    if best_target.get('radius', 0) > 30:  # 假设半径大于30表示足够接近
                        state = GRAB_BALL  # 转换到抓取状态
                        state_timer = time.time()
                else:
                    # 丢失目标，返回搜索状态
                    print("[接近球] 丢失目标，返回搜索状态")
                    state = SEARCH_BALL

            elif state == GRAB_BALL:  # 抓取状态
                print("[抓取] 执行抓取动作...")
                # 发送抓取命令
                # serial.send_grab_command()
                claw_state = "closed"
                
                # 抓取后转换到寻找区域状态
                state_duration = time.time() - state_timer
                if state_duration > 2:  # 等待2秒完成抓取动作
                    state = SEARCH_AREA
                    state_timer = time.time()

            elif state == SEARCH_AREA:  # 寻找放置区域状态
                print("[寻找区域] 搜索放置区域...")
                # 假设有区域检测逻辑
                if detected_areas:
                    print("[寻找区域] 发现放置区域")
                    state = PLACE_BALL  # 转换到放置状态
                    state_timer = time.time()
                else:
                    # 发送旋转指令搜索区域
                    # serial.send_rotation(30)
                    pass

            elif state == PLACE_BALL:  # 放置状态
                print("[放置] 执行放置动作...")
                # 发送放置命令
                # serial.send_place_command()
                claw_state = "open"
                
                # 放置后转换回搜索状态
                state_duration = time.time() - state_timer
                if state_duration > 2:  # 等待2秒完成放置动作
                    state = SEARCH_BALL
                    state_timer = time.time()

            # 从电控接收状态信息
            received_data = serial.receive_data()
            if received_data:
                print(f"收到电控数据: {received_data.hex()}")
                # 可以根据收到的数据调整状态机

            time.sleep(0.05) # 控制循环频率
            
            # 从电控接收状态信息（如果需要）
            # 注意：接收逻辑已集成到状态机内部

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