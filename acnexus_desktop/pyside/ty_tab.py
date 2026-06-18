"""预警信息 Tab 构建器 + 数据渲染函数（纯UI操作，需在主线程调用）"""

import json
from datetime import datetime
from pathlib import Path

from PySide6 import QtCore, QtGui, QtWidgets

import acnexus_core.config as _cfg
from ._utils import frm, lbl, toggle


def _draw_forecast_chart(detail, dist, dark=False):
    """绘制台风路径预报图 → QPixmap"""
    pw, ph = 340, 110
    bg_color = QtGui.QColor("#2B2B2B" if dark else "#F2F2F2")
    pix = QtGui.QPixmap(pw, ph)
    pix.fill(bg_color)
    p = QtGui.QPainter(pix)
    p.setRenderHint(QtGui.QPainter.Antialiasing)

    # 收集坐标点
    loc_lat, loc_lon = _cfg.LOCATION["lat"], _cfg.LOCATION["lon"]
    loc_name = _cfg.LOCATION["name"]
    fc_pts = [(detail["lat"], detail["lon"], "当前")]
    for fc in detail.get("forecasts", [])[:4]:
        fc_pts.append((fc["lat"], fc["lon"], f"+{fc['hours']}h"))
    all_pts = fc_pts + [(loc_lat, loc_lon, loc_name)]
    lats = [p[0] for p in all_pts]; lons = [p[1] for p in all_pts]
    min_lat, max_lat = min(lats), max(lats)
    min_lon, max_lon = min(lons), max(lons)
    range_lat = max_lat - min_lat or 0.1
    range_lon = max_lon - min_lon or 0.1

    def geo2cv(lat, lon):
        x = 30 + (lon - min_lon) / range_lon * 280
        y = 10 + (max_lat - lat) / range_lat * 85
        return x, y

    # 预报路径连线（虚线）
    dash_pen = QtGui.QPen(QtGui.QColor("#666"), 1, QtCore.Qt.DashLine)
    p.setPen(dash_pen)
    for i in range(len(fc_pts) - 1):
        p.drawLine(int(geo2cv(fc_pts[i][0], fc_pts[i][1])[0]),
                    int(geo2cv(fc_pts[i][0], fc_pts[i][1])[1]),
                    int(geo2cv(fc_pts[i+1][0], fc_pts[i+1][1])[0]),
                    int(geo2cv(fc_pts[i+1][0], fc_pts[i+1][1])[1]))

    # 当前 → 你家连线 + 距离标注
    x0, y0 = geo2cv(detail["lat"], detail["lon"])
    x1, y1 = geo2cv(loc_lat, loc_lon)
    p.setPen(QtGui.QPen(QtGui.QColor("#E67E22"), 1, QtCore.Qt.DashLine))
    p.drawLine(int(x0), int(y0), int(x1), int(y1))
    mx, my = (x0 + x1) / 2, (y0 + y1) / 2
    p.setPen(QtGui.QColor("#E67E22"))
    p.setFont(QtGui.QFont("", 8))
    p.drawText(int(mx - 40), int(my - 18), 80, 14, QtCore.Qt.AlignCenter, f"{dist}km")

    # 画预报点 + 标注
    for i, (lat, lon, label) in enumerate(fc_pts):
        x, y = geo2cv(lat, lon)
        if i == 0:
            p.setFont(QtGui.QFont("", 12))
            p.setPen(QtGui.QColor("#333"))
            p.drawText(int(x - 10), int(y + 4), 20, 16, QtCore.Qt.AlignCenter, "🌀")
        else:
            p.setBrush(QtGui.QColor("#888"))
            p.setPen(QtCore.Qt.NoPen)
            p.drawEllipse(QtCore.QPointF(x, y), 3, 3)
        p.setPen(QtGui.QColor("#999"))
        p.setFont(QtGui.QFont("", 8))
        p.drawText(int(x - 20), int(y - 16), 40, 12, QtCore.Qt.AlignCenter, label)

    # 画你家
    xh, yh = geo2cv(loc_lat, loc_lon)
    p.setBrush(QtGui.QColor("#3498DB"))
    p.setPen(QtCore.Qt.NoPen)
    p.drawEllipse(QtCore.QPointF(xh, yh), 3, 3)
    p.setPen(QtGui.QColor("#3498DB"))
    p.setFont(QtGui.QFont("", 8))
    p.drawText(int(xh - 20), int(yh - 14), 40, 12, QtCore.Qt.AlignCenter, loc_name)

    p.end()
    return pix


