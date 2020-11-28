# coding: utf-8

import sys

import alfa_CR6_test.test_db
import alfa_CR6_test.test_dymo_labeler
import alfa_CR6_test.test_ui
import alfa_CR6_test.test_ws_comm

def test_all():
    if "test_ws_comm" in sys.argv:
        alfa_CR6_test.test_ws_comm.test_all()
    if "test_dymo_labeler" in sys.argv:
        alfa_CR6_test.test_dymo_labeler.test_all()
    if "test_ui" in sys.argv:
        alfa_CR6_test.test_ui.test_all()
    if "test_db" in sys.argv:
        alfa_CR6_test.test_db.test_all()
    
