from __future__ import annotations

from datetime import datetime
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QButtonGroup,
    QDialog,
    QFileDialog,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QMessageBox,
    QPushButton,
    QTabWidget,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from core.usage_tracker import PRICE_PER_MTOKEN, UsageTracker


class UsageDialog(QDialog):
    def __init__(self, tracker: UsageTracker, parent=None) -> None:
        super().__init__(parent)
        self._tracker = tracker
        self._show_rmb = False
        self.setWindowTitle("用量与费用")
        self.resize(760, 520)
        self._build_ui()
        self._refresh()

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(16, 14, 16, 14)
        root.setSpacing(10)

        # Summary + mode toggle
        top_row = QHBoxLayout()
        self._summary = QLabel()
        self._summary.setStyleSheet("color:#eef7ff; font-size:13px;")
        top_row.addWidget(self._summary, 1)

        self._btn_token = QPushButton("Token")
        self._btn_rmb = QPushButton("人民币")
        for btn in (self._btn_token, self._btn_rmb):
            btn.setCheckable(True)
            btn.setFixedHeight(24)
            btn.setStyleSheet(
                "QPushButton{padding:0 10px;border:1px solid #4a6fa5;border-radius:3px;font-size:12px;}"
                "QPushButton:checked{background:#4a6fa5;color:#fff;}"
                "QPushButton:!checked{background:transparent;color:#aac;}"
            )
        self._btn_token.setChecked(True)
        grp = QButtonGroup(self)
        grp.setExclusive(True)
        grp.addButton(self._btn_token)
        grp.addButton(self._btn_rmb)
        self._btn_token.toggled.connect(lambda checked: self._on_mode_toggle(checked))

        toggle_row = QHBoxLayout()
        toggle_row.setSpacing(0)
        toggle_row.addWidget(self._btn_token)
        toggle_row.addWidget(self._btn_rmb)
        top_row.addLayout(toggle_row)
        root.addLayout(top_row)

        tabs = QTabWidget()
        tabs.addTab(self._build_events_tab(), "明细")
        tabs.addTab(self._build_daily_tab(), "按天")
        tabs.addTab(self._build_monthly_tab(), "按月")
        root.addWidget(tabs, 1)

        btn_row = QHBoxLayout()
        btn_row.addStretch()
        export_btn = QPushButton("导出 CSV")
        export_btn.clicked.connect(self._on_export)
        btn_row.addWidget(export_btn)
        close_btn = QPushButton("关闭")
        close_btn.clicked.connect(self.accept)
        btn_row.addWidget(close_btn)
        root.addLayout(btn_row)

    def _on_mode_toggle(self, token_checked: bool) -> None:
        self._show_rmb = not token_checked
        self._refresh()

    def _build_events_tab(self) -> QWidget:
        w = QWidget()
        lay = QVBoxLayout(w)
        lay.setContentsMargins(0, 6, 0, 0)
        self._events_tbl = QTableWidget(0, 7)
        self._events_tbl.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self._events_tbl.verticalHeader().setVisible(False)
        self._events_tbl.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        lay.addWidget(self._events_tbl)
        return w

    def _build_daily_tab(self) -> QWidget:
        w = QWidget()
        lay = QVBoxLayout(w)
        lay.setContentsMargins(0, 6, 0, 0)
        self._daily_tbl = QTableWidget(0, 3)
        self._daily_tbl.setHorizontalHeaderLabels(["日期", "事件数", "费用(元)"])
        self._daily_tbl.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self._daily_tbl.verticalHeader().setVisible(False)
        self._daily_tbl.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        lay.addWidget(self._daily_tbl)
        return w

    def _build_monthly_tab(self) -> QWidget:
        w = QWidget()
        lay = QVBoxLayout(w)
        lay.setContentsMargins(0, 6, 0, 0)
        self._monthly_tbl = QTableWidget(0, 3)
        self._monthly_tbl.setHorizontalHeaderLabels(["月份", "事件数", "费用(元)"])
        self._monthly_tbl.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self._monthly_tbl.verticalHeader().setVisible(False)
        self._monthly_tbl.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        lay.addWidget(self._monthly_tbl)
        return w

    def _refresh(self) -> None:
        st = self._tracker.state
        self._summary.setText(
            f"本次会话: ¥{st.session_cost:.4f} ({st.session_events} 条)   "
            f"累计: ¥{st.total_cost:.2f} ({st.total_events} 条)"
        )

        # Events (latest 500)
        if self._show_rmb:
            self._events_tbl.setHorizontalHeaderLabels(
                ["时间", "来源", "时长(ms)", "音频输入(元)", "文本输出(元)", "音频输出(元)", "合计(元)"]
            )
        else:
            self._events_tbl.setHorizontalHeaderLabels(
                ["时间", "来源", "时长(ms)", "input_audio", "output_text", "output_audio", "合计(元)"]
            )

        evs = st.events[-500:][::-1]
        self._events_tbl.setRowCount(len(evs))
        for r, e in enumerate(evs):
            self._events_tbl.setItem(r, 0, QTableWidgetItem(e.ts))
            self._events_tbl.setItem(r, 1, QTableWidgetItem(e.source))
            self._events_tbl.setItem(r, 2, QTableWidgetItem(str(e.duration_ms)))
            if self._show_rmb:
                ia = e.tokens.get("input_audio_tokens", 0.0) * PRICE_PER_MTOKEN.get("input_audio_tokens", 0.0) / 1_000_000.0
                ot = e.tokens.get("output_text_tokens", 0.0) * PRICE_PER_MTOKEN.get("output_text_tokens", 0.0) / 1_000_000.0
                oa = e.tokens.get("output_audio_tokens", 0.0) * PRICE_PER_MTOKEN.get("output_audio_tokens", 0.0) / 1_000_000.0
                self._events_tbl.setItem(r, 3, QTableWidgetItem(f"{ia:.6f}"))
                self._events_tbl.setItem(r, 4, QTableWidgetItem(f"{ot:.6f}"))
                self._events_tbl.setItem(r, 5, QTableWidgetItem(f"{oa:.6f}"))
            else:
                self._events_tbl.setItem(r, 3, QTableWidgetItem(str(int(e.tokens.get("input_audio_tokens", 0)))))
                self._events_tbl.setItem(r, 4, QTableWidgetItem(str(int(e.tokens.get("output_text_tokens", 0)))))
                self._events_tbl.setItem(r, 5, QTableWidgetItem(str(int(e.tokens.get("output_audio_tokens", 0)))))
            self._events_tbl.setItem(r, 6, QTableWidgetItem(f"{e.cost:.6f}"))

        # Daily
        daily = sorted(st.daily.items(), reverse=True)
        self._daily_tbl.setRowCount(len(daily))
        for r, (day, info) in enumerate(daily):
            self._daily_tbl.setItem(r, 0, QTableWidgetItem(day))
            self._daily_tbl.setItem(r, 1, QTableWidgetItem(str(int(info.get("events", 0)))))
            self._daily_tbl.setItem(r, 2, QTableWidgetItem(f"{float(info.get('cost', 0.0)):.4f}"))

        # Monthly aggregate from daily
        monthly: dict[str, tuple[int, float]] = {}
        for day, info in st.daily.items():
            month = day[:7]
            n, c = monthly.get(month, (0, 0.0))
            monthly[month] = (n + int(info.get("events", 0)), c + float(info.get("cost", 0.0)))
        rows = sorted(monthly.items(), reverse=True)
        self._monthly_tbl.setRowCount(len(rows))
        for r, (month, (n, c)) in enumerate(rows):
            self._monthly_tbl.setItem(r, 0, QTableWidgetItem(month))
            self._monthly_tbl.setItem(r, 1, QTableWidgetItem(str(n)))
            self._monthly_tbl.setItem(r, 2, QTableWidgetItem(f"{c:.4f}"))

    def _on_export(self) -> None:
        default = f"sayhey_usage_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
        path, _ = QFileDialog.getSaveFileName(self, "导出 CSV", default, "CSV (*.csv)")
        if not path:
            return
        n = self._tracker.export_csv(Path(path))
        QMessageBox.information(self, "导出完成", f"已导出 {n} 条记录到\n{path}")
