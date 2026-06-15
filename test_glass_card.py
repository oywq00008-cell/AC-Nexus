"""液态玻璃效果 — 放弃 GraphicsEffect，纯 paintEvent 手绘"""
import sys
from PySide6 import QtCore, QtGui, QtWidgets

APP = QtWidgets.QApplication(sys.argv)
APP.setStyle("Fusion")


class Glass(QtWidgets.QWidget):
    def __init__(self, parent, radius=20, tint=QtGui.QColor(255,255,255,70)):
        super().__init__(parent)
        self._r = radius
        self._tint = tint

    def set_tint(self, c): self._tint = c; self.update()

    def paintEvent(self, event):
        w, h = self.width(), self.height()
        r = self._r
        pad = 40                    # 四周留白给阴影
        body = QtCore.QRectF(pad, pad, w - pad * 2, h - pad * 2)
        blur = 36                   # 阴影模糊范围

        p = QtGui.QPainter(self)
        p.setRenderHint(QtGui.QPainter.Antialiasing)

        # ── 阴影：QPainterPath + addRoundedRect，半径等比增大 ──
        layers = 24
        for i in range(layers):
            t = i / layers
            expand = blur * t
            alpha = int(60 * (1 - t) ** 2.5)
            if alpha < 1:
                continue
            # 阴影层 rect
            sr = body.adjusted(-expand, -expand + 4, expand, expand + 4)
            # 半径等比增大
            rr = r + expand
            path = QtGui.QPainterPath()
            path.addRoundedRect(sr, rr, rr)
            p.fillPath(path, QtGui.QColor(0, 0, 0, alpha))

        # ── 玻璃体 ──
        clip = QtGui.QPainterPath()
        clip.addRoundedRect(body, r, r)
        p.setClipPath(clip)

        # 底层白
        p.fillRect(body, QtGui.QColor(255, 255, 255, 30))

        # 纵向渐变
        grad = QtGui.QLinearGradient(body.topLeft(), body.bottomLeft())
        grad.setColorAt(0.0, QtGui.QColor(255, 255, 255, 50))
        grad.setColorAt(0.3, QtGui.QColor(255, 255, 255, 150))
        grad.setColorAt(0.7, QtGui.QColor(255, 255, 255, 80))
        grad.setColorAt(1.0, QtGui.QColor(255, 255, 255, 20))
        p.fillRect(body, grad)

        if self._tint.alpha() > 0:
            p.fillRect(body, self._tint)

        p.setClipping(False)

        # ── 边框 ──
        p.setPen(QtGui.QPen(QtGui.QColor(255, 255, 255, 55), 1))
        p.setBrush(QtCore.Qt.NoBrush)
        p.drawRoundedRect(body.adjusted(0.5, 0.5, -0.5, -0.5), r, r)

        p.end()


win = QtWidgets.QMainWindow()
win.setWindowTitle("液态玻璃效果")
win.resize(800, 600)

central = QtWidgets.QWidget()
central.setStyleSheet("""
    background: qlineargradient(x1:0, y1:0, x2:0.4, y2:1,
        stop:0 #EAD5F8, stop:0.3 #D0E5FF, stop:0.6 #C8F0E0, stop:1 #FFE5D0);
""")
win.setCentralWidget(central)

root = QtWidgets.QVBoxLayout(central)
root.setContentsMargins(10, 16, 10, 16)
root.setSpacing(12)


def card(tl, ds, tint=QtGui.QColor(255,255,255,70), tc="#333", dc="#666", **kw):
    c = Glass(central, tint=tint, **kw)
    c.setMinimumHeight(108)
    lo = QtWidgets.QVBoxLayout(c)
    lo.setContentsMargins(76, 60, 76, 28)
    lo.setSpacing(4)
    a = QtWidgets.QLabel(tl)
    a.setStyleSheet(f"font-size:15px; font-weight:bold; color:{tc}; background:transparent;")
    lo.addWidget(a)
    b = QtWidgets.QLabel(ds)
    b.setStyleSheet(f"font-size:12px; color:{dc}; background:transparent;")
    lo.addWidget(b)
    root.addWidget(c)


card("清透白玻璃", "24 层 QPainterPath 叠加阴影 · 渐变染色")
card("蓝色调玻璃", "tint=rgba(47 128 237 35)", tint=QtGui.QColor(47, 128, 237, 35),
     tc="#1A4FA0", dc="#3A6FD8")
card("深色玻璃", "tint=rgba(0 0 0 85)", tint=QtGui.QColor(0, 0, 0, 85),
     tc="#EEE", dc="#AAA")

root.addStretch()
hint = QtWidgets.QLabel("纯 paintEvent · QPainterPath fillPath 多层叠加 · 无 GraphicsEffect")
hint.setAlignment(QtCore.Qt.AlignCenter)
hint.setStyleSheet("color:#999; font-size:11px; background:transparent;")
root.addWidget(hint)

win.show()
sys.exit(APP.exec())
