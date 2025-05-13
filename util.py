# -*- coding: utf-8 -*-
#

import math
from aenum import Enum
from typing import Dict, List, Any

from PyQt5.QtCore import Qt, QSize
from PyQt5.QtSvg import QSvgRenderer
from PyQt5.QtWidgets import QMessageBox
from PyQt5.QtGui import QIcon, QPixmap, QPainter, QColor


from logging import getLogger, StreamHandler, Formatter, DEBUG

logger = getLogger("EXIFilm")
logger.setLevel(DEBUG)
handler = StreamHandler()
handler.setLevel(DEBUG)
handler.setFormatter(Formatter('%(asctime)s %(name)s %(levelname)s %(message)s'))
logger.addHandler(handler)



class ErrorMsgBox(QMessageBox):
    def __init__(self, title: str, text: str):
        super().__init__()
        self.setWindowTitle(title)
        self.setText(text)
        self.setIcon(QMessageBox.Critical)
        self.setStandardButtons(QMessageBox.Ok)
        self.setDefaultButton(QMessageBox.Ok)
        self.setModal(True)
        # self.setAttribute(Qt.WA_DeleteOnClose)

    def show(self):
        super().show()
        self.raise_()
        self.activateWindow()


class ExifTagNames(Enum):

    _init_ = 'value string'

    Make         = 0x010F, 'Make'
    Model        = 0x0110, 'Model'
    ISO          = 0x8827, 'ISO'
    Shutter      = 0x829A, 'Shutter'
    Aperture     = 0x829D, 'Aperture'
    MeteringMode = 0x9207, 'Metering mode'
    Flash        = 0x9209, 'Flash'
    FocalLength  = 0x920A, 'Focal length'
    ImageNumber  = 0x9211, 'Frame#'
    UserComment  = 0x9286, 'User comment'
    ExposureMode = 0xA402, 'Exposure mode'

    def __str__(self):
        return self.string

# Visible EXIF tags
VISIBLE_EXIF_TAGS = [
    ExifTagNames.ISO.value,
    ExifTagNames.Shutter.value,
    ExifTagNames.Aperture.value,
    ExifTagNames.Make.value,
    ExifTagNames.Model.value,
    ExifTagNames.FocalLength.value,
    # ExifTagNames.Flash.value,
    # ExifTagNames.ExposureMode.value,
    # ExifTagNames.MeteringMode.value,
]


def bcd_to_int(n):
    return int(('%x' % n), base=10)


def checksum(payload):
    return sum(payload) & 0xFF


def format_aperture(val: Any) -> str:
    """
    Format aperture: f-stop value.
    """
    if type(val) == str:
        return val

    if val is None:
        return "Unknown"
    if math.isnan(val):
        return "N/A"
    if math.isinf(val):
        return "Hi" if val > 0 else "Lo"
    
    try:
        if isinstance(val, tuple):
            t = val[0] / val[1]
        else:
            t = float(val)
    except Exception:
        return str(val)
    return f"f/{t:.1f}"


def format_exposure_time(val: Any) -> str:
    """
    Format exposure time: if <1s, as fraction; else in seconds.
    """
    if type(val) == str:
        return val

    if val is None:
        return "Unknown"
    if math.isnan(val):
        return "N/A"
    if math.isinf(val):
        return "Bulb" if val > 0 else "Lo"
    
    try:
        if isinstance(val, tuple):
            t = val[0] / val[1]
        else:
            t = float(val)
    except Exception:
        return str(val)
    if t >= 1:
        return f"{int(t)}s"
    denom = round(1 / t)
    return f"1/{denom}"


def print_rolls_summary(all_rolls: List[Dict[str,Any]]):
    print("\n=== Rolls Summary ===")
    print(f"{'Roll':>6}  {'ISO':>4}  {'Frames':>6}")
    for r in all_rolls:
        print(f"{r['roll_number']:>6}  {r['iso']:>4}  {len(r['frames']):>6}")


def print_frame_table(roll: Dict[str,Any]):
    print(f"\n--- Roll {roll['roll_number']} (ISO={(roll['iso'])}) ---")
    print(f"{'#':>3}  {'Shutter':>8}  {'Aperture':>8}  {'Flash':>6}  {'Meter':>15}  {'Mode':>25}  {'Focal':>5}")
    for i, f in enumerate(roll['frames'], 0):
        print(f"{i:3d} {f['raw'].hex()} {f['shutter']:>8}  {f['aperture']:>8}  "
              f"{f['flash']:>6}  {f['meter']:>15}  {f['mode']:>25}  {f['focal']:>5}")


class ExifTagNames(Enum):

    _init_ = 'value string'

    Make         = 0x010F, 'Make'
    Model        = 0x0110, 'Model'
    ISO          = 0x8827, 'ISO'
    Shutter      = 0x829A, 'Shutter'
    Aperture     = 0x829D, 'Aperture'
    MeteringMode = 0x9207, 'Metering mode'
    Flash        = 0x9209, 'Flash'
    FocalLength  = 0x920A, 'Focal length'
    ImageNumber  = 0x9211, 'Frame#'
    UserComment  = 0x9286, 'Comment'
    ExposureMode = 0xA402, 'Exposure mode'

    def __str__(self):
        return self.string




def load_svg_icon(path: str, size: QSize, color: QColor) -> QIcon:
    """
    Load an SVG file and color it before converting to QIcon.

    :param path: Path to the SVG file.
    :param size: Desired icon size (QSize).
    :param color: QColor to apply to the SVG.
    :return: QIcon with the colored SVG.
    """
    # Create a QPixmap with transparent background
    pixmap = QPixmap(size)
    pixmap.fill(Qt.transparent)

    # Render SVG onto the pixmap
    renderer = QSvgRenderer(path)
    painter = QPainter(pixmap)
    renderer.render(painter)

    # Apply color using CompositionMode_SourceIn
    painter.setCompositionMode(QPainter.CompositionMode_SourceIn)
    painter.fillRect(pixmap.rect(), color)
    painter.end()

    return QIcon(pixmap)