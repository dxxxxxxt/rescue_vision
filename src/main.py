import time
import threading
from utils.logger_utils import get_logger

# 状态常量定义
STATE_FINDING_BALL = 0       # 寻找小球
STATE_APPROACHING_BALL = 1   # 接近小球
STATE_GRABBING = 2           # 抓取小球
STATE_FINDING_ZONE = 3       # 寻找目标区域
STATE_PLACING = 4            # 放置小球

class RescueVision:
    def __init__(self):
        self.logger = get_logger(__name__)
        self.current_state = STATE_FINDING_BALL  # 初始状态
        self.last_state_change_time = time.time()
        self.ball_detected = False
        self.target_zone_found = False
        self.ball_grabbed = False
        self.run_time_limit = 180  # 默认运行时间限制（秒）
        self.start_time = time.time()
        self.serial_port = None
    
    def initialize_serial(self, port, baudrate=115200):
        # 初始化串口通信
        self.logger.info(f"初始化串口: {port}, 波特率: {baudrate}")
        # 实际应用中这里应该初始化真实的串口
        # 简化示例中省略具体实现
        self.serial_port = MockSerial(port, baudrate)
        return True
    
    def detect_ball(self):
        # 检测小球（实际应用中应该调用vision_core中的方法）
        # 简化示例中模拟检测结果
        time.sleep(0.5)  # 模拟处理时间
        self.ball_detected = True
        return self.ball_detected
    
    def approach_ball(self):
        # 接近小球（实际应用中应该控制机器人移动）
        self.logger.info("接近小球中...")
        time.sleep(1.0)  # 模拟移动时间
        return True
    
    def grab_ball(self):
        # 抓取小球
        self.logger.info("抓取小球中...")
        time.sleep(0.8)  # 模拟抓取动作
        self.ball_grabbed = True
        return True
    
    def find_target_zone(self):
        # 寻找目标区域
        self.logger.info("寻找目标区域...")
        time.sleep(1.0)  # 模拟寻找时间
        self.target_zone_found = True
        return True
    
    def place_ball(self):
        # 放置小球
        self.logger.info("放置小球中...")
        time.sleep(0.8)  # 模拟放置动作
        self.ball_grabbed = False
        self.target_zone_found = False
        return True
    
    def run_state_machine(self):
        # 运行状态机
        try:
            while self._should_continue_running():
                current_time = time.time()
                state_changed = False
                
                # 状态机逻辑
                if self.current_state == STATE_FINDING_BALL:
                    if self.detect_ball():
                        self.current_state = STATE_APPROACHING_BALL
                        state_changed = True
                
                elif self.current_state == STATE_APPROACHING_BALL:
                    if self.approach_ball():
                        self.current_state = STATE_GRABBING
                        state_changed = True
                
                elif self.current_state == STATE_GRABBING:
                    if self.grab_ball():
                        self.current_state = STATE_FINDING_ZONE
                        state_changed = True
                
                elif self.current_state == STATE_FINDING_ZONE:
                    if self.find_target_zone():
                        self.current_state = STATE_PLACING
                        state_changed = True
                
                elif self.current_state == STATE_PLACING:
                    if self.place_ball():
                        self.current_state = STATE_FINDING_BALL
                        state_changed = True
                
                # 记录状态变化
                if state_changed:
                    self.last_state_change_time = current_time
                    state_name = self._get_state_name(self.current_state)
                    self.logger.info(f"状态切换至: {state_name}")
                
                # 控制循环频率
                time.sleep(0.1)
                
        except KeyboardInterrupt:
            self.logger.info("程序被用户中断")
        except Exception as e:
            self.logger.error(f"状态机运行出错: {e}")
        finally:
            self._cleanup()
    
    def _should_continue_running(self):
        # 检查是否应该继续运行
        # 1. 检查运行时间限制
        if time.time() - self.start_time > self.run_time_limit:
            self.logger.info("达到运行时间限制，程序退出")
            return False
        return True
    
    def _get_state_name(self, state):
        # 获取状态名称
        state_names = {
            STATE_FINDING_BALL: "寻找小球",
            STATE_APPROACHING_BALL: "接近小球",
            STATE_GRABBING: "抓取小球",
            STATE_FINDING_ZONE: "寻找目标区域",
            STATE_PLACING: "放置小球"
        }
        return state_names.get(state, f"未知状态({state})")
    
    def _cleanup(self):
        # 清理资源
        self.logger.info("清理资源...")
        if self.serial_port:
            self.serial_port.close()

# 简化的MockSerial类，用于测试
class MockSerial:
    def __init__(self, port, baudrate):
        self.port = port
        self.baudrate = baudrate
        self.is_open = True
        self.logger = get_logger(__name__)
        self.logger.info(f"MockSerial初始化: {port}, {baudrate}")
    
    def close(self):
        self.is_open = False
        self.logger.info(f"MockSerial关闭: {self.port}")

# 主函数
def main():
    logger = get_logger(__name__)
    logger.info("=== 智能救援视觉系统启动 ===")
    
    try:
        # 创建视觉系统实例
        vision_system = RescueVision()
        
        # 初始化串口（实际应用中应根据配置文件设置）
        vision_system.initialize_serial("COM1", 115200)
        
        # 启动状态机
        vision_system.run_state_machine()
        
    except Exception as e:
        logger.error(f"系统异常: {e}")
    finally:
        logger.info("=== 智能救援视觉系统关闭 ===")

if __name__ == "__main__":
    main()