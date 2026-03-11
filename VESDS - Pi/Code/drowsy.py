import cv2
from scipy.spatial import distance

# Initialize camera
cap = cv2.VideoCapture(0)
if not cap.isOpened():
    print("Cannot open camera. Please check your webcam connection.")
    exit()

# Load Haar cascades for face and eyes
face_cascade = cv2.CascadeClassifier(cv2.data.haarcascades + "haarcascade_frontalface_default.xml")
eye_cascade = cv2.CascadeClassifier(cv2.data.haarcascades + "haarcascade_eye.xml")

# Function to calculate Eye Aspect Ratio (EAR) from bounding box
def Detect_Eye(eye):
    (ex, ey, ew, eh) = eye
    top = (ex + ew // 2, ey)
    bottom = (ex + ew // 2, ey + eh)
    left = (ex, ey + eh // 2)
    right = (ex + ew, ey + eh // 2)

    poi_A = distance.euclidean(top, bottom)
    poi_C = distance.euclidean(left, right)

    if poi_C == 0:
        return 1.0
    aspect_ratio_Eye = poi_A / poi_C
    return aspect_ratio_Eye

while True:
    ret, frame = cap.read()
    if not ret:
        print("Failed to grab frame from camera.")
        break

    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
    faces = face_cascade.detectMultiScale(gray, 1.3, 5)

    status = "Not Drowsy"

    for (x, y, w, h) in faces:
        cv2.rectangle(frame, (x, y), (x + w, y + h), (255, 0, 0), 2)
        roi_gray = gray[y:y+h, x:x+w]
        roi_color = frame[y:y+h, x:x+w]

        eyes = eye_cascade.detectMultiScale(roi_gray)
        ear_list = []

        for (ex, ey, ew, eh) in eyes:
            cv2.rectangle(roi_color, (ex, ey), (ex + ew, ey + eh), (0, 255, 0), 2)
            eye_box = (ex, ey, ew, eh)
            ear = Detect_Eye(eye_box)
            ear_list.append(ear)

        if len(ear_list) >= 2:  
            # Both eyes detected → calculate EAR
            Eye_Rat = sum(ear_list) / len(ear_list)
            Eye_Rat = round(Eye_Rat, 2)

            if Eye_Rat < 0.25:  
                status = "Drowsiness Detected"
        else:
            # No eyes detected → treat as drowsy
            status = "Drowsiness Detected"

    # Show status on frame
    cv2.putText(frame, status, (50, 50), cv2.FONT_HERSHEY_SIMPLEX,
                1, (0, 0, 255) if status == "Drowsiness Detected" else (0, 255, 0), 2)

    # Show camera output
    cv2.imshow("Drowsiness Detection", frame)

    # Also print to terminal
    print(status)

    key = cv2.waitKey(10) & 0xFF
    if key == 27:  # ESC key to exit
        break

cap.release()
cv2.destroyAllWindows()
