"""空调控制 Tab 构建器"""

from pathlib import Path
from PySide6 import QtCore, QtGui, QtWidgets

import acnexus_core.config as _cfg
from acnexus_core.config import save_config
from acnexus_core.ac_control import MODES, FANS, MODE_KEYS
from ._utils import frm, lbl, toggle, _DARK


def _base_dir():
    return Path(__file__).resolve().parent.parent.parent


def weather_icon_path(text: str) -> str:
    """根据天气文字返回对应 SVG 图标路径"""
    base = str(_base_dir() / "icons" / "weather")
    if "雷" in text:       return f"{base}/thunder.svg"
    if "雪" in text:       return f"{base}/snow.svg"
    if "雨夹雪" in text:   return f"{base}/sleet.svg"
    if any(k in text for k in ("沙","尘","雾","霾")):
                           return f"{base}/fog.svg"
    if any(k in text for k in ("雨","冻雨")):
                           return f"{base}/rain.svg"
    if "晴" in text:       return f"{base}/clear.svg"
    if any(k in text for k in ("多云","少云","晴间多云")):
                           return f"{base}/cloudy.svg"
    if "阴" in text:       return f"{base}/overcast.svg"
    return f"{base}/wind.svg"


def build_ac_tab(app: QtWidgets.QMainWindow) -> QtWidgets.QWidget:
    """构建空调控制 Tab，将子控件注册到 app 上"""
    w = QtWidgets.QWidget()
    grid = QtWidgets.QGridLayout(w)
    grid.setContentsMargins(5, 5, 5, 5)
    grid.setSpacing(4)
    grid.setColumnStretch(0, 1)
    grid.setColumnStretch(1, 1)
    grid.setRowStretch(0, 4)
    grid.setRowStretch(1, 5)

    grid.addWidget(_weather_card(app), 0, 0)
    grid.addWidget(_control_card(app), 0, 1)
    _schedule_card(app, grid)
    return w


