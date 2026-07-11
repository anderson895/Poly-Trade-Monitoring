"""One-off: i-print ang scaled strategy config ng bawat timeframe."""
import sys
from pathlib import Path
from tempfile import mkdtemp

from PySide6.QtWidgets import QApplication

app = QApplication(sys.argv)

from src.core.engine import TF_TO_INTERVAL, BotEngine  # noqa: E402
from src.storage.db import Database  # noqa: E402

db = Database(Path(mkdtemp()) / "t.db")
engine = BotEngine(db)
for tf in ("daily", "4h", "1h", "15m"):
    db.set_setting("market_timeframe", tf)
    c = engine._load_config()
    print(f"{tf:>5}: entry {c.entry_start_hour*60:6.1f}-"
          f"{c.entry_end_hour*60:6.1f} min | stretch "
          f"{c.min_stretch_pct:.3f}-{c.max_stretch_pct:.3f}% | "
          f"exit {c.eod_exit_hour*60:6.1f} min | "
          f"binance interval {TF_TO_INTERVAL[tf]}")
db.set_setting("market_timeframe", "daily")
