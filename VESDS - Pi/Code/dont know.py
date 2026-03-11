#!/usr/bin/env python3
# ==========================================================
# Vision Enhanced Safety Platform (MVSP – Smart Edition)
# Raspberry Pi 4 + MPU6050 + MQ3 + Ultrasonic + Camera + LCD + Buzzer + Relay + A9G (GPS + GSM)
# ==========================================================

import cv2
import smbus2 as smbus
import time
import math
import RPi.GPIO as GPIO
from scipy.spatial import distance
from RPLCD.i2c import CharLCD
import requests
import serial
import os

# ===============================
# -------- FIREBASE CONFIG -------
# ===============================
FIREBASE_URL = "https://vision-enhance-safety-platform-default-rtdb.firebaseio.com"
DATABASE_SECRET = "HaZbsYJWnOiBipSR751tHgPTwd5cY4ZB5Ctilu2G"

# ===============================
# -------- A9G GSM + GPS --------
# ===============================
UART_PORT = "/dev/serial0"
BAUD = 115200

def send_at(cmd, delay=1):
    ser.write((cmd + "\r\n").encode())
    time.sleep(delay)
    if ser.in_waiting:
        print(ser.read(ser.in_waiting).decode(errors="ignore"))

def get_gps_location():
    """Returns latitude,longitude from A9G"""
    try:
        send_at("AT+GPS=1", 1)
        send_at("AT+GPSRD=1", 1)
        ser.write(b"AT+LOCATION=2\r\n")
        time.sleep(2)
        data = ""
        if ser.in_waiting:
            data = ser.read(ser.in_waiting).decode(errors="ignore")
        if "+LOCATION:" in data:
            parts = data.split(":")[1].split(",")
            lat, lon = parts[0].strip(), parts[1].strip()
            return f"{lat},{lon}"
    except:
        pass
    return "0.0,0.0"

def send_sms(message):
    """Send SMS with alert and GPS link"""
    try:
        send_at("AT+CMGF=1")
        send_at('AT+CMGS="YOUR_PHONE_NUMBER"')  # <-- replace YOUR_PHONE_NUMBER
        ser.write(message.encode())
        ser.write(bytes([26]))  # Ctrl+Z
        time.sleep(3)
        print("[OK] SMS Sent")
    except Exception as e:
        print(f"[ERROR] SMS Send Failed: {e}")

# ===============================
# --- FIREBASE + SMS COMBINED ---
# ===============================
def upload_and_sms(data, alert_triggered=False):
    """Upload data to Firebase and send SMS when alert is triggered"""
    try:
        timestamp = time.strftime("%Y-%m-%d %H:%M:%S")
        key = time.strftime("%Y%m%d_%H%M%S")
        payload = {"timestamp": timestamp, **data}

        # -------- FIREBASE UPLOAD --------
        requests.put(f"{FIREBASE_URL}/VehicleData/logs/{key}.json?auth={DATABASE_SECRET}", json=payload)
        requests.put(f"{FIREBASE_URL}/VehicleData/last_update.json?auth={DATABASE_SECRET}", json=payload)
        print(f"[OK] Firebase Updated at {timestamp}")

        # -------- SMS ALERT (when triggered) --------
        if alert_triggered:
            gps = get_gps_location()
            sms_msg = (
                "🚨 MVSP ALERT 🚨\n"
                f"Time: {timestamp}\n"
                f"Alert: {data['alert_message']}\n"
                f"Alcohol: {data['alcohol']}\n"
                f"G-Force: {data['accident_gforce']}g\n"
                f"Distance: {data['distance_cm']} cm\n"
                f"Driver: {data['driver_status']}\n"
                f"Location: https://maps.google.com/?q={gps}"
            )
            send_sms(sms_msg)
    except Exception as e:
        print(f"[ERROR] Firebase/SMS failed: {e}")

# ===============================
# -------- GPIO & SENSORS -------
# ===============================
GPIO.setmode(GPIO.BCM)
RELAY_PIN, MQ3_PIN, BUZZER_PIN, TRIG, ECHO = 17, 27, 21, 11, 24
GPIO.setup([RELAY_PIN, BUZZER_PIN, TRIG], GPIO.OUT)
GPIO.setup([MQ3_PIN, ECHO], GPIO.IN)
GPIO.output(RELAY_PIN, GPIO.LOW)
GPIO.output(BUZZER_PIN, GPIO.HIGH)
time.sleep(2)

lcd = CharLCD('PCF8574', 0x27)
lcd.clear(); lcd.write_string("System Booting...")

# MPU6050
bus = smbus.SMBus(1)
ADDR, PWR_MGMT_1 = 0x68, 0x6B
bus.write_byte_data(ADDR, PWR_MGMT_1, 0)
def read_raw(a):
    h = bus.read_byte_data(ADDR, a)
    l = bus.read_byte_data(ADDR, a + 1)
    val = (h << 8) | l
    return val - 65536 if val > 32768 else val
