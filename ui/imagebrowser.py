import os
import pickle
from PIL import Image, ExifTags
from typing import Any, Dict, List, Set, Tuple

from PyQt5.QtWidgets import (
    QApplication, QWidget, QVBoxLayout,
    QTableWidget, QTableWidgetItem, QFileDialog,
    QScrollArea, QFrame, QProgressBar,
    QSplitter, QAction, QHeaderView,
    QToolBar
)
from PyQt5.QtGui import QPixmap, QImage, QColor
from PyQt5.QtCore import Qt, QSize, QRunnable, QThreadPool, pyqtSignal, QObject


from util import *
from f90.f90 import *
from ui.flow_layout import FlowLayout
from ui.thumbnail_widget import ThumbnailWidget, ExifImage



IMAGE_EXTS = ('.jpg', '.jpeg', '.png', '.tiff', '.gif')


class InsertionIndicator(QFrame):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedWidth(4)
        self.setStyleSheet("background-color: #0078d7;")  # or any accent color
        self.hide()
        # make sure it's on top
        self.setAttribute(Qt.WA_TransparentForMouseEvents)
        self.raise_()



class WorkerSignals(QObject):
    progress=pyqtSignal(int)
    thumbnail_ready=pyqtSignal(str,QPixmap,dict)



class LoadTask(QRunnable):
    def __init__(self,path:str,thumb_size:QSize,idx:int,total:int,signals:WorkerSignals):
        super().__init__(); self.path,self.thumb_size,self.idx,self.total,self.signals=path,thumb_size,idx,total,signals
    
    def run(self):
        pix = QPixmap()
        exif_data = {}
        try:
            img = Image.open(self.path)
            raw = img._getexif() or {}
            exif_data = {t:v for t,v in raw.items()}
            # exif_data={ExifTags.TAGS.get(t,t):v for t,v in raw.items()}
            qimg=QImage(self.path).scaled(self.thumb_size,Qt.KeepAspectRatio,Qt.SmoothTransformation)
            pix=QPixmap.fromImage(qimg)
        except Exception as e: 
            logger.error(f"Load error {self.path}: {e}")

        self.signals.thumbnail_ready.emit(self.path,pix,exif_data)
        self.signals.progress.emit(int(self.idx/self.total*100))



