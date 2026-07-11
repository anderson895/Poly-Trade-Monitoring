"""One-off: cash-style ba ang Paper Balance? (BUY = bawas, SELL = balik)"""
import sys
from pathlib import Path
from tempfile import mkdtemp

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from PySide6.QtWidgets import QApplication  # noqa: E402

app = QApplication(sys.argv)

from src.execution.paper import PaperExecutor  # noqa: E402
from src.storage.db import Database  # noqa: E402
from src.ui.dashboard_page import DashboardPage  # noqa: E402

db = Database(Path(mkdtemp()) / "t.db")
dash = DashboardPage(db)


def balance() -> str:
    dash.refresh_balance()
    return dash.balance_card._value.text()


print(f"simula          : {balance()}")   # 1,000.00
ex = PaperExecutor(db)
ex.buy("BTC Up/Down [15m] test [PAPER]", "DOWN", 0.20, 200.0)
b1 = balance()
print(f"pagka-BUY ($200): {b1}")           # dapat 800.00
ok_buy = "800.00" in b1
ex.sell("BTC Up/Down [15m] test [PAPER]", 0.40)  # 1000 shares x 0.40 = 400
b2 = balance()
print(f"pagka-SELL      : {b2}")           # 1000 + 200 pnl = 1,200.00
ok_sell = "1,200.00" in b2
print(f"[{'OK' if ok_buy else 'FAIL'}] bumaba ang balance pagka-buy")
print(f"[{'OK' if ok_sell else 'FAIL'}] bumalik + PnL pagka-sell")
