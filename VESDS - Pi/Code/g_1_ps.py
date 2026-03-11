import serial
import time
import RPi.GPIO as GPIO

# Constants
UART_PORT = '/dev/serial0'  # UART port on Raspberry Pi
BAUD_RATE = 115200         # A9G default baud rate
PWRKEY_PIN = 18            # GPIO pin for A9G PWRKEY
PHONE_NUMBER = '+918122735200'  # Target phone number
SMS_MESSAGE = 'Hiiii...This is from pi'  # Message to send

# Setup GPIO for PWRKEY
GPIO.setmode(GPIO.BCM)
GPIO.setup(PWRKEY_PIN, GPIO.OUT)
GPIO.output(PWRKEY_PIN, GPIO.HIGH)  # Idle high

def power_on_module():
    """Power on A9G by pulsing PWRKEY low."""
    print("Powering on A9G...")
    GPIO.output(PWRKEY_PIN, GPIO.LOW)
    time.sleep(2)  # Hold for 2 seconds
    GPIO.output(PWRKEY_PIN, GPIO.HIGH)
    time.sleep(5)  # Wait for module to boot

def send_at_command(ser, command, wait_time=1, expected='OK'):
    """Send AT command and check response."""
    ser.write((command + '\r\n').encode())
    time.sleep(wait_time)
    response = ser.read_all().decode('utf-8', errors='ignore').strip()
    print(f"Command: {command} | Response: {response}")
    return response, expected in response

def init_gsm(ser):
    """Initialize GSM for SMS."""
    print("Initializing GSM...")
    # Check module
    _, success = send_at_command(ser, 'AT')
    if not success:
        raise Exception("Module not responding")
    
    # Echo off
    send_at_command(ser, 'ATE0')
    
    # Set SMS text mode
    send_at_command(ser, 'AT+CMGF=1')
    
    # Check network registration
    send_at_command(ser, 'AT+CREG=1')
    time.sleep(2)
    response, _ = send_at_command(ser, 'AT+CREG?', 1, '+CREG: 1,1')
    if '+CREG: 1,1' not in response and '+CREG: 0,5' not in response:
        raise Exception("Network registration failed")
    
    # Check signal strength
    response, _ = send_at_command(ser, 'AT+CSQ')
    print(f"Signal Strength: {response}")

def send_sms(ser, phone, message):
    """Send SMS to the specified number."""
    print(f"Sending SMS to {phone}: {message}")
    # Set recipient
    response, _ = send_at_command(ser, f'AT+CMGS="{phone}"', 1)
    if '>' not in response:
        raise Exception("Failed to initiate SMS")
    time.sleep(1)
    # Send message with Ctrl+Z
    ser.write((message + chr(26)).encode())
    time.sleep(5)
    response = ser.read_all().decode('utf-8', errors='ignore').strip()
    print(f"Response: {response}")
    if 'OK' in response:
        print("SMS sent successfully!")
    else:
        raise Exception("SMS send failed")

def main():
    try:
        # Power on the module
        power_on_module()

        # Initialize serial connection
        ser = serial.Serial(UART_PORT, BAUD_RATE, timeout=1)
        time.sleep(2)
        print(f"Connected to {UART_PORT} at {BAUD_RATE} baud.")

        # Initialize GSM
        init_gsm(ser)

        # Send SMS
        send_sms(ser, PHONE_NUMBER, SMS_MESSAGE)

    except Exception as e:
        print(f"Error: {e}")
    finally:
        # Cleanup
        if 'ser' in locals():
            ser.close()
        GPIO.cleanup()
        print("Serial port closed and GPIO cleaned up.")

if __name__ == "__main__":
    main()