class ImageBrowser(QWidget):
    def __init__(self, status_bar, icon_color, parent=None):
        super().__init__(parent)
        self.status_bar = status_bar
        self.pool = QThreadPool.globalInstance()
        self.pool.setMaxThreadCount(os.cpu_count())

        self.ascending = True
        self.last_sort_key = 'name'
        self.icon_color = icon_color
        self.selected: Set[ExifImage] = set()
        self.exif_images: List[ExifImage] = []

        layout = QVBoxLayout(self)

        # Create toolbar widget
        self.toolbar_browser = QToolBar()
        self.toolbar_browser.setIconSize(QSize(32, 32))
        self.toolbar_browser.setMovable(False)
        self.toolbar_browser.setFloatable(False)
        self.toolbar_browser.setContextMenuPolicy(Qt.PreventContextMenu)
        self.toolbar_browser.setToolButtonStyle(Qt.ToolButtonTextUnderIcon)
        layout.addWidget(self.toolbar_browser)

        # Load file button
        icon = load_svg_icon("svg/plus-file.svg", self.toolbar_browser.iconSize(), icon_color)
        self.act_load_photo_file = QAction(icon, "Load file(s)", self)
        self.act_load_photo_file.triggered.connect(self.add_files)
        self.toolbar_browser.addAction(self.act_load_photo_file)

        # Load folder button
        icon = load_svg_icon("svg/plus-folder.svg", self.toolbar_browser.iconSize(), icon_color)
        self.act_load_photo_folder = QAction(icon, "Open folder", self)
        self.act_load_photo_folder.triggered.connect(self.load_folder)
        self.toolbar_browser.addAction(self.act_load_photo_folder)

        self.toolbar_browser.addSeparator()

        # Sort by name button
        icon = load_svg_icon("svg/sort-name.svg", self.toolbar_browser.iconSize(), icon_color)
        self.act_sort_name = QAction(icon, "By name", self)
        self.act_sort_name.setCheckable(True)
        self.act_sort_name.triggered.connect(lambda _, k='name': self.sort_items(k))
        self.toolbar_browser.addAction(self.act_sort_name)

        # Sort by file time button
        icon = load_svg_icon("svg/sort-time-file.svg", self.toolbar_browser.iconSize(), icon_color)
        self.act_sort_file_time = QAction(icon, "By file time", self)
        self.act_sort_file_time.setCheckable(True)
        self.act_sort_name.triggered.connect(lambda _, k='file_date': self.sort_items(k))
        self.toolbar_browser.addAction(self.act_sort_file_time)

        # Sort by EXIF time button
        icon = load_svg_icon("svg/sort-time-exif.svg", self.toolbar_browser.iconSize(), icon_color)
        self.act_sort_file_exif = QAction(icon, "By EXIF time", self)
        self.act_sort_file_exif.setCheckable(True)
        self.act_sort_name.triggered.connect(lambda _, k='exif': self.sort_items(k))
        self.toolbar_browser.addAction(self.act_sort_file_exif)

        # Ascending/descending sort button
        icon = load_svg_icon("svg/sort-asc.svg", self.toolbar_browser.iconSize(), icon_color)
        self.act_asc_desc = QAction(icon, "Ascending", self)
        self.act_asc_desc.triggered.connect(self.toggle_order)
        self.toolbar_browser.addAction(self.act_asc_desc)

        self.toolbar_browser.addSeparator()

        # Sort by name button
        icon = load_svg_icon("svg/save-file.svg", self.toolbar_browser.iconSize(), icon_color)
        self.act_save_file = QAction(icon, "Save selected", self)
        self.act_save_file.triggered.connect(self.save_selected_images)
        self.toolbar_browser.addAction(self.act_save_file)

        # Sort by file time button
        icon = load_svg_icon("svg/save-changed.svg", self.toolbar_browser.iconSize(), icon_color)
        self.act_save_changed = QAction(icon, "Save changed", self)
        self.act_save_changed.triggered.connect(self.save_all_changed_images)
        self.toolbar_browser.addAction(self.act_save_changed)


        # Thumbnail area
        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.container = QWidget()
        self.container.setAcceptDrops(True)
        self.container.dragEnterEvent = self.dragEnterEvent
        self.container.dragMoveEvent = self.dragMoveEvent
        self.container.dropEvent = self.dropEvent
        self.flow = FlowLayout(self.container)
        self.container.setLayout(self.flow)
        self.scroll.setWidget(self.container)

        self.indicator = InsertionIndicator(self.container)

        # EXIF table
        self.exif_table = QTableWidget(0,2)
        self.exif_table.setHorizontalHeaderLabels(["Tag","Value"])
        self.exif_table.itemChanged.connect(self.on_exif_item_changed)
        header = self.exif_table.horizontalHeader()
        header.setSectionResizeMode(QHeaderView.Stretch)

        self.splitter = QSplitter(Qt.Vertical)
        self.splitter.addWidget(self.scroll)
        self.splitter.addWidget(self.exif_table)
        layout.addWidget(self.splitter)


    def add_thumbnail(self, path: str, pix: QPixmap, exif: Dict[str, Any]):
        exif_img = ExifImage(path, exif)
        thumb = ThumbnailWidget(exif_img, pix)
        thumb.mousePressEvent = lambda e, w=thumb: self.toggle_select(w)
        self.flow.addWidget(thumb)
        self.exif_images.append(exif_img)
        self.update_exif_table()

    def toggle_select(self, thmbnl: ThumbnailWidget):
        img = next((i for i in self.exif_images if i.path == thmbnl.exif_image.path), None)
        if not img: return
        if QApplication.keyboardModifiers() & Qt.ControlModifier:
            img in self.selected and self.selected.remove(img) or self.selected.add(img)
        else:
            self.selected = {img}
        self.refresh_thumbnails()
        self.update_exif_table()

    def refresh_thumbnails(self):
        for img in self.exif_images:
            sel = img in self.selected
            chg = img.has_changes()
            style = ('background: gray;' if sel else 'background: none;',
                    'border:1px solid red;' if chg else 'border:1px solid gray;')
            img.widget.setStyleSheet(''.join(style))

    def sort_items(self, key: str):
        self.last_sort_key = key
        items: List[Tuple[Any, ExifImage]] = []
        for img in self.exif_images:
            if key == 'name':
                val = img.name
            elif key == 'file_date':
                val = img.file_date
            else:
                val = img.exif_current.get('DateTimeOriginal') or img.exif_current.get('DateTime', '')
            items.append((val, img))
        items.sort(key=lambda x: x[0], reverse=not self.ascending)

        # Update internal order
        self.exif_images = [img for _, img in items]

        # Rebuild layout
        while self.flow.count():
            w = self.flow.takeAt(0).widget()
            w.setParent(None)
        for img in self.exif_images:
            self.flow.addWidget(img.widget)

        # disable slog/signals before setting checked state
        self.act_sort_name.triggered.disconnect()
        self.act_sort_file_time.triggered.disconnect()
        self.act_sort_file_exif.triggered.disconnect()

        # Update sort action states
        self.act_sort_name.setChecked(key == 'name')
        self.act_sort_file_time.setChecked(key == 'file_date')
        self.act_sort_file_exif.setChecked(key == 'exif')
        
        # re-enable signals
        self.act_sort_name.triggered.connect(lambda _, k='name': self.sort_items(k))
        self.act_sort_file_time.triggered.connect(lambda _, k='file_date': self.sort_items(k))
        self.act_sort_file_exif.triggered.connect(lambda _, k='exif': self.sort_items(k))

    def toggle_order(self, asc: bool):
        self.ascending = not self.ascending
        self.act_asc_desc.setText('Ascending' if self.ascending else 'Descending')
        self.act_asc_desc.setIcon(
            load_svg_icon(
                "svg/sort-asc.svg" if self.ascending else "svg/sort-desc.svg", 
                self.toolbar_browser.iconSize(),
                self.icon_color
            )
        )
        self.sort_items(self.last_sort_key)

    def on_exif_item_changed(self, item: QTableWidgetItem):
        if item.column() != 1 or not self.selected: return
        tag = self.exif_table.item(item.row(), 0).text()
        val = item.text()
        for img in self.selected: img.exif_current[tag] = val
        self.refresh_thumbnails()
        item.setBackground(
            QColor('#ea2055') if any(i.exif_current.get(tag) != i.exif_original.get(tag) for i in self.selected)
            else QColor('#101012')
        )

    def update_exif_table(self):
        self.exif_table.blockSignals(True)
        self.exif_table.setRowCount(0)
        if not self.selected:
            self.exif_table.blockSignals(False)
            return
        
        rows = []
        all_data = [i.exif_current for i in self.selected]
        keys = set().union(*all_data)

        for k in sorted(keys):
            if k not in VISIBLE_EXIF_TAGS:
                continue
            vals = [d.get(k) for d in all_data]
            display = vals[0] if all(v == vals[0] for v in vals) else '...'
            changed = any(i.exif_current.get(k) != i.exif_original.get(k) for i in self.selected)
            rows.append((k, str(display), changed))
        self.exif_table.setRowCount(len(rows))

        for i, (k, v, ch) in enumerate(rows):
            kkk = ExifTags.TAGS.get(k, k)
            ik = QTableWidgetItem(kkk)
            iv = QTableWidgetItem(v)
            iv.setFlags(iv.flags() | Qt.ItemIsEditable)
            bg = QColor('#ea2055') if ch else QColor('#101012')
            ik.setBackground(bg); iv.setBackground(bg)
            self.exif_table.setItem(i, 0, ik); self.exif_table.setItem(i, 1, iv)
        self.exif_table.blockSignals(False)

    def load_folder(self):
        dlg = QFileDialog(self); dlg.setFileMode(QFileDialog.Directory)
        if dlg.exec_():
            folder = dlg.selectedFiles()[0]
            folder = os.path.abspath(folder)
            imgs = [os.path.join(folder, f) for f in os.listdir(folder)
                    if f.lower().endswith(('.jpg','.jpeg','.png','.tiff','.gif'))]
            self.start_loading(imgs)

    def add_files(self):
        files, _ = QFileDialog.getOpenFileNames(self, 'Select Images', '',
                                                'Images (*.jpg *.jpeg *.png *.tiff *.gif)')
        if files: self.start_loading(files)

    def start_loading(self, paths:List[str]):
        # clear prev
        self.exif_images.clear(); self.selected.clear()
        # progress bar
        self.progress=QProgressBar()
        self.progress.setValue(0)
        self.status_bar.addPermanentWidget(self.progress)
        # signals
        self.signals=WorkerSignals()
        self.signals.progress.connect(self.progress.setValue)
        self.signals.thumbnail_ready.connect(self.add_thumbnail)
        self.signals.progress.connect(lambda v: v)
        self.signals.progress.connect(lambda v: self.status_bar.removeWidget(self.progress) if v>=100 else None)
        total=len(paths)
        for idx,p in enumerate(paths,1):
            self.pool.start(LoadTask(p,QSize(100,100),idx,total,self.signals))
    
    def save_selected_images(self):
        for img in list(self.selected):
            if img.save_exif(): self.refresh_thumbnails()
        self.update_exif_table()

    def save_all_changed_images(self):
        for img in self.exif_images:
            if img.has_changes(): 
                img.save_exif()
        self.update_exif_table()

    def closeEvent(self, e):
        # ensure thread stops
        if hasattr(self, 'loader') and self.loader.isRunning():
            self.loader.terminate()
        super().closeEvent(e)

    def keyPressEvent(self, event):
        if event.key() == Qt.Key_Delete:
            for img in list(self.selected):
                self.exif_images.remove(img)
                img.widget.deleteLater()
            self.selected.clear()
            self.refresh_thumbnails()
            self.update_exif_table()
            event.accept()
        elif event.key() == Qt.Key_Escape:
            self.selected.clear()
            self.refresh_thumbnails()
            self.update_exif_table()
            event.accept()
        elif event.key() == Qt.Key_A and event.modifiers() & Qt.ControlModifier:
            # Select all images
            self.selected = set(self.exif_images)
            self.refresh_thumbnails()
            self.update_exif_table()
            event.accept()
        else:
            super().keyPressEvent(event)

    def dragEnterEvent(self, event):
        if (event.mimeData().hasFormat('application/x-roll-frame-exif') or 
            event.mimeData().hasText()):
            event.acceptProposedAction()

    def dragMoveEvent(self, event):
        if event.mimeData().hasFormat('application/x-roll-frame-exif'):
            self.indicator.hide()
            event.acceptProposedAction()

            pos = event.pos()
            for img in self.exif_images:
                chg = img.has_changes()
                style = ('background: gray;' if img.widget.geometry().contains(pos) else 'background: none;',
                        'border:1px solid red;' if chg else 'border:1px solid gray;')
                img.widget.setStyleSheet(''.join(style))
            return
        
        # 1) mouse pos *in* the container’s coords
        pos = event.pos()

        # 2) all thumbs in true order
        thumbs = [img.widget for img in self.exif_images]

        # 3) pick out just the ones under this y (same "row")
        row = [w for w in thumbs
            if w.y() <= pos.y() <= w.y() + w.height()]

        if not row:
            # if you aren't over a thumbnail‐row, hide marker
            self.indicator.hide()
            return

        # 4) sort that row left→right
        row.sort(key=lambda w: w.x())

        # 5) find insert point
        insert_at = None
        ref_widget = None
        for w in row:
            mid = w.x() + w.width() / 2
            if pos.x() < mid:
                insert_at = thumbs.index(w)
                ref_widget = w
                break
        if insert_at is None:
            # past the last in the row
            ref_widget = row[-1]
            insert_at = thumbs.index(ref_widget) + 1

        # 6) compute the indicator’s geometry
        geo = ref_widget.geometry()
        # put it on the left edge if inserting before, else on the right
        x = geo.x() if insert_at <= thumbs.index(ref_widget) else geo.x() + geo.width()
        y = geo.y()
        h = geo.height()

        # center the 4px‐wide bar on that x
        self.indicator.setGeometry(x - 2, y, 4, h)
        self.indicator.show()

    def dropEvent(self, event):
        mime = event.mimeData()
        if mime.hasFormat('application/x-roll-frame-exif'):
            # Handle EXIF update from roll table
            data = mime.data('application/x-roll-frame-exif')
            exif_update = pickle.loads(data.data())
            pos = event.pos()
            target_thumb = None
            for img in self.exif_images:
                if img.widget.geometry().contains(pos):
                    target_thumb = img
                    break

            if target_thumb:
                target_thumb.exif_current.update(exif_update)
                self.refresh_thumbnails()
                self.update_exif_table()
                target_thumb.widget.update_exif()
                event.accept()
            else:
                event.ignore()
        else:
            # 1) Only handle our own internal drags (we encoded the image path as plain text)
            mimimii = event.mimeData()
            if not event.mimeData().hasText():
                return
            event.acceptProposedAction()

            # 2) Figure out where to insert
            pos = event.pos()
            thumbs = [img.widget for img in self.exif_images]
            # find all widgets on the same “row” (y-span) as the drop point
            row = [w for w in thumbs
                if w.y() <= pos.y() <= w.y() + w.height()]
            if not row:
                # if you aren’t over any row, just hide the indicator and bail
                self.indicator.hide()
                return

            row.sort(key=lambda w: w.x())
            # default to end-of-row
            insert_at = None
            for w in row:
                mid = w.x() + w.width() / 2
                if pos.x() < mid:
                    insert_at = thumbs.index(w)
                    break
            if insert_at is None:
                insert_at = thumbs.index(row[-1]) + 1

            # 3) Find which image was dragged by matching the text payload (= file path)
            path = event.mimeData().text()
            old_index = next((i for i,img in enumerate(self.exif_images)
                            if img.path == path), None)
            if old_index is None:
                self.indicator.hide()
                return
            dragged = self.exif_images.pop(old_index)

            # 4) Re-insert into our model list
            #    adjust insert_at if removing something before the new position
            if old_index < insert_at:
                insert_at -= 1
            self.exif_images.insert(insert_at, dragged)

            # 5) Rebuild the flow layout in the new order
            while self.flow.count():
                item = self.flow.takeAt(0)
                w = item.widget()
                w.setParent(None)
            for img in self.exif_images:
                self.flow.addWidget(img.widget)

            # 6) Hide the insertion indicator now that we’ve dropped
            self.indicator.hide()
