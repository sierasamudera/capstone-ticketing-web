"""Entry point WSGI untuk deployment (Render / Railway / Fly / Heroku).

Host PaaS umumnya menjalankan::

    gunicorn wsgi:app

dan menyediakan port lewat env ``PORT``. Entry point ini membuat instance
Flask yang sama persis dengan ``python -m ticketing.web`` lokal, sehingga
perilaku di online == lokal.
"""

from __future__ import annotations

import os

from ticketing.web import create_app

# Path dataset boleh di-override lewat env (mis. volume persistent di PaaS);
# kalau tidak di-set, memakai data/tickets.json seperti lokal.
app = create_app(os.environ.get("TICKETING_DATA_PATH"))

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))