def _weather_card(app):
    wc = frm()
    vw = QtWidgets.QVBoxLayout(wc)
    vw.setContentsMargins(14, 12, 14, 12)
    vw.setSpacing(8)

    # 标题
    app._wx_title = lbl("当前天气", bold=True, size=14)
    vw.addWidget(app._wx_title, alignment=QtCore.Qt.AlignLeft)

    # ── 图标 + 右侧文字 ──
    icon_row = QtWidgets.QWidget()
    irl = QtWidgets.QHBoxLayout(icon_row)
    irl.setContentsMargins(0, 0, 0, 4)
    irl.setSpacing(16)

    # 天气图标（大图，左置）
    icon_wrap = QtWidgets.QWidget()
    iw = QtWidgets.QVBoxLayout(icon_wrap)
    iw.setContentsMargins(0, 6, 0, 0)
    app._wx_icon = QtWidgets.QLabel()
    app._wx_icon.setFixedSize(72, 72)
    iw.addWidget(app._wx_icon)
    iw.addStretch()
    irl.addWidget(icon_wrap, alignment=QtCore.Qt.AlignTop)

    # 右侧双行文字
    right_text = QtWidgets.QWidget()
    rtv = QtWidgets.QVBoxLayout(right_text)
    rtv.setContentsMargins(8, 0, 0, 0)
    rtv.setSpacing(4)

    # 行1: 定位图标 + 地名
    loc_row = QtWidgets.QWidget()
    lrl = QtWidgets.QHBoxLayout(loc_row)
    lrl.setContentsMargins(0, 0, 0, 0)
    lrl.setSpacing(4)
    loc_icon = QtWidgets.QLabel()
    loc_icon.setPixmap(QtGui.QIcon(str(_base_dir() / "icons" / "location.svg")).pixmap(14, 14))
    lrl.addWidget(loc_icon)
    app._wx_location = lbl("--", color="#666")
    lrl.addWidget(app._wx_location)
    lrl.addStretch()
    rtv.addWidget(loc_row)

    # 行2: 大温度 + 天气状况
    temp_row = QtWidgets.QWidget()
    trl = QtWidgets.QHBoxLayout(temp_row)
    trl.setContentsMargins(0, 0, 0, 0)
    trl.setSpacing(20)
    trl.setAlignment(QtCore.Qt.AlignBottom)
    app._wx_temp = lbl("—°C", size=36, bold=True)
    trl.addWidget(app._wx_temp, alignment=QtCore.Qt.AlignBottom)
    # 天气状况单独包一层，底部 padding 上推对齐温度基线
    wx_wrapper = QtWidgets.QWidget()
    ww = QtWidgets.QVBoxLayout(wx_wrapper)
    ww.setContentsMargins(0, 0, 0, 9)
    app._wx_text = lbl("", size=12, color="#333")
    ww.addWidget(app._wx_text, alignment=QtCore.Qt.AlignBottom)
    trl.addWidget(wx_wrapper, alignment=QtCore.Qt.AlignBottom)
    trl.addStretch()
    rtv.addWidget(temp_row)

    irl.addWidget(right_text, 1)
    vw.addWidget(icon_row)

    vw.addSpacing(16)

    # ── 三栏信息（统一框 + 竖线分隔）──
    base_icons = str(_base_dir() / "icons")
    info_box = QtWidgets.QFrame()
    info_box.setObjectName("info_box")
    info_box.setStyleSheet("""
        QFrame#info_box { background:white; border:1px solid #DEDEDE; border-radius:8px; }
        QFrame#info_box QWidget { background-color:transparent; }
    """)
    ibl = QtWidgets.QHBoxLayout(info_box)
    ibl.setContentsMargins(10, 10, 10, 10)
    ibl.setSpacing(0)

    def _info_item(icon_file, label_text, value_obj_name):
        w = QtWidgets.QWidget()
        wl = QtWidgets.QHBoxLayout(w)
        wl.setContentsMargins(4, 2, 4, 2)
        wl.setSpacing(6)
        ic = QtWidgets.QLabel()
        ic.setPixmap(QtGui.QIcon(f"{base_icons}/{icon_file}").pixmap(30, 30))
        # 蓝染色
        tint = QtGui.QPixmap(30, 30); tint.fill(QtCore.Qt.transparent)
        p = QtGui.QPainter(tint)
        p.drawPixmap(0, 0, QtGui.QIcon(f"{base_icons}/{icon_file}").pixmap(30, 30))
        p.setCompositionMode(QtGui.QPainter.CompositionMode_SourceIn)
        p.fillRect(tint.rect(), QtGui.QColor("#2F80ED"))
        p.end()
        ic.setPixmap(tint)
        wl.addWidget(ic, alignment=QtCore.Qt.AlignVCenter)
        tw = QtWidgets.QWidget()
        tv = QtWidgets.QVBoxLayout(tw)
        tv.setContentsMargins(0, 0, 0, 0); tv.setSpacing(1)
        from ._utils import _DARK_COLOR_MAP, _DARK
        c1 = _DARK_COLOR_MAP.get("#555", "#555") if _DARK else "#555"
        c2 = _DARK_COLOR_MAP.get("#333", "#333") if _DARK else "#333"
        lb = QtWidgets.QLabel(label_text)
        lb.setStyleSheet(f"background:transparent; color:{c1}; font-size:12px;")
        lb.setProperty("label_color", "#555")
        tv.addWidget(lb)
        val = QtWidgets.QLabel("--")
        val.setObjectName(value_obj_name)
        val.setStyleSheet(f"background:transparent; color:{c2}; font-size:13px; font-weight:bold;")
        val.setProperty("label_color", "#333")
        tv.addWidget(val)
        wl.addWidget(tw, 1)
        return w, val

    app._wx_feels_block, app._wx_feels_val = _info_item("thermometer.svg", "体感温度", "wx_feels_val")
    app._wx_humid_block, app._wx_humid_val = _info_item("humidity.svg", "湿度", "wx_humid_val")
    app._wx_wind_block, app._wx_wind_val   = _info_item("windforce.svg", "风向风力", "wx_wind_val")

    ibl.addWidget(app._wx_feels_block)
    _sep1 = QtWidgets.QFrame(); _sep1.setFrameShape(QtWidgets.QFrame.VLine)
    _sep1.setStyleSheet("QFrame { color:#DEDEDE; }"); ibl.addWidget(_sep1)
    ibl.addWidget(app._wx_humid_block)
    _sep2 = QtWidgets.QFrame(); _sep2.setFrameShape(QtWidgets.QFrame.VLine)
    _sep2.setStyleSheet("QFrame { color:#DEDEDE; }"); ibl.addWidget(_sep2)
    ibl.addWidget(app._wx_wind_block)

    vw.addWidget(info_box)

    vw.addStretch()

    # 底部刷新按钮 + 更新时间
    bottom = QtWidgets.QWidget()
    bl = QtWidgets.QHBoxLayout(bottom)
    bl.setContentsMargins(0, 0, 0, 0)
    bl.setSpacing(4)
    refresh_btn = QtWidgets.QPushButton()
    refresh_btn.setIcon(QtGui.QIcon(str(_base_dir() / "icons" / "refresh.svg")))
    refresh_btn.setToolTip("刷新天气和预警信息")
    refresh_btn.setIconSize(QtCore.QSize(12, 12))
    refresh_btn.setFixedSize(14, 14)
    refresh_btn.setFlat(True)
    refresh_btn.setCursor(QtCore.Qt.PointingHandCursor)
    refresh_btn.setStyleSheet("QPushButton { border:none; background:transparent; } QPushButton:hover { background:#E8F0FE; border-radius:2px; }")
    refresh_btn.clicked.connect(app._fetch_weather_all)
    bl.addWidget(refresh_btn, alignment=QtCore.Qt.AlignVCenter)
    app._wx_update = lbl("", size=8, color="#999")
    bl.addWidget(app._wx_update, alignment=QtCore.Qt.AlignVCenter)
    bl.addStretch()
    vw.addWidget(bottom, alignment=QtCore.Qt.AlignLeft)

    return wc


