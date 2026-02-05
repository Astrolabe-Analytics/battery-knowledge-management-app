"""Simple HTTP server to serve PDF files for viewing in browser."""
import http.server
import socketserver
import threading
from pathlib import Path

# Global server instance
_server = None
_server_thread = None
_server_port = 8503
_project_root = Path(__file__).parent.parent


def start_pdf_server(port=8503):
    """Start a simple HTTP server to serve PDF files."""
    global _server, _server_thread, _server_port, _project_root

    # If server is already running, return the port
    if _server is not None:
        return _server_port

    _server_port = port

    # Create custom handler that serves PDFs from project root
    class PDFHandler(http.server.SimpleHTTPRequestHandler):
        def __init__(self, *args, **kwargs):
            # Set directory to project root
            super().__init__(*args, directory=str(_project_root), **kwargs)

        def end_headers(self):
            # Add CORS headers to allow cross-origin requests
            self.send_header('Access-Control-Allow-Origin', '*')
            self.send_header('Access-Control-Allow-Methods', 'GET')
            self.send_header('Access-Control-Allow-Headers', 'Content-Type')
            # Ensure PDF is displayed inline, not downloaded
            if self.path.endswith('.pdf'):
                self.send_header('Content-Disposition', 'inline')
            super().end_headers()

        def guess_type(self, path):
            """Override to ensure PDFs are served with correct MIME type."""
            if path.endswith('.pdf'):
                return 'application/pdf'
            return super().guess_type(path)

        def log_message(self, format, *args):
            """Suppress log messages."""
            pass

    try:
        # Create the server
        _server = socketserver.TCPServer(("", port), PDFHandler)

        # Start server in a daemon thread
        _server_thread = threading.Thread(target=_server.serve_forever, daemon=True)
        _server_thread.start()

        print(f"PDF server started on port {port}")
        return port

    except OSError as e:
        if e.errno == 10048:  # Port already in use (Windows)
            # Try next port
            return start_pdf_server(port + 1)
        raise


def get_pdf_url(pdf_filename):
    """Get the URL to access a PDF file."""
    global _server_port

    # Ensure server is started
    if _server is None:
        start_pdf_server()

    return f"http://localhost:{_server_port}/papers/{pdf_filename}"


def stop_pdf_server():
    """Stop the PDF server."""
    global _server, _server_thread

    if _server is not None:
        _server.shutdown()
        _server = None
        _server_thread = None