def accel_g():
    x = read_raw(0x3B) / 16384.0
    y = read_raw(0x3D) / 16384.0
    z = read_raw(0x3F) / 16384.0
    return math.sqrt(x**2 + y**2 + z**2)

ACCIDENT_THRESHOLD = 1.6
baseline = accel_g()
print(f"MPU Baseline: {baseline:.2f}g")

# Ultrasonic
def distance_cm():
    GPIO.output(TRIG, True); time.sleep(0.00001); GPIO.output(TRIG, False)
    while GPIO.input(ECHO) == 0: start = time.time()
    while GPIO.input(ECHO) == 1: stop = time.time()
    dist = (stop - start) * 17150
    return 400 if dist < 2 or dist > 400 else round(dist, 2)

# Camera
haar = cv2.data.haarcascades
face_cascade = cv2.CascadeClassifier(os.path.join(haar, "haarcascade_frontalface_default.xml"))
eye_cascade = cv2.CascadeClassifier(os.path.join(haar, "haarcascade_eye.xml"))
cap = cv2.VideoCapture(0)
cap.set(3, 320); cap.set(4, 240); cap.set(5, 15)
if not cap.isOpened():
    print("Camera not found!"); exit()
lcd.clear(); lcd.write_string("Camera Ready")

def eye_ratio(eye):
    ex, ey, ew, eh = eye
    A = distance.euclidean((ex + ew//2, ey), (ex + ew//2, ey+eh))
    C = distance.euclidean((ex, ey+eh//2), (ex+ew, ey+eh//2))
    return A / C if C else 1.0

def relay_cutdown(alert):
    for i in range(10, -1, -1):
        lcd.clear()
        lcd.write_string(alert[:16])
        lcd.cursor_pos = (1, 0)
        lcd.write_string(f"Stop in {i}s")
        GPIO.output(BUZZER_PIN, GPIO.LOW)
        time.sleep(1)
    GPIO.output(RELAY_PIN, GPIO.HIGH)
    GPIO.output(BUZZER_PIN, GPIO.HIGH)
    lcd.clear(); lcd.write_string("MOTOR STOPPED")
    send_sms(f"{alert} - Vehicle stopped.")

# ===============================
# ----------- MAIN LOOP ---------
# ===============================
try:
    ser = serial.Serial(UART_PORT, BAUD, timeout=2)
    time.sleep(1)
    print("System Ready. MVSP Active.")
    lcd.clear(); lcd.write_string("MVSP Active...")

    frame_count = 0
    while True:
        alert_type = "SAFE"
        relay_trigger = False

        # MQ3 (alcohol)
        if GPIO.input(MQ3_PIN):
            alert_type = "ALCOHOL DETECTED"
            relay_trigger = True

        # Accident (G-force)
        g = accel_g()
        if g > ACCIDENT_THRESHOLD:
            alert_type = f"ACCIDENT {g:.2f}g"
            relay_trigger = True

        # Distance
        d = distance_cm()
        if d < 10:
            lcd.clear(); lcd.write_string("Too Close!")
            GPIO.output(BUZZER_PIN, GPIO.LOW)
            time.sleep(0.4); GPIO.output(BUZZER_PIN, GPIO.HIGH)

        # Camera
        for _ in range(3): cap.grab()
        ret, frame = cap.read()
        if not ret: break
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        frame_count += 1

        status = "Normal"
        if frame_count % 5 == 0:
            faces = face_cascade.detectMultiScale(gray, 1.2, 4, minSize=(40,40))
            for (x,y,w,h) in faces:
                roi = gray[y:y+h, x:x+w]
                eyes = eye_cascade.detectMultiScale(roi, 1.2, 4, minSize=(20,20))
                ear = [eye_ratio(e) for e in eyes]
                if len(ear) < 2 or (sum(ear)/len(ear)) < 0.25:
                    status = "Drowsy"
        if status == "Drowsy":
            alert_type = "DROWSY DETECTED"
            relay_trigger = True

        # Firebase + SMS
        data = {"alcohol": bool(GPIO.input(MQ3_PIN)),
                "accident_gforce": round(g, 2),
                "distance_cm": d,
                "driver_status": status,
                "alert_message": alert_type}

        upload_and_sms(data, alert_triggered=relay_trigger)

        if relay_trigger:
            relay_cutdown(alert_type)
        else:
            GPIO.output(RELAY_PIN, GPIO.LOW)
            lcd.clear(); lcd.write_string("SAFE")

        time.sleep(1)

except KeyboardInterrupt:
    print("\nStopped by user")

finally:
    GPIO.output(RELAY_PIN, GPIO.HIGH)
    GPIO.output(BUZZER_PIN, GPIO.HIGH)
    GPIO.cleanup()
    cap.release()
    cv2.destroyAllWindows()
    lcd.clear(); lcd.write_string("System Off")
    print("System safely shut down.")