def _base_dir():
    return Path(__file__).resolve().parent.parent.parent


def build_ty_tab(app) -> QtWidgets.QWidget:
    w = QtWidgets.QWidget()
    layout = QtWidgets.QVBoxLayout(w)
    layout.setContentsMargins(5, 5, 5, 5)
    layout.setSpacing(6)

    # QSplitter 左右分栏
    splitter = QtWidgets.QSplitter(QtCore.Qt.Horizontal)
    splitter.addWidget(_typhoon_card(app))
    splitter.addWidget(_alert_card(app))
    splitter.setStretchFactor(0, 1)
    splitter.setStretchFactor(1, 1)
    splitter.setSizes([100000, 100000])  # 强制等宽
    layout.addWidget(splitter, 1)

    layout.addWidget(_bottom_bar(app))
    return w


def _typhoon_card(app):
    base = str(_base_dir() / "icons")
    left = frm()
    lv = QtWidgets.QVBoxLayout(left)
    lv.setContentsMargins(12, 10, 12, 10)
    lv.setSpacing(6)

    # 标题行
    tr = QtWidgets.QWidget()
    tl = QtWidgets.QHBoxLayout(tr)
    tl.setContentsMargins(0, 0, 0, 0)
    tl.setSpacing(6)
    ic = QtWidgets.QLabel()
    ic.setPixmap(QtGui.QIcon(f"{base}/typhoon.svg").pixmap(20, 20))
    tl.addWidget(ic)
    tl.addWidget(lbl("风暴监测", bold=True, size=14))
    app._ty_provider_cb = QtWidgets.QComboBox()
    app._ty_provider_cb.addItems(["西北太平洋台风", "北大西洋飓风"])
    app._ty_provider_cb.currentTextChanged.connect(app._on_ty_provider_change)
    tl.addWidget(app._ty_provider_cb)
    tl.addStretch()
    refresh_btn = QtWidgets.QPushButton()
    refresh_btn.setIcon(QtGui.QIcon(f"{base}/refresh.svg"))
    refresh_btn.setToolTip("刷新台风数据")
    refresh_btn.setFixedSize(28, 28)
    refresh_btn.clicked.connect(app._fetch_typhoon_all)
    tl.addWidget(refresh_btn)
    lv.addWidget(tr)

    app._ty_source_label = QtWidgets.QLabel("")
    app._ty_source_label.setStyleSheet("color:gray;")
    lv.addWidget(app._ty_source_label)
    app._update_ty_source_label()

    # 滚动内容
    app._ty_scroll = QtWidgets.QScrollArea()
    app._ty_scroll.setWidgetResizable(True)
    app._ty_content = QtWidgets.QWidget()
    app._ty_content_layout = QtWidgets.QVBoxLayout(app._ty_content)
    app._ty_scroll.setWidget(app._ty_content)
    lv.addWidget(app._ty_scroll)
    app._ty_content_layout.addStretch()
    app._ty_content_layout.addWidget(QtWidgets.QLabel("点击右侧刷新按钮获取台风信息"), alignment=QtCore.Qt.AlignCenter)
    app._ty_content_layout.addStretch()

    # 翻页
    nav = QtWidgets.QWidget()
    nl = QtWidgets.QHBoxLayout(nav)
    nl.setContentsMargins(0, 0, 0, 0)
    app._ty_prev = QtWidgets.QPushButton("← 上一页")
    app._ty_prev.clicked.connect(app._ty_prev_page)
    app._ty_page_lbl = QtWidgets.QLabel("")
    app._ty_next = QtWidgets.QPushButton("下一页 →")
    app._ty_next.clicked.connect(app._ty_next_page)
    nl.addWidget(app._ty_prev)
    nl.addStretch()
    nl.addWidget(app._ty_page_lbl)
    nl.addStretch()
    nl.addWidget(app._ty_next)
    lv.addWidget(nav)
    return left


