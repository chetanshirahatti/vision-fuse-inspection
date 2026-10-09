BG, PANEL, PANEL2, BORDER = "#0f141b", "#171d27", "#1e2633", "#2a3444"
TEXT, MUTED = "#e6e9ef", "#8b96a8"
ACCENT, OK, NOK, WARN = "#3b82f6", "#22c55e", "#ef4444", "#f59e0b"

QSS = f"""
* {{ font-family: 'Segoe UI', 'Inter', sans-serif; font-size: 13px; }}
QWidget {{ background: {BG}; color: {TEXT}; }}
QLabel {{ background: transparent; }}
QLabel#h1 {{ font-size: 20px; font-weight: 600; }}
QLabel#h2 {{ font-size: 14px; font-weight: 600; color: {MUTED}; }}
QLabel#muted {{ color: {MUTED}; }}
QFrame#card, QGroupBox {{ background: {PANEL}; border: 1px solid {BORDER}; border-radius: 10px; }}
QGroupBox {{ margin-top: 14px; padding: 14px 10px 10px 10px; font-weight: 600; }}
QGroupBox::title {{ subcontrol-origin: margin; left: 12px; padding: 0 6px; color: {MUTED}; background: {BG}; }}
QFrame#sidebar {{ background: {PANEL}; border-right: 1px solid {BORDER}; }}
QPushButton#nav {{ text-align: left; padding: 12px 18px; border: none; border-radius: 8px; background: transparent; color: {MUTED}; font-size: 14px; }}
QPushButton#nav:hover {{ background: {PANEL2}; color: {TEXT}; }}
QPushButton#nav:checked {{ background: {ACCENT}; color: white; font-weight: 600; }}
QPushButton {{ background: {PANEL2}; border: 1px solid {BORDER}; border-radius: 7px; padding: 7px 14px; }}
QPushButton:hover {{ border-color: {ACCENT}; }}
QPushButton:pressed {{ background: {BORDER}; }}
QPushButton:disabled {{ color: #566073; background: {PANEL}; }}
QPushButton[kind="accent"] {{ background: {ACCENT}; border-color: {ACCENT}; color: white; font-weight: 600; }}
QPushButton[kind="accent"]:hover {{ background: #2f6fe0; }}
QPushButton[kind="danger"] {{ background: transparent; border-color: {NOK}; color: {NOK}; }}
QPushButton[kind="danger"]:hover {{ background: {NOK}; color: white; }}
QLineEdit, QComboBox, QSpinBox, QDoubleSpinBox, QPlainTextEdit {{ background: {PANEL2}; border: 1px solid {BORDER}; border-radius: 6px; padding: 5px 8px; selection-background-color: {ACCENT}; }}
QLineEdit:focus, QComboBox:focus, QSpinBox:focus, QDoubleSpinBox:focus {{ border-color: {ACCENT}; }}
QComboBox QAbstractItemView {{ background: {PANEL2}; selection-background-color: {ACCENT}; border: 1px solid {BORDER}; }}
QTableWidget {{ background: {PANEL}; alternate-background-color: {PANEL2}; gridline-color: {BORDER}; border: 1px solid {BORDER}; border-radius: 8px; selection-background-color: #25437a; }}
QHeaderView::section {{ background: {PANEL2}; color: {MUTED}; padding: 6px; border: none; border-bottom: 1px solid {BORDER}; font-weight: 600; }}
QTabWidget::pane {{ border: 1px solid {BORDER}; border-radius: 8px; top: -1px; }}
QTabBar::tab {{ background: {PANEL}; padding: 8px 18px; border: 1px solid {BORDER}; border-bottom: none; border-top-left-radius: 8px; border-top-right-radius: 8px; color: {MUTED}; }}
QTabBar::tab:selected {{ background: {PANEL2}; color: {TEXT}; }}
QSlider::groove:horizontal {{ height: 6px; background: {BORDER}; border-radius: 3px; }}
QSlider::sub-page:horizontal {{ background: {ACCENT}; border-radius: 3px; }}
QSlider::handle:horizontal {{ background: white; width: 14px; margin: -5px 0; border-radius: 7px; }}
QCheckBox {{ spacing: 8px; }}
QCheckBox::indicator, QRadioButton::indicator {{ width: 16px; height: 16px; border: 1px solid #566073; background: {PANEL2}; border-radius: 4px; }}
QRadioButton::indicator {{ border-radius: 9px; }}
QCheckBox::indicator:checked, QRadioButton::indicator:checked {{ background: {ACCENT}; border-color: {ACCENT}; }}
QScrollBar:vertical {{ background: transparent; width: 10px; }}
QScrollBar::handle:vertical {{ background: {BORDER}; border-radius: 5px; min-height: 30px; }}
QScrollBar::add-line, QScrollBar::sub-line {{ height: 0; width: 0; }}
QStatusBar {{ background: {PANEL}; border-top: 1px solid {BORDER}; color: {MUTED}; }}
QMenuBar {{ background: {PANEL}; }} QMenuBar::item:selected {{ background: {PANEL2}; }}
QMenu {{ background: {PANEL2}; border: 1px solid {BORDER}; }} QMenu::item:selected {{ background: {ACCENT}; }}
QToolTip {{ background: {PANEL2}; color: {TEXT}; border: 1px solid {BORDER}; }}
QGraphicsView {{ border: 1px solid {BORDER}; border-radius: 8px; background: #0a0d12; }}
"""
