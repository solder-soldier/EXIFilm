# -*- coding: utf-8 -*-
#

import pickle
from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QTableWidgetItem, 
    QTableWidget, QLabel, QAbstractItemView, QLineEdit
)

from PyQt5.QtGui import QDrag
from PyQt5.QtCore import Qt, QMimeData

from util import *
from rolldata import *
from f90.f90 import *
from f90.constants import *



class RollSummaryTable(QWidget):
    def __init__(self, roll:RollData, parent=None):
        super().__init__(parent)
        self.roll      = roll
        self.auto_hide = True

        self.layout = QVBoxLayout(self)

        self.lbl_header = QLabel("")
        self.lbl_header.setStyleSheet("font-size: 14px;")
        self.layout.addWidget(self.lbl_header)

        desc_layout = QHBoxLayout()
        self.layout.addLayout(desc_layout)
        lbl = QLabel("Description:")
        desc_layout.addWidget(lbl)
        self.txt_desc = QLineEdit(self)
        self.txt_desc.setPlaceholderText("Enter a description for this roll")
        desc_layout.addWidget(self.txt_desc)


        # Main table
        self.table = QTableWidget(self)
        self.table.setEditTriggers(QAbstractItemView.NoEditTriggers)  # cells are not editable
        self.table.verticalHeader().setVisible(False)
        self.table.setSelectionBehavior(QTableWidget.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SingleSelection)
        self.layout.addWidget(self.table)

        # Enable drag from table rows
        self.table.setDragEnabled(True)
        self.table.viewport().setAcceptDrops(False)
        self.table.setDragDropMode(QAbstractItemView.DragOnly)

        def startDrag_local(supported_actions):
            selected = self.table.selectedItems()
            if not selected:
                return
            
            # pickle the whole row
            row = selected[0].row()
            frame = self.roll.frames[row]

            # use EXIF tag IDs as keys
            exif_data = {}
            for k, v in frame.items():
                exif_data[k.value] = v
            exif_data[ExifTagNames.ISO.value] = self.roll.iso
            
            mime = QMimeData()
            mime.setData('application/x-roll-frame-exif', pickle.dumps(exif_data))
            drag = QDrag(self)
            drag.setMimeData(mime)
            drag.exec_(Qt.CopyAction)

        # Bind our custom startDrag
        self.table.startDrag = startDrag_local
        self.populate()


    def populate(self):
        if not self.roll:
            return
        
        self.setWindowTitle(f"Roll {self.roll.roll_number}")
        self.table.setRowCount(len(self.roll.frames))
        self.lbl_header.setText(f"<b>Roll {self.roll.roll_number}</b> - ISO {self.roll.iso}, {len(self.roll.frames)} frames")

        frame_size = len(self.roll.frames[0]) if self.roll.frames else 0
        columns = ["Frame", "Shutter", "Aperture"]
        if frame_size >= 4:
            columns += ["Focal Length", "Exp. Mode", "Metering", "Flash Sync"]
        if frame_size >= 6:
            columns.append("Compensations")

            
        self.table.setColumnCount(len(columns))
        self.table.setHorizontalHeaderLabels(columns)

        if self.roll.frames:
            # Populate rows
            for i, frame in enumerate(self.roll.frames):
                # MINIMUM STORAGE MODE (2 bytes)
                shutter = frame[ExifTagNames.Shutter]
                aperture = frame[ExifTagNames.Aperture]
                items = [
                    QTableWidgetItem(f"{frame[ExifTagNames.ImageNumber]:02d}"),
                    QTableWidgetItem(f"{format_exposure_time(shutter)}"),
                    QTableWidgetItem(f"{format_aperture(aperture)}"),
                ]

                # FOUR BYTE STORAGE MODE
                if ExifTagNames.FocalLength in frame:
                    items.append(QTableWidgetItem(f"{frame[ExifTagNames.FocalLength]} mm"))
                else:
                    items.append(QTableWidgetItem("Unknown"))
                
                if ExifTagNames.ExposureMode in frame:
                    items.append(QTableWidgetItem(frame[ExifTagNames.ExposureMode]))
                else:
                    items.append(QTableWidgetItem("Unknown"))

                if ExifTagNames.MeteringMode in frame:
                    items.append(QTableWidgetItem(frame[ExifTagNames.MeteringMode]))
                else:
                    items.append(QTableWidgetItem("Unknown"))
                
                if ExifTagNames.Flash in frame:
                    items.append(QTableWidgetItem(frame[ExifTagNames.Flash]))
                else:
                    items.append(QTableWidgetItem("Unknown"))

                # SIX BYTE STORAGE MODE
                # if show_extra:
                #     ec = parse_exposure_compensation(payload[4])
                #     fc = parse_exposure_compensation(payload[5])
                #     items.append(QTableWidgetItem(f"EC={ec}, FC={fc}"))

                for col, item in enumerate(items):
                    self.table.setItem(i, col, item)

            self.table.resizeColumnsToContents()
        


    def set_auto_hide(self, auto_hide:bool):
        self.auto_hide = auto_hide
        # auto hide means, that rows which have been successfully dragged
        # should be hidden from the table
            








