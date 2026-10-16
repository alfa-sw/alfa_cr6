#!/usr/bin/env python3
"""Render the English S01-S19 scale-refill popups from the Qt UI layout."""

import os
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt5.QtCore import QRect, QSize, Qt  # pylint: disable=wrong-import-position
from PyQt5.QtGui import (  # pylint: disable=wrong-import-position
    QColor,
    QFont,
    QIcon,
    QImage,
    QPainter,
    QPen,
    QPixmap,
)
from PyQt5.QtWidgets import (  # pylint: disable=wrong-import-position
    QApplication,
    QFrame,
    QLabel,
    QStyle,
)
from PyQt5.uic import loadUi  # pylint: disable=wrong-import-position


ROOT = Path(__file__).resolve().parents[1]
UI_PATH = ROOT / "src/alfa_CR6_frontend/ui/input_dialog.ui"
IMAGE_DIR = ROOT / "src/alfa_CR6_frontend/images"
OUTPUT_DIR = ROOT / "doc/__hidden__/refill_scale_popups_en"
MESSAGE_IMAGE_SCALE = 300 / 1024

BASE_STYLE = """
QWidget {background:#CCBBBBBB; border: 1px solid #999999; border-radius: 4px;}
QLabel {border: 0px;}
QLineEdit {background:#FFFFAA;}
QComboBox {background:#CCCCCC;}
QPushButton {background-color: #F3F3F3F3;}
QPushButton:pressed {background-color: #AAAAAA;}
"""

POPUPS = [
    {
        "id": "S01",
        "icon": "SP_MessageBoxQuestion",
        "message": "Place the open canister on the scale.<br>Scan its barcode.",
        "content": "",
        "requires_content": True,
        "image": "refill_scale_can_full.png",
    },
    {
        "id": "S02",
        "icon": "SP_MessageBoxCritical",
        "message": (
            "The scanned barcode does not match<br>"
            "any product configured on the machine."
        ),
    },
    {
        "id": "S03",
        "icon": "SP_MessageBoxQuestion",
        "message": "The product is configured on multiple circuits.",
        "content": "Choose the circuit to refill:",
        "choices": [
            "A - B01 - Red (250.0/1000.0)",
            "B - C01 - Blue (400.0/1000.0)",
        ],
    },
    {
        "id": "S04",
        "icon": "SP_MessageBoxCritical",
        "message": "Pause the carousel before starting the refill.",
    },
    {
        "id": "S05",
        "icon": "SP_MessageBoxCritical",
        "message": "Head A is not ready for refill.",
    },
    {
        "id": "S06",
        "icon": "SP_MessageBoxCritical",
        "message": "Head A has an operation in progress.",
    },
    {
        "id": "S07",
        "icon": "SP_MessageBoxCritical",
        "message": "Unable to read a stable weight<br>from the scale.",
    },
    {
        "id": "S08",
        "icon": "SP_MessageBoxCritical",
        "message": "Unable to position the refill circuit.",
    },
    {
        "id": "S09",
        "icon": "SP_MessageBoxQuestion",
        "message": "Scan the barcode on circuit B01<br>of head A.",
        "content": "",
        "image": "refill_scan_pipe.png",
    },
    {
        "id": "S10",
        "icon": "SP_MessageBoxCritical",
        "message": "Refill preparation failed:<br>invalid pipe name: X01",
    },
    {
        "id": "S11",
        "icon": "SP_MessageBoxCritical",
        "message": "Barcode mismatch:<br>123456789 != 987654321",
    },
    {
        "id": "S12",
        "icon": "SP_MessageBoxQuestion",
        "message": (
            "Remove the canister from the scale and refill the circuit.<br>"
            "When finished, put it back on the scale and scan its barcode."
        ),
        "content": "",
        "image": "refill_sequence_scale.png",
        "image_scale_factor": 1.5,
    },
    {
        "id": "S13",
        "icon": "SP_MessageBoxInformation",
        "message": (
            "Refilled quantity: 742.35 g<br>"
            "adjusted_levels: B01: 618.62 (cc)<br>"
            "RESET head: A?"
        ),
    },
    {
        "id": "S14",
        "icon": "SP_MessageBoxInformation",
        "message": (
            "Refilled quantity: 742.35 g<br>"
            "adjusted_levels: B01: 1000.0 (cc)<br>"
            "The recorded level has been capped at the configured maximum.<br>"
            "RESET head: A?"
        ),
    },
    {
        "id": "S15",
        "icon": "SP_MessageBoxCritical",
        "message": "Unable to display the refill result.",
    },
    {
        "id": "S16",
        "icon": "SP_MessageBoxCritical",
        "message": "The measured refill must be greater<br>than zero grams.",
    },
    {
        "id": "S17",
        "icon": "SP_MessageBoxCritical",
        "message": "The product specific weight is not valid.",
    },
    {
        "id": "S18",
        "icon": "SP_MessageBoxCritical",
        "message": "Unable to update the product level.",
    },
    {
        "id": "S19",
        "icon": "SP_MessageBoxCritical",
        "message": "Refill failed:<br>unexpected internal error",
    },
]


