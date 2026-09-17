"""Windows 11 Fluent Dark Design System for Claude Switcher."""

FLUENT_DARK_QSS = """
/* Global Window Styling */
QMainWindow, QDialog {
    background-color: #0f1115;
    color: #f3f4f6;
    font-family: 'Segoe UI Variable Text', 'Segoe UI', system-ui, sans-serif;
    font-size: 13px;
}


/* Tooltips */
QToolTip {
    background-color: #1e222b;
    color: #f3f4f6;
    border: 1px solid #3b4252;
    border-radius: 6px;
    padding: 6px 10px;
    font-size: 12px;
}

/* Tab Bar */
QTabWidget::pane {
    border: 1px solid #232733;
    border-top: none;
    background-color: #13151b;
    border-bottom-left-radius: 12px;
    border-bottom-right-radius: 12px;
}

QTabBar::tab {
    background-color: #171a21;
    color: #9ca3af;
    padding: 10px 24px;
    margin-right: 4px;
    border-top-left-radius: 8px;
    border-top-right-radius: 8px;
    border: 1px solid #232733;
    border-bottom: none;
    font-weight: 600;
    font-size: 13px;
}

QTabBar::tab:hover {
    background-color: #1f232d;
    color: #e5e7eb;
}

QTabBar::tab:selected {
    background-color: #13151b;
    color: #f59e0b; /* Terracotta amber highlight */
    border-top: 2px solid #f59e0b;
}

/* Push Buttons */
QPushButton {
    background-color: #222632;
    color: #f3f4f6;
    border: 1px solid #33394a;
    border-radius: 8px;
    padding: 8px 16px;
    font-weight: 600;
    font-size: 13px;
}

QPushButton:hover {
    background-color: #2d3343;
    border-color: #4b5568;
    color: #ffffff;
}

QPushButton:pressed {
    background-color: #191c24;
    border-color: #f59e0b;
}

QPushButton:disabled {
    background-color: #171920;
    color: #525b6e;
    border-color: #232733;
}

/* Primary Accent Buttons */
QPushButton.primary-btn {
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #d97706, stop:1 #ea580c);
    color: #ffffff;
    border: 1px solid #f59e0b;
    font-weight: 700;
    border-radius: 8px;
    padding: 9px 20px;
}

QPushButton.primary-btn:hover {
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #f59e0b, stop:1 #f97316);
    border-color: #fbbf24;
}

QPushButton.primary-btn:pressed {
    background-color: #b45309;
}

/* Violet Accent Buttons */
QPushButton.violet-btn {
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #7c3aed, stop:1 #9333ea);
    color: #ffffff;
    border: 1px solid #a855f7;
    font-weight: 600;
    border-radius: 8px;
    padding: 8px 16px;
}

QPushButton.violet-btn:hover {
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #8b5cf6, stop:1 #a855f7);
    border-color: #c084fc;
}

/* Danger Buttons */
QPushButton.danger-btn {
    background-color: #7f1d1d;
    color: #fecaca;
    border: 1px solid #dc2626;
    border-radius: 8px;
    padding: 8px 16px;
    font-weight: 600;
}

QPushButton.danger-btn:hover {
    background-color: #991b1b;
    color: #ffffff;
    border-color: #ef4444;
}

QPushButton.table-btn {
    padding: 4px 10px;
    font-size: 11px;
    border-radius: 6px;
    font-weight: 600;
}

QPushButton.table-danger-btn {
    padding: 4px 10px;
    font-size: 11px;
    border-radius: 6px;
    font-weight: 600;
    background-color: #3b1818;
    color: #fca5a5;
    border: 1px solid #7f1d1d;
}

QPushButton.table-danger-btn:hover {
    background-color: #7f1d1d;
    color: #ffffff;
    border-color: #ef4444;
}

/* Inputs & Combos */
QLineEdit, QComboBox, QSpinBox {
    background-color: #161920;
    border: 1px solid #2e3545;
    border-radius: 8px;
    padding: 8px 12px;
    color: #f3f4f6;
    font-size: 13px;
    selection-background-color: #d97706;
}

QLineEdit:focus, QComboBox:focus {
    border: 1px solid #f59e0b;
    background-color: #1a1e27;
}

QComboBox::drop-down {
    subcontrol-origin: padding;
    subcontrol-position: top right;
    width: 28px;
    border-left: 1px solid #2e3545;
}

QComboBox QAbstractItemView {
    background-color: #161920;
    border: 1px solid #33394a;
    color: #f3f4f6;
    selection-background-color: #2d3343;
    selection-color: #f59e0b;
    padding: 4px;
    border-radius: 6px;
}

/* Checkboxes */
QCheckBox {
    color: #e5e7eb;
    font-size: 13px;
    spacing: 8px;
}

QCheckBox::indicator {
    width: 18px;
    height: 18px;
    border-radius: 4px;
    border: 1px solid #3b4252;
    background-color: #181b22;
}

QCheckBox::indicator:hover {
    border-color: #f59e0b;
}

QCheckBox::indicator:checked {
    background-color: #d97706;
    border-color: #f59e0b;
    image: none;
}

/* Tables */
QTableWidget {
    background-color: #13151b;
    border: 1px solid #232733;
    border-radius: 8px;
    gridline-color: #1f232d;
    selection-background-color: #272d3b;
    selection-color: #ffffff;
    font-size: 13px;
}

QHeaderView::section {
    background-color: #181b22;
    color: #9ca3af;
    padding: 8px 12px;
    border: none;
    border-bottom: 1px solid #282d3b;
    font-weight: 700;
    font-size: 12px;
    text-transform: uppercase;
}

/* Scrollbars */
QScrollBar:vertical {
    background: #111317;
    width: 10px;
    margin: 0px;
    border-radius: 5px;
}

QScrollBar::handle:vertical {
    background: #2a303d;
    min-height: 24px;
    border-radius: 5px;
}

QScrollBar::handle:vertical:hover {
    background: #3e4658;
}

QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
    height: 0px;
}

QScrollBar:horizontal {
    background: #111317;
    height: 10px;
    margin: 0px;
    border-radius: 5px;
}

QScrollBar::handle:horizontal {
    background: #2a303d;
    min-width: 24px;
    border-radius: 5px;
}

/* Cards & Frames */
QFrame.card-frame {
    background-color: #181b23;
    border: 1px solid #292f3d;
    border-radius: 12px;
}

QFrame.card-frame:hover {
    border-color: #3f475a;
    background-color: #1c202a;
}

QFrame.card-frame-active {
    background-color: #1a1e27;
    border: 1.5px solid #f59e0b;
    border-radius: 12px;
}

QFrame.banner-frame {
    background-color: #14171e;
    border: 1px solid #252a36;
    border-radius: 10px;
}

/* Status Badges */
QLabel.badge-active {
    background-color: #064e3b;
    color: #34d399;
    border: 1px solid #059669;
    border-radius: 10px;
    padding: 3px 10px;
    font-size: 11px;
    font-weight: 700;
}

QLabel.badge-inactive {
    background-color: #1f232d;
    color: #9ca3af;
    border: 1px solid #33394a;
    border-radius: 10px;
    padding: 3px 10px;
    font-size: 11px;
    font-weight: 600;
}

QLabel.badge-rate-limited {
    background-color: #451a03;
    color: #f59e0b;
    border: 1px solid #b45309;
    border-radius: 10px;
    padding: 3px 10px;
    font-size: 11px;
    font-weight: 600;
}
"""
