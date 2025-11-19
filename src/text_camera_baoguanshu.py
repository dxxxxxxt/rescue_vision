import cv2
import numpy as np

def force_mjpg_color():
    """强制MJPG格式获取真彩色"""
    cap = cv2.VideoCapture(0)
    
    # 关键：设置MJPG格式
    fourcc = cv2.VideoWriter_fourcc(*'MJPG')
    cap.set(cv2.CAP_PROP_FOURCC, fourcc)
    
    # 设置参数
    cap.set(cv2.CAP_PROP_BRIGHTNESS, 0.49)
    cap.set(cv2.CAP_PROP_CONTRAST, 0.4)
    cap.set(cv2.CAP_PROP_SATURATION, 1.0)
    cap.set(cv2.CAP_PROP_EXPOSURE, -2.5)
    cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
    
    print("强制MJPG格式...")
    
    ret, frame = cap.read()
    if ret:
        print(f"图像形状: {frame.shape}")
        if len(frame.shape) == 3:
            channel_diff = np.mean(np.abs(frame[:,:,0] - frame[:,:,1]))
            print(f"通道差异: {channel_diff}")
            
            if channel_diff > 10:
                print("✅ MJPG格式提供真彩色！")
                return cap
            else:
                print("❌ MJPG格式仍是伪彩色")
    
    cap.release()
    return None

# 尝试强制MJPG
mjpg_camera = force_mjpg_color()