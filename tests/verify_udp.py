import socket

UDP_IP = "127.0.0.1"
UDP_PORT = 39539  # Target port to check

sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
try:
    sock.bind((UDP_IP, UDP_PORT))
    print(f"Listening for UDP packets on {UDP_IP}:{UDP_PORT}...")
    print("Please click the 'Smile' button in your browser now.")
    
    # Receive up to 5 packets to verify
    for i in range(5):
        data, addr = sock.recvfrom(1024)
        print(f"\n[PACKET {i+1}] Received from {addr}:")
        print(f"Raw data: {data}")
        # Try to print as string, replacing non-printable chars
        print(f"Decoded: {''.join(chr(b) if 32 <= b < 127 else '.' for b in data)}")
except Exception as e:
    print(f"Error binding/receiving: {e}")
finally:
    sock.close()