def _control_card(app):
    from acnexus_core.config import get_current_device

    cc = frm()
    cv = QtWidgets.QVBoxLayout(cc)
    cv.setContentsMargins(14, 12, 14, 12)
    cv.setSpacing(6)

    # ── 标题行：图标 + 品牌名 ──
    title_row = QtWidgets.QWidget()
    tl = QtWidgets.QHBoxLayout(title_row)
    tl.setContentsMargins(0, 0, 0, 0)
    tl.setSpacing(6)
    tl.setAlignment(QtCore.Qt.AlignTop)

    aircon_icon = QtWidgets.QLabel()
    aircon_icon.setPixmap(QtGui.QIcon(str(_base_dir() / "icons" / "aircon.svg")).pixmap(22, 22))
    tl.addWidget(aircon_icon, alignment=QtCore.Qt.AlignTop)

    brand = get_current_device().get("brand", "格力")
    app._ctrl_title = lbl(f"{brand}空调控制", bold=True, size=14)
    tl.addWidget(app._ctrl_title, alignment=QtCore.Qt.AlignTop)
    tl.addStretch()

    app._logo_lbl = QtWidgets.QLabel()
    app._logo_lbl.setFixedSize(80, 56)
    app._logo_lbl.setAlignment(QtCore.Qt.AlignRight | QtCore.Qt.AlignTop)
    tl.addWidget(app._logo_lbl, alignment=QtCore.Qt.AlignTop)
    cv.addWidget(title_row)

    # ── 表单 ──
    # ── 控件行（标签左，控件右）──
    def _ctrl_row(label_text, widget):
        row = QtWidgets.QWidget()
        rl = QtWidgets.QHBoxLayout(row)
        rl.setContentsMargins(0, 3, 0, 3)
        rl.addWidget(QtWidgets.QLabel(label_text))
        rl.addStretch()
        rl.addWidget(widget)
        cv.addWidget(row)
    
    app._power_sw = QtWidgets.QPushButton("  开启")
    app._power_sw.setCheckable(True); app._power_sw.setChecked(True)
    app._power_sw.setIcon(QtGui.QIcon(str(_base_dir() / "icons" / "power_on.svg")))
    app._power_sw.setStyleSheet("""
        QPushButton {
            border-radius: 9px;
            background: #4CAF50;
            color: white;
            font-weight: bold;
            font-size: 11px;
            border: none;
            padding: 2px 18px;
            min-height: 20px;
            margin-left: 105px;
        }
        QPushButton:!checked {
            background: #E5E5E5;
            color: #333;
        }
    """)
    def _toggle_power():
        if app._power_sw.isChecked():
            app._power_sw.setText("  开启")
            app._power_sw.setIcon(QtGui.QIcon(str(_base_dir() / "icons" / "power_on.svg")))
        else:
            app._power_sw.setText("  关闭")
            app._power_sw.setIcon(QtGui.QIcon(str(_base_dir() / "icons" / "power_off.svg")))
    app._power_sw.clicked.connect(_toggle_power)
    pw_row = QtWidgets.QWidget()
    pwl = QtWidgets.QHBoxLayout(pw_row); pwl.setContentsMargins(0, 3, 0, 3)
    pwl.addWidget(QtWidgets.QLabel("电源"))
    pwl.addWidget(app._power_sw)
    pwl.addStretch()
    cv.addWidget(pw_row)

    # 模式
    app._mode_cb = QtWidgets.QComboBox()
    app._mode_cb.addItems([k for k in MODES if k != "关闭"])
    app._mode_cb.setCurrentText("制冷")
    app._mode_cb.setMinimumWidth(250)
    _ctrl_row("模式", app._mode_cb)

    # 温度
    from ._utils import is_dark
    dark = is_dark()
    temp_frame = QtWidgets.QFrame()
    temp_frame.setStyleSheet("QFrame { background:transparent; }")
    temp_frame.setMinimumWidth(250)
    temp_frame.setFixedHeight(32)
    temp_btn_bg = "#3D3D3D" if dark else "#F0F0F0"
    temp_btn_hover = "#555" if dark else "#DEE4EA"
    temp_btn_color = "#DCDCDC" if dark else "#333"
    temp_btn_qss = f"QPushButton {{ border:none; background:{temp_btn_bg}; color:{temp_btn_color}; border-radius:8px; font-size:16px; font-weight:bold; }} QPushButton:hover {{ background:{temp_btn_hover}; }}"
    tfl = QtWidgets.QHBoxLayout(temp_frame); tfl.setContentsMargins(0, 0, 0, 0); tfl.setSpacing(0)
    b = QtWidgets.QPushButton("−"); b.setFixedSize(38, 32); b.clicked.connect(app._temp_down)
    b.setObjectName("temp_down_btn")
    b.setCursor(QtCore.Qt.PointingHandCursor)
    b.setStyleSheet(temp_btn_qss)
    tfl.addWidget(b)
    tfl.addStretch()
    temp_label_color = "#5B9BD5" if dark else "#2F80ED"
    app._temp_lbl = lbl("26°C", size=14, bold=False, color=temp_label_color)
    app._temp_lbl.setAlignment(QtCore.Qt.AlignCenter); app._temp_lbl.setFixedWidth(50)
    tfl.addWidget(app._temp_lbl)
    tfl.addStretch()
    b = QtWidgets.QPushButton("+"); b.setFixedSize(38, 32); b.clicked.connect(app._temp_up)
    b.setObjectName("temp_up_btn")
    b.setCursor(QtCore.Qt.PointingHandCursor)
    b.setStyleSheet(temp_btn_qss)
    tfl.addWidget(b)
    _ctrl_row("温度", temp_frame)

    # 风速
    app._fan_cb = QtWidgets.QComboBox()
    app._fan_cb.addItems(list(FANS.keys())); app._fan_cb.setCurrentText("自动")
    app._fan_cb.setMinimumWidth(250)
    _ctrl_row("风速", app._fan_cb)

    cv.addSpacing(8)

    # ── 发送按钮 ──
    btn = QtWidgets.QPushButton(" 发送控制指令")
    btn.setIcon(QtGui.QIcon(str(_base_dir() / "icons" / "send_on.svg")))
    btn.setIconSize(QtCore.QSize(20, 20))
    btn.setStyleSheet("""
        QPushButton {
            background: #0076D4;
            color: white;
            border: none;
            border-radius: 8px;
            min-height: 34px;
            font-size: 14px;
            font-weight: 500;
            padding: 0 20px;
        }
        QPushButton:hover { background: #0065B8; }
    """)
    btn.setCursor(QtCore.Qt.PointingHandCursor)
    btn.clicked.connect(app._on_send_click)
    cv.addWidget(btn)

    cv.addStretch(1)

    return cc


