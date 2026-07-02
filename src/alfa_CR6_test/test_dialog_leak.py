# coding: utf-8

"""
Regression / measurement test for the ModalMessageBox memory accumulation.

It reproduces, on THIS pc, the growth caused by opening alarm dialogs the way
MainWindow.open_alert_dialog() does:

    _msgbox = ModalMessageBox(parent=self, msg=msg, title=title, ...)   # show(), non-blocking

ModalMessageBox has NO Qt.WA_DeleteOnClose and is parented to main_window, so
closing it only hides it: the C++ QWidget tree (box + buttons + label + help
QPixmap) stays alive as a child of the parent for the whole process lifetime.

Run from the project root with the project venv (needs PyQt5 + redis etc.).

  * as a unittest module:

        QT_QPA_PLATFORM=offscreen PYTHONPATH=/opt/PROJECTS/alfa_cr6/src \
            /opt/alfa_cr6/venv/bin/python3 -m unittest \
            src/alfa_CR6_test/test_dialog_leak.py -v

  * as a plain script (same thing, uses the __main__ block at the bottom):

        QT_QPA_PLATFORM=offscreen PYTHONPATH=/opt/PROJECTS/alfa_cr6/src \
            /opt/alfa_cr6/venv/bin/python3 \
            src/alfa_CR6_test/test_dialog_leak.py

  * with a different number of dialogs (default 50):

        DIALOG_LEAK_N=200 QT_QPA_PLATFORM=offscreen \
            PYTHONPATH=/opt/PROJECTS/alfa_cr6/src \
            /opt/alfa_cr6/venv/bin/python3 -m unittest \
            src/alfa_CR6_test/test_dialog_leak.py -v

The three tests are complementary:
  * test_dialogs_accumulate_without_deleteonclose -> documents the CURRENT leak
    (after N open+close, N boxes are still allocated under the parent).
  * test_deleteonclose_releases_dialogs -> shows the TARGET behaviour: with
    WA_DeleteOnClose the count returns to baseline. This is what the fix in
    ModalMessageBox.__init__ must achieve, and it proves the measurement is
    able to tell a leak from a clean release.
  * test_frozen_carousel_dialog_released_on_ok -> the FIX verified through
    the real production path of the "carousel is paused" dialog
    (wait_for_carousel_not_frozen -> MainWindow.open_frozen_dialog ->
    ok_callback=freeze_carousel, cb_args=[False]); refill is one of its
    triggers. It drives the actual MainWindow methods, clicking OK to run the
    real freeze_carousel(False) callback: since b313570/0ce0944 the click
    schedules deleteLater, so the boxes must be released, not retained.
"""

import os
import ctypes
import logging
import unittest
from collections import Counter

# must be set before any QApplication is constructed
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt5 import QtCore
from PyQt5.QtCore import Qt, QEvent
from PyQt5.QtWidgets import QApplication, QWidget, QMessageBox

from alfa_CR6_backend.globals import import_settings
from alfa_CR6_frontend.dialogs import ModalMessageBox

# QtWebEngineWidgets must be imported (and AA_ShareOpenGLContexts set) BEFORE any
# QApplication exists. Importing MainWindow pulls in browser_page -> WebEngine,
# so do it here at module load (the app is only created later in setUpClass),
# not lazily inside the test where it would be too late.
QApplication.setAttribute(Qt.AA_ShareOpenGLContexts)
try:
    from PyQt5 import QtWebEngineWidgets  # noqa: F401  pylint: disable=unused-import
    from alfa_CR6_frontend.main_window import MainWindow as MAIN_WINDOW_CLS
except Exception:  # pylint: disable=broad-except
    MAIN_WINDOW_CLS = None


N_DIALOGS = int(os.environ.get("DIALOG_LEAK_N", "50"))


# --------------------------------------------------------------------------- #
# measurement helpers
# --------------------------------------------------------------------------- #
def count_msgboxes(parent):
    """QMessageBox instances still allocated as children of `parent`."""
    return len(parent.findChildren(QMessageBox))


