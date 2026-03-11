import serial
import time
import RPi.GPIO as GPIO

# Constants
UART_PORT = '/dev/serial0'
BAUD_RATE = 115200
PWRKEY_PIN = 18
PHONE_NUMBER = '1234567890'  # Replace with target phone number
SMS_MESSAGE_PREFIX = 'Current Location: '

# Setup GPIO
GPIO.setmode(GPIO.BCM)
GPIO.setup(PWRKEY_PIN, GPIO.OUT)
GPIO.output(PWRKEY_PIN, GPIO.HIGH)

def send_at_command(ser, command, wait_time=1, expected='OK'):
    """Send AT command and check response."""
    ser.write((command + '\r\n').encode())
    time.sleep(wait_time)
    response = ser.read_all().decode('utf-8', errors='ignore')
    print(f"Command: {command} | Response: {response.strip()}")
    return response, expected in response

def power_on_module():
    """Power on A9G."""
    print("Powering on A9G...")
    GPIO.output(PWRKEY_PIN, GPIO.LOW)
    time.sleep(2)
    GPIO.output(PWRKEY_PIN, GPIO.HIGH)
    time.sleep(5)

def init_gsm_gps(ser):
    """Initialize GSM and GPS."""
    print("Initializing GSM...")
    # Check module
    _, success = send_at_command(ser, 'AT')
    if not success:
        raise Exception("Module not responding")
    
    send_at_command(ser, 'ATE0')
    send_at_command(ser, 'AT+CMGF=1')
    send_at_command(ser, 'AT+CREG=1')
    time.sleep(2)
    response, _ = send_at_command(ser, 'AT+CREG?', 1, '+CREG: 0,1')
    if '+CREG: 0,1' not in response and '+CREG: 0,5' not in response:
        raise Exception("Network registration failed")
    
    # Check signal strength
    response, _ = send_at_command(ser, 'AT+CSQ')
    print(f"Signal Strength: {response}")
    
    print("Initializing GPS...")
    # Try GPS initialization with retries
    for attempt in range(3):
        send_at_command(ser, 'AT+GPS=0')  # Reset GPS
        time.sleep(1)
        _, success = send_at_command(ser, 'AT+GPS=1', 2)
        if success:
            send_at_command(ser, 'AT+GPSMODE=1')  # GPS only
            _, start_success = send_at_command(ser, 'AT+GPSSTART', 2)
            if start_success:
                return
        print(f"GPS init attempt {attempt + 1} failed, retrying...")
        time.sleep(5)
    raise Exception("GPS initialization failed")

def get_gps_location(ser):
    """Get GPS coordinates."""
    print("Waiting for GPS fix...")
    timeout = 120  # Increased to 120s
    start_time = time.time()
    
    while time.time() - start_time < timeout:
        # Try AT+GPSRDY? first
        response, _ = send_at_command(ser, 'AT+GPSRDY?', 1)
        if '+GPSRDY: 1' in response:
            print("GPS fix acquired!")
            # Try AT+LOCATION? for coordinates
            response, _ = send_at_command(ser, 'AT+LOCATION?', 2)
            if '+LOCATION:' in response:
                parts = response.split('+LOCATION:')[1].strip().split(',')
                if len(parts) >= 2:
                    lat, lon = parts[0], parts[1]
                    return lat, lon
            # Fallback to AT+GNSSTF
            response, _ = send_at_command(ser, 'AT+GNSSTF', 2)
            if '+GNSSTF:' in response:
                parts = response.split('+GNSSTF:')[1].strip().split(',')
                if len(parts) >= 4:
                    lat, lon = parts[0], parts[2]
                    return lat, lon
        time.sleep(5)
    
    raise Exception("No GPS fix within timeout")

def send_sms(ser, phone, message):
    """Send SMS."""
    print(f"Sending SMS to {phone}: {message}")
    send_at_command(ser, f'AT+CMGS="{phone}"', 1)
    time.sleep(1)
    ser.write((message + chr(26)).encode())
    time.sleep(5)
    response = ser.read_all().decode('utf-8', errors='ignore')
    if 'OK' in response:
        print("SMS sent successfully!")
    else:
        print("SMS send failed")

# Main execution
try:
    power_on_module()
    ser = serial.Serial(UART_PORT, BAUD_RATE, timeout=1)
    time.sleep(2)
    
    init_gsm_gps(ser)
    lat, lon = get_gps_location(ser)
    location_msg = f"{SMS_MESSAGE_PREFIX} Lat: {lat}, Lon: {lon}"
    send_sms(ser, PHONE_NUMBER, location_msg)

except Exception as e:
    print(f"Error: {e}")
finally:
    send_at_command(ser, 'AT+GPSSTOP') if 'ser' in locals() else None
    send_at_command(ser, 'AT+GPS=0') if 'ser' in locals() else None
    ser.close() if 'ser' in locals() else None
    GPIO.cleanup()