def _alert_card(app):
    base = str(_base_dir() / "icons")
    right = frm()
    rv = QtWidgets.QVBoxLayout(right)
    rv.setContentsMargins(12, 10, 12, 10)
    rv.setSpacing(6)

    # 标题行
    tr2 = QtWidgets.QWidget()
    t2l = QtWidgets.QHBoxLayout(tr2)
    t2l.setContentsMargins(0, 0, 0, 0)
    t2l.setSpacing(6)
    ic = QtWidgets.QLabel()
    ic.setPixmap(QtGui.QIcon(f"{base}/warning.svg").pixmap(20, 20))
    t2l.addWidget(ic)
    t2l.addWidget(lbl("天气预警", bold=True, size=14))
    t2l.addStretch()
    refresh_btn = QtWidgets.QPushButton()
    refresh_btn.setIcon(QtGui.QIcon(f"{base}/refresh.svg"))
    refresh_btn.setToolTip("刷新预警数据")
    refresh_btn.setFixedSize(28, 28)
    refresh_btn.clicked.connect(app._fetch_weather_all)
    t2l.addWidget(refresh_btn)
    rv.addWidget(tr2)

    app._alert_source_label = QtWidgets.QLabel("")
    app._alert_source_label.setStyleSheet("color:gray;")
    rv.addWidget(app._alert_source_label)
    app._update_alert_source()

    # 滚动内容
    app._alert_scroll = QtWidgets.QScrollArea()
    app._alert_scroll.setWidgetResizable(True)
    app._alert_content = QtWidgets.QWidget()
    app._alert_content_layout = QtWidgets.QVBoxLayout(app._alert_content)
    app._alert_scroll.setWidget(app._alert_content)
    rv.addWidget(app._alert_scroll)
    app._alert_content_layout.addStretch()
    app._alert_content_layout.addWidget(QtWidgets.QLabel("点击右侧刷新按钮获取当地预警"), alignment=QtCore.Qt.AlignCenter)
    app._alert_content_layout.addStretch()

    # 翻页
    nav2 = QtWidgets.QWidget()
    n2l = QtWidgets.QHBoxLayout(nav2)
    n2l.setContentsMargins(0, 0, 0, 0)
    app._alert_prev = QtWidgets.QPushButton("← 上一页")
    app._alert_prev.clicked.connect(app._alert_prev_page)
    app._alert_page_lbl = QtWidgets.QLabel("")
    app._alert_next = QtWidgets.QPushButton("下一页 →")
    app._alert_next.clicked.connect(app._alert_next_page)
    n2l.addWidget(app._alert_prev)
    n2l.addStretch()
    n2l.addWidget(app._alert_page_lbl)
    n2l.addStretch()
    n2l.addWidget(app._alert_next)
    rv.addWidget(nav2)
    return right