def build_popup(app, spec, large_layout=True):
    frame = QFrame()
    loadUi(str(UI_PATH), frame)
    standard_frame_height = frame.height()
    frame.setStyleSheet(BASE_STYLE)

    frame.ok_button.setText("OK")
    frame.esc_button.setText("Cancel")
    frame.ok_button.setIcon(QIcon(QPixmap(str(IMAGE_DIR / "green.png"))))
    frame.esc_button.setIcon(QIcon(QPixmap(str(IMAGE_DIR / "red.png"))))

    icon = frame.style().standardIcon(getattr(QStyle, spec["icon"]))
    frame.icon_label.setPixmap(icon.pixmap(QSize(64, 64)))
    frame.message_label.setText(spec["message"])

    content = spec.get("content")
    choices = spec.get("choices")

    if large_layout:
        message_font = frame.message_label.font()
        message_font.setPointSizeF(message_font.pointSizeF() * 1.40)
        frame.message_label.setFont(message_font)
        frame.message_label.resize(
            frame.message_label.width(), 281)
        frame.message_label.setWordWrap(True)

        button_y = frame.message_label.y() + frame.message_label.height() + 9
        frame.esc_button.setGeometry(120, button_y, 200, 51)
        frame.ok_button.setGeometry(870, button_y, 201, 51)

        content_y = button_y + frame.ok_button.height() + 9
        if content is None:
            frame.content_container.hide()
            content_height = 0
        else:
            frame.content_container.setGeometry(2, content_y, 1071, 80)
            frame.content_container.setText(content)
            content_font = frame.content_container.font()
            content_font.setPointSizeF(max(
                14, content_font.pointSizeF() * 1.40))
            frame.content_container.setFont(content_font)
            content_height = 80

        bottom = content_y + content_height
        if choices:
            frame.content_container.setReadOnly(True)
            frame.combo_box.clear()
            frame.combo_box.addItems(sorted(choices))
            frame.combo_box.setGeometry(80, bottom + 9, 891, 60)
            frame.combo_box.setStyleSheet(
                "QComboBox {font-size: 34px; min-height: 60px;}"
                "QComboBox QAbstractItemView {font-size: 30px;}"
                "QAbstractItemView::item {min-height: 48px;}"
            )
            frame.combo_box.show()
            bottom += 69
        else:
            frame.combo_box.hide()
        frame.resize(1078, bottom + 9)
    else:
        if content is None:
            frame.content_container.hide()
            frame.resize(1078, 275)
        else:
            frame.content_container.resize(frame.content_container.width(), 400)
            frame.content_container.setText(content)
            frame.resize(1078, standard_frame_height)

        if choices:
            frame.content_container.setReadOnly(True)
            frame.combo_box.clear()
            frame.combo_box.addItems(sorted(choices))
            frame.combo_box.resize(frame.combo_box.width(), 60)
            frame.combo_box.show()
        else:
            frame.combo_box.hide()

    if spec.get("image"):
        pixmap = QPixmap(str(IMAGE_DIR / spec["image"]))
        if pixmap.isNull():
            raise RuntimeError("Unable to load popup image: {}".format(spec["image"]))
        scaled = pixmap.scaled(
            pixmap.size() * (MESSAGE_IMAGE_SCALE * spec.get("image_scale_factor", 1.0)),
            Qt.KeepAspectRatio, Qt.SmoothTransformation)
        frame.message_image_label = QLabel(frame)
        frame.message_image_label.setStyleSheet(
            "border: 0px; background: transparent;")
        frame.message_image_label.setPixmap(scaled)
        frame.message_image_label.setAlignment(Qt.AlignCenter)
        image_y = frame.ok_button.y() + frame.ok_button.height() + 9
        frame.message_image_label.setGeometry(
            frame.content_container.x(), image_y,
            frame.content_container.width(), scaled.height())
        frame.message_image_label.show()
        bottom = image_y + scaled.height()
        if content is not None:
            frame.content_container.setGeometry(
                frame.content_container.x(), bottom + 12,
                frame.content_container.width(), 80)
            bottom = frame.content_container.y() + 80
        if choices:
            frame.combo_box.move(frame.combo_box.x(), bottom + 9)
            bottom = frame.combo_box.y() + frame.combo_box.height()
        frame.resize(1078, bottom + 9)

    frame.ok_button.setEnabled(not spec.get("requires_content", False))
    frame.show()
    app.processEvents()
    return frame


