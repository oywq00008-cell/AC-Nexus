"""品牌选择弹窗 — 博联 / 米家 二选一"""
import sys
import os
from PySide6 import QtCore, QtGui, QtWidgets

from ._utils import lbl, is_dark

# 品牌类型常量
BRAND_BROADLINK = "broadlink"
BRAND_XIAOMI = "xiaomi_cloud"

# logo 路径
_LOGO_DIR = os.path.join(os.path.dirname(__file__), "..", "..", "logos")


def open_brand_dialog(parent, current_brand="broadlink"):
    """弹出品牌选择弹窗，返回选中的 brand_type，取消返回 None"""
    dlg = QtWidgets.QDialog(parent, QtCore.Qt.FramelessWindowHint)
    dlg.setAttribute(QtCore.Qt.WA_TranslucentBackground)
    dlg.setWindowModality(QtCore.Qt.WindowModal)
    dlg.setWindowTitle("选择设备类型")
    dlg.resize(360, 340)

    dark = is_dark()
    bg = "#2D2D2D" if dark else "white"
    bd = "#444" if dark else "#DEDEDE"
    fg = "#EEE" if dark else "#333"

    outer = QtWidgets.QFrame(dlg)
    outer.setObjectName("brand_outer")
    outer.setStyleSheet(f"QFrame#brand_outer {{ background:{bg}; border:1px solid {bd}; border-radius:12px; }}")
    # 阴影
    shadow = QtWidgets.QGraphicsDropShadowEffect()
    shadow.setBlurRadius(24)
    shadow.setOffset(0, 2)
    shadow.setColor(QtGui.QColor(0, 0, 0, 80))
    outer.setGraphicsEffect(shadow)
    ov = QtWidgets.QVBoxLayout(outer); ov.setContentsMargins(0, 0, 0, 0); ov.setSpacing(0)

    # 标题栏（可拖拽移动）
    tb = QtWidgets.QWidget(); tb.setFixedHeight(36)
    tb.setStyleSheet(f"background: transparent; border-bottom: 1px solid {bd};")
    tl = QtWidgets.QHBoxLayout(tb); tl.setContentsMargins(16, 0, 8, 0)
    tl.addWidget(lbl("选择设备类型", bold=True, size=13)); tl.addStretch()
    close = QtWidgets.QPushButton("✕"); close.setFixedSize(28, 28); close.setFlat(True)
    close.setStyleSheet(
        f"QPushButton {{ font-size:14px; color:{'#AAA' if dark else '#888'}; "
        f"border:none; background:transparent; }} "
        f"QPushButton:hover {{ background:{'#444' if dark else '#F0F0F0'}; border-radius:4px; }}")
    close.clicked.connect(dlg.reject)
    tl.addWidget(close)
    # 拖拽标题栏移动窗口
    def _on_press(e):
        if e.button() == QtCore.Qt.LeftButton:
            tb._drag_start = e.globalPosition().toPoint() - dlg.frameGeometry().topLeft()
    def _on_move(e):
        if hasattr(tb, '_drag_start'):
            dlg.move(e.globalPosition().toPoint() - tb._drag_start)
    tb.mousePressEvent = _on_press
    tb.mouseMoveEvent = _on_move
    ov.addWidget(tb)

    # 内容区
    body = QtWidgets.QVBoxLayout(); body.setContentsMargins(20, 16, 20, 16); body.setSpacing(12)

    # ── 品牌选择卡（互斥 QPushButton）──
    btn_group = QtWidgets.QButtonGroup(dlg)
    btn_group.setExclusive(True)

    unsel_bd = "#444" if dark else "#DEDEDE"
    sel_bd = "#2F80ED"
    card_bg = "#3D3D3D" if dark else "#FAFAFA"

    def _make_brand_card(text, logo_file, brand_val):
        btn = QtWidgets.QPushButton()
        btn.setCheckable(True)
        btn.setFixedSize(130, 120)
        btn.setCursor(QtCore.Qt.PointingHandCursor)
        vl = QtWidgets.QVBoxLayout(btn)
        vl.setContentsMargins(8, 12, 8, 8); vl.setSpacing(6)

        logo_lbl = QtWidgets.QLabel()
        logo_lbl.setPixmap(QtGui.QPixmap(os.path.join(_LOGO_DIR, logo_file)).scaled(
            80, 44, QtCore.Qt.KeepAspectRatio, QtCore.Qt.SmoothTransformation))
        logo_lbl.setAlignment(QtCore.Qt.AlignCenter)
        vl.addWidget(logo_lbl)

        txt_lbl = QtWidgets.QLabel(text)
        txt_lbl.setAlignment(QtCore.Qt.AlignCenter)
        txt_lbl.setStyleSheet(f"color:{fg}; font-size:12px; font-weight:bold;")
        vl.addWidget(txt_lbl)

        def _set_qss(checked):
            bd = sel_bd if checked else unsel_bd
            btn.setStyleSheet(f"""
                QPushButton {{ background:{card_bg}; border:2px solid {bd}; border-radius:12px; }}
                QPushButton:hover {{ border-color:{sel_bd}; }}
            """)
        _set_qss(False)
        btn.toggled.connect(_set_qss)
        btn.clicked.connect(lambda: None)  # toggled 足够
        return btn, brand_val

    btn_broadlink, _ = _make_brand_card("博联 Broadlink", "Broadlink_logo.png", BRAND_BROADLINK)
    btn_xiaomi, _   = _make_brand_card("米家 Mijia", "mijia_logo.png", BRAND_XIAOMI)

    btn_group.addButton(btn_broadlink)
    btn_group.addButton(btn_xiaomi)

    if current_brand == BRAND_XIAOMI:
        btn_xiaomi.setChecked(True)
    else:
        btn_broadlink.setChecked(True)

    cards_row = QtWidgets.QHBoxLayout()
    cards_row.addStretch()
    cards_row.addWidget(btn_broadlink)
    cards_row.addSpacing(16)
    cards_row.addWidget(btn_xiaomi)
    cards_row.addStretch()

    body.addStretch()
    body.addLayout(cards_row)
    body.addStretch()

    # 确定按钮
    btn_row = QtWidgets.QHBoxLayout(); btn_row.addStretch()
    ok_btn = QtWidgets.QPushButton("确定")
    ok_btn.setFixedSize(80, 32)
    ok_btn.setStyleSheet(f"""
        QPushButton {{
            background: #1677FF; color: white; border: none; border-radius: 6px; font-size: 13px;
        }}
        QPushButton:hover {{ background: #4096FF; }}
    """)
    btn_row.addWidget(ok_btn); btn_row.addStretch()
    body.addLayout(btn_row)
    ov.addLayout(body)

    full = QtWidgets.QVBoxLayout(dlg); full.setContentsMargins(10, 10, 10, 10); full.addWidget(outer)

    result = {"brand": None}

    def on_ok():
        if btn_xiaomi.isChecked():
            result["brand"] = BRAND_XIAOMI
        else:
            result["brand"] = BRAND_BROADLINK
        dlg.accept()

    ok_btn.clicked.connect(on_ok)

    dlg.exec()
    return result["brand"]
