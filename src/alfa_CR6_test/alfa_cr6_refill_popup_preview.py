r"""Preview all 21 scale-refill popups directly from the project sources.

Activate the project's Python environment, then run from the repository root
in a terminal with access to a graphical desktop session:

    python3 src/alfa_CR6_test/alfa_cr6_refill_popup_preview.py

No new wheel installation is required. The window inherits MainWindow's style
and uses the real InputDialog with sample data, without connecting to the machine.
Use Previous/Next or the popup menu to select a popup. The Larger messages
checkbox lets you compare both layouts. Use the Language menu to switch popup
localizations without changing the application's saved configuration.

Options (append to the launch command):

    --large                   Start with the larger-message layout.
    --popup S03               Start with the circuit-selection popup.
    --language en             Start with English popup text (it, fr, de, etc.).
    --snapshot S03.png         Save the selected popup and exit.
    --snapshots-dir refill_popups
                              Save all 21 popups and exit.

To save screenshots without a graphical desktop session:

    QT_QPA_PLATFORM=offscreen python3 \
        src/alfa_CR6_test/alfa_cr6_refill_popup_preview.py \
        --language en --snapshots-dir refill_popups

The initial language follows the application's configuration unless --language
is provided. Missing translations fall back to the original English text.
"""

import argparse
import ast
import sys
from pathlib import Path

# Prefer this checkout's sources to any package installed in the virtualenv.
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import (
    QApplication, QCheckBox, QComboBox, QHBoxLayout, QLabel, QMainWindow,
    QPushButton, QVBoxLayout, QWidget,
)
from alfa_CR6_frontend import dialogs as dialogs_module
from alfa_CR6_frontend.dialogs import InputDialog
from alfa_CR6_backend.globals import LANGUAGE_MAP, import_settings, tr_


AVAILABLE_LANGUAGES = {
    code: name.title() for name, code in LANGUAGE_MAP.items()
}


def main_window_stylesheet():
    """Read the real parent stylesheet without starting the machine UI."""
    source = Path(dialogs_module.__file__).with_name("main_window.py")
    tree = ast.parse(source.read_text(encoding="utf-8"))
    main_class = next(
        node for node in tree.body
        if isinstance(node, ast.ClassDef) and node.name == "MainWindow")
    constructor = next(
        node for node in main_class.body
        if isinstance(node, ast.FunctionDef) and node.name == "__init__")
    styles = [
        ast.literal_eval(node.args[0])
        for node in ast.walk(constructor)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
        and node.func.attr == "setStyleSheet"
        and isinstance(node.func.value, ast.Name)
        and node.func.value.id == "self"
    ]
    if len(styles) != 1:
        raise RuntimeError("Unable to identify the MainWindow stylesheet")
    return styles[0]


def popup(popup_id, title, message, icon="SP_MessageBoxCritical", **kwargs):
    return {
        "id": popup_id,
        "title": title,
        "kwargs": {
            "icon_name": icon, "message": tr_(message), "content": None, **kwargs},
    }


