"""Start the local web application and open it in the default browser."""

import webbrowser
from threading import Timer

from app import create_app


def open_browser():
    webbrowser.open_new("http://127.0.0.1:5000")


if __name__ == "__main__":
    Timer(1.25, open_browser).start()
    create_app().run(host="127.0.0.1", port=5000, debug=False, use_reloader=False)