def _bottom_bar(app):
    bot = QtWidgets.QWidget(); bl = QtWidgets.QHBoxLayout(bot)
    bl.setContentsMargins(0, 0, 0, 0); bl.setSpacing(8)
    km = _cfg.config.get("typhoon_alert_km", 800)
    status_text = f"风暴预警距离 {km}km 生效中" if _cfg.config.get("typhoon_alert_enabled", True) else f"风暴预警距离 {km}km (提醒已关)"

    # 预警距离 框
    grp1 = QtWidgets.QFrame()
    grp1.setObjectName("ty_grp1")
    grp1.setStyleSheet("QFrame#ty_grp1 { background:white; border:1px solid #DEDEDE; border-radius:6px; } QFrame#ty_grp1 QWidget { background-color:transparent; }")
    g1l = QtWidgets.QHBoxLayout(grp1); g1l.setContentsMargins(6, 2, 6, 2); g1l.setSpacing(6)
    app._ty_status_label = QtWidgets.QLabel(status_text); g1l.addWidget(app._ty_status_label)
    b = QtWidgets.QPushButton("修改"); b.setFixedWidth(50); b.setFixedHeight(24)
    b.setObjectName("ty_modify_btn")
    b.setStyleSheet("QPushButton#ty_modify_btn { border:1px solid #CCC; border-radius:4px; background:#F5F5F5; } QPushButton#ty_modify_btn:hover { background:#E8E8E8; }")
    b.clicked.connect(app._edit_ty_alert); g1l.addWidget(b)
    bl.addWidget(grp1)

    # 自动关机 框
    grp2 = QtWidgets.QFrame()
    grp2.setObjectName("ty_grp2")
    grp2.setStyleSheet("QFrame#ty_grp2 { background:white; border:1px solid #DEDEDE; border-radius:6px; } QFrame#ty_grp2 QWidget { background-color:transparent; }")
    g2l = QtWidgets.QHBoxLayout(grp2); g2l.setContentsMargins(6, 2, 6, 2); g2l.setSpacing(4)
    g2l.addWidget(QtWidgets.QLabel("风暴<100km自动关闭空调"))
    app._ty_ac_off_sw = toggle()
    app._ty_ac_off_sw.setChecked(_cfg.config.get("typhoon_ac_off", True))
    app._ty_ac_off_sw.clicked.connect(app._on_ac_off_toggle); g2l.addWidget(app._ty_ac_off_sw)
    bl.addWidget(grp2)

    bl.addStretch()
    b = QtWidgets.QPushButton("🌍 卫星云图"); b.clicked.connect(app._open_zoom_earth); bl.addWidget(b)
    app._ty_time_label = QtWidgets.QLabel(""); bl.addWidget(app._ty_time_label)
    return bot


# ── 渲染函数（必须在主线程调用）──

def render_weather(app):
    w = app._weather_data
    try:
        if w:
            from .ac_tab import weather_icon_path
            path = weather_icon_path(w.get("text", ""))
            app._wx_icon.setPixmap(QtGui.QIcon(path).pixmap(72, 72))
            app._wx_location.setText(_cfg.LOCATION.get("name", "--"))
            app._wx_temp.setText(f"{w['temp']}°C")
            app._wx_text.setText(w.get("text", ""))
            app._wx_feels_val.setText(f"{w.get('feelsLike','--')}°C")
            app._wx_humid_val.setText(f"{w.get('humidity','--')}%")
            wind = f"{w.get('windDir','')} {w.get('windScale','')}级".strip()
            app._wx_wind_val.setText(wind or "--")
            obs = w.get("obsTime", "")[:16] if w.get("obsTime") else ""
            app._wx_update.setText(f"更新于 {obs}" if obs else "更新于 --:--")
        else:
            app._wx_icon.clear()
            app._wx_location.setText(_cfg.LOCATION.get("name", "--"))
            app._wx_temp.setText("—°C")
            app._wx_text.setText("无法获取天气")
            app._wx_feels_val.setText("--°C")
            app._wx_humid_val.setText("--%")
            app._wx_wind_val.setText("--")
            app._wx_update.setText("请检查天气 API 配置")
    except Exception as e:
        print(f"[render_weather] ERROR: {e}")
        import traceback; traceback.print_exc()


def render_typhoon(app):
    app._ty_page = 0; _do_render_typhoon(app)


