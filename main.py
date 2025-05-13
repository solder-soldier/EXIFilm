# -*- coding: utf-8 -*-
#

import os
import sys

from PyQt5.QtWidgets import (
    QTabWidget, QSplitter, QAction,
    QToolBar, QMessageBox, QWidget,
    QLabel, QFileDialog, QVBoxLayout,
    QApplication, QMainWindow, QHBoxLayout,
)
from PyQt5.QtGui import QColor, QPalette
from PyQt5.QtGui import QDragEnterEvent, QDropEvent
from PyQt5.QtCore import Qt, QSize, QPoint, QSettings


from util import *
from f90.f90 import *
from ui.camera_win import CameraWindow
from ui.imagebrowser import ImageBrowser
from ui.roll_summary_table import RollSummaryTable, RollData

settings = QSettings('Oliver Hertel', 'EXIFilm')










class DropTabWidget(QTabWidget):
    """A QTabWidget that accepts file drops."""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAcceptDrops(True)
        self.setTabsClosable(True)
        # tabs shall be moveable
        self.setMovable(True)
        self.tabCloseRequested.connect(lambda i: self.removeTab(i))

    def dragEnterEvent(self, event: QDragEnterEvent):
        # Only accept if it has file URLs
        if event.mimeData().hasUrls():
            for url in event.mimeData().urls():
                if url.toLocalFile().lower().endswith(('.json', '.csv')):
                    event.acceptProposedAction()
                    return
        event.ignore()

    def dropEvent(self, event: QDropEvent):
        # For each file dropped, create a new tab
        for url in event.mimeData().urls():
            path = url.toLocalFile()
            if path.lower().endswith('.json'):
                self._load_json(path)
            elif path.lower().endswith('.csv'):
                self._load_csv(path)
        event.acceptProposedAction()

    def _load_json(self, path):
        try:
            roll = RollData.from_json(path)
            roll_table = RollSummaryTable(roll)
            self.addTab(roll_table, f"Roll {roll_table.roll.roll_number}")
            logger.debug(f"Loaded roll {roll_table.roll.roll_number} from {path}")
        except Exception as e:
            logger.error(e)
            self.addTab(QLabel(f"Error: {e}"), 'Error')

    def _load_csv(self, path):
        try:
            roll = RollData.from_csv(path)
            roll_table = RollSummaryTable(roll)
            self.addTab(roll_table, f"Roll {roll_table.roll.roll_number}")
            logger.debug(f"Loaded roll {roll_table.roll.roll_number} from {path}")
        except Exception as e:
            logger.error(e)
            self.addTab(QLabel(f"Error: {e}"), 'Error')





