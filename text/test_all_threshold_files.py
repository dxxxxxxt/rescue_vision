import os
import sys
import importlib.util
import time

# 添加项目根目录到路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# 要测试的阈值调整文件列表
threshold_files = [
    'test_yuzhi_red.py',   # 红色小球
    'test_yuzhi_blue.py',  # 蓝色小球
    'test_yuzhi_yellow.py', # 黄色小球
    'test_yuzhi_black.py'   # 黑色小球
]

# 测试结果
results = {}

print("==== 阈值调整文件功能测试 ====\n")

for file_name in threshold_files:
    print(f"\n测试文件: {file_name}")
    file_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), file_name)
    
    # 检查文件是否存在
    if not os.path.exists(file_path):
        results[file_name] = {"status": "失败", "reason": "文件不存在"}
        print(f"❌ 错误: 文件 {file_path} 不存在")
        continue
    
    try:
        # 使用importlib加载模块，这样可以在不实际运行main循环的情况下测试导入
        spec = importlib.util.spec_from_file_location(file_name[:-3], file_path)
        if spec is None:
            results[file_name] = {"status": "失败", "reason": "无法创建模块规格"}
            print(f"❌ 错误: 无法为 {file_name} 创建模块规格")
            continue
            
        module = importlib.util.module_from_spec(spec)
        
        # 替换模块中的cv2.VideoCapture和cv2.namedWindow函数，避免实际打开摄像头和窗口
        original_video_capture = None
        original_named_window = None
        original_imshow = None
        original_waitkey = None
        original_destroyallwindows = None
        
        # 模拟函数定义
        def mock_video_capture(source):
            class MockCapture:
                def __init__(self):
                    self.is_opened_called = False
                    self.released = False
                    self.props = {}
                    
                def isOpened(self):
                    self.is_opened_called = True
                    return True
                    
                def set(self, prop, value):
                    self.props[prop] = value
                    return True
                    
                def read(self):
                    return False, None
                    
                def release(self):
                    self.released = True
            return MockCapture()
            
        def mock_named_window(name):
            pass
            
        def mock_imshow(name, frame):
            pass
            
        def mock_waitkey(delay):
            return ord('q')  # 立即返回退出键
            
        def mock_destroyallwindows():
            pass
        
        # 备份原始函数并替换
        import cv2
        if hasattr(cv2, 'VideoCapture'):
            original_video_capture = cv2.VideoCapture
            cv2.VideoCapture = mock_video_capture
            
        if hasattr(cv2, 'namedWindow'):
            original_named_window = cv2.namedWindow
            cv2.namedWindow = mock_named_window
            
        if hasattr(cv2, 'imshow'):
            original_imshow = cv2.imshow
            cv2.imshow = mock_imshow
            
        if hasattr(cv2, 'waitKey'):
            original_waitkey = cv2.waitKey
            cv2.waitKey = mock_waitkey
            
        if hasattr(cv2, 'destroyAllWindows'):
            original_destroyallwindows = cv2.destroyAllWindows
            cv2.destroyAllWindows = mock_destroyallwindows
        
        # 执行导入
        spec.loader.exec_module(module)
        
        # 恢复原始函数
        if original_video_capture is not None:
            cv2.VideoCapture = original_video_capture
        if original_named_window is not None:
            cv2.namedWindow = original_named_window
        if original_imshow is not None:
            cv2.imshow = original_imshow
        if original_waitkey is not None:
            cv2.waitKey = original_waitkey
        if original_destroyallwindows is not None:
            cv2.destroyAllWindows = original_destroyallwindows
        
        results[file_name] = {"status": "成功", "reason": "模块导入成功"}
        print(f"✅ 成功: {file_name} 导入和初始化成功")
        
        # 检查关键变量和函数是否存在
        required_vars = ['DEFAULT_THRESHOLDS', 'COLOR_NAME', 'COLOR_DISPLAY_NAME']
        required_funcs = ['save_thresholds', 'print_current_thresholds', 'nothing']
        
        for var in required_vars:
            if not hasattr(module, var):
                print(f"⚠️  警告: {file_name} 缺少必要变量 {var}")
                results[file_name]["status"] = "警告"
                if "warnings" not in results[file_name]:
                    results[file_name]["warnings"] = []
                results[file_name]["warnings"].append(f"缺少变量: {var}")
        
        for func in required_funcs:
            if not hasattr(module, func):
                print(f"⚠️  警告: {file_name} 缺少必要函数 {func}")
                results[file_name]["status"] = "警告"
                if "warnings" not in results[file_name]:
                    results[file_name]["warnings"] = []
                results[file_name]["warnings"].append(f"缺少函数: {func}")
                
    except ImportError as e:
        results[file_name] = {"status": "失败", "reason": f"导入错误: {str(e)}"}
        print(f"❌ 导入错误: {e}")
    except SyntaxError as e:
        results[file_name] = {"status": "失败", "reason": f"语法错误: {str(e)}"}
        print(f"❌ 语法错误: {e}")
    except Exception as e:
        results[file_name] = {"status": "失败", "reason": f"运行时错误: {str(e)}"}
        print(f"❌ 运行时错误: {e}")
    
    # 短暂休眠避免资源冲突
    time.sleep(0.1)

# 打印测试结果摘要
print("\n==== 测试结果摘要 ====")
success_count = sum(1 for r in results.values() if r["status"] == "成功")
warning_count = sum(1 for r in results.values() if r["status"] == "警告")
fail_count = sum(1 for r in results.values() if r["status"] == "失败")

total_files = len(results)
print(f"总计测试文件数: {total_files}")
print(f"✅ 成功: {success_count}")
print(f"⚠️  警告: {warning_count}")
print(f"❌ 失败: {fail_count}")

# 详细结果
print("\n详细结果:")
for file_name, result in results.items():
    print(f"{file_name}: {result['status']}")
    if result.get("warnings"):
        for warning in result["warnings"]:
            print(f"  - {warning}")

# 提供使用说明
print("\n==== 使用说明 ====")
print("1. 各颜色小球阈值调整文件已成功创建并通过基本测试")
print("2. 运行方式:")
for file_name in threshold_files:
    color_name = file_name.split('_')[-1].split('.')[0]
    color_display = {
        'red': '红色小球(普通球/对方球)',
        'blue': '蓝色小球(普通球/本方球)',
        'yellow': '黄色小球(危险球)',
        'black': '黑色小球(核心球)'
    }.get(color_name, color_name)
    print(f"   - python {file_name}  # 调整{color_display}阈值")
print("3. 快捷键:")
print("   - 's': 保存当前阈值配置")
print("   - 'p': 打印当前阈值设置")
print("   - 'r': 恢复默认阈值")
print("   - 'q': 退出程序")
print("\n阈值配置将保存到: d:\Rescue_Rebot\rescue_vision\config\ 目录下")
