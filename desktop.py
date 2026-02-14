import subprocess
import time
import webview
import socket

def wait_for_port(host: str, port: int, timeout: float = 10.0) -> bool:
    start = time.time()
    while time.time() - start < timeout:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.settimeout(0.2)
            if s.connect_ex((host, port)) == 0:
                return True
        time.sleep(0.1)
    return False

def main():
    # Start Streamlit as a background process
    proc = subprocess.Popen(
        ["streamlit", "run", "app.py", "--server.headless", "true", "--server.port", "8501"],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )

    if not wait_for_port("127.0.0.1", 8501, timeout=15.0):
        proc.terminate()
        raise RuntimeError("Streamlit did not start in time.")

    # Create a native window that hosts the local Streamlit app
    webview.create_window("stockDash", "http://127.0.0.1:8501", width=1200, height=800)
    webview.start()

    # When the window closes, stop Streamlit
    proc.terminate()

if __name__ == "__main__":
    main()