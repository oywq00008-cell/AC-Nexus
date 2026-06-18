"""米家云登录弹窗 — 扫码登录"""
from PySide6 import QtCore, QtGui, QtWidgets

from ._utils import lbl, is_dark


def _make_draggable(title_bar, dlg):
    """让标题栏可拖拽移动窗口"""
    def press(e):
        if e.button() == QtCore.Qt.LeftButton:
            title_bar._drag_start = e.globalPosition().toPoint() - dlg.frameGeometry().topLeft()
    def move(e):
        if hasattr(title_bar, '_drag_start'):
            dlg.move(e.globalPosition().toPoint() - title_bar._drag_start)
    title_bar.mousePressEvent = press
    title_bar.mouseMoveEvent = move


class _LoginSignals(QtCore.QObject):
    """线程安全的 UI 更新信号"""
    show_link = QtCore.Signal(str)
    set_status = QtCore.Signal(str, str)  # text, color
    login_ok = QtCore.Signal(object)
    login_err = QtCore.Signal(str)


def open_xiaomi_login_dialog(parent):
    signals = _LoginSignals()

    dlg = QtWidgets.QDialog(parent, QtCore.Qt.FramelessWindowHint)
    dlg.setAttribute(QtCore.Qt.WA_TranslucentBackground)
    dlg.setWindowModality(QtCore.Qt.WindowModal)
    dlg.setWindowTitle("米家云登录")
    dlg.resize(390, 400)  # 额外空间给阴影

    dark = is_dark()
    bg = "#2D2D2D" if dark else "white"
    bd = "#444" if dark else "#DEDEDE"
    fg = "#EEE" if dark else "#333"

    outer = QtWidgets.QFrame(dlg)
    outer.setObjectName("xiaomi_login_outer")
    outer.setStyleSheet(f"QFrame#xiaomi_login_outer {{ background:{bg}; border:1px solid {bd}; border-radius:12px; }}")
    shadow = QtWidgets.QGraphicsDropShadowEffect()
    shadow.setBlurRadius(24)
    shadow.setOffset(0, 2)
    shadow.setColor(QtGui.QColor(0, 0, 0, 80))
    outer.setGraphicsEffect(shadow)
    ov = QtWidgets.QVBoxLayout(outer); ov.setContentsMargins(0, 0, 0, 0); ov.setSpacing(0)

    # 标题栏
    tb = QtWidgets.QWidget(); tb.setFixedHeight(36)
    tb.setStyleSheet(f"background: transparent; border-bottom: 1px solid {bd};")
    tl = QtWidgets.QHBoxLayout(tb); tl.setContentsMargins(16, 0, 8, 0)
    tl.addWidget(lbl("米家云登录", bold=True, size=12)); tl.addStretch()
    close = QtWidgets.QPushButton("✕"); close.setFixedSize(28, 28); close.setFlat(True)
    close.setStyleSheet(f"QPushButton {{ font-size:14px; color:{'#AAA' if dark else '#888'}; border:none; background:transparent; }} QPushButton:hover {{ background:{'#444' if dark else '#F0F0F0'}; border-radius:4px; }}")
    close.clicked.connect(dlg.reject)
    tl.addWidget(close)
    _make_draggable(tb, dlg)
    ov.addWidget(tb)

    body = QtWidgets.QVBoxLayout(); body.setContentsMargins(24, 16, 24, 16); body.setSpacing(10)

    # 中间区域 — 二维码/占位
    center = QtWidgets.QLabel("正在获取二维码...")
    center.setFixedSize(160, 160)
    center.setAlignment(QtCore.Qt.AlignCenter)
    center.setStyleSheet(f"border: none; background: white; font-size:12px; color:{'#888' if dark else '#666'};")
    body.addWidget(center, alignment=QtCore.Qt.AlignCenter)

    # 链接文字
    link_label = QtWidgets.QLabel()
    link_label.setAlignment(QtCore.Qt.AlignCenter)
    link_label.setWordWrap(True)
    link_label.setVisible(False)
    link_label.setOpenExternalLinks(True)
    link_label.setTextFormat(QtCore.Qt.RichText)
    link_label.setStyleSheet("border: none; background: transparent;")
    body.addWidget(link_label)

    # 状态
    status = QtWidgets.QLabel("正在连接小米服务器...")
    status.setAlignment(QtCore.Qt.AlignCenter)
    status.setStyleSheet(f"border: none; color: {'#AAA' if dark else '#888'}; font-size: 12px;")
    body.addWidget(status)

    body.addStretch()

    # 取消按钮
    btn_row = QtWidgets.QHBoxLayout(); btn_row.addStretch()
    cancel_btn = QtWidgets.QPushButton("取 消"); cancel_btn.setFixedSize(100, 34)
    cancel_btn.setStyleSheet("""
        QPushButton { background: transparent; color: #888; border: 1px solid #888; border-radius: 6px; font-size: 13px; }
        QPushButton:hover { background: #F0F0F0; }
    """)
    cancel_btn.clicked.connect(dlg.reject)
    btn_row.addWidget(cancel_btn); btn_row.addStretch()
    body.addLayout(btn_row)

    ov.addLayout(body)
    full = QtWidgets.QVBoxLayout(dlg); full.setContentsMargins(10, 10, 10, 10); full.addWidget(outer)

    result = {"session": None}

    # ── 信号绑定 ──
    def _on_qr_ready(login_url):
        """二维码链接就绪 → 生成 QR code 显示在窗口上"""
        if not login_url:
            signals.set_status.emit("获取失败，请重试", "#E74C3C")
            return
        link_label.setText(
            f'<a href="{login_url}" style="color:#1677FF; font-size:13px;">在浏览器中打开扫码页面</a>')
        link_label.setVisible(True)
        status.setText("请使用米家APP扫一扫，或点击蓝色链接跳转到浏览器")
        # 生成二维码图片
        try:
            import qrcode
            qr = qrcode.QRCode(box_size=4, border=2)
            qr.add_data(login_url); qr.make(fit=True)
            img = qr.make_image(fill_color="black", back_color="white")
            ba = QtCore.QByteArray()
            buf = QtCore.QBuffer(ba); buf.open(QtCore.QIODevice.WriteOnly)
            img.save(buf, "PNG")
            pixmap = QtGui.QPixmap()
            pixmap.loadFromData(ba)
            center.setPixmap(pixmap.scaled(160, 160, QtCore.Qt.KeepAspectRatio, QtCore.Qt.SmoothTransformation))
        except ImportError:
            center.setText("扫码登录\n请点击下方链接")

    signals.show_link.connect(_on_qr_ready)
    signals.set_status.connect(lambda t, c: (
        status.setText(t),
        status.setStyleSheet(f"color: {c}; font-size: 12px;") if c else None,
    ))
    signals.login_ok.connect(lambda s: dlg.accept())
    signals.login_err.connect(lambda m: (
        status.setText(f"登录失败：{m}"),
        status.setStyleSheet("color: #E74C3C; font-size: 12px;"),
    ))

    # ── 后台执行 ──
    import threading

    def do_login():
        try:
            from acnexus_core.cloud_auth import login_qr

            def show_qr(qr_png, login_url):
                if login_url:
                    signals.show_link.emit(login_url)
                else:
                    signals.set_status.emit("获取失败，请重试", "#E74C3C")

            session = login_qr(qr_callback=show_qr)
            result["session"] = session
            signals.login_ok.emit(session)

        except Exception as e:
            signals.login_err.emit(str(e))

    threading.Thread(target=do_login, daemon=True).start()
    dlg.exec()
    return result["session"]