def scenarios():
    # Same strings and input options as ScaleRefillProcedureHelper, with
    # example head/circuit/barcode/quantity values. No machine is connected.
    result = "<br>".join([
        tr_("Refilled quantity: {} g").format(742.35),
        "{}: B01: 618.62 (cc)".format(tr_("adjusted_levels")),
        tr_("RESET head: {}?").format("A"),
    ])
    overflow_result = "<br>".join([
        tr_("Refilled quantity: {} g").format(742.35),
        "{}: B01: 1018.62 (cc)".format(tr_("adjusted_levels")),
        tr_("Warning: the measured refill exceeds<br>the configured maximum level."),
        tr_("RESET head: {}?").format("A"),
    ])
    specs = [
        popup("S01", "Scansione iniziale della tanica",
              "Place the open canister on the scale.<br>Scan its barcode.",
              "SP_MessageBoxQuestion", **{
                  "content": "", "ok_on_enter": 1, "ok_requires_content": True}),
        popup("S02", "Colorante non configurato",
              "The scanned barcode does not match<br>any product configured on the machine."),
        popup("S03", "Scelta del circuito",
              "The product is configured on multiple circuits.",
              "SP_MessageBoxQuestion", **{
                  "content": tr_("Choose the circuit to refill:"),
                  "choices": {
                      "A - B01 - Rosso (250.0/1000.0)": "A-B01",
                      "B - C01 - Rosso (400.0/1000.0)": "B-C01",
                  },
                  "content_editable": False, "use_combo_for_choice": True}),
        popup("S04", "Carosello da mettere in pausa",
              "Pause the carousel before starting the refill."),
        popup("S05", "Testa non pronta",
              "Head {} is not ready for refill."),
        popup("S06", "Operazione sulla testa in corso",
              "Head {} has an operation in progress."),
        popup("S07", "Peso stabile non disponibile",
              "Unable to read a stable weight from the scale."),
        popup("S08", "Posizionamento del circuito fallito",
              "Unable to position the refill circuit."),
        popup("S09", "Scansione del circuito",
              "Scan the barcode on circuit {}<br>of head {}.",
              "SP_MessageBoxQuestion", **{"content": "", "ok_on_enter": 1}),
        popup("S10", "Errore nella preparazione",
              "Refill preparation failed: {}"),
        popup("S11", "Barcode diverso da quello atteso",
              "Barcode mismatch: {} != {}"),
        popup("S12", "Rabbocco e scansione finale della tanica",
              "Remove the canister from the scale and refill the circuit.<br>"
              "When finished, put it back on the scale and scan its barcode.",
              "SP_MessageBoxQuestion", **{"content": "", "ok_on_enter": 1}),
        popup("S13", "Risultato del rabbocco", result,
              "SP_MessageBoxInformation", action_text=tr_("Continue refill")),
        popup("S14", "Risultato con superamento del livello massimo", overflow_result,
              "SP_MessageBoxInformation", action_text=tr_("Continue refill")),
        popup("S15", "Visualizzazione del risultato fallita",
              "Unable to display the refill result."),
        popup("S16", "Quantità misurata non positiva",
              "The measured refill must be greater<br>than zero grams."),
        popup("S17", "Peso specifico non valido",
              "The product specific weight is not valid."),
        popup("S18", "Aggiornamento del livello fallito",
              "Unable to update the product level."),
        popup("S19", "Errore durante il rabbocco", "Refill failed: {}"),
        popup("S20", "Bilancia non rilevata",
              "No scale was detected.<br>Connect the scale and try again.",
              "SP_MessageBoxWarning"),
        popup("S21", "Bilancia collegata ma senza risposta",
              "The scale is connected but not responding.<br>"
              "Check that it is switched on and try again.", "SP_MessageBoxWarning"),
    ]
    examples = {
        "S05": ("A",), "S06": ("A",), "S09": ("B01", "A"),
        "S10": ("invalid pipe name: X01",),
        "S11": ("123456789", "987654321"),
        "S19": ("unexpected internal error",),
    }
    for spec in specs:
        if spec["id"] in examples:
            spec["kwargs"]["message"] = spec["kwargs"]["message"].format(
                *examples[spec["id"]])
    return specs


