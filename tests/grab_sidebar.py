"""One-off check: sidebar toggle (collapse/expand + persistence).

Run:  .\\venv\\Scripts\\python.exe -m tests.grab_sidebar
"""
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from PySide6.QtCore import QTimer  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402

app = QApplication(sys.argv)

from src.core.engine import BotEngine  # noqa: E402
from src.storage.db import Database  # noqa: E402
from src.ui.main_window import MainWindow  # noqa: E402

db = Database()
db.set_setting("sidebar_collapsed", "0")  # simulan nang expanded
engine = BotEngine(db)
window = MainWindow(engine, db)
window.resize(1600, 900)
window.show()


def check() -> None:
    nav = window._nav
    body_before = window._stack.width()
    print(f"[{'OK' if nav.width() == 190 else 'FAIL'}] expanded: "
          f"nav width = {nav.width()}, body = {body_before}px")

    window._toggle_sidebar()  # collapse
    app.processEvents()  # hayaang mag-relayout bago sumukat
    texts_empty = all(nav.item(i).text() == "" for i in range(nav.count()))
    brand_hidden = not window._brand.isVisible()
    body_after = window._stack.width()
    print(f"[{'OK' if window._sidebar.width() == 62 else 'FAIL'}] collapsed: "
          f"sidebar = {window._sidebar.width()}px")
    print(f"[{'OK' if body_after > body_before + 100 else 'FAIL'}] "
          f"BODY STRETCHED: {body_before}px -> {body_after}px")
    print(f"[{'OK' if texts_empty else 'FAIL'}] collapsed: icons lang")
    print(f"[{'OK' if brand_hidden else 'FAIL'}] collapsed: nakatago ang "
          f"brand/labels")
    persisted = db.get_setting("sidebar_collapsed")
    print(f"[{'OK' if persisted == '1' else 'FAIL'}] naka-save ang state")
    no_hbar = not nav.horizontalScrollBar().isVisible()
    print(f"[{'OK' if no_hbar else 'FAIL'}] walang horizontal scrollbar")
    # Hintayin ang buong relayout/repaint bago kumuha ng screenshot
    QTimer.singleShot(400, snap_then_expand)


def snap_then_expand() -> None:
    nav = window._nav
    window.grab().save("data/sidebar_collapsed.png")
    window._toggle_sidebar()  # expand ulit
    app.processEvents()
    restored = (nav.width() == 190
                and nav.item(0).text() == "Dashboard"
                and window._brand.isVisible())
    print(f"[{'OK' if restored else 'FAIL'}] bumalik nang buo "
          f"(body = {window._stack.width()}px)")
    db.set_setting("sidebar_collapsed", "0")
    app.quit()


QTimer.singleShot(700, check)
app.exec()