def update_brand_logo(app):
    """更新品牌 Logo 和控制标题"""
    if getattr(app, '_brand_type', 'broadlink') == "xiaomi_cloud":
        app._logo_lbl.clear()
        app._ctrl_title.setText("米家空调控制")
        return
    brand_cn = _cfg.config.get("brand", "格力")
    brand_key = _cfg.AC_BRANDS.get(brand_cn, "gree")
    LOGO_NAME = {
        "奥克斯": "aux_ac", "格力": "gree", "美的": "midea",
        "海尔": "haier", "华凌": "wahin", "海信": "hisense",
        "大金": "daikin", "三菱": "mitsubishi", "小米": "xiaomi",
        "松下": "panasonic",
        "日立": "hitachi", "富士通": "fujitsu", "巴鲁": "ballu",
        "开利": "carrier", "现代": "hyundai", "Fuego": "fuego",
    }
    logo_file = LOGO_NAME.get(brand_cn, brand_key)
    try:
        path = app._get_asset(f"logos/{logo_file}.png")
        pixmap = QtGui.QPixmap(str(path))
        scaled = pixmap.scaled(80, 56, QtCore.Qt.KeepAspectRatio, QtCore.Qt.SmoothTransformation)
        app._logo_lbl.setPixmap(scaled)
    except Exception:
        app._logo_lbl.clear()
    app._ctrl_title.setText(f"{brand_cn}空调控制")


