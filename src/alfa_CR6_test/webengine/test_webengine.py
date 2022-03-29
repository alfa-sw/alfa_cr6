
import sys, os
from PyQt5.Qt import QUrl
from PyQt5.QtWebEngineWidgets import QWebEngineView
from PyQt5.QtWidgets import QApplication

os.environ['DISPLAY'] = ':0'

app = QApplication([])
web = QWebEngineView()

print(f"web:{web}")
web.load(QUrl("https://www.octoral.com/en"))
# ~ web.load(QUrl("https://google.com"))
web.show()
sys.exit(app.exec_())
