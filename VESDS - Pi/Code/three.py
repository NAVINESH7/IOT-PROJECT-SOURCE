#!/usr/bin/env python3
import serial
import time
import sys

# -------------------------
# Config — edit these
# -------------------------
UART_PORT = '/dev/serial0'   # try '/dev/ttyAMA0' if serial0 doesn't work
BAUD = 115200
PHONE_NUMBER = '+918122735200'   # <- <-- replace with real number (include +country code)
MESSAGE_TEXT = (
    "Hi, this is from Pi.\n"
    "My location: 11.3628, 77.8279\n"
    "https://maps.app.goo.gl/jANYPc3NRyoTDEg66"
)
# -------------------------

def open_serial(port, baud, timeout=1):
    try:
        ser = serial.Serial(port, baud, timeout=timeout)
        ser.reset_input_buffer()
        ser.reset_output_buffer()
        return ser
    except Exception as e:
        print(f"[ERROR] Cannot open serial port {port}: {e}")
        return None

def at_cmd(ser, cmd, wait=1.0, read_wait=0.2):
    """Send AT command and return raw response."""
    if ser is None:
        return None
    print(f">>> {cmd}")
    ser.write((cmd + '\r\n').encode())
    time.sleep(wait)
    # read available bytes (tries a few times)
    output = b''
    for _ in range(int(wait / read_wait) + 2):
        time.sleep(read_wait)
        try:
            chunk = ser.read_all()
            if chunk:
                output += chunk
        except Exception:
            pass
    try:
        txt = output.decode('utf-8', errors='ignore')
    except Exception:
        txt = repr(output)
    print(f"<<< {txt.strip()}")
    return txt

def send_sms(ser, phone, text):
    # set text mode
    at_cmd(ser, 'AT+CMGF=1', wait=1)
    # optional: check network registration and signal
    at_cmd(ser, 'AT+CREG?', wait=0.7)
    at_cmd(ser, 'AT+CSQ', wait=0.7)
    # start send
    resp = at_cmd(ser, f'AT+CMGS="{phone}"', wait=1.5)
    # module typically responds with a '>' prompt — check
    if resp is None:
        print("[ERROR] no response to CMGS")
        return False
    if '>' not in resp and 'OK' not in resp and 'CMGS' not in resp:
        print("[WARN] CMGS prompt not detected, still will attempt to send.")
    # send message + Ctrl-Z
    ser.write((text + chr(26)).encode())
    time.sleep(3)
    final = ser.read_all().decode('utf-8', errors='ignore')
    print("<<< final response:", final.strip())
    if 'OK' in final or '+CMGS:' in final:
        print("[OK] SMS sent or accepted by modem.")
        return True
    print("[ERROR] SMS not confirmed. Response:", final.strip())
    return False

def main():
    print("=== SMS debug script starting ===")
    ser = open_serial(UART_PORT, BAUD)
    if ser is None:
        print("Try: check port name, run as root (sudo), or try /dev/ttyAMA0")
        sys.exit(1)

    # Basic sanity AT check and retries
    tries = 3
    ok = False
    for i in range(tries):
        r = at_cmd(ser, 'AT', wait=0.5)
        if r and ('OK' in r or 'AT' in r):
            ok = True
            break
        print(f"[INFO] No OK from AT (attempt {i+1}/{tries}), retrying...")
        time.sleep(1)

    if not ok:
        print("[FATAL] Module not responding to AT. Stop and check wiring/power/SIM.")
        ser.close()
        sys.exit(1)

    # disable echo to simplify reads
    at_cmd(ser, 'ATE0', wait=0.3)

    success = send_sms(ser, PHONE_NUMBER, MESSAGE_TEXT)
    if success:
        print("[SUCCESS] SMS flow finished successfully.")
    else:
        print("[FAILED] SMS did not send. See the logs above for clues.")

    ser.close()
    print("=== Finished ===")

if __name__ == '__main__':
    main()