def _do_render_typhoon(app):
    while app._ty_content_layout.count():
        w = app._ty_content_layout.takeAt(0).widget()
        if w: w.deleteLater()
    if not app._ty_data:
        provider = _cfg.config.get("typhoon_provider", "nmc")
        msg = "北大西洋当前无活跃飓风 ✅" if provider == "nhc" else "西北太平洋当前无活跃台风 ✅"
        app._ty_content_layout.addStretch()
        app._ty_content_layout.addWidget(QtWidgets.QLabel(msg), alignment=QtCore.Qt.AlignCenter)
        app._ty_content_layout.addStretch()
        app._ty_prev.hide(); app._ty_next.hide(); app._ty_page_lbl.hide()
        return

    PER = 2; total = len(app._ty_data); pages = max(1, (total + PER - 1) // PER)
    start = app._ty_page * PER; page_data = app._ty_data[start:start + PER]
    if pages > 1:
        app._ty_prev.show(); app._ty_next.show(); app._ty_page_lbl.show()
    else:
        app._ty_prev.hide(); app._ty_next.hide(); app._ty_page_lbl.hide()

    filled = 0
    for i, t in enumerate(page_data):
        if i > 0:
            sep = QtWidgets.QFrame()
            sep.setFrameShape(QtWidgets.QFrame.HLine)
            sep.setStyleSheet("QFrame { color:#DEDEDE; }")
            app._ty_content_layout.addWidget(sep)
        detail = t.get("detail")
        if not detail:
            continue

        from acnexus_core.typhoon import calc_distance
        dist = calc_distance(_cfg.LOCATION["lat"], _cfg.LOCATION["lon"],
                             detail["lat"], detail["lon"])
        alert = dist < _cfg.config.get("typhoon_alert_km", 800)
        status = "⚠️ 预警" if alert else "✅ 安全"
        status_color = "#E74C3C" if alert else "#27AE60"

        card = frm(); cl = QtWidgets.QVBoxLayout(card); cl.setContentsMargins(8, 4, 8, 4)

        # 标题行
        header = QtWidgets.QWidget(); hl = QtWidgets.QHBoxLayout(header); hl.setContentsMargins(0, 0, 0, 0)
        hl.addWidget(lbl(f"🌀 {detail['cn']}  {detail['eng']}", bold=True, size=12))
        hl.addWidget(lbl(f"#{detail['code']}", color="gray", size=10))
        hl.addStretch()
        hl.addWidget(lbl(status, bold=True, color=status_color, size=10))
        cl.addWidget(header)

        # 详细信息
        cat = detail.get("cat", detail.get("category", ""))
        press = detail.get("pressure", "?")
        wind = detail.get("wind", detail.get("speed", "?"))
        cl.addWidget(lbl(f"等级: {cat}  |  气压: {press}hPa  |  风速: {wind}m/s", size=10))

        lon = detail["lon"]
        lon_str = f"{abs(lon):.1f}°{'W' if lon < 0 else 'E'}" if lon < 0 else f"{lon}°E"
        direction = detail.get("direction", "?")
        speed = detail.get("speed", "?")
        cl.addWidget(lbl(f"位置: {detail['lat']}°N, {lon_str}  |  移向: {direction}  |  移速: {speed}km/h", size=10))

        dist_trend = ""
        if detail.get("forecasts"):
            last_fc = detail["forecasts"][-1]
            dist_far = calc_distance(_cfg.LOCATION["lat"], _cfg.LOCATION["lon"],
                                     last_fc["lat"], last_fc["lon"])
            # 跨半球（经度差 > 120°）时不判断方向——球面最短距会绕反
            lon_diff = abs(detail["lon"] - _cfg.LOCATION["lon"])
            if lon_diff > 180:
                lon_diff = 360 - lon_diff
            if lon_diff < 120:
                diff = dist_far - dist
                if diff < -30:
                    dist_trend = "  🔴 正在靠近"
                elif diff > 30:
                    dist_trend = "  🟢 正在远离"
                else:
                    dist_trend = "  ⚪ 徘徊"

        cl.addWidget(lbl(f"📏 距你 {dist:.0f} km{dist_trend}", bold=True,
            color="#E74C3C" if dist < 200 else ("#E67E22" if dist < 800 else "gray")))
        # 路径预报图
        if detail.get("forecasts"):
            chart_lbl = QtWidgets.QLabel()
            chart_lbl.setPixmap(_draw_forecast_chart(detail, int(dist)))
            chart_lbl.setFixedHeight(110)
            cl.addWidget(chart_lbl)

        app._ty_content_layout.addWidget(card, 1)
        filled += 1

    # 不足 PER 条时用空白占位保持高度比例
    for i in range(filled, PER):
        if i > 0:
            sep = QtWidgets.QFrame()
            sep.setFrameShape(QtWidgets.QFrame.HLine)
            sep.setStyleSheet("QFrame { color:#DEDEDE; }")
            app._ty_content_layout.addWidget(sep)
        spacer = QtWidgets.QWidget()
        app._ty_content_layout.addWidget(spacer, 1)

    app._ty_page_lbl.setText(f"第 {app._ty_page + 1}/{pages} 页" if pages > 1 else "")
    t = datetime.now().strftime("%H:%M"); app._ty_time_label.setText(f"数据更新: {t}")


def render_alerts(app):
    app._alert_page = 0; _do_render_alerts(app)


def _do_render_alerts(app):
    while app._alert_content_layout.count():
        w = app._alert_content_layout.takeAt(0).widget()
        if w: w.deleteLater()
    if not app._alerts_data:
        app._alert_content_layout.addStretch()
        app._alert_content_layout.addWidget(QtWidgets.QLabel("✅ 暂无预警信息"), alignment=QtCore.Qt.AlignCenter)
        app._alert_content_layout.addStretch()
        app._alert_prev.hide(); app._alert_next.hide(); app._alert_page_lbl.hide()
        return
    sev_order = {"extreme": 0, "severe": 1, "moderate": 2, "minor": 3}
    alerts = sorted(app._alerts_data, key=lambda a: sev_order.get(a.get("severity", ""), 99))
    sev_cn = {"extreme": "红色", "severe": "橙色", "moderate": "黄色", "minor": "蓝色"}
    sev_color = {"extreme": "#E74C3C", "severe": "#E67E22", "moderate": "#F1C40F", "minor": "#3498DB"}
    PER = 3; total = len(alerts); pages = max(1, (total + PER - 1) // PER)
    start = app._alert_page * PER
    filled = 0
    for i, a in enumerate(alerts[start:start + PER]):
        if i > 0:
            sep = QtWidgets.QFrame()
            sep.setFrameShape(QtWidgets.QFrame.HLine)
            sep.setStyleSheet("QFrame { color:#DEDEDE; }")
            app._alert_content_layout.addWidget(sep)
        sev = a.get("severity", "minor")
        card = frm(); cl = QtWidgets.QVBoxLayout(card); cl.setContentsMargins(8, 4, 8, 4)
        prefix = f"{sev_cn[sev]}预警 " if sev in sev_cn else ""
        cl.addWidget(lbl(f"{prefix}{a.get('headline', '')}", bold=True, color=sev_color.get(sev, "#888")))
        if a.get("senderName"): cl.addWidget(lbl(a["senderName"], color="gray"))
        if a.get("description"):
            desc = QtWidgets.QLabel(a["description"])
            desc.setWordWrap(True)
            cl.addWidget(desc)
        eff = (a.get("effectiveTime", "")[:16]).replace("T", " ")
        exp = (a.get("expireTime", "")[:16]).replace("T", " ")
        if eff and exp: cl.addWidget(lbl(f"📅 {eff} → {exp}", color="gray"))
        app._alert_content_layout.addWidget(card, 1)
        filled += 1
    # 不足 PER 条时用空白占位保持高度比例
    for i in range(filled, PER):
        if i > 0:
            sep = QtWidgets.QFrame()
            sep.setFrameShape(QtWidgets.QFrame.HLine)
            sep.setStyleSheet("QFrame { color:#DEDEDE; }")
            app._alert_content_layout.addWidget(sep)
        spacer = QtWidgets.QWidget()
        app._alert_content_layout.addWidget(spacer, 1)
    app._alert_page_lbl.setText(f"第 {app._alert_page + 1}/{pages} 页" if pages > 1 else "")
    if pages > 1:
        app._alert_prev.show(); app._alert_next.show(); app._alert_page_lbl.show()
    else:
        app._alert_prev.hide(); app._alert_next.hide(); app._alert_page_lbl.hide()
