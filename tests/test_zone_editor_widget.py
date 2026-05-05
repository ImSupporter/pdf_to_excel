import os


class _Point:
    def __init__(self, x=0, y=0):
        self._x = x
        self._y = y

    def x(self):
        return self._x

    def y(self):
        return self._y


class _ContextEvent:
    def pos(self):
        return _Point(10, 10)

    def globalPos(self):
        return _Point(100, 100)


class _Menu:
    executed_at = None

    def __init__(self, parent=None):
        self._actions = []

    def addAction(self, text, callback):
        self._actions.append((text, callback))

    def actions(self):
        return self._actions

    def exec(self, pos):
        type(self).executed_at = pos


def test_context_menu_event_uses_qcontextmenu_global_pos(monkeypatch):
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    from PyQt6.QtWidgets import QApplication
    from ui import zone_editor_widget
    from ui.zone_editor_widget import ZoneEditorWidget

    app = QApplication.instance() or QApplication([])
    widget = ZoneEditorWidget()
    monkeypatch.setattr(widget, "_find_target", lambda _sx, _sy: ("v", 0))
    monkeypatch.setattr(zone_editor_widget, "QMenu", _Menu)

    widget.contextMenuEvent(_ContextEvent())

    assert _Menu.executed_at is not None


def test_find_target_returns_hline_in_clicked_column():
    from ui.zone_editor_widget import ZoneEditorWidget

    widget = ZoneEditorWidget.__new__(ZoneEditorWidget)
    widget._page_w = 300.0
    widget._vlines = [100.0, 200.0]
    widget._hlines = {
        0: [50.0],
        1: [50.0],
        2: [50.0],
    }
    widget._header_start = -100.0
    widget._header_end = -90.0
    widget._data_start = -80.0
    widget._data_end = -70.0

    target = widget._find_target(150.0 * 1.5, 50.0 * 1.5)

    assert target == ("h", 1, 0)
