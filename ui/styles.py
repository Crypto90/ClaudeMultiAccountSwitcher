"""Windows 11 Fluent Dark Glassmorphism Design System for Claude Switcher.
Matches the cinematic obsidian, terracotta amber, and cyber violet aesthetic of the hero banner.
"""

FLUENT_DARK_QSS = """
/* Global Window Styling */
QMainWindow, QDialog {
    background-color: #090c13;
    color: #f1f5f9;
    font-family: 'Segoe UI Variable Text', 'Segoe UI', system-ui, sans-serif;
    font-size: 13px;
}

/* Tooltips */
QToolTip {
    background-color: #141824;
    color: #f8fafc;
    border: 1px solid rgba(245, 158, 11, 0.4);
    border-radius: 8px;
    padding: 6px 12px;
    font-size: 12px;
}

/* Tab Bar */
QTabWidget::pane {
    border: 1px solid rgba(255, 255, 255, 0.08);
    border-top: none;
    background-color: #0d1017;
    border-bottom-left-radius: 14px;
    border-bottom-right-radius: 14px;
}

QTabBar::tab {
    background-color: #12151f;
    color: #94a3b8;
    padding: 10px 24px;
    margin-right: 6px;
    border-top-left-radius: 10px;
    border-top-right-radius: 10px;
    border: 1px solid rgba(255, 255, 255, 0.06);
    border-bottom: none;
    font-weight: 600;
    font-size: 13px;
}

QTabBar::tab:hover {
    background-color: #181d2c;
    color: #e2e8f0;
    border-color: rgba(255, 255, 255, 0.12);
}

QTabBar::tab:selected {
    background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #181d2a, stop:1 #0d1017);
    color: #fbbf24; /* Luminous amber highlight */
    border-top: 2px solid #f59e0b;
    border-left: 1px solid rgba(255, 255, 255, 0.1);
    border-right: 1px solid rgba(255, 255, 255, 0.1);
}

/* Push Buttons */
QPushButton {
    background-color: #181c28;
    color: #f1f5f9;
    border: 1px solid rgba(255, 255, 255, 0.1);
    border-radius: 8px;
    padding: 8px 16px;
    font-weight: 600;
    font-size: 13px;
}

QPushButton:hover {
    background-color: #222838;
    border-color: rgba(255, 255, 255, 0.2);
    color: #ffffff;
}

QPushButton:pressed {
    background-color: #121520;
    border-color: #f59e0b;
}

QPushButton:disabled {
    background-color: #11141d;
    color: #475569;
    border-color: rgba(255, 255, 255, 0.04);
}

/* Primary Accent Buttons (Amber Terracotta Glow) */
QPushButton.primary-btn {
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #d97706, stop:1 #ea580c);
    color: #ffffff;
    border: 1px solid #fbbf24;
    font-weight: 700;
    border-radius: 8px;
    padding: 9px 20px;
}

QPushButton.primary-btn:hover {
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #f59e0b, stop:1 #f97316);
    border-color: #fde68a;
}

QPushButton.primary-btn:pressed {
    background: #b45309;
    border-color: #d97706;
}

/* Violet Accent Buttons (Cyber Violet Glow) */
QPushButton.violet-btn {
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #7c3aed, stop:1 #9333ea);
    color: #ffffff;
    border: 1px solid #c084fc;
    font-weight: 600;
    border-radius: 8px;
    padding: 8px 16px;
}

QPushButton.violet-btn:hover {
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #8b5cf6, stop:1 #a855f7);
    border-color: #e9d5ff;
}

/* Danger Buttons */
QPushButton.danger-btn {
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #991b1b, stop:1 #7f1d1d);
    color: #fee2e2;
    border: 1px solid #ef4444;
    border-radius: 8px;
    padding: 8px 16px;
    font-weight: 600;
}

QPushButton.danger-btn:hover {
    background: #b91c1c;
    color: #ffffff;
    border-color: #f87171;
}

QPushButton.table-btn {
    padding: 5px 12px;
    font-size: 11px;
    border-radius: 6px;
    font-weight: 600;
    background-color: #1e2434;
    border: 1px solid rgba(255, 255, 255, 0.12);
}

QPushButton.table-btn:hover {
    background-color: #2b334a;
    border-color: #f59e0b;
    color: #ffffff;
}

QPushButton.table-danger-btn {
    padding: 5px 12px;
    font-size: 11px;
    border-radius: 6px;
    font-weight: 600;
    background-color: #2e1414;
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
    background-color: #111520;
    border: 1px solid rgba(255, 255, 255, 0.1);
    border-radius: 8px;
    padding: 8px 12px;
    color: #f1f5f9;
    font-size: 13px;
    selection-background-color: #d97706;
}

QLineEdit:focus, QComboBox:focus {
    border: 1px solid #f59e0b;
    background-color: #151a28;
}

QComboBox::drop-down {
    subcontrol-origin: padding;
    subcontrol-position: top right;
    width: 28px;
    border-left: 1px solid rgba(255, 255, 255, 0.08);
}

QComboBox QAbstractItemView {
    background-color: #111520;
    border: 1px solid rgba(255, 255, 255, 0.15);
    color: #f1f5f9;
    selection-background-color: #242c3d;
    selection-color: #fbbf24;
    padding: 6px;
    border-radius: 8px;
}

/* Checkboxes */
QCheckBox {
    color: #e2e8f0;
    font-size: 13px;
    spacing: 8px;
}

QCheckBox::indicator {
    width: 18px;
    height: 18px;
    border-radius: 5px;
    border: 1px solid rgba(255, 255, 255, 0.15);
    background-color: #121622;
}

QCheckBox::indicator:hover {
    border-color: #f59e0b;
    background-color: #181d2c;
}

QCheckBox::indicator:checked {
    background-color: #d97706;
    border-color: #fbbf24;
}

/* Tables (Terminal/IDE Theme) */
QTableWidget {
    background-color: #0c0f16;
    border: 1px solid rgba(255, 255, 255, 0.08);
    border-radius: 10px;
    gridline-color: rgba(255, 255, 255, 0.04);
    selection-background-color: #1e2638;
    selection-color: #ffffff;
    font-size: 13px;
}

QHeaderView::section {
    background-color: #111520;
    color: #94a3b8;
    padding: 9px 12px;
    border: none;
    border-bottom: 1px solid rgba(255, 255, 255, 0.08);
    font-weight: 700;
    font-size: 11px;
    text-transform: uppercase;
    letter-spacing: 0.5px;
}

/* Scrollbars */
QScrollBar:vertical {
    background: #090c13;
    width: 8px;
    margin: 0px;
    border-radius: 4px;
}

QScrollBar::handle:vertical {
    background: #242a3a;
    min-height: 24px;
    border-radius: 4px;
}

QScrollBar::handle:vertical:hover {
    background: #3b445d;
}

QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
    height: 0px;
}

QScrollBar:horizontal {
    background: #090c13;
    height: 8px;
    margin: 0px;
    border-radius: 4px;
}

QScrollBar::handle:horizontal {
    background: #242a3a;
    min-width: 24px;
    border-radius: 4px;
}

/* Cards & Frames (Glassmorphism Nodes) */
QFrame.card-frame {
    background-color: #11141e;
    border: 1px solid rgba(255, 255, 255, 0.08);
    border-radius: 14px;
}

QFrame.card-frame:hover {
    border-color: rgba(255, 255, 255, 0.16);
    background-color: #141824;
}

QFrame.card-frame-active {
    background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #181d2c, stop:1 #11141e);
    border: 1.5px solid #f59e0b;
    border-radius: 14px;
}

QFrame.banner-frame {
    background-color: #10131d;
    border: 1px solid rgba(255, 255, 255, 0.08);
    border-radius: 12px;
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
    background-color: #171b26;
    color: #94a3b8;
    border: 1px solid rgba(255, 255, 255, 0.1);
    border-radius: 10px;
    padding: 3px 10px;
    font-size: 11px;
    font-weight: 600;
}

QLabel.badge-rate-limited {
    background-color: #451a03;
    color: #fbbf24;
    border: 1px solid #b45309;
    border-radius: 10px;
    padding: 3px 10px;
    font-size: 11px;
    font-weight: 600;
}
"""
