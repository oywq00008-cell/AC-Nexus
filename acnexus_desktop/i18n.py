"""AC-Nexus i18n — 外挂 JSON 语言库，不改源码即可切换 GUI 语言

用法:
    from i18n import load_lang, apply_lang

    load_lang("en")              # 加载 langs/en.json
    apply_lang(main_window)      # 递归替换所有控件文字

设计原则:
    - 精确匹配：控件 .text() 键必须与 JSON key 完全一致
    - 含 {format} 的字符串：直接替换（Python .format 语法）
    - 未匹配项：保持原样（中文兜底）
    - 表格/列表数据（台风名、品牌名等）不翻译，只翻译 UI 标签
"""

import json
from pathlib import Path
from PySide6 import QtWidgets

_LANG_DIR = Path(__file__).resolve().parent.parent / "langs"
_TRANSLATIONS = {}  # zh → en 映射
_CURRENT_LANG = "zh"


def load_lang(lang_code: str) -> bool:
    """加载语言包，成功返回 True。路径自动解析为 langs/{lang_code}.json。
    "zh" 为内置中文模式，无需 JSON 文件。"""
    global _TRANSLATIONS, _CURRENT_LANG
    _CURRENT_LANG = lang_code
    if lang_code == "zh":
        return True
    path = _LANG_DIR / f"{lang_code}.json"
    if not path.exists():
        return False
    _TRANSLATIONS = json.loads(path.read_text(encoding="utf-8"))
    return True


def tr(text: str) -> str:
    """翻译单条文本。zh→en 正向，en→zh 反向。未匹配时返回原文兜底"""
    if _CURRENT_LANG == "zh":
        return text
    return _TRANSLATIONS.get(text, text)


def apply_lang(widget: QtWidgets.QWidget):
    """递归遍历 widget 树，替换所有控件的显示文本。

    正向: _TRANSLATIONS[中文] → 英文
    反向（切回中文）: _TRANSLATIONS 的值 → 键
    
    覆盖: QLabel, QPushButton, QCheckBox, QRadioButton,
          QComboBox items, QGroupBox, QTabWidget tabs,
          QMenu actions, QToolButton, QMenuBar actions
    """
    # 构建查找字典
    if _CURRENT_LANG == "zh":
        lookup = {v: k for k, v in _TRANSLATIONS.items()} if _TRANSLATIONS else {}
        if not lookup:
            return
    else:
        lookup = _TRANSLATIONS

    def _update_widget(w):
        if isinstance(w, (QtWidgets.QLabel, QtWidgets.QPushButton,
                          QtWidgets.QCheckBox, QtWidgets.QRadioButton,
                          QtWidgets.QToolButton)):
            txt = w.text()
            if txt and txt in lookup:
                w.setText(lookup[txt])
        elif isinstance(w, QtWidgets.QComboBox):
            idx = w.currentIndex()
            w.blockSignals(True)
            for i in range(w.count()):
                txt = w.itemText(i)
                if txt and txt in lookup:
                    w.setItemText(i, lookup[txt])
            w.setCurrentIndex(idx)  # 翻译后恢复索引，防 Qt 内部重置
            w.blockSignals(False)
        elif isinstance(w, QtWidgets.QGroupBox):
            txt = w.title()
            if txt and txt in lookup:
                w.setTitle(lookup[txt])
        elif isinstance(w, QtWidgets.QMenu):
            txt = w.title()
            if txt and txt in lookup:
                w.setTitle(lookup[txt])
            for action in w.actions():
                txt = action.text()
                if txt and txt in lookup:
                    action.setText(lookup[txt])
        elif isinstance(w, QtWidgets.QMenuBar):
            for action in w.actions():
                txt = action.text()
                if txt and txt in lookup:
                    action.setText(lookup[txt])
        elif isinstance(w, QtWidgets.QTabWidget):
            for i in range(w.count()):
                txt = w.tabText(i)
                if txt and txt in lookup:
                    w.setTabText(i, lookup[txt])

    _update_widget(widget)
    for child in widget.findChildren(QtWidgets.QWidget):
        _update_widget(child)