def render_popup(app, spec):
    frame = build_popup(app, spec, large_layout=True)

    output_path = OUTPUT_DIR / "{}_en.png".format(spec["id"])
    if not frame.grab().save(str(output_path), "PNG"):
        raise RuntimeError("Unable to save {}".format(output_path))
    frame.close()
    return output_path


def render_layout_comparison(app):
    spec = next(item for item in POPUPS if item["id"] == "S12")

    standard_frame = build_popup(app, spec, large_layout=False)
    standard = standard_frame.grab()
    standard_frame.close()

    large_frame = build_popup(app, spec, large_layout=True)
    large = large_frame.grab()
    large_frame.close()

    margin = 36
    title_height = 70
    label_height = 42
    section_gap = 30
    width = max(standard.width(), large.width()) + 2 * margin
    height = (title_height + 2 * label_height + standard.height()
              + large.height() + section_gap + 2 * margin)

    image = QImage(width, height, QImage.Format_ARGB32)
    image.fill(QColor("white"))
    painter = QPainter(image)
    painter.setRenderHint(QPainter.Antialiasing)

    painter.setPen(QColor("#1F2937"))
    painter.setFont(QFont("DejaVu Sans", 24, QFont.Bold))
    painter.drawText(
        QRect(0, margin // 2, width, title_height),
        Qt.AlignCenter,
        "Scale refill popup layout comparison",
    )

    painter.setFont(QFont("DejaVu Sans", 16, QFont.Bold))
    y = title_height + margin
    painter.drawText(
        QRect(0, y, width, label_height),
        Qt.AlignCenter,
        "ENABLE_REFILL_BY_SCALE_LARGE_MESSAGE_LAYOUT = false",
    )
    y += label_height
    x = (width - standard.width()) // 2
    painter.drawPixmap(x, y, standard)
    painter.setPen(QPen(QColor("#6B7280"), 2))
    painter.drawRect(x, y, standard.width() - 1, standard.height() - 1)

    y += standard.height() + section_gap
    painter.setPen(QColor("#1F2937"))
    painter.drawText(
        QRect(0, y, width, label_height),
        Qt.AlignCenter,
        "ENABLE_REFILL_BY_SCALE_LARGE_MESSAGE_LAYOUT = true",
    )
    y += label_height
    x = (width - large.width()) // 2
    painter.drawPixmap(x, y, large)
    painter.setPen(QPen(QColor("#6B7280"), 2))
    painter.drawRect(x, y, large.width() - 1, large.height() - 1)
    painter.end()

    output_path = (
        ROOT
        / "doc/__hidden__/refill_scale_large_message_layout_comparison_en.png"
    )
    if not image.save(str(output_path), "PNG"):
        raise RuntimeError("Unable to save {}".format(output_path))
    return output_path


def main():
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    app = QApplication.instance() or QApplication([])
    for spec in POPUPS:
        path = render_popup(app, spec)
        print(path)
    print(render_layout_comparison(app))


if __name__ == "__main__":
    main()
