# -*- coding: utf-8 -*-
#

import serial
import serial.tools
import serial.tools.list_ports
from PyQt5.QtCore import QThread
from PyQt5.QtWidgets import QMainWindow, QWidget, QSpacerItem, QCheckBox, QProgressBar, QPushButton, QGridLayout, QVBoxLayout, QHBoxLayout, QGroupBox, QLabel, QComboBox, QMessageBox, QApplication, QSizePolicy


from logging import getLogger, StreamHandler, Formatter, DEBUG

logger = getLogger(__name__)
logger.setLevel(DEBUG)
handler = StreamHandler()
handler.setLevel(DEBUG)
handler.setFormatter(Formatter('%(asctime)s %(name)s %(levelname)s %(message)s'))
logger.addHandler(handler)

from f90.f90 import *






class CameraWindow(QMainWindow):
    sig_connect_camera    = pyqtSignal()
    sig_disconnect_camera = pyqtSignal(bool)
    sig_download_rolls    = pyqtSignal()
    sig_roll_data         = pyqtSignal(list)

    def __init__(self):
        super().__init__()
        self.setWindowTitle('Camera')
        self.setBaseSize(800, 600)
        self._is_connected = False

        self.init_ui()
        self.reset_camera_widgets()


    def init_ui(self):
        self.central_widget = QWidget()
        self.setCentralWidget(self.central_widget)
        self.layout = QVBoxLayout()
        self.central_widget.setLayout(self.layout)

        # connection group
        self.conn_group = QGroupBox('Connection')
        self.layout.addWidget(self.conn_group)
        self.conn_group_layout = QHBoxLayout()
        self.conn_group.setLayout(self.conn_group_layout)
        lbl = QLabel('Camera Port:')
        self.conn_group_layout.addWidget(lbl)

        # list serial ports
        self.port_input = QComboBox()
        ports = serial.tools.list_ports.comports()
        for port in ports:
            self.port_input.addItem(port.device)
        self.port_input.setCurrentIndex(0)
        self.conn_group_layout.addWidget(self.port_input)

        self.btn_connect = QPushButton('Connect')
        self.btn_connect.clicked.connect(self.connect_camera)
        self.conn_group_layout.addWidget(self.btn_connect)

        # camera info group
        self.info_group = QGroupBox('Camera Info')
        self.info_group.setEnabled(False)
        self.layout.addWidget(self.info_group)
        self.info_group_layout = QGridLayout()
        self.info_group.setLayout(self.info_group_layout)

        lbl = QLabel('Model name:')
        lbl.setStyleSheet('font-size: 12px') #; font-weight: bold;')
        self.info_group_layout.addWidget(lbl, 0, 0)
        self.lbl_model = QLabel('N/A')
        self.info_group_layout.addWidget(self.lbl_model, 0, 1)
        self.lbl_model.setStyleSheet('font-size: 12px') #; font-weight: bold;')

        lbl = QLabel('Total shots:')
        lbl.setStyleSheet('font-size: 12px') #; font-weight: bold;')
        self.info_group_layout.addWidget(lbl, 1, 0)
        self.lbl_total_shot_cnt = QLabel('N/A')
        self.info_group_layout.addWidget(self.lbl_total_shot_cnt, 1, 1)
        self.lbl_total_shot_cnt.setStyleSheet('font-size: 12px') #; font-weight: bold;')

        # memory holder settings
        self.memory_holder_group = QGroupBox('Memory Holder')
        self.memory_holder_group.setEnabled(False)
        self.layout.addWidget(self.memory_holder_group)
        self.memory_holder_group_layout = QGridLayout()
        self.memory_holder_group.setLayout(self.memory_holder_group_layout)

        self.chk_memo_enabled = QCheckBox('Use memory holder')
        self.chk_memo_enabled.setChecked(False)
        self.memory_holder_group_layout.addWidget(self.chk_memo_enabled, 0, 0, 1, 2)

        lbl = QLabel('Storage mode:')
        self.memory_holder_group_layout.addWidget(lbl, 1, 0)
        self.cmb_memo_mode = QComboBox()
        self.cmb_memo_mode.addItem('Minimum (2 bytes)', userData=0x05)
        self.cmb_memo_mode.addItem('Intermediate (4 bytes)', userData=0x0E)
        self.cmb_memo_mode.addItem('All data (6 bytes)', userData=0x1F)
        self.memory_holder_group_layout.addWidget(self.cmb_memo_mode, 1, 1)

        # Add download button
        self.btn_save = QPushButton('Save settings')
        self.memory_holder_group_layout.addWidget(self.btn_save, 2, 0, 1, 2)
        # self.btn_save.clicked.connect(self.download_memory_holder)
        
        lbl = QLabel('')
        self.memory_holder_group_layout.addWidget(lbl, 3, 0)

        # Current roll info (number and frames count)
        lbl = QLabel('Current roll:')
        lbl.setStyleSheet('font-size: 12px') #; font-weight: bold;')
        self.memory_holder_group_layout.addWidget(lbl, 4, 0)
        self.lbl_current_roll = QLabel('N/A')
        self.memory_holder_group_layout.addWidget(self.lbl_current_roll, 4, 1)
        self.lbl_current_roll.setStyleSheet('font-size: 12px') #; font-weight: bold;')

        # First roll in memory holder
        lbl = QLabel('First roll:')
        lbl.setStyleSheet('font-size: 12px') #; font-weight: bold;')
        self.memory_holder_group_layout.addWidget(lbl, 5, 0)
        self.lbl_first_roll = QLabel('N/A')
        self.memory_holder_group_layout.addWidget(self.lbl_first_roll, 5, 1)
        self.lbl_first_roll.setStyleSheet('font-size: 12px') #; font-weight: bold;')

        # Memory used by roll data
        lbl = QLabel('Roll data:')
        lbl.setStyleSheet('font-size: 12px') #; font-weight: bold;')
        self.memory_holder_group_layout.addWidget(lbl, 6, 0)
        self.lbl_memory_used = QLabel('N/A')
        self.memory_holder_group_layout.addWidget(self.lbl_memory_used, 6, 1)
        self.lbl_memory_used.setStyleSheet('font-size: 12px') #; font-weight: bold;')

        # Total memory size
        lbl = QLabel('Memory size:')
        lbl.setStyleSheet('font-size: 12px') #; font-weight: bold;')
        self.memory_holder_group_layout.addWidget(lbl, 7, 0)
        self.lbl_memory_total = QLabel('N/A')
        self.memory_holder_group_layout.addWidget(self.lbl_memory_total, 7, 1)
        self.lbl_memory_total.setStyleSheet('font-size: 12px') #; font-weight: bold;')

        # Add download button
        self.btn_download = QPushButton('Download roll data')
        self.memory_holder_group_layout.addWidget(self.btn_download, 8, 0, 1, 2)
        self.btn_download.clicked.connect(self.sig_download_rolls.emit)

        # add a spacer
        self.layout.addItem(QSpacerItem(20, 40, QSizePolicy.Minimum, QSizePolicy.Expanding))

        # progress bar at bottom
        self.progress_bar = QProgressBar()
        self.layout.addWidget(self.progress_bar)
        self.progress_bar.setValue(0)
        self.progress_bar.setRange(0, 100)


    # override closeEvent to disconnect camera
    def closeEvent(self, event):
        self.disconnect_camera()
        event.accept()


    @pyqtSlot(int)
    def on_camera_progress(self, value):
        """ Handle camera progress updates. """
        self.progress_bar.setValue(value)

        # if progress bar reaches 100%, hide progress 
        # bar after 1 second without blocking the UI
        if value >= 100:
            self.progress_bar.setValue(0)
            self.progress_bar.setEnabled(False)
            self.btn_save.setEnabled(True)
            self.btn_connect.setEnabled(True)
            self.btn_download.setEnabled(True)
            # QTimer.singleShot(1000, lambda: self.progress_bar.setVisible(False))
        else:
            # self.progress_bar.setVisible(True)
            self.progress_bar.setEnabled(True)
            self.btn_save.setEnabled(False)
            self.btn_connect.setEnabled(False)
            self.btn_download.setEnabled(False)
        QApplication.processEvents()


    @pyqtSlot(F90Error, str)
    def on_camera_error(self, id, msg):
        """ Handle camera errors and show message box. """
        logger.error(f"Camera error: {id.name} - '{msg}'")
        msgbox = QMessageBox(self)
        msgbox.setIcon(QMessageBox.Critical)
        msgbox.setText('Error communicating with camera:\n\n{}'.format(msg))
        msgbox.setWindowTitle('Error')
        msgbox.exec_()
        self.disconnect_camera(True)
        self.info_group.setEnabled(False)
        self.memory_holder_group.setEnabled(False)


    @pyqtSlot(F90Response, object)
    def on_camera_response(self, id, data):
        """ Handle camera responses and update UI accordingly. """
        # logger.debug(f"Camera response: {id.name} - '{data}'")

        if id == F90Response.PORT_OPENED:
            self._is_connected = True
            self.info_group.setEnabled(True)
            self.memory_holder_group.setEnabled(True)
            self.btn_connect.setEnabled(True)
            self.btn_connect.setText('Disconnect')
            self.btn_connect.clicked.disconnect()
            self.btn_connect.clicked.connect(self.disconnect_camera)

        elif id == F90Response.PORT_CLOSED:
            self.info_group.setEnabled(False)
            self.memory_holder_group.setEnabled(False)
            self.port_input.setEnabled(True)
            self.btn_connect.setText('Connect')
            self.btn_connect.setEnabled(True)
            self.btn_connect.clicked.disconnect()
            self.btn_connect.clicked.connect(self.connect_camera)

        elif id == F90Response.MODEL:
            self.lbl_model.setText(f'<b>{data}</b>')

        elif id == F90Response.TOTAL_SHOTS:
            self.lbl_total_shot_cnt.setText(f'<b>{data}</b>')

        elif id == F90Response.MEMORY_INFO:
            if data is None:
                self.lbl_memory_used.setText('N/A')
                self.lbl_memory_total.setText('N/A')
                self.lbl_current_roll.setText('N/A')
                self.btn_save.setEnabled(False)
                self.btn_download.setEnabled(False)
                self.cmb_memo_mode.setEnabled(False)
                self.chk_memo_enabled.setChecked(False)
                return
            
            # total memory size
            bytes_total = data['ring_end'] - data['ring_start']
            self.lbl_memory_total.setText(f'<b>{bytes_total} bytes</b>')

            # used memory size
            bytes_used = data['bytes_used']
            percent = int((bytes_used / bytes_total) * 100)
            self.lbl_memory_used.setText(f'<b>{bytes_used} bytes ({percent} %)</b>')
            if bytes_used == 0:
                self.btn_download.setEnabled(False)
            else:
                self.btn_download.setEnabled(True)

            # memo holder settings
            self.chk_memo_enabled.setChecked(data['memo_enabled'])
            
            self.cmb_memo_mode.setEnabled(True)
            storage_mode = data['storage_mode']
            if storage_mode == 0x05:
                self.cmb_memo_mode.setCurrentIndex(0)
            elif storage_mode == 0x0E:
                self.cmb_memo_mode.setCurrentIndex(1)
            elif storage_mode == 0x1F:
                self.cmb_memo_mode.setCurrentIndex(2)
            else:
                logger.error(f"Unknown memory storage mode: {storage_mode}")

            # first roll info
            first_roll_num = data['first_roll_number']
            first_roll_len = data['first_roll_length']
            first_roll_frms = (first_roll_len - 4) // data['frame_size']
            self.lbl_first_roll.setText(f'<b>{first_roll_num} ({first_roll_frms} frames)</b>')

        elif id == F90Response.CURRENT_ROLL:
            if not data:
                self.lbl_current_roll.setText('<i>no film</i>')
            else:
                # current roll info
                current_roll_num = data['roll']
                current_frame = data['frame']
                self.lbl_current_roll.setText(f'<b>{current_roll_num} ({current_frame} frames)</b>')

        elif id == F90Response.ROLL_DATA:
            self.sig_roll_data.emit(data)
        
        else:
            logger.error(f"Unknown response id: {id}, data: {data}")

        QApplication.processEvents()


    def connect_camera(self):
        """ Connect to the camera. """
        if self._is_connected:
            return
        self.port_input.setEnabled(False)
        self.btn_connect.setEnabled(False)
        self.btn_connect.setText('Connecting...')
        QApplication.processEvents()
        
        self.port = self.port_input.currentText()
        self.camera = F90(port=self.port)
        self.camera.error.connect(self.on_camera_error)
        self.camera.progress.connect(self.on_camera_progress)
        self.camera.response.connect(self.on_camera_response)

        self.thread = QThread(self)
        self.sig_connect_camera.connect(self.camera.init)
        self.sig_disconnect_camera.connect(self.camera.close)
        self.sig_download_rolls.connect(self.camera.query_roll_data)
        self.camera.moveToThread(self.thread)
        self.thread.start()

        self.sig_connect_camera.emit()


    def disconnect_camera(self, force=False):
        if not self._is_connected and not force:
            return
        self.camera.close()
        self.thread.quit()
        self.thread.wait()
        self._is_connected = False
        self.reset_camera_widgets()
        self.sig_disconnect_camera.emit(force)


    def reset_camera_widgets(self):
        self.progress_bar.setValue(0)
        self.lbl_model.setText('N/A')
        self.lbl_first_roll.setText('N/A')
        self.lbl_memory_used.setText('N/A')
        self.lbl_memory_total.setText('N/A')
        self.lbl_current_roll.setText('N/A')
        self.lbl_total_shot_cnt.setText('N/A')
        self.btn_save.setEnabled(False)
        self.btn_download.setEnabled(False)
        self.cmb_memo_mode.setEnabled(False)
        self.chk_memo_enabled.setChecked(False)