class MainWindow(QMainWindow):
    def __init__(self, icon_color=QColor("white"), parent=None):
        super().__init__()
        self.setWindowTitle('EXIFilm')
        self.setBaseSize(1500, 1200)
        self.auto_hide  = True  # load from settings
        self.icon_color = icon_color
        
        cw = QWidget(self)
        self.setCentralWidget(cw)
        lay = QHBoxLayout(cw)

        widget_rolls = self.create_rolls_browser()
        widget_browser = self.create_image_browser()

        # Main splitter: sidebar on left, image browser on right
        self.main_splitter = QSplitter(Qt.Horizontal)
        self.main_splitter.addWidget(widget_rolls)
        self.main_splitter.addWidget(widget_browser)
        lay.addWidget(self.main_splitter)

        lay.addWidget(self.main_splitter)

        # Restore state
        self.restore_window_state()
        # self.show_camera_window()


    def create_rolls_browser(self):
        self.roll_tabs = DropTabWidget(self)

        # Create toolbar widget
        self.toolbar_rolls = QToolBar()
        self.toolbar_rolls.setIconSize(QSize(32, 32))
        self.toolbar_rolls.setMovable(False)
        self.toolbar_rolls.setFloatable(False)
        self.toolbar_rolls.setContextMenuPolicy(Qt.PreventContextMenu)
        self.toolbar_rolls.setToolButtonStyle(Qt.ToolButtonTextUnderIcon)

        icon = load_svg_icon("svg/camera-roll.svg", self.toolbar_rolls.iconSize(), self.icon_color)
        self.act_load_roll_file = QAction(icon, "Load file(s)", self)
        self.act_load_roll_file.triggered.connect(self.load_roll)
        self.toolbar_rolls.addAction(self.act_load_roll_file)

        icon = load_svg_icon("svg/camera-plus.svg", self.toolbar_rolls.iconSize(), self.icon_color)
        self.act_load_roll_camera = QAction(icon, "Download", self)
        self.act_load_roll_camera.triggered.connect(self.show_camera_window)
        self.toolbar_rolls.addAction(self.act_load_roll_camera)

        self.toolbar_rolls.addSeparator()

        icon = load_svg_icon("svg/save-file.svg", self.toolbar_rolls.iconSize(), self.icon_color)
        self.act_save_roll = QAction(icon, "Save selected", self)
        self.act_save_roll.triggered.connect(self.save_current_roll)
        self.toolbar_rolls.addAction(self.act_save_roll)

        icon = load_svg_icon("svg/filetype-csv.svg", self.toolbar_rolls.iconSize(), self.icon_color)
        self.act_save_all_rolls_csv = QAction(icon, "Save CSV", self)
        self.act_save_all_rolls_csv.triggered.connect(lambda: self.save_all_rolls(extension='csv'))
        self.toolbar_rolls.addAction(self.act_save_all_rolls_csv)

        icon = load_svg_icon("svg/filetype-json.svg", self.toolbar_rolls.iconSize(), self.icon_color)
        self.act_save_all_rolls_json = QAction(icon, "Save JSON", self)
        self.act_save_all_rolls_json.triggered.connect(lambda: self.save_all_rolls(extension='json'))
        self.toolbar_rolls.addAction(self.act_save_all_rolls_json)

        self.toolbar_rolls.addSeparator()

        icon = load_svg_icon("svg/invisible.svg", self.toolbar_rolls.iconSize(), self.icon_color)
        self.act_auto_hide = QAction(icon, "Auto hide", self)
        self.act_auto_hide.triggered.connect(self.toggle_auto_hide)
        self.toolbar_rolls.addAction(self.act_auto_hide)

        container = QWidget()
        vlay = QVBoxLayout(container)
        vlay.setContentsMargins(0,0,0,0)
        vlay.setSpacing(0)
        vlay.addWidget(self.toolbar_rolls)
        vlay.addWidget(self.roll_tabs)

        return container


    def toggle_auto_hide(self):
        # toggle button icon
        self.auto_hide = not self.auto_hide

        if self.auto_hide:
            self.act_auto_hide.setText("Auto hide")
            self.act_auto_hide.setIcon(
                load_svg_icon("svg/invisible.svg", 
                    self.toolbar_rolls.iconSize(),
                    self.icon_color
                )
            )
        else:
            self.act_auto_hide.setText("All visible")
            self.act_auto_hide.setIcon(
                load_svg_icon("svg/visible.svg", 
                    self.toolbar_rolls.iconSize(),
                    self.icon_color
                )
            )
        # toggle auto hide


    def create_image_browser(self):
        self.image_browser = ImageBrowser(self.statusBar(), icon_color=self.icon_color)
        return self.image_browser


    def show_camera_window(self):
        self.camera_window = CameraWindow()
        self.camera_window.show()
        # self.camera_window.setAttribute(Qt.WA_DeleteOnClose)
        self.camera_window.sig_roll_data.connect(self.on_roll_data)


    @pyqtSlot(list)
    def on_roll_data(self, rolls: list[RollData]):
        logger.debug(f"Received {len(rolls)} rolls from camera")
        
        for roll in rolls:
            try:
                roll_table = RollSummaryTable(roll)
                self.roll_tabs.addTab(roll_table, f"Roll {roll.roll_number}")
            except Exception as e:
                logger.error(e)
                self.roll_tabs.addTab(QLabel(f"Error: {e}"), 'Error')


    def load_roll(self):
        files, _ = QFileDialog.getOpenFileNames(self, 'Select Roll', '', 'Rolls (*.json)')
        if not files:
            return
        
        for file in files:
            try:
                roll = RollData.from_json(file)
                roll_table = RollSummaryTable(roll)
                self.roll_tabs.addTab(roll_table, f"Roll {roll_table.roll.roll_number}")
                logger.debug(f"Loaded roll {roll_table.roll.roll_number} from {file}")
            except Exception as e:
                logger.error(e)
                self.roll_tabs.addTab(QLabel(f"Error: {e}"), 'Error')


    def save_current_roll(self):
        current = self.roll_tabs.currentWidget()
        if not current or not isinstance(current, RollSummaryTable):
            return

        try:
            # ask for file name
            path, _ = QFileDialog.getSaveFileName(self, 'Save Roll', '', 'JSON (*.json);;CSV (*.csv)')
            if not path:
                return
            if path.lower().endswith('.csv'):
                current.save_csv(path)
            else:
                current.save_json(path)
        except Exception as e:
            logger.error(e)
            ErrorMsgBox("Error saving roll", str(e), self).exec_()


    def save_all_rolls(self, path=None, extension='json'):
        # ask for folder name
        path = QFileDialog.getExistingDirectory(
            self, f'Save all rolls as {extension}', '', QFileDialog.ShowDirsOnly)
        if not path:
            return

        for i in range(self.roll_tabs.count()):
            current = self.roll_tabs.widget(i)
            if not current or not isinstance(current, RollSummaryTable):
                continue

            try:
                if extension == 'csv':
                    current.save_csv(os.path.join(path, f"roll_{current.roll}.csv"))
                else:
                    current.save_json(os.path.join(path, f"roll_{current.roll}.json"))
            except Exception as e:
                logger.error(e)
                ErrorMsgBox("Error saving roll", str(e), self).exec_()


    def store_window_state(self):
        # store window size and position
        if self.isMaximized():
            settings.setValue('window_state', 'maximized')
        else:
            settings.setValue('window_state', 'normal')
            settings.setValue('window_size', self.size())
            settings.setValue('window_pos', self.pos())
            
        # store splitter states
        settings.setValue('main_splitter', self.main_splitter.saveState())
        settings.setValue('image_browser_splitter', self.image_browser.splitter.saveState())
        settings.sync()


    def restore_window_state(self):
        # restore window size and position
        state = settings.value('window_state', 'normal')
        if state == 'maximized':
            self.showMaximized()
        else:
            size = settings.value('window_size', QSize(1500, 1200))
            pos = settings.value('window_pos', QPoint(100, 100))
            self.resize(size); self.move(pos)

        # restore splitter states
        sp_state = settings.value('main_splitter')
        if sp_state:
            self.main_splitter.restoreState(sp_state)
        sp_state = settings.value('image_browser_splitter')
        if sp_state:
            self.image_browser.splitter.restoreState(sp_state)


    def closeEvent(self, event):
        self.store_window_state()

        # check for unsaved changes
        unsaved = [img for img in self.image_browser.exif_images if img.has_changes()]
        if unsaved:
            msg = QMessageBox(self)
            msg.setIcon(QMessageBox.Warning)
            msg.setText("Saved changes")
            msg.setInformativeText("You have unsaved changes. Do you want to save before exit?")
            msg.setStandardButtons(QMessageBox.Yes | QMessageBox.No | QMessageBox.Cancel)
            msg.setDefaultButton(QMessageBox.Cancel)
            ret = msg.exec_()
            if ret == QMessageBox.Cancel:
                event.ignore()
                return
            elif ret == QMessageBox.Yes:
                self.image_browser.save_all_changed_images()
                event.accept()
                return
            else:
                event.accept()
                return
        event.accept()



if __name__ == '__main__':
    use_qdarktheme = False
    try:
        import qdarktheme
        qdarktheme.enable_hi_dpi()
        use_qdarktheme = True
    except Exception as e:
        logger.error("qdarktheme not found, using default theme")
        use_qdarktheme = False
    app = QApplication(sys.argv)
    if use_qdarktheme:
        qdarktheme.setup_theme()
    mw = MainWindow(QApplication.palette().color(QPalette.Text))
    mw.show()
    sys.exit(app.exec_())