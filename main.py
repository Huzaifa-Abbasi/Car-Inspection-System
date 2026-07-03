"""
AutoScan Pro — Desktop Entry Point

Starts the FastAPI server on a background thread, then opens a native
PyWebView window pointing to it.
"""

import sys
import time
import threading
import socket

import uvicorn


def _find_free_port(start: int = 8000, end: int = 8100) -> int:
    """Find the first available port in the given range."""
    for port in range(start, end):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            try:
                s.bind(("127.0.0.1", port))
                return port
            except OSError:
                continue
    raise RuntimeError(f"No free port found in range {start}-{end}")


def _start_server(host: str, port: int):
    """Run the FastAPI/Uvicorn server (blocking — run in a thread)."""
    from backend.app import create_app

    app = create_app()
    uvicorn.run(
        app,
        host=host,
        port=port,
        log_level="info",
        # Disable Uvicorn's signal handlers since we're in a thread
        # (PyWebView's main loop handles the process lifecycle)
    )


def _wait_for_server(host: str, port: int, timeout: float = 45.0):
    """Block until the server is accepting connections, or timeout."""
    start = time.time()
    while time.time() - start < timeout:
        try:
            with socket.create_connection((host, port), timeout=0.5):
                return True
        except (ConnectionRefusedError, OSError):
            time.sleep(0.1)
    return False


def main():
    host = "127.0.0.1"
    port = _find_free_port()
    url = f"http://{host}:{port}"

    print(f"[AutoScan Pro] Starting server on {url} ...")

    # Start FastAPI in a daemon thread
    server_thread = threading.Thread(
        target=_start_server,
        args=(host, port),
        daemon=True,
        name="UvicornServerThread",
    )
    server_thread.start()

    # Wait for the server to be ready
    if not _wait_for_server(host, port):
        print("[ERROR] Server failed to start. Exiting.")
        sys.exit(1)

    print(f"[AutoScan Pro] Server ready. Opening desktop window...")

    # Open the native desktop window
    try:
        import webview

        window = webview.create_window(
            title="AutoScan Pro — Vehicle Inspection System",
            url=url,
            width=1400,
            height=900,
            min_size=(1024, 680),
            resizable=True,
            text_select=False,
        )
        # start() blocks until the window is closed
        webview.start(debug=False)
    except ImportError:
        print("[WARNING] pywebview not installed. Opening in browser instead.")
        import webbrowser
        webbrowser.open(url)
        print(f"[AutoScan Pro] Running at {url} — Press Ctrl+C to stop.")
        try:
            server_thread.join()
        except KeyboardInterrupt:
            print("\n[AutoScan Pro] Shutting down.")

    print("[AutoScan Pro] Window closed. Goodbye!")


if __name__ == "__main__":
    main()
