r"""Preview refill popups with or without a scale directly from the sources.

Activate the project's Python environment, then run from the repository root
in a terminal with access to a graphical desktop session:

    python3 src/alfa_CR6_test/alfa_cr6_refill_popup_preview.py

No new wheel installation is required. The window inherits MainWindow's style
and uses the real dialogs with sample data, without connecting to the machine.
Use Refill mode to select With scale (21 popups, S01-S21) or Without scale
(14 popups, M01-M14). Only the selected flow's popups appear in the menu and
in screenshot exports. The manual flow includes quantity entry, confirmation,
results and QR-code variants; scale readings and scale connection errors are
absent. Use Previous/Next or the popup menu to select a popup.
The Larger messages checkbox compares both scale-refill layouts; the manual
flow uses its production layout. Use Language to switch popup localizations.
These controls do not change the application's saved configuration.
S01, S09, S12, M01 and M04 show illustrations below the buttons with a compact
barcode input beneath them. Images use a base scale of 29.3% of their original dimensions;
S12 applies an additional factor of 1.5 to make the sequence easier to see.
S20 shows the USB connection warning illustration below its buttons.
S21 shows the power-on warning illustration in the same area and at the same scale.
S20 and S21 also stop an ongoing refill; those dialogs additionally show
"Refill procedure interrupted." in production.
Production checks scale communication before each forward step, including
circuit selection, refill instructions and the final reset confirmation.
To add an illustration to another popup, pass
message_image=get_res("IMAGE", "image.png") in its scenario options and in the
corresponding production dialog. Images keep their aspect ratio; the message
retains its full width.

Options (append to the launch command):

    --large                   Start with the larger-message layout.
    --mode scale              Preview refill with a scale (default).
    --mode manual             Preview refill without a scale.
    --popup S03               Start with the circuit-selection popup.
    --mode manual --popup M06 Start with manual quantity entry.
    --language en             Start with English popup text (it, fr, de, etc.).
    --snapshot S03.png         Save the selected popup and exit.
    --snapshots-dir refill_popups
                              Save all popups for the selected mode and exit.

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
    QApplication, QCheckBox, QComboBox, QHBoxLayout, QLabel, QMainWindow, QMessageBox,
    QPushButton, QVBoxLayout, QWidget,
)
from alfa_CR6_frontend import dialogs as dialogs_module
from alfa_CR6_frontend.dialogs import InputDialog, ModalMessageBox, RefillDialog
from alfa_CR6_backend.globals import LANGUAGE_MAP, get_res, import_settings, tr_


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


def popup(popup_id, title, message, icon="SP_MessageBoxCritical",
          dialog_type="input", **kwargs):
    options = {"icon_name": icon, "message": tr_(message)}
    if dialog_type == "input":
        options["content"] = None
    return {
        "id": popup_id,
        "title": title,
        "dialog_type": dialog_type,
        "kwargs": {**options, **kwargs},
    }


def manual_scenarios():
    """Match RefillProcedureHelper's barcode, quantity and QR-code branches."""
    def alert(popup_id, title, message, window_title="ALERT", show_cancel=True):
        return {
            "id": popup_id, "title": title, "dialog_type": "alert",
            "show_cancel": show_cancel,
            "kwargs": {"msg": message, "title": window_title},
        }

    quantity_message = tr_(
        "please, input quantity (in {}) of product: {}<br> for refilling pipe: {} "
        "(current level:{}),<br> leave as is for total refill or select from the list."
    ).format("cc", "Rosso", "B01", 250.0)
    fill_up = {"label": tr_("FILL UP"), "value": 750.0}
    result = "{}: B01, 750.0 (cc){}".format(
        tr_("adjusted_levels"), tr_(". RESET head: {} ?").format("A"))
    return [
        popup("M01", "Scansione iniziale del barcode",
              "please, input barcode for refill", "SP_MessageBoxQuestion",
              message_image=get_res("IMAGE", "refill_scan_can_full.png"),
              content="", ok_on_enter=1),
        alert("M02", "Colorante non configurato",
              tr_("The code entered '{}' does not match any toner on HEAD {} ({})")
              .format("123456789", "1", "A"), show_cancel=False),
        popup("M03", "Scelta del circuito",
              tr_("Multiple circuits found for {}").format("Rosso"),
              "SP_MessageBoxQuestion", content=tr_("Choose circuit to refill:"),
              choices={tr_("{} (level {}/{})").format("B01", 250.0, 1000.0): "B01",
                       tr_("{} (level {}/{})").format("B02", 400.0, 1000.0): "B02"},
              content_editable=False, use_combo_for_choice=True),
        popup("M04", "Verifica barcode sulla tanica",
              tr_("please, verify barcode {} on canister.").format("123456789"),
              "SP_MessageBoxQuestion",
              message_image=get_res("IMAGE", "refill_scan_pipe.png"),
              content="", ok_on_enter=1),
        popup("M05", "Barcode diverso da quello atteso",
              tr_("barcode mismatch <br/>{} != {}").format("123456789", "987654321")),
        popup("M06", "Inserimento della quantità",
              quantity_message, "SP_MessageBoxQuestion", dialog_type="refill",
              unit="CC", choices=[fill_up, 500, 250, 100]),
        popup("M07", "Conferma della quantità",
              tr_("please, confirm refilling pipe: {} <br>with {} ({}) of product: {}?.")
              .format("B01", 500.0, "cc", "Rosso"), "SP_MessageBoxQuestion"),
        popup("M08", "Quantità superiore alla capacità residua",
              tr_("refilling with {} ({}) would exceed maximum level! Aborting.")
              .format(900.0, "cc")),
        popup("M09", "Quantità proposta dal QR code",
              quantity_message, "SP_MessageBoxQuestion", dialog_type="refill",
              unit="CC", choices=[fill_up, 500]),
        popup("M10", "Conferma del limite per la quantità da QR code",
              tr_("QR proposes {} ({}) which exceeds maximum level for pipe: {}.<br>"
                  "Refill will be capped to {} ({}). Confirm?")
              .format(900.0, "cc", "B01", 750.0, "cc"), "SP_MessageBoxWarning"),
        popup("M11", "Risultato del rabbocco e reset della testa",
              result, "SP_MessageBoxInformation"),
        alert("M12", "Errore nella decodifica del QR code",
              tr_("KCC QR decode failed: {}").format("invalid QR code"),
              window_title="ERROR"),
        alert("M13", "Circuito del prodotto da QR code non trovato",
              tr_("pipe with pigment:{} not found.").format("Rosso"),
              window_title="ERROR"),
        alert("M14", "Eccezione nella decodifica del QR code",
              tr_("DECODE KCC QRCODE EXCEPTION"), window_title="ERROR"),
    ]


