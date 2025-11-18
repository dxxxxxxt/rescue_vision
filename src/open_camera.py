import cv2

cv2.namedWindow("Rescue Vision", cv2.WINDOW_AUTOSIZE)

cap = cv2.VideoCapture(0)
while True:
    ret, frame = cap.read()

    cv2.imshow("Rescue Vision", frame)

   

    
    if cv2.waitKey(1) & 0xFF == ord('q'):
        break

cap.release()
cv2.destroyAllWindows()