def _schedule_card(app, grid):
    from .dialogs import open_schedule_template

    sc = frm()
    sv = QtWidgets.QVBoxLayout(sc)
    sv.setContentsMargins(14, 12, 14, 12)
    sv.setSpacing(8)

    base = str(_base_dir() / "icons")
    # 标题
    title_row = QtWidgets.QWidget()
    tl = QtWidgets.QHBoxLayout(title_row)
    tl.setContentsMargins(0, 0, 0, 0)
    ic = QtWidgets.QLabel()
    ic.setPixmap(QtGui.QIcon(f"{base}/timer.svg").pixmap(20, 20))
    tl.addWidget(ic)
    tl.addWidget(lbl("定时任务", bold=True, size=14))
    tl.addStretch()
    sv.addWidget(title_row)

    # ── 模板快速切换 ──
    tmpl_cb = QtWidgets.QComboBox()
    tmpl_cb.setMinimumWidth(140)
    def _refresh_tmpl_cb():
        tmpl_cb.blockSignals(True)
        tmpl_cb.clear()
        tmpl_cb.addItems(["< 关闭定时 >"] + list((_cfg.config.get("schedule_templates") or {}).keys()))
        mac = _cfg.config.get("current_device_mac", "")
        provider = _cfg.config.get("current_brand_type", "broadlink")
        dev = _cfg.config.get("devices", {}).get(provider, {}).get(mac, {})
        active = dev.get("active_template", "")
        if active and active in (_cfg.config.get("schedule_templates") or {}):
            tmpl_cb.setCurrentText(active)
        else:
            tmpl_cb.setCurrentIndex(0)
        tmpl_cb.blockSignals(False)
    _refresh_tmpl_cb()

    # 挂到 app 上供 _refresh_device_ui 调用
    app._refresh_tmpl_cb = _refresh_tmpl_cb

    def _on_tmpl_switch(t):
        mac = _cfg.config.get("current_device_mac", "")
        provider = _cfg.config.get("current_brand_type", "broadlink")
        dev = _cfg.config.setdefault("devices", {}).setdefault(provider, {}).setdefault(mac, {})
        if t == "< 关闭定时 >":
            dev.pop("active_template", None)
            dev["schedule_enabled"] = False
            _cfg.config["schedule_enabled"] = False
            from acnexus_core.logger import write_log
            write_log("定时", "已关闭")
        else:
            dev["active_template"] = t
            dev["schedule_enabled"] = True
            _cfg.config["schedule_enabled"] = True
            from acnexus_core.logger import write_log
            write_log("定时", f"已开启 → {t}")
        save_config(_cfg.config)
        from acnexus_core.scheduler import register_all_jobs
        import acnexus_core.scheduler as _sched
        with _sched._sched_lock: register_all_jobs()
        _update_schedule_display(app)
    tmpl_cb.currentTextChanged.connect(_on_tmpl_switch)
    sv.addWidget(tmpl_cb)

    # ── 摘要卡片（动态渲染，按日期组分 mini-frame）──
    summary_box = QtWidgets.QFrame()
    summary_box.setObjectName("sched_summary_box")
    bg = "#2D2D2D" if _DARK else "white"
    bd = "#444" if _DARK else "#DEDEDE"
    summary_box.setStyleSheet(f"""
        QFrame#sched_summary_box {{ background:{bg}; border:1px solid {bd}; border-radius:8px; }}
""")
    app._sched_summary_layout = QtWidgets.QVBoxLayout(summary_box)
    app._sched_summary_layout.setContentsMargins(12, 10, 12, 10)
    app._sched_summary_layout.setSpacing(8)

    app._sched_summary_box = summary_box
    sv.addWidget(summary_box)

    sv.addStretch()

    # ── 编辑按钮 ──
    btn = QtWidgets.QPushButton(" 编辑定时")
    btn.setIcon(QtGui.QIcon(f"{base}/edit.svg"))
    btn.setCursor(QtCore.Qt.PointingHandCursor)
    btn.clicked.connect(lambda: [open_schedule_template(app), _refresh_tmpl_cb(), _update_schedule_display(app)])
    sv.addWidget(btn)

    grid.addWidget(sc, 1, 0)
    _rules_card(app, grid)


