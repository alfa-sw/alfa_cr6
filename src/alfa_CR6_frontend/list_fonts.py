
import sys
import logging

from PyQt5.QtCore import *
from PyQt5.QtGui import *
from PyQt5.QtWidgets import *


class Widget(QWidget):
    def __init__(self, parent=None):
        super(Widget, self).__init__()

        layout = QGridLayout()

        txt = """

        실차색상 배합입니다. (희석10%, 2회도장) 서페이서 적용색상입니다. 리피니쉬 벨류쉐이드 가이드 주소안내
        
        자동차 보수용 수용성 페인트 폐기 시 사용되는 응집제입니다.

        한글

        ㄱ ㄲ ㄴ ㄷ ㄸ ㄹ ㅁ ㅂ ㅃ ㅅ ㅆ ㅇ ㅈ ㅉ ㅊ ㅋ ㅌ ㅍ ㅎ 
        ㅏ ㅐ ㅑ ㅒ ㅓ ㅔ ㅕ ㅖ ㅗ ㅘ ㅙ ㅚ ㅛ ㅜ ㅝ ㅞ ㅟ ㅠ ㅡ ㅢ ㅣ 

        """

        lbl = QLabel(txt)
        self.exit_btn = QPushButton("exit")
        layout.addWidget(lbl, 0, 0)
        layout.addWidget(self.exit_btn, 1, 0)

        self.setLayout(layout)


if __name__ == "__main__":

    app = QApplication(sys.argv)

    # ~ app.setStyleSheet("""QWidget {font-size: 32px;}""")
    # ~ app.setStyleSheet("""QWidget {font-size: 32px; font-family:Noto Sans;}""")
    app.setStyleSheet("""QWidget {font-size: 32px; font-family:Dejavu;}""")

    qf = QFontDatabase()
    qff = qf.families()
    
    logging.warning(f"qff:{str(qff)}")

    dialog = Widget()

    dialog.exit_btn.clicked.connect(app.exit)

    dialog.show()

    app.exec_()
