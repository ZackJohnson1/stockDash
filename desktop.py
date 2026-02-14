import subprocess
import time
import socket
import webview


def wait_for_port(host: str, port: int, timeout: float = 15.0) -> bool:
    start = time.time()
    while time.time() - start < timeout:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.settimeout(0.2)
            if s.connect_ex((host, port)) == 0:
                return True
        time.sleep(0.1)
    return False


def main():
    proc = subprocess.Popen(
        ["streamlit", "run", "app.py", "--server.headless", "true", "--server.port", "8501"],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )

    if not wait_for_port("127.0.0.1", 8501):
        proc.terminate()
        raise RuntimeError("Streamlit did not start in time.")

    webview.create_window("stockDash", "http://127.0.0.1:8501", width=1350, height=900)
    webview.start()
    proc.terminate()


if __name__ == "__main__":
    main()