def _update_schedule_display(app, dark=None):
    """刷新定时摘要（供外部调用），支持多日期组 — 每组独立 mini-frame"""
    from .dialogs import _schedule_summary
    if dark is None:
        from ._utils import is_dark
        dark = is_dark()
    _dark = dark
    if not hasattr(app, '_sched_summary_box'):
        return
    data = _schedule_summary(app)
    layout = app._sched_summary_layout
    # 清空旧内容（用 setParent(None) 立即释放，避免 deleteLater 异步残留）
    while layout.count():
        w = layout.takeAt(0).widget()
        if w:
            w.hide()
            w.setParent(None)

    base = str(_base_dir() / "icons")
    sep_color = "#444" if _dark else "#DEDEDE"
    day_color = "#CCC" if _dark else "#555"
    time_color = "#EEE" if _dark else "#333"
    dim_color = "#888" if _dark else "#999"

    error = data.get("error")
    if error:
        lbl = QtWidgets.QLabel(error)
        lbl.setStyleSheet(f"font-size:14px; color:{dim_color};")
        lbl.setProperty("label_color", "#999")  # 存原始浅色值，供 refresh_labels 重映射
        layout.addWidget(lbl, alignment=QtCore.Qt.AlignCenter)
        return

    groups = data.get("groups", [])
    if not groups:
        lbl = QtWidgets.QLabel("无时段设置")
        lbl.setStyleSheet(f"font-size:14px; color:{dim_color};")
        lbl.setProperty("label_color", "#999")  # 存原始浅色值，供 refresh_labels 重映射
        layout.addWidget(lbl, alignment=QtCore.Qt.AlignCenter)
        return

    for idx, grp in enumerate(groups):
        # 组间分割线（非第一组）
        if idx > 0:
            sep = QtWidgets.QFrame()
            sep.setFrameShape(QtWidgets.QFrame.HLine)
            sep.setStyleSheet(f"QFrame {{ color:{sep_color}; }}")
            layout.addWidget(sep)

        days_str = grp.get("days_str", "")
        times = grp.get("times", [])

        # 日期行
        day_row = QtWidgets.QWidget()
        drl = QtWidgets.QHBoxLayout(day_row)
        drl.setContentsMargins(0, 0, 0, 0); drl.setSpacing(8)
        cal_icon = QtWidgets.QLabel()
        cal_icon.setPixmap(QtGui.QIcon(f"{base}/calendar.svg").pixmap(21, 21))
        drl.addWidget(cal_icon, alignment=QtCore.Qt.AlignVCenter)
        day_lbl = QtWidgets.QLabel(days_str)
        day_lbl.setStyleSheet(f"font-size:14px; color:{day_color};")
        day_lbl.setProperty("label_color", "#555")  # 存原始浅色值，供 refresh_labels 重映射
        drl.addWidget(day_lbl, 1)
        drl.addStretch()
        layout.addWidget(day_row)

        # 分割线
        inner_sep = QtWidgets.QFrame()
        inner_sep.setFrameShape(QtWidgets.QFrame.HLine)
        inner_sep.setStyleSheet(f"QFrame {{ color:{sep_color}; }}")
        layout.addWidget(inner_sep)

        # 时间行
        time_row = QtWidgets.QWidget()
        trl = QtWidgets.QHBoxLayout(time_row)
        trl.setContentsMargins(0, 0, 0, 0); trl.setSpacing(8)
        clk_icon = QtWidgets.QLabel()
        clk_icon.setPixmap(QtGui.QIcon(f"{base}/clock.svg").pixmap(21, 21))
        trl.addWidget(clk_icon, alignment=QtCore.Qt.AlignVCenter)
        time_lbl = QtWidgets.QLabel("  →  ".join(times) if times else "")
        time_lbl.setStyleSheet(f"font-size:15px; color:{time_color}; font-weight:bold;")
        time_lbl.setProperty("label_color", "#333")  # 存原始浅色值，供 refresh_labels 重映射
        trl.addWidget(time_lbl, 1)
        trl.addStretch()
        layout.addWidget(time_row)