class PopupGallery(QMainWindow):
    def __init__(self, large=False, initial_id="S01", language=None):
        super().__init__()
        self.setWindowTitle("Scale-refill popup preview")
        self.setStyleSheet(main_window_stylesheet())
        self.settings = import_settings()
        language = language or getattr(self.settings, "LANGUAGE", "en")
        if language not in AVAILABLE_LANGUAGES:
            language = "en"
        # tr_ reads this cached module. Only update this process's memory;
        # the production set_language helper saves settings and restarts the app.
        self.settings.LANGUAGE = language
        self.specs = scenarios()

        central = QWidget(self)
        self.setCentralWidget(central)
        layout = QVBoxLayout(central)
        controls = QHBoxLayout()
        layout.addLayout(controls)
        self.previous_button = QPushButton("Previous")
        self.next_button = QPushButton("Next")
        self.selector = QComboBox()
        self.selector.addItems([
            "{} — {}".format(spec["id"], spec["title"]) for spec in self.specs])
        self.large_checkbox = QCheckBox("Larger messages")
        self.large_checkbox.setChecked(large)
        controls.addWidget(self.previous_button)
        controls.addWidget(self.selector, 1)
        controls.addWidget(self.next_button)
        controls.addWidget(self.large_checkbox)
        language_controls = QHBoxLayout()
        layout.addLayout(language_controls)
        language_controls.addWidget(QLabel("Language"))
        self.language_selector = QComboBox()
        for code, name in sorted(AVAILABLE_LANGUAGES.items(), key=lambda item: item[1]):
            self.language_selector.addItem("{} ({})".format(name, code), code)
        self.language_selector.setCurrentIndex(
            self.language_selector.findData(language))
        language_controls.addWidget(self.language_selector)
        language_controls.addStretch()
        self.popup_layout = QVBoxLayout()
        self.popup_layout.setContentsMargins(0, 0, 0, 0)
        layout.addLayout(self.popup_layout)
        self.dialog = None
        self.previous_button.clicked.connect(lambda: self.step(-1))
        self.next_button.clicked.connect(lambda: self.step(1))
        self.selector.currentIndexChanged.connect(self.show_current)
        self.large_checkbox.toggled.connect(self.show_current)
        self.language_selector.currentIndexChanged.connect(self.change_language)
        initial_index = next(
            i for i, spec in enumerate(self.specs) if spec["id"] == initial_id)
        self.selector.setCurrentIndex(initial_index)
        if self.dialog is None:
            self.show_current()

    def change_language(self, *_):
        self.settings.LANGUAGE = self.language_selector.currentData()
        self.specs = scenarios()
        self.show_current()

    def step(self, delta):
        index = self.selector.currentIndex() + delta
        if 0 <= index < len(self.specs):
            self.selector.setCurrentIndex(index)

    def show_current(self, *_):
        if self.dialog is not None:
            self.popup_layout.removeWidget(self.dialog)
            self.dialog.hide()
            self.dialog.deleteLater()
        self.dialog = InputDialog(self)
        kwargs = dict(self.specs[self.selector.currentIndex()]["kwargs"])
        if "action_text" in kwargs:
            # Enables the same result action button; its preview action
            # only returns to the first popup.
            kwargs["action_cb"] = lambda: None
        self.dialog.show_dialog(
            **kwargs, large_message_layout=self.large_checkbox.isChecked())
        self.dialog.setFixedSize(self.dialog.size())
        self.popup_layout.addWidget(self.dialog, alignment=Qt.AlignHCenter)
        self.dialog.show()
        # Replace production handlers (including .ui hide connections)
        # with gallery navigation. The input validation remains active.
        self.dialog.esc_button.clicked.disconnect()
        self.dialog.ok_button.clicked.disconnect()
        self.dialog.action_button.clicked.disconnect()
        self.dialog.esc_button.clicked.connect(self.close)
        self.dialog.ok_button.clicked.connect(lambda: self.step(1))
        self.dialog.action_button.clicked.connect(
            lambda: self.selector.setCurrentIndex(0))
        index = self.selector.currentIndex()
        self.previous_button.setEnabled(index > 0)
        self.next_button.setEnabled(index < len(self.specs) - 1)
        self.adjustSize()


def main():
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--large", action="store_true")
    parser.add_argument(
        "--language", choices=sorted(AVAILABLE_LANGUAGES),
        help="Popup language (defaults to the application's configured language)")
    parser.add_argument("--popup", default="S01", choices=[
        "S{:02d}".format(i) for i in range(1, 22)])
    parser.add_argument("--snapshot", help="Save the selected popup as PNG and exit")
    parser.add_argument("--snapshots-dir", help="Save every popup as PNG and exit")
    args = parser.parse_args()
    app = QApplication([])
    gallery = PopupGallery(args.large, args.popup, args.language)
    gallery.show()
    app.processEvents()
    if args.snapshots_dir:
        output = Path(args.snapshots_dir)
        output.mkdir(parents=True, exist_ok=True)
        for index, spec in enumerate(gallery.specs):
            gallery.selector.setCurrentIndex(index)
            app.processEvents()
            path = output / (spec["id"] + ".png")
            if not gallery.dialog.grab().save(str(path)):
                raise RuntimeError("Unable to save {}".format(path))
        print("Salvati {} popup in {}".format(len(gallery.specs), output))
    elif args.snapshot:
        if not gallery.dialog.grab().save(args.snapshot):
            raise RuntimeError("Unable to save preview")
    else:
        return app.exec_()
    gallery.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
