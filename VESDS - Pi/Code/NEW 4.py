import smbus
import time
import cv2
import RPi.GPIO as GPIO
from RPLCD.i2c import CharLCD
from scipy.spatial import distance
from threading import Thread, Event

# LCD Setup
try:
    lcd = CharLCD('PCF8574', 0x27, cols=16, rows=2)
    lcd.clear()
    lcd.write_string('Initializing...')
    time.sleep(2)
except Exception as e:
    print("LCD initialization failed:", e)
    lcd = None  # Continue without LCD if it fails

# MPU6050 Accelerometer Setup
bus = smbus.SMBus(1)
MPU6050_ADDR = 0x68
PWR_MGMT_1 = 0x6B
ACCEL_XOUT_H = 0x3B
bus.write_byte_data(MPU6050_ADDR, PWR_MGMT_1, 0)  # Wake up sensor

def read_word_2c(addr):
    high = bus.read_byte_data(MPU6050_ADDR, addr)
    low = bus.read_byte_data(MPU6050_ADDR, addr + 1)
    val = (high << 8) + low
    return val if val < 0x8000 else val - 65536

def get_accel_data():
    x = read_word_2c(ACCEL_XOUT_H) / 16384.0
    y = read_word_2c(ACCEL_XOUT_H + 2) / 16384.0
    z = read_word_2c(ACCEL_XOUT_H + 4) / 16384.0
    return x, y, z

# Relay Setup
relay_pin = 17
GPIO.setmode(GPIO.BCM)
GPIO.setup(relay_pin, GPIO.OUT, initial=GPIO.HIGH)  # Relay OFF (active-low)

def trigger_relay(duration=10):
    GPIO.output(relay_pin, GPIO.LOW)  # Relay ON
    time.sleep(duration)
    GPIO.output(relay_pin, GPIO.HIGH)  # Relay OFF

# Alcohol Sensor Setup
alcohol_pin = 27
GPIO.setup(alcohol_pin, GPIO.IN, pull_up_down=GPIO.PUD_DOWN)

# Webcam + Drowsiness Detection Setup
cap = cv2.VideoCapture(0)
face_cascade = cv2.CascadeClassifier('haarcascade_frontalface_default.xml')
eye_cascade = cv2.CascadeClassifier('haarcascade_eye.xml')

def detect_eye(eye):
    ex, ey, ew, eh = eye
    top = (ex + ew // 2, ey)
    bottom = (ex + ew // 2, ey + eh)
    left = (ex, ey + eh // 2)
    right = (ex + ew, ey + eh // 2)
    poi_A = distance.euclidean(top, bottom)  # Height
    poi_C = distance.euclidean(left, right)  # Width
    return poi_A / poi_C if poi_C != 0 else 1.0

# Main Parameters
ACCIDENT_THRESHOLD = 1.5  # in g
RELAY_DURATION = 10  # seconds
EAR_THRESHOLD = 0.25  # Eye Aspect Ratio threshold for drowsiness
relay_event = Event()  # To prevent multiple relay triggers

# Main Loop
try:
    while True:
        # Accident Detection
        accel_x, accel_y, accel_z = get_accel_data()
        accel_magnitude = (accel_x**2 + accel_y**2 + accel_z**2)**0.5
        accident_detected = accel_magnitude > ACCIDENT_THRESHOLD

        # Alcohol Detection
        alcohol_detected = GPIO.input(alcohol_pin) == GPIO.HIGH

        # Drowsiness Detection
        drowsy = False
        ret, frame = cap.read()
        if ret:
            gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
            faces = face_cascade.detectMultiScale(gray, 1.3, 5)
            for (fx, fy, fw, fh) in faces:
                roi_gray = gray[fy:fy+fh, fx:fx+fw]
                eyes = eye_cascade.detectMultiScale(roi_gray)
                ear_values = []
                for eye in eyes:
                    ear = detect_eye(eye)
                    ear_values.append(ear)
                if ear_values and min(ear_values) < EAR_THRESHOLD:
                    drowsy = True
                    break
            # Display status on frame
            status_text = "ALL GOOD" if not (accident_detected or alcohol_detected or drowsy) else "ALERT!"
            cv2.putText(frame, status_text, (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 0, 255) if "ALERT" in status_text else (0, 255, 0), 2)
            cv2.imshow('Driver Monitoring', frame)
            if cv2.waitKey(1) & 0xFF == ord('q'):
                break

        # Set Status
        if accident_detected:
            status = "ACCIDENT "
        elif alcohol_detected:
            status = "ALCOHOL "
        elif drowsy:
            status = "DROWSY "
        else:
            status = "ALL GOOD "

        # Actions
        print(status.strip())
        if lcd:
            lcd.clear()
            lcd.write_string(status)
        
        if status != "ALL GOOD " and not relay_event.is_set():
            relay_event.set()
            Thread(target=trigger_relay, args=(RELAY_DURATION,)).start()
            # Reset event after duration to allow future triggers
            Thread(target=lambda: (time.sleep(RELAY_DURATION), relay_event.clear())).start()

        time.sleep(0.1)  # Loop delay to avoid high CPU usage

finally:
    # Cleanup
    GPIO.output(relay_pin, GPIO.HIGH)  # Ensure relay OFF
    GPIO.cleanup()
    cap.release()
    cv2.destroyAllWindows()
    if lcd:
        lcd.clear()