def widget_histogram(app):
    """process-wide count of live QWidget subclasses, by class name."""
    return Counter(type(w).__name__ for w in app.allWidgets())


def malloc_in_use():
    """glibc malloc bytes currently in use (uordblks). None if unavailable.

    This box runs glibc 2.31 -> no mallinfo2; the legacy mallinfo has int
    fields, fine for the small deltas measured here.
    """
    class _MallInfo(ctypes.Structure):
        _fields_ = [(n, ctypes.c_int) for n in (
            "arena", "ordblks", "smblks", "hblks", "hblkhd", "usmblks",
            "fsmblks", "uordblks", "fordblks", "keepcost")]
    try:
        libc = ctypes.CDLL("libc.so.6")
        libc.mallinfo.restype = _MallInfo
        return int(libc.mallinfo().uordblks)
    except Exception:  # pylint: disable=broad-except
        return None


def malloc_trim():
    try:
        ctypes.CDLL("libc.so.6").malloc_trim(0)
    except Exception:  # pylint: disable=broad-except
        pass


def rss_kb():
    """resident set size in kB (noisy: glibc retention; reference only)."""
    try:
        with open("/proc/self/status", "r") as f:
            for line in f:
                if line.startswith("VmRSS:"):
                    return int(line.split()[1])
    except Exception:  # pylint: disable=broad-except
        pass
    return None


def drain_deferred_deletes(app):
    """force processing of deleteLater()/WA_DeleteOnClose deletions."""
    app.processEvents()
    QApplication.sendPostedEvents(None, QEvent.DeferredDelete)
    app.processEvents()


# --------------------------------------------------------------------------- #
class _FakeApp(QApplication):
    """Minimal stand-in for the real Application: provides only the two hooks
    that MainWindow.open_frozen_dialog / open_alert_dialog reach for, so the
    real production methods can run without booting the whole app."""

    def __init__(self, argv):
        super().__init__(argv)
        self.carousel_frozen = False
        self.freeze_calls = []
        self.db_events = 0

    def freeze_carousel(self, flag):
        self.carousel_frozen = bool(flag)
        self.freeze_calls.append(flag)

    def insert_db_event(self, **kwargs):  # pylint: disable=unused-argument
        self.db_events += 1


