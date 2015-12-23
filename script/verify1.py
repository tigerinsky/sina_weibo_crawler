#!/user/bin/env python
#coding: utf-8

from asprise_ocr_api import *

Ocr.set_up() # one time setup
ocrEngine = Ocr()
ocrEngine.start_engine("eng")
s = ocrEngine.recognize("pin.jpg", -1, -1, -1, -1, -1,
                  OCR_RECOGNIZE_TYPE_ALL, OCR_OUTPUT_FORMAT_PLAINTEXT)
print "Result: " + s
# recognizes more images here ..
ocrEngine.stop_engine()
