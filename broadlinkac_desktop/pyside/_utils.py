"""共享 UI 工具"""
from PySide6 import QtCore, QtGui, QtWidgets

_DARK = False  # 全局暗色状态


def set_dark_mode(enabled):
    global _DARK
    _DARK = enabled


def is_dark():
    return _DARK


class ToggleSwitch(QtWidgets.QCheckBox):
    """滑动开关组件 — 带圆点滑块 + 滑动动画"""
    def __init__(self, text="", parent=None):
        super().__init__(text, parent)
        self.setFixedSize(50, 26)
        self.setCursor(QtCore.Qt.PointingHandCursor)
        self.setStyleSheet("""
            QCheckBox { spacing: 6px; }
            QCheckBox::indicator {
                width: 44px; height: 24px; border-radius: 12px;
                background: #bbb;
            }
            QCheckBox::indicator:checked {
                background: #4CAF50;
            }
        """)
        self._offset = 1.0 if self.isChecked() else 0.0
        self._anim = None

    def setChecked(self, checked):
        """同步 _offset，防止外部 setChecked 导致滑块位置反"""
        super().setChecked(checked)
        self._offset = 1.0 if checked else 0.0
        self.update()

    def nextCheckState(self):
        """拦截点击 → 先提交状态再动画滑杆，防止 Qt 的 emitClicked 用旧值"""
        target = 1.0 if not self.isChecked() else 0.0
        new_checked = target > 0.5
        # 立即切状态但屏蔽信号，因为 QAbstractButton.click() 之后会调 emitClicked
        # 如果这时 isChecked() 还是旧值，clicked 信号会携带错误状态
        self.blockSignals(True)
        self.setChecked(new_checked)
        self.blockSignals(False)
        # 重置 offset 为旧位置，供动画从当前视觉位置滑向目标
        self._offset = 1.0 - target
        # 启动滑杆动画，结束后手动补发信号
        self._anim = QtCore.QPropertyAnimation(self, b"offset")
        self._anim.setDuration(300)
        self._anim.setStartValue(self._offset)
        self._anim.setEndValue(target)
        self._anim.setEasingCurve(QtCore.QEasingCurve.OutBack)
        self._anim.start()

    def _get_offset(self):
        return self._offset

    def _set_offset(self, value):
        self._offset = value
        self.update()

    offset = QtCore.Property(float, fget=_get_offset, fset=_set_offset)

    def paintEvent(self, event):
        super().paintEvent(event)
        painter = QtGui.QPainter(self)
        painter.setRenderHint(QtGui.QPainter.Antialiasing)
        opt = QtWidgets.QStyleOptionButton()
        self.initStyleOption(opt)
        indicator_rect = self.style().subElementRect(
            QtWidgets.QStyle.SE_CheckBoxIndicator, opt, self)
        r = indicator_rect.height() // 2 - 2
        left_x = indicator_rect.left() + r + 1
        right_x = indicator_rect.right() - r - 1
        x = left_x + (right_x - left_x) * self._offset
        y = indicator_rect.center().y() + 1
        painter.setBrush(QtGui.QColor("#fff"))
        painter.setPen(QtCore.Qt.NoPen)
        painter.drawEllipse(QtCore.QPointF(x, y), r, r)


def frm():
    f = QtWidgets.QFrame()
    f.setObjectName("card")
    f.setStyleSheet(_build_card_qss())
    f.setGraphicsEffect(_card_shadow())
    return f


def _card_shadow():
    shadow = QtWidgets.QGraphicsDropShadowEffect()
    shadow.setBlurRadius(16)
    shadow.setOffset(0, 2)
    shadow.setColor(QtGui.QColor(0, 0, 0, 25))
    return shadow


def _build_card_qss():
    if _DARK:
        bg, bd = "#2D2D2D", "#444"
    else:
        bg, bd = "white", "#DEDEDE"
    return f"""
        QFrame#card {{
            background: {bg};
            border: 1px solid {bd};
            border-radius: 12px;
        }}
        QFrame#card QWidget {{
            background-color: {bg};
        }}
        QFrame#card QWidget QPushButton#primary {{
            background-color: #2F80ED;
        }}
    """


_DARK_COLOR_MAP = {
    "#555": "#EEE", "#666": "#EEE", "#999": "#AAA", "#888": "#999",
    "#333": "#EEE", "gray": "#AAA",
}


def lbl(text, bold=False, color=None, size=None):
    l = QtWidgets.QLabel(text)
    f = l.font()
    if bold: f.setBold(True)
    if size: f.setPointSize(size)
    l.setFont(f)
    if color:
        c = _DARK_COLOR_MAP.get(color, color) if _DARK else color
        l.setStyleSheet(f"color:{c};")
        l.setProperty("label_color", color)  # 存原始色，供主题切换时重映射
    return l


def refresh_labels(app):
    """主题切换后刷新所有 lbl 创建的标签颜色"""
    for label in app.allWidgets():
        if isinstance(label, QtWidgets.QLabel):
            orig = label.property("label_color")
            if orig:
                c = _DARK_COLOR_MAP.get(orig, orig) if _DARK else orig
                current = label.styleSheet()
                # 保留 background:transparent 等已有样式，只替换 color
                import re
                label.setStyleSheet(re.sub(r"color:[^;]+;?", f"color:{c};", current))


def toggle(text=""):
    """创建滑动开关"""
    return ToggleSwitch(text)
