import os
import sys 
import json
import time
import ctypes
import threading
import tkinter as tk
from websocket import WebSocketApp

# Windows API constants
GWL_STYLE = -16
GWL_EXSTYLE = -20
WS_POPUP = 0x80000000
WS_VISIBLE = 0x10000000
WS_EX_LAYERED = 0x00080000
WS_EX_TRANSPARENT = 0x00000020

user32 = ctypes.windll.user32
if ctypes.sizeof(ctypes.c_void_p) == 8:
    GetWindowLong = user32.GetWindowLongPtrW
    SetWindowLong = user32.SetWindowLongPtrW
else:
    GetWindowLong = user32.GetWindowLongW
    SetWindowLong = user32.SetWindowLongW

def make_win32_borderless(hwnd):
    # Set window style to WS_POPUP (strips title bars and borders)
    SetWindowLong(hwnd, GWL_STYLE, WS_POPUP | WS_VISIBLE)
    user32.SetWindowPos(hwnd, 0, 0, 0, 0, 0, 0x0027) # SWP_NOSIZE | SWP_NOMOVE | SWP_NOZORDER | SWP_FRAMECHANGED

def make_win32_clickthrough(hwnd):
    # Set window style to layered and transparent (click-through)
    ex_style = GetWindowLong(hwnd, GWL_EXSTYLE)
    SetWindowLong(hwnd, GWL_EXSTYLE, ex_style | WS_EX_LAYERED | WS_EX_TRANSPARENT)

class SubtitleOverlay:
    def __init__(self):
        self.root = tk.Tk()

        # Set up window properties
        self.root.title("AI Vtuber Overlay Subtitles")
        self.root.attributes("-topmost", True)  # Always on top
        self.root.overrideredirect(False)       # Must be False so OBS and taskbar detect it

        # Position window: Width 1200, Height 120, centered horizontally, near bottom
        screen_width = self.root.winfo_screenwidth()
        screen_height = self.root.winfo_screenheight()
        width = 1200
        height = 120
        x = (screen_width - width) // 2
        y = int(screen_height * 0.82)
        self.root.geometry(f"{width}x{height}+{x}+{y}")

        # Setup dark gray background color
        self.bg_color = "#161616"
        self.root.config(bg=self.bg_color)

        # Standard Tkinter Label for reliable text rendering
        self.label = tk.Label(
            self.root,
            text="",
            font=("Arial", 24, "bold"),
            fg="#ffeb3b",  # Yellow text
            bg=self.bg_color,
            justify="center",
            wraplength=1100
        )
        self.label.pack(fill="both", expand=True)

        # Apply chroma key transparency (makes background color invisible)
        self.root.wm_attributes("-transparentcolor", self.bg_color)

        # Map/render the window so FindWindowW can find it
        self.root.update()

        # Resolve the top-level HWND by title
        hwnd = user32.FindWindowW(None, "AI Vtuber Overlay Subtitles")
        if hwnd:
            make_win32_borderless(hwnd)
            make_win32_clickthrough(hwnd)
            print("[Overlay] Win32 borderless and click-through styles applied to HWND:", hwnd)

        # Timer to auto-hide subtitles
        self.last_update_time = time.time()
        self.root.after(1000, self.check_fade_timeout)

    def update_canvas_text(self, text):
        """Updates the text inside the label."""
        print(f"[Overlay] Received text: '{text}'")
        self.label.config(text=text)
        self.root.update()
        self.last_update_time = time.time()

    def check_fade_timeout(self):
        """Clear subtitle if no updates are received for 5 seconds."""
        if time.time() - self.last_update_time > 5.0:
            self.update_canvas_text("")
        self.root.after(1000, self.check_fade_timeout)

    def on_ws_message(self, ws, message):
        """Trigger when FastAPI broadcasts a text response."""
        try:
            data = json.loads(message)
            if data.get("type") == "TEXT":
                val = data.get("value", "")
                self.root.after(0, lambda: self.update_canvas_text(val))
        except Exception as e:
            print(f'Error parsing message: {e}')

    def run_websocket(self):
        """Connects to the server websocket in the background."""
        def run():
            while True:
                try:
                    ws = WebSocketApp(
                        "ws://127.0.0.1:8000/ws/chat", on_message=self.on_ws_message
                    )
                    ws.run_forever()
                except Exception as e:
                    print(f"WS Disconnected: {e}. Reconnecting...")
                time.sleep(5)
        threading.Thread(target=run, daemon=True).start()

    def start(self):
        self.run_websocket()
        self.root.mainloop()

if __name__ == "__main__":
    overlay = SubtitleOverlay()
    overlay.start()