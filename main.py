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


class DesktopAPI:
    """Native API methods exposed to PyWebView JavaScript frontend."""

    def __init__(self, window_holder: list):
        self._window_holder = window_holder

    def save_report_pdf(self, inspection_id: str, token: str = None) -> dict:
        """Prompt user with native Save As dialog and save the PDF report."""
        import shutil
        import os
        from pathlib import Path
        import webview
        from sqlalchemy.orm import joinedload
        from backend.database import SessionLocal
        from backend.models import Inspection
        from backend.services.report_service import ReportService

        db = SessionLocal()
        try:
            # Eagerly load all relationships to avoid lazy-loading failures
            # across threads (critical for SQLite + PyInstaller)
            inspection = (
                db.query(Inspection)
                .options(
                    joinedload(Inspection.vehicle),
                    joinedload(Inspection.inspector),
                    joinedload(Inspection.defects),
                )
                .filter(Inspection.id == inspection_id)
                .first()
            )
            if not inspection:
                return {"success": False, "error": "Inspection not found"}

            report_svc = ReportService()
            pdf_path = report_svc.generate_pdf(inspection)

            window = self._window_holder[0] if self._window_holder else None
            target_path = None

            if window:
                try:
                    dialog_type = getattr(webview, "FileDialog", None).SAVE if hasattr(webview, "FileDialog") else getattr(webview, "SAVE_DIALOG", 1)
                    res = window.create_file_dialog(
                        dialog_type,
                        save_filename=f"inspection_report_{inspection_id[:8]}.pdf",
                        file_types=("PDF Files (*.pdf)", "All Files (*.*)"),
                    )
                    if res:
                        target_path = res[0] if isinstance(res, (list, tuple)) else res
                except Exception as dialog_err:
                    print(f"[DesktopAPI] File dialog error: {dialog_err}")

            if not target_path:
                downloads_dir = Path.home() / "Downloads"
                downloads_dir.mkdir(parents=True, exist_ok=True)
                target_path = downloads_dir / f"inspection_report_{inspection_id[:8]}.pdf"

            shutil.copy2(pdf_path, target_path)

            try:
                os.startfile(target_path)
            except Exception:
                pass

            return {"success": True, "saved_path": str(target_path)}
        except Exception as e:
            print(f"[DesktopAPI] Error saving report PDF: {e}")
            import traceback
            traceback.print_exc()
            return {"success": False, "error": str(e)}
        finally:
            db.close()

    def open_external_url(self, url: str) -> dict:
        """Open a URL in default system browser."""
        import webbrowser
        try:
            webbrowser.open(url)
            return {"success": True}
        except Exception as e:
            return {"success": False, "error": str(e)}


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

        window_holder = [None]
        desktop_api = DesktopAPI(window_holder)

        window = webview.create_window(
            title="AutoScan Pro — Vehicle Inspection System",
            url=url,
            width=1400,
            height=900,
            min_size=(1024, 680),
            resizable=True,
            text_select=False,
            js_api=desktop_api,
        )
        window_holder[0] = window

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
