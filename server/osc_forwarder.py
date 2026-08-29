from pythonosc import udp_client

# VSeeFace VMC Protocol Receivers
VS_VOICE_IP = '127.0.0.1'
VS_PORTS = [39539, 39540]

_osc_clients = []

def get_osc_clients():
    global _osc_clients
    if not _osc_clients:
        _osc_clients = [udp_client.SimpleUDPClient(VS_VOICE_IP, port) for port in VS_PORTS]
    return _osc_clients

def send_osc_blendshapes(blendshape_messages):
    """Forward OSC blendshape messages to VSeeFace via UDP.
    
    Args:
        blendshape_messages: list of (address, args) tuples
        e.g. [('/VMC/Ext/Blend/Val', ['Joy', 0.5]), ('/VMC/Ext/Blend/Apply', [])]
    """
    clients = get_osc_clients()
    for address, args in blendshape_messages:
        # Ensure that numeric blendshape values are explicitly passed as floats
        processed_args = []
        for arg in args:
            if isinstance(arg, (int, float)) and not isinstance(arg, bool):
                processed_args.append(float(arg))
            else:
                processed_args.append(arg)
        
        for client in clients:
            client.send_message(address, processed_args)


