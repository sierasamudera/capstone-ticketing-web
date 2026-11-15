import os
import shutil
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

# Filesystem Vercel read-only: salin data ke /tmp saat cold start
TMP = "/tmp/ticketing-data"
os.makedirs(TMP, exist_ok=True)
for name in ("tickets.json", "ticketing.db"):
    dst = os.path.join(TMP, name)
    if not os.path.exists(dst):
        shutil.copy(os.path.join(ROOT, "data", name), dst)

from ticketing.web.app import create_app

app = create_app(
    data_path=os.path.join(TMP, "tickets.json"),
    db_path=os.path.join(TMP, "ticketing.db"),
)