def scenarios(mode="scale"):
    if mode == "manual":
        return manual_scenarios()
    if mode != "scale":
        raise ValueError("Unknown refill mode: {}".format(mode))
    # Same strings and input options as ScaleRefillProcedureHelper, with
    # example head/circuit/barcode/quantity values. No machine is connected.
    result = "<br>".join([
        tr_("Refilled quantity: {} g").format(742.35),
        "{}: B01: 618.62 (cc)".format(tr_("adjusted_levels")),
        tr_("RESET head: {}?").format("A"),
    ])
    overflow_result = "<br>".join([
        tr_("Refilled quantity: {} g").format(742.35),
        "{}: B01: 1000.0 (cc)".format(tr_("adjusted_levels")),
        tr_("The recorded level has been capped at the configured maximum."),
        tr_("RESET head: {}?").format("A"),
    ])
    specs = [
        popup("S01", "Scansione iniziale della tanica",
              "Place the open canister on the scale.<br>Scan its barcode.",
              "SP_MessageBoxQuestion", **{
                  "message_image": get_res("IMAGE", "refill_scale_can_full.png"),
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
              "SP_MessageBoxQuestion", **{
                  "message_image": get_res("IMAGE", "refill_scan_pipe.png"),
                  "content": "", "ok_on_enter": 1}),
        popup("S10", "Errore nella preparazione",
              "Refill preparation failed: {}"),
        popup("S11", "Barcode diverso da quello atteso",
              "Barcode mismatch: {} != {}"),
        popup("S12", "Rabbocco e scansione finale della tanica",
              "Remove the canister from the scale and refill the circuit.<br>"
              "When finished, put it back on the scale and scan its barcode.",
              "SP_MessageBoxQuestion", **{
                  "message_image": get_res("IMAGE", "refill_scale_sequence.png"),
                  "message_image_scale_factor": 1.5,
                  "content": "", "ok_on_enter": 1}),
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
              "No scale was detected.<br>"
              "Connect the scale or check that the USB cable is properly connected.",
              "SP_MessageBoxWarning",
              message_image=get_res("IMAGE", "refill_scale_warn_unplugged.png")),
        popup("S21", "Bilancia senza risposta",
              "The scale is not responding.<br>"
              "Check that it is switched on and that the communication cable<br>"
              "is properly connected at the back of the scale.", "SP_MessageBoxWarning",
              message_image=get_res("IMAGE", "refill_scale_warn_off.png")),
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
    def __init__(self, large=False, initial_id=None, language=None, mode="scale"):
        super().__init__()
        self.setWindowTitle("Refill popup preview")
        self.setStyleSheet(main_window_stylesheet())
        self.settings = import_settings()
        language = language or getattr(self.settings, "LANGUAGE", "en")
        if language not in AVAILABLE_LANGUAGES:
            language = "en"
        # tr_ reads this cached module. Only update this process's memory;
        # the production set_language helper saves settings and restarts the app.
        self.settings.LANGUAGE = language
        self.mode = mode
        self.specs = scenarios(mode)

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
        self.large_checkbox.setEnabled(mode == "scale")
        self.large_checkbox.setToolTip("Applies to refill with a scale")
        controls.addWidget(self.previous_button)
        controls.addWidget(self.selector, 1)
        controls.addWidget(self.next_button)
        controls.addWidget(self.large_checkbox)
        language_controls = QHBoxLayout()
        layout.addLayout(language_controls)
        language_controls.addWidget(QLabel("Refill mode"))
        self.mode_selector = QComboBox()
        self.mode_selector.addItem("With scale", "scale")
        self.mode_selector.addItem("Without scale", "manual")
        self.mode_selector.setCurrentIndex(self.mode_selector.findData(mode))
        language_controls.addWidget(self.mode_selector)
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
        self.mode_selector.currentIndexChanged.connect(self.change_mode)
        initial_id = initial_id or self.specs[0]["id"]
        initial_index = next(
            i for i, spec in enumerate(self.specs) if spec["id"] == initial_id)
        self.selector.setCurrentIndex(initial_index)
        if self.dialog is None:
            self.show_current()

    def change_language(self, *_):
        self.settings.LANGUAGE = self.language_selector.currentData()
        self.reload_scenarios()

    def change_mode(self, *_):
        self.mode = self.mode_selector.currentData()
        self.large_checkbox.setEnabled(self.mode == "scale")
        self.reload_scenarios()

    def reload_scenarios(self):
        current_id = self.specs[self.selector.currentIndex()]["id"]
        self.specs = scenarios(self.mode)
        self.selector.blockSignals(True)
        self.selector.clear()
        self.selector.addItems([
            "{} — {}".format(spec["id"], spec["title"]) for spec in self.specs])
        index = next((i for i, spec in enumerate(self.specs)
                      if spec["id"] == current_id), 0)
        self.selector.setCurrentIndex(index)
        self.selector.blockSignals(False)
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
        spec = self.specs[self.selector.currentIndex()]
        kwargs = dict(spec["kwargs"])
        if "action_text" in kwargs:
            # Enables the same result action button; its preview action
            # only returns to the first popup.
            kwargs["action_cb"] = lambda: None
        dialog_type = spec["dialog_type"]
        if dialog_type == "alert":
            self.dialog = ModalMessageBox(parent=self, auto_delete=False, **kwargs)
            self.dialog.hide()
            self.dialog.setWindowFlags(Qt.Widget)
            self.dialog.setWindowModality(Qt.NonModal)
            self.dialog.enable_buttons(True, spec["show_cancel"], False)
            self.dialog.adjustSize()
        elif dialog_type == "refill":
            self.dialog = RefillDialog(self)
            self.dialog.show_dialog(**kwargs)
        else:
            self.dialog = InputDialog(self)
            self.dialog.show_dialog(
                **kwargs, large_message_layout=(
                    self.mode == "scale" and self.large_checkbox.isChecked()))
        self.dialog.setFixedSize(self.dialog.size())
        self.popup_layout.addWidget(self.dialog, alignment=Qt.AlignHCenter)
        self.dialog.show()
        # Replace production handlers (including .ui hide connections)
        # with gallery navigation. The input validation remains active.
        if dialog_type == "alert":
            self.dialog.button(QMessageBox.Cancel).clicked.connect(self.close)
            self.dialog.button(QMessageBox.Ok).clicked.connect(lambda: self.step(1))
        else:
            self.dialog.esc_button.clicked.disconnect()
            self.dialog.ok_button.clicked.disconnect()
            self.dialog.esc_button.clicked.connect(self.close)
            self.dialog.ok_button.clicked.connect(lambda: self.step(1))
            if isinstance(self.dialog, InputDialog):
                self.dialog.action_button.clicked.disconnect()
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
    parser.add_argument("--mode", choices=("scale", "manual"), default="scale")
    parser.add_argument(
        "--language", choices=sorted(AVAILABLE_LANGUAGES),
        help="Popup language (defaults to the application's configured language)")
    parser.add_argument("--popup", help="Initial popup ID: S01-S21 or M01-M14")
    parser.add_argument("--snapshot", help="Save the selected popup as PNG and exit")
    parser.add_argument("--snapshots-dir", help="Save every popup as PNG and exit")
    args = parser.parse_args()
    valid_ids = [spec["id"] for spec in scenarios(args.mode)]
    if args.popup is not None and args.popup not in valid_ids:
        parser.error("Popup {} is unavailable in {} mode; choose {}".format(
            args.popup, args.mode, ", ".join(valid_ids)))
    app = QApplication([])
    gallery = PopupGallery(args.large, args.popup, args.language, args.mode)
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