# --------------------------------------------------------------------------- #
class DialogLeakTest(unittest.TestCase):

    app = None

    @classmethod
    def setUpClass(cls):
        # the production dialog code logs a warning per open/click; mute it so the
        # measurement report stays readable
        logging.disable(logging.WARNING)
        import_settings()  # makes get_res()/tr_() resolve real resource paths
        cls.app = QApplication.instance() or _FakeApp([])

    def _open_alert(self, parent, i, delete_on_close=False):
        """Builds the dialog exactly as open_alert_dialog() does, then closes it."""
        box = ModalMessageBox(parent=parent, msg="alarm %d" % i, title="ALERT")
        if delete_on_close:
            box.setAttribute(Qt.WA_DeleteOnClose)
        box.close()

    def _report(self, tag, parent, base):
        drain_deferred_deletes(self.app)
        malloc_trim()
        leaked = count_msgboxes(parent)
        hist = widget_histogram(self.app)
        # isinstance-based: ModalMessageBox is a QMessageBox subclass, so the
        # exact-class-name histogram would miss it (reports it as ModalMessageBox)
        boxes_process = sum(isinstance(w, QMessageBox) for w in self.app.allWidgets())
        print(
            "\n[%s] N=%d  ->  QMessageBox under parent: %d (baseline %d)\n"
            "          all QMessageBox(process): %d | QPushButton: %d | QLabel: %d\n"
            "          malloc uordblks delta: %s bytes | RSS delta: %s kB"
            % (
                tag, N_DIALOGS, leaked, base["boxes"],
                boxes_process,
                hist.get("QPushButton", 0),
                hist.get("QLabel", 0),
                _delta(malloc_in_use(), base["malloc"]),
                _delta(rss_kb(), base["rss"]),
            )
        )
        return leaked

    def _baseline(self, parent):
        drain_deferred_deletes(self.app)
        malloc_trim()
        return {
            "boxes": count_msgboxes(parent),
            "malloc": malloc_in_use(),
            "rss": rss_kb(),
        }

    def test_dialogs_accumulate_without_deleteonclose(self):
        """CURRENT behaviour: N open+close leave N boxes allocated."""
        parent = QWidget()
        base = self._baseline(parent)

        for i in range(N_DIALOGS):
            self._open_alert(parent, i, delete_on_close=False)

        leaked = self._report("LEAK", parent, base)
        # every closed dialog is still alive under the parent
        self.assertEqual(
            leaked, base["boxes"] + N_DIALOGS,
            "expected all %d closed dialogs to remain allocated (leak)" % N_DIALOGS,
        )

    def test_deleteonclose_releases_dialogs(self):
        """TARGET behaviour: with WA_DeleteOnClose the count returns to baseline."""
        parent = QWidget()
        base = self._baseline(parent)

        for i in range(N_DIALOGS):
            self._open_alert(parent, i, delete_on_close=True)

        leaked = self._report("CLEAN", parent, base)
        self.assertLessEqual(
            leaked, base["boxes"],
            "WA_DeleteOnClose dialogs should be destroyed on close, not retained",
        )

    def test_frozen_carousel_dialog_released_on_ok(self):
        """The FIX, exercised through the REAL 'carousel is paused' path.

        wait_for_carousel_not_frozen(freeze=True) -> MainWindow.open_frozen_dialog
        (default branch) -> ok_callback=freeze_carousel, cb_args=[False] ->
        ModalMessageBox. Refill is one of the ~12 triggers of this dialog.
        Pressing OK runs on_button_clicked, which since b313570/0ce0944
        schedules deleteLater: no box may survive the click.
        """
        if not hasattr(self.app, "freeze_calls"):
            self.skipTest("needs _FakeApp (freeze_carousel/insert_db_event hooks)")
        if MAIN_WINDOW_CLS is None:
            self.skipTest("MainWindow / QtWebEngineWidgets unavailable")
        MainWindow = MAIN_WINDOW_CLS

        class _FakeMainWindow(QWidget):
            # bind the REAL production methods so the dialog is built exactly as
            # in main_window.py (formatting, callback wiring, ModalMessageBox)
            open_alert_dialog = MainWindow.open_alert_dialog
            open_frozen_dialog = MainWindow.open_frozen_dialog

        mw = _FakeMainWindow()
        base = self._baseline(mw)
        self.app.freeze_calls.clear()

        for i in range(N_DIALOGS):
            before = set(mw.findChildren(QMessageBox))
            mw.open_frozen_dialog(
                message_args=("station %d" % i,),
                message_fmt="please refill, then hit OK",   # a refill-style trigger
                title="INFO",
            )
            for box in mw.findChildren(QMessageBox):
                if box in before:
                    continue
                # operator presses the visible OK -> on_button_clicked runs
                # ok_callback = freeze_carousel(False), then the box hides.
                # NB: dispatch keys off objectName 'ok' (set in ModalMessageBox),
                # NOT the QMessageBox.Ok enum: self.buttons() ordering is platform
                # dependent, so the enum-mapped button is not necessarily the one
                # labelled OK on screen.
                ok_btn = next(
                    (b for b in box.buttons() if b.objectName().lower() == "ok"),
                    None,
                )
                if ok_btn is not None:
                    ok_btn.click()
                else:
                    box.close()

        leaked = self._report("FROZEN", mw, base)
        self.assertLessEqual(
            leaked, base["boxes"],
            "frozen-carousel dialogs must be released after OK "
            "(deleteLater scheduled by on_button_clicked)",
        )
        # proof the real ok_callback wiring ran: every OK -> freeze_carousel(False)
        self.assertEqual(self.app.freeze_calls, [False] * N_DIALOGS)


def _delta(now, then):
    if now is None or then is None:
        return "n/a"
    return "%+d" % (now - then)


if __name__ == "__main__":
    unittest.main(verbosity=2)