#         # Helper function to populate comboboxes
#         def populate_combobox(combobox, options, current_key):
#             combobox.clear()
#             # Sort options by key and add to combobox
#             for key in sorted(options.keys()):
#                 combobox.addItem(options[key], userData=key)
#             # Set current selection
#             index = combobox.findData(current_key)
#             combobox.setCurrentIndex(index if index != -1 else 0)

#         # Table setup
#         table = QTableWidget(self)
#         table.setRowCount(len(frames))
#         table.setColumnCount(len(columns))
#         table.setHorizontalHeaderLabels(columns)
#         table.verticalHeader().setVisible(False)
#         table.setSelectionBehavior(QTableWidget.SelectRows)
#         table.verticalHeader().setSectionResizeMode(QHeaderView.Fixed)

#         for i, payload in enumerate(frames):
#             # Frame number (always editable)
#             table.setItem(i, 0, QTableWidgetItem(f"{i+1:02d}"))

#             # Shutter speed combobox
#             shutter_combo = QComboBox()
#             populate_combobox(shutter_combo, SHUTTER_SPEEDS, payload[0])
#             shutter_combo.currentIndexChanged.connect(
#                 lambda idx, row=i: self.decoded['frames'][row].__setitem__(0, shutter_combo.currentData())
#             )
#             table.setCellWidget(i, 1, shutter_combo)

#             # Aperture combobox
#             aperture_combo = QComboBox()
#             populate_combobox(aperture_combo, APERTURES, payload[1])
#             aperture_combo.currentIndexChanged.connect(
#                 lambda idx, row=i: self.decoded['frames'][row].__setitem__(1, aperture_combo.currentData())
#             )
#             table.setCellWidget(i, 2, aperture_combo)

#             if payload_len >= 4:
#                 b2 = payload[2]
                
#                 # Focal length combobox
#                 focal_combo = QComboBox()
#                 populate_combobox(focal_combo, FOCAL_LENGTHS, payload[3])
#                 focal_combo.currentIndexChanged.connect(
#                     lambda idx, row=i: self.decoded['frames'][row].__setitem__(3, focal_combo.currentData())
#                 )
#                 table.setCellWidget(i, 3, focal_combo)

#                 # Exposure mode combobox
#                 exp_mode_combo = QComboBox()
#                 current_exp_mode = b2 & 0b00001111
#                 populate_combobox(exp_mode_combo, EXPOSURE_MODES, current_exp_mode)
#                 exp_mode_combo.currentIndexChanged.connect(
#                     lambda idx, row=i: self.update_byte_field(row, 2, 0b00001111, exp_mode_combo.currentData())
#                 )
#                 table.setCellWidget(i, 4, exp_mode_combo)

#                 # Metering combobox
#                 metering_combo = QComboBox()
#                 current_metering = (b2 & 0b01000000) >> 6
#                 populate_combobox(metering_combo, METERING_SYSTEM, current_metering)
#                 metering_combo.currentIndexChanged.connect(
#                     lambda idx, row=i: self.update_byte_field(row, 2, 0b01000000, metering_combo.currentData() << 6)
#                 )
#                 table.setCellWidget(i, 5, metering_combo)

#                 # Flash sync combobox
#                 flash_combo = QComboBox()
#                 current_flash = (b2 & 0b11000000) >> 6
#                 populate_combobox(flash_combo, FLASH_MODES, current_flash)
#                 flash_combo.currentIndexChanged.connect(
#                     lambda idx, row=i: self.update_byte_field(row, 2, 0b11000000, flash_combo.currentData() << 6)
#                 )
#                 table.setCellWidget(i, 6, flash_combo)

#             if show_extra:
#                 ec = parse_exposure_compensation(payload[4])
#                 fc = parse_exposure_compensation(payload[5])
#                 comp_text = f"EC={ec}, FC={fc}"
#                 # row_items.append(QTableWidgetItem(comp_text))

#             # for col, item in enumerate(row_items):  
#             #     table.setItem(i, col, item)

#         table.resizeColumnsToContents()
#         layout.addWidget(table)

#     def update_byte_field(self, row, byte_pos, mask, new_value):
#         """Helper to update specific bits in a byte"""
#         current = self.decoded['frames'][row][byte_pos]
#         self.decoded['frames'][row][byte_pos] = (current & ~mask) | (new_value & mask)

