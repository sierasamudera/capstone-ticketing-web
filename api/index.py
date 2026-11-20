
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from ticketing.web.app import create_app

app = create_app(
    data_path=os.path.join(ROOT, "data", "tickets.json"),
)