def _rules_card(app, grid):
    rc = frm()
    rv = QtWidgets.QVBoxLayout(rc)
    rv.setContentsMargins(14, 12, 14, 12)
    rv.setSpacing(8)

    base = str(_base_dir() / "icons")
    # 标题
    title_row = QtWidgets.QWidget()
    tl = QtWidgets.QHBoxLayout(title_row)
    tl.setContentsMargins(0, 0, 0, 0)
    ic = QtWidgets.QLabel()
    ic.setPixmap(QtGui.QIcon(f"{base}/rule.svg").pixmap(20, 20))
    tl.addWidget(ic)
    tl.addWidget(lbl("智能温控规则", bold=True, size=14))
    tl.addStretch()
    rv.addWidget(title_row)

    # ── 规则表格 + 编辑按钮（包在一个框内）──
    rule_box = QtWidgets.QFrame()
    rule_box.setStyleSheet("QFrame { border:1px solid #DEDEDE; border-radius:8px; }")
    rbl = QtWidgets.QVBoxLayout(rule_box)
    rbl.setContentsMargins(0, 0, 0, 0)
    rbl.setSpacing(0)

    app._rules_table = QtWidgets.QTableWidget()
    app._rules_table.setColumnCount(2)
    app._rules_table.setHorizontalHeaderLabels(["室外温度范围", "空调动作"])
    app._rules_table.horizontalHeader().setStretchLastSection(True)
    app._rules_table.horizontalHeader().setSectionResizeMode(0, QtWidgets.QHeaderView.Stretch)
    app._rules_table.verticalHeader().setVisible(False)
    app._rules_table.setEditTriggers(QtWidgets.QAbstractItemView.NoEditTriggers)
    app._rules_table.setSelectionMode(QtWidgets.QAbstractItemView.NoSelection)
    app._rules_table.setVerticalScrollBarPolicy(QtCore.Qt.ScrollBarAlwaysOff)
    app._rules_table.setHorizontalScrollBarPolicy(QtCore.Qt.ScrollBarAlwaysOff)
    app._rules_table.horizontalHeader().setStyleSheet(
        "QHeaderView::section { background:#F5F8FC; border:none; border-bottom:1px solid #DEDEDE; padding:4px; font-weight:bold; }"
    )
    app._rules_table.setStyleSheet("QTableWidget { border:none; }")
    rbl.addWidget(app._rules_table)

    # 编辑按钮（在框内底部）
    btn = QtWidgets.QPushButton(" 编辑规则")
    btn.setIcon(QtGui.QIcon(f"{base}/edit.svg"))
    btn.setCursor(QtCore.Qt.PointingHandCursor)
    btn.clicked.connect(app._edit_rules)
    rbl.addWidget(btn)

    rv.addWidget(rule_box)

    # ── 自动调温开关 ──
    adj_row = QtWidgets.QWidget()
    al = QtWidgets.QHBoxLayout(adj_row); al.setContentsMargins(0, 0, 0, 0); al.setSpacing(6)
    al.addWidget(lbl("每2小时根据室外温度自动调整", color="gray"))
    al.addStretch()
    app._adjust_sw = toggle("自动调温")
    app._adjust_sw.setChecked(_cfg.config.get("auto_adjust", True))
    app._adjust_sw.clicked.connect(app._save_adjust)
    al.addWidget(app._adjust_sw)
    rv.addWidget(adj_row)

    app._refresh_rules_display()
    grid.addWidget(rc, 1, 1)
