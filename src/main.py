import cv2
import time
import sys
import os
import numpy as np
from datetime import datetime
from vision_core import VisionCore
from vision_serial import VisionSerial  
from config.config import ConfigLoader
from utils.logger_utils import setup_logging, get_logger

# 初始化日志系统（全局唯一一次）
setup_logging()
logger = get_logger(__name__)

# 获取项目根目录
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

def main():
    """
    主函数，启动视觉控制程序
    """
    try:
        logger.info("启动智能救援小车视觉与控制系统...")
        
        # 初始化配置加载器
        config_loader = ConfigLoader()
        
        # 初始化视觉核心
        vision_core = VisionCore(config_loader)
        team_color = vision_core.team_color
        logger.info(f"从配置文件读取队伍颜色: {team_color}")
        # 敌方颜色自动根据队伍颜色设置
        vision_core.enemy_color = 'blue' if team_color == 'red' else 'red'
        
        # 初始化串口通信
        try:
            serial = VisionSerial(port='COM1', baudrate=115200, team_color=team_color)
            logger.info("串口通信初始化成功")
        except Exception as e:
            logger.error(f"串口初始化失败: {e}")
            logger.info("将在模拟模式下运行，不发送实际命令")
            # 创建一个模拟的串口对象
            class MockSerial:
                def send_ball_detection(self, data):
                    logger.debug(f"[模拟发送] 球检测数据: {data}")
                def send_stop_command(self):
                    logger.debug("[模拟发送] 停止命令")
                def send_grab_command(self):
                    logger.debug("[模拟发送] 抓取命令")
                def send_place_command(self):
                    logger.debug("[模拟发送] 放置命令")
                def send_rotation(self, angle):
                    logger.debug(f"[模拟发送] 旋转命令: {angle}度")
                def receive_data(self):
                    return None
                def close(self):
                    logger.debug("[模拟] 关闭串口")
            serial = MockSerial()
        
        # 定义状态常量（使用字符串常量提高可读性）
        SEARCH_BALL = "search_ball"
        APPROACH_BALL = "approach_ball"
        GRAB_BALL = "grab_ball"
        SEARCH_AREA = "search_area"
        PLACE_BALL = "place_ball"
        
        # 状态名称映射
        state_names = {
            SEARCH_BALL: '寻找球',
            APPROACH_BALL: '接近球', 
            GRAB_BALL: '抓取', 
            SEARCH_AREA: '寻找区域', 
            PLACE_BALL: '放置'
        }
        
        # 初始状态
        state = SEARCH_BALL
        claw_state = "open"
        
        # 状态计时器和辅助变量
        state_timer = time.time()
        no_ball_count = 0  # 未检测到球的连续帧数
        approach_frames = 0  # 接近状态的帧数计数
        
        logger.info(f"队伍颜色: {vision_core.team_color}")
        logger.info(f"敌方颜色: {vision_core.enemy_color}")
        logger.info("按 'q' 键退出")

        # 运行时间限制 (5分钟)
        start_time = time.time()
        max_run_time = 5 * 60  # 5分钟

        while True:
            # 检查运行时间限制
            if time.time() - start_time > max_run_time:
                logger.info("达到运行时间限制，系统将关闭")
                break
                
            # 获取帧并处理
            try:
                vision_result = vision_core.process_frame(vision_core.get_frame())
                annotated_frame = vision_result['frame']
                best_target = vision_result['best_target']
                detected_areas = vision_result.get('detected_areas', [])
            except RuntimeError as e:
                logger.error(f"获取帧失败: {e}")
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
                logger.info("[寻找球] 正在搜索目标球...")
                
                if best_target and best_target['color'] in [vision_core.team_color, 'black', 'yellow']:
                    logger.info(f"[寻找球] 发现目标: {best_target['color']}球")
                    state = APPROACH_BALL  # 转换到接近球状态
                    state_timer = time.time()
                    approach_frames = 0
                    no_ball_count = 0
                else:
                    # 未发现目标，增加计数
                    logger.info("[寻找球] 未发现目标，继续搜索...")
                    no_ball_count += 1
                    
                    # 如果连续10帧都没有检测到球，向电控发送停止指令
                    if no_ball_count >= 10:
                        try:
                            # 发送停止命令
                            serial.send_stop()
                        except Exception as e:
                            logger.error(f"发送停止命令失败: {e}")

            elif state == APPROACH_BALL:  # 接近球状态
                if best_target and best_target['color'] in [vision_core.team_color, 'black', 'yellow']:
                    # 计算目标距离（假设基于半径估算）
                    radius = best_target.get('radius', 20)
                    logger.info(f"[接近球] 接近目标中，当前半径: {radius}")
                    
                    # 将小球数据转换为VisionSerial需要的格式
                    try:
                        # 数据验证
                        if not isinstance(best_target, dict):
                            logger.error(f"无效的目标数据类型: {type(best_target)}")
                            continue
                        
                        required_keys = ['color', 'x', 'y']
                        for key in required_keys:
                            if key not in best_target:
                                logger.error(f"目标数据缺少必要字段: {key}")
                                continue
                                
                        # 确保坐标是合理的（假设图像大小在合理范围内）
                        if not (0 <= best_target['x'] <= 1920 and 0 <= best_target['y'] <= 1080):
                            logger.warning(f"目标坐标超出合理范围: x={best_target['x']}, y={best_target['y']}")
                        
                        ball_data = {
                            'color': best_target['color'],
                            'x': best_target['x'],
                            'y': best_target['y'],
                            'radius': radius
                        }
                        
                        # 发送给电控系统
                        serial.send_ball_detection(ball_data)
                    except Exception as e:
                        logger.error(f"发送球检测数据失败: {e}")
                    
                    approach_frames += 1
                    no_ball_count = 0
                    
                    # 判断是否足够接近目标
                    if radius > 30 or approach_frames >= 30:  # 半径大于30或接近超过30帧
                        state = GRAB_BALL  # 转换到抓取状态
                        state_timer = time.time()
                else:
                    # 丢失目标，返回搜索状态
                    logger.warning("[接近球] 丢失目标，返回搜索状态")
                    no_ball_count += 1
                    
                    # 如果连续3帧都没有检测到球，返回搜索状态
                    if no_ball_count >= 3:
                        state = SEARCH_BALL
                        try:
                            serial.send_stop_command()
                        except Exception as e:
                            logger.error(f"发送停止命令失败: {e}")

            elif state == GRAB_BALL:  # 抓取状态
                logger.info("[抓取] 执行抓取动作...")
                
                try:
                    # 发送抓取命令
                    serial.send_grab_command()
                    claw_state = "closed"
                    logger.info("抓取命令发送成功")
                except Exception as e:
                    logger.error(f"发送抓取命令失败: {e}")
                
                # 抓取后转换到寻找区域状态
                if time.time() - state_timer > 2:  # 等待2秒完成抓取动作
                    state = SEARCH_AREA
                    state_timer = time.time()

            elif state == SEARCH_AREA:  # 寻找放置区域状态
                logger.info("[寻找区域] 搜索放置区域...")
                
                # 区域检测逻辑
                if detected_areas:
                    logger.info("[寻找区域] 发现放置区域")
                    state = PLACE_BALL  # 转换到放置状态
                    state_timer = time.time()
                else:
                    try:
                        # 发送旋转指令搜索区域
                        serial.send_rotation(30)
                    except Exception as e:
                        logger.error(f"发送旋转命令失败: {e}")

            elif state == PLACE_BALL:  # 放置状态
                logger.info("[放置] 执行放置动作...")
                
                try:
                    # 发送放置命令
                    serial.send_place_command()
                    claw_state = "open"
                    logger.info("放置命令发送成功")
                except Exception as e:
                    logger.error(f"发送放置命令失败: {e}")
                
                # 放置后转换回搜索状态
                if time.time() - state_timer > 2:  # 等待2秒完成放置动作
                    state = SEARCH_BALL
                    state_timer = time.time()

            # 从电控接收状态信息
            try:
                received_data = serial.receive_data()
                if received_data:
                    # 验证数据类型
                    if hasattr(received_data, 'hex'):
                        logger.debug(f"收到电控数据: {received_data.hex()}")
                    else:
                        logger.debug(f"收到电控数据: {received_data}")
                    # 可以根据收到的数据调整状态机
            except Exception as e:
                logger.error(f"接收数据失败: {e}")

            # 统一延时，避免占用过多CPU
            time.sleep(0.05)

    except KeyboardInterrupt:
        logger.info("程序被用户中断")
    except Exception as e:
        logger.error(f"发生错误: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
    finally:
        serial.close()
        cv2.destroyAllWindows()
        logger.info("系统已关闭")

if __name__ == "__main__":
    main()