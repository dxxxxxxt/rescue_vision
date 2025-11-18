import cv2
import numpy as np

# 定义一个空函数，用于创建轨迹栏
def nothing(x):
    pass

# 读取一张来自比赛现场的照片，或者使用视频流
# frame = cv2.imread('competition_field.jpg')
cap = cv2.VideoCapture('your_video_from_competition_site.mp4')

# 创建一个窗口和轨迹栏（滑动条）用于调整阈值
cv2.namedWindow('Threshold Adjustment')
# 创建滑块，参数分别是：滑块名，窗口名，最小值，最大值，空函数
cv2.createTrackbar('H Min', 'Threshold Adjustment', 0, 179, nothing) # H: 0-179
cv2.createTrackbar('S Min', 'Threshold Adjustment', 0, 255, nothing) # S: 0-255
cv2.createTrackbar('V Min', 'Threshold Adjustment', 0, 255, nothing) # V: 0-255
cv2.createTrackbar('H Max', 'Threshold Adjustment', 179, 179, nothing)
cv2.createTrackbar('S Max', 'Threshold Adjustment', 255, 255, nothing)
cv2.createTrackbar('V Max', 'Threshold Adjustment', 255, 255, nothing)

while True:
    # 如果是图片，用这行：
    # frame_to_use = frame.copy()
    # 如果是视频，用这两行：
    ret, frame_to_use = cap.read()
    if not ret:
        break

    # 转换为HSV颜色空间，比RGB更易区分颜色
    hsv = cv2.cvtColor(frame_to_use, cv2.COLOR_BGR2HSV)

    # 从轨迹栏获取当前阈值
    h_min = cv2.getTrackbarPos('H Min', 'Threshold Adjustment')
    s_min = cv2.getTrackbarPos('S Min', 'Threshold Adjustment')
    v_min = cv2.getTrackbarPos('V Min', 'Threshold Adjustment')
    h_max = cv2.getTrackbarPos('H Max', 'Threshold Adjustment')
    s_max = cv2.getTrackbarPos('S Max', 'Threshold Adjustment')
    v_max = cv2.getTrackbarPos('V Max', 'Threshold Adjustment')

    # 定义阈值范围
    lower_bound = np.array([h_min, s_min, v_min])
    upper_bound = np.array([h_max, s_max, v_max])

    # 根据阈值创建掩膜，在范围内的变为白色，不在的变为黑色
    mask = cv2.inRange(hsv, lower_bound, upper_bound)

    # 将原图和掩膜显示出来
    cv2.imshow('Original Frame', frame_to_use)
    cv2.imshow('Mask', mask)

    # 按'q'键退出调试
    if cv2.waitKey(1) & 0xFF == ord('q'):
        break

cap.release()
cv2.destroyAllWindows()