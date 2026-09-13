import time
from pythonosc import udp_client

client = udp_client.SimpleUDPClient('127.0.0.1', 39539)

def test_mouth_flap():
    print("Sending mouth A=1.0 to VSeeFace on port 39539...")
    client.send_message('/VMC/Ext/Blend/Val', ['A', 1.0])
    client.send_message('/VMC/Ext/Blend/Apply', [])
    time.sleep(1.0)

    print("Sending mouth A=0.0 to VSeeFace on port 39539...")
    client.send_message('/VMC/Ext/Blend/Val', ['A', 0.0])
    client.send_message('/VMC/Ext/Blend/Apply', [])
    print("Done!")

if __name__ == "__main__":
    test_mouth_flap()
