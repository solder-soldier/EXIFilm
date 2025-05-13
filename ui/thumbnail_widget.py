import os
from typing import Any, Dict
import PIL
from PIL import Image, ExifTags
import exif as exiflib

from PyQt5.QtWidgets import (
    QApplication, QVBoxLayout,
    QLabel, QFrame, QMenu, QWidget
)
from PyQt5.QtGui import QPixmap, QDrag, QCursor
from PyQt5.QtCore import Qt, QMimeData, QPoint

from util import *


class ExifImage(QWidget):
    def __init__(self, path: str, exif_data: Dict[str, Any]):
        super().__init__()
        
        self.path = path
        # Cache metadata
        self.name = os.path.basename(path)
        self.file_date = os.path.getmtime(path)
        self.exif_original = exif_data.copy()
        self.exif_current = exif_data.copy()
        
        # Fallback DateTimeOriginal using DateTime tag
        if 'DateTimeOriginal' not in self.exif_current and 'DateTime' in self.exif_current:
            self.exif_current['DateTimeOriginal'] = self.exif_current['DateTime']
            self.exif_original['DateTimeOriginal'] = self.exif_original.get('DateTime')
        
        # widget will be set by ThumbnailWidget
        self.widget = None

    def contextMenuEvent(self, event):
        menu = QMenu()
        index = self.indexAt(event.pos())
        someAction = menu.addAction('')
        if index.isValid():
            someAction.setText('Selected item: "{}"'.format(index.data()))
        else:
            someAction.setText('No selection')
            someAction.setEnabled(False)
        anotherAction = menu.addAction('Do something')

        res = menu.exec_(event.globalPos())
        if res == someAction:
            print('first action triggered')
    #     # add context menu
    #     self.setContextMenuPolicy(Qt.CustomContextMenu)
    #     self.customContextMenuRequested.connect(self.emptySpaceMenu)

    
    # def emptySpaceMenu(self):
    #     menu = QMenu()
    #     menu.setStyleSheet("QMenu { background-color: #2E2E2E; color: white; }")
    #     menu.setStyleSheet("QMenu::item { padding: 5px; }")
    #     menu.addAction("Save EXIF") #self.save_exif)
    #     menu.addAction("Reset EXIF") #self.reset_exif)
    #     menu.addAction("Remove file") #self.delete_exif)
    #     menu.exec_(QCursor.pos())

    def save_exif(self) -> bool:
        try:
            pillow_image = PIL.Image.open(self.path)
            img_exif = pillow_image.getexif()
            # print(img_exif[33434])
            # print(img_exif[33437])
            # print(img_exif[34855])

            for tag, val in self.exif_current.items():
                if tag not in VISIBLE_EXIF_TAGS:
                    continue
                img_exif[tag] = val

            # print(img_exif[33434])
            # print(img_exif[33437])
            # print(img_exif[34855])

            pillow_image.save(self.path, exif=img_exif)
            self.exif_original = self.exif_current.copy()
            return True

            import exif
            from exif._constants import ATTRIBUTE_NAME_MAP
            from PIL import ExifTags
            from fractions import Fraction

            with open(self.path, "rb") as image_file:
                img = exif.Image(image_file)
            
            for tag, val in self.exif_current.items():
                if tag not in VISIBLE_EXIF_TAGS:
                    continue
                img.set(ATTRIBUTE_NAME_MAP[tag], val)

            # 3) Write back (in-place)
            with open(self.path, "wb") as new_file:
                new_file.write(img.get_file())
                
            # with open(self.path, 'rb') as f:
            #     img = exiflib.Image(f)

            # for tag, val in self.exif_current.items():
            #     tag = ExifTags.TAGS[tag]
            #     try:
            #         if hasattr(img, tag): 
            #             setattr(img, tag, val)
            #     except Exception as e:
            #         logger.debug(f"Failed setting EXIF tag {tag} = '{val}': {e}")
            #         continue

            # with open(self.path, 'wb') as out:
            #     out.write(img.get_file())
            # self.exif_original = self.exif_current.copy()
            # return True
        
        except Exception as e:
            logger.error(f"Failed saving EXIF for {self.path}: {e}")
            return False

    def has_changes(self) -> bool:
        return self.exif_current != self.exif_original



class ThumbnailWidget(QFrame):
    """
    Displays exposure info, image thumbnail, and filename within a single frame.
    """
    def __init__(self, exif_image: ExifImage, pix: QPixmap):
        super().__init__()
        self.exif_image = exif_image
        exif_image.widget = self
        self.drag_start_pos = QPoint(0, 0)

        self.setFrameShape(QFrame.Box)
        self.layout = QVBoxLayout(self)
        self.layout.setContentsMargins(0, 0, 0, 0)
        self.setStyleSheet('border:1px solid gray;')

        # Exposure and aperture
        exif = exif_image.exif_current
        shutter = exif.get(ExifTags.Base.ExposureTime)
        ap = exif.get(ExifTags.Base.FNumber)
        self.info_text = f"{format_exposure_time(shutter)}  f/{int(ap[0]/ap[1]) if isinstance(ap, tuple) else ap}"
        self.info_lbl = QLabel(self.info_text)
        self.info_lbl.setAlignment(Qt.AlignCenter)
        self.info_lbl.setStyleSheet("border: none;")
        self.layout.addWidget(self.info_lbl)

        # Image
        self.img_lbl = QLabel()
        self.img_lbl.setPixmap(pix)
        self.img_lbl.setFixedSize(100, 100)
        self.img_lbl.setAlignment(Qt.AlignCenter)
        self.img_lbl.setStyleSheet("border: none;")
        self.layout.addWidget(self.img_lbl)

        # Filename
        basename = os.path.basename(self.exif_image.path)
        self.name_lbl = QLabel(basename)
        self.name_lbl.setAlignment(Qt.AlignCenter)
        self.name_lbl.setStyleSheet("border: none;")
        self.name_lbl.setToolTip(self.exif_image.path)
        if len(basename) > 15:
            self.name_lbl.setText(f'{basename[:15]}...')
        self.layout.addWidget(self.name_lbl)

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.drag_start_pos = event.pos()
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        if event.buttons() & Qt.LeftButton:
            if (event.pos() - self.drag_start_pos).manhattanLength() > QApplication.startDragDistance():
                drag = QDrag(self)
                mime = QMimeData()
                mime.setText(self.exif_image.path)
                drag.setMimeData(mime)
                drag.exec_(Qt.MoveAction)
        super().mouseMoveEvent(event)

    def update_exif(self):
        exif = self.exif_image.exif_current
        shutter = exif.get(ExifTags.Base.ExposureTime)
        shutter = format_exposure_time(shutter)
        aperture = exif.get(ExifTags.Base.FNumber)
        aperture = format_aperture(aperture)
        self.info_text = f"{shutter}  {aperture}"
        # self.info_text = f"{shutter}  f/{int(ap[0]/ap[1]) if isinstance(ap, tuple) else ap}"
        self.info_lbl.setText(self.info_text)
