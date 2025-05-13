# -*- coding: utf-8 -*-
#

import time
import serial
from enum import IntEnum
from typing import Dict, List, Any
from PyQt5.QtCore import QObject, pyqtSignal, pyqtSlot

from util import *
from rolldata import *
from f90.constants import *




class F90Error(IntEnum):
    """Error codes for the F90 camera."""
    NO_ERROR         = 0
    NO_CONNECTION    = 1
    NO_RESPONSE      = 2
    INVALID_CHECKSUM = 3


class F90Response(IntEnum):
    """Response codes for the F90 camera."""
    PORT_OPENED    = 0
    PORT_CLOSED    = 1
    MODEL          = 2
    TOTAL_SHOTS    = 3
    MEMORY_INFO    = 4
    CURRENT_ROLL   = 7
    ROLL_DATA      = 8


class F90(QObject):
    # Emitted whenever a new chunk arrives
    progress = pyqtSignal(int)             
    error    = pyqtSignal(F90Error, str)
    response = pyqtSignal(F90Response, object)

    def __init__(self, port: str, baudrate: int = 1200, timeout: float = 2.0, parent: QObject = None) -> None:
        super().__init__(parent)
        self.port         = port
        self.baudrate     = baudrate
        self.timeout      = timeout
        self.is_connected = False
        self.memo_info    = None
        self.serial       = None


    def open(self) -> None:
        """Open the serial connection."""
        if self.is_connected:
            logger.warning("Serial port is already open")
        
        try:
            self.serial = serial.Serial(self.port, self.baudrate, timeout=self.timeout)
            self.is_connected = True
            self.response.emit(F90Response.PORT_OPENED, self.serial.is_open)

        except serial.SerialException as e:
            self.error.emit(F90Error.NO_CONNECTION, str(e))
            return False
        return True
    

    @pyqtSlot(bool)
    def close(self, force: bool = False) -> None:
        """Close the serial connection."""
        if not self.is_connected and not force:
            logger.warning("Serial port is already closed")
            return False
        
        try:
            if self.serial:
              self.serial.close()
              self.serial = None
        except serial.SerialException as e:
            logger.error(f"Error closing serial port: {e}")
            return False
        
        self.response.emit(F90Response.PORT_CLOSED, True)
        self.is_connected = False
        return True

    # --- high level commands ---

    @pyqtSlot()
    def init(self) -> None:
        STEPS = 8
        STEP  = 100 / STEPS

        self.progress.emit(int(STEP))
        if not self.open():
            self.close(True)
            return

        self.progress.emit(int(STEP * 2))
        self.wake_up()

        self.progress.emit(int(STEP * 3))
        self.model = self.query_model()
        if not self.model:
            self.close(True)
            return
        
        self.progress.emit(int(STEP * 4))
        self.set_9600_baud()

        self.progress.emit(int(STEP * 5))
        self.query_total_shots()

        self.progress.emit(int(STEP * 6))
        self.query_roll_data_info()
        
        self.progress.emit(int(STEP * 7))
        self.query_current_roll_info()

        self.progress.emit(100)


    @pyqtSlot()
    def wake_up(self) -> None:
        # Wake device
        logger.debug("Waking up camera")
        self.serial.write(b'\x00')
        time.sleep(0.2)
        self.serial.reset_input_buffer()


    @pyqtSlot()
    def query_model(self) -> str:
      logger.debug("Querying unit info")
      self.serial.write(b'S1000\x05')
      model = self.serial.read(16)

      if not model or len(model) < 7:
          self.error.emit(F90Error.NO_RESPONSE, "No response from camera")
          return None
      # if not model.startswith(b'1020') or model[-1] != 0x06:
      #     tlogging.error(f"Unexpected response from camera: {model}")
      #     raise RuntimeError(f"Unexpected response from camera: {model}")
      model = model[4:-3].decode('utf-8', errors='ignore')
      logger.debug(f"Camera model: {model}")
      self.response.emit(F90Response.MODEL, model)
      return model


    @pyqtSlot()
    def query_total_shots(self) -> int:
        total_shots = self.read_le16(TOTAL_SHOTS_ADDR)
        logger.debug(f"Total shots: {total_shots}")
        if total_shots is None:
            self.error.emit(F90Error.NO_RESPONSE, "No response from camera")
        self.response.emit(F90Response.TOTAL_SHOTS, total_shots)
        return total_shots


    @pyqtSlot()
    def query_current_roll_info(self) -> int:
        current_roll = self.read_data(0, ROLL_NUMBER_ADDR, 2)
        current_roll = bcd_to_int(current_roll[0]) + bcd_to_int(current_roll[1]) * 100
        logger.debug(f"Current roll: {current_roll}")
        if current_roll is None:
            self.error.emit(F90Error.NO_RESPONSE, "No response from camera")
            return None
        
        current_frame = self.read_register(FRAME_NUMBER_ADDR)
        logger.debug(f"Current frame: {current_frame}")
        if current_frame is None:
            self.error.emit(F90Error.NO_RESPONSE, "No response from camera")
            return None
    
        result = {'roll': current_roll, 'frame': current_frame}
        self.response.emit(F90Response.CURRENT_ROLL, result)
        return result


    @pyqtSlot()
    def query_roll_data_info(self) -> Dict[str, Any]:
        logger.debug("Fetching memo holder info")

        if not self.is_connected:
            return

        try:
            self.serial.write(bytes([0x01, 0x20, 0x1B, 0x92, 0, 0, 0, 0, END_BYTE]))
            info = self.read_packet()
            first_roll_number = bcd_to_int(info[0]) + bcd_to_int(info[1]) * 10
            first_roll_length = int.from_bytes(info[2:4], 'little')
        
            start         = time.time()
            rs_re         = self.read_data(0, RING_BUF_ADDRS_ADDR, 4)
            rb_start      = int.from_bytes(rs_re[0:2], 'little')
            rb_end        = int.from_bytes(rs_re[2:4], 'little')
            wp_sp_ip      = self.read_data(0, MEMO_SETTINGS_ADDR, 8)
            frame_sz      = FRAME_SIZES[wp_sp_ip[0]]
            rb_write_ptr  = int.from_bytes(wp_sp_ip[2:4], 'little')
            rb_start_ptr  = int.from_bytes(wp_sp_ip[4:6], 'little') - 4  # Uncomment to read headers too
            rb_insert_ptr = int.from_bytes(wp_sp_ip[6:8], 'little')

            logger.debug(f"Time to read ring metadata: {time.time() - start:.3f} seconds")
            logger.debug(f"Ring start: {rb_start:#06x}, end: {rb_end:#06x}, frame size: {frame_sz} bytes")
            logger.debug(f"Write pointer: {rb_write_ptr:#06x}, start pointer: {rb_start_ptr:#06x}, insert pointer: {rb_insert_ptr:#06x}")

            # Check if memo holder is enabled
            memo_enabled = wp_sp_ip[0] & 0x40
            logger.debug(f"Memo holder enabled: {memo_enabled}")

            # Determine storage mode
            storage_mode = F90StorageMode(wp_sp_ip[0] & 0x1F)
            logger.debug(f"Storage mode: {storage_mode.name}")

            # Determine total bytes in the ring buffer to read (including headers/skips)
            used = 0
            if rb_start_ptr == rb_insert_ptr:
                logger.debug("No data in ring buffer")
            elif rb_start_ptr == rb_end:
                logger.debug("Ring buffer is full")
            elif rb_start_ptr < rb_insert_ptr:
                used = rb_insert_ptr - rb_start_ptr
            else:
                used = (rb_end - rb_start_ptr) + (rb_insert_ptr - rb_start)
            logger.debug(f"Total bytes used by ring buffer: {used} (approx. {int(used / frame_sz * .96)} frames)")

            result = {
                'ring_start':        rb_start,
                'ring_end':          rb_end,
                'write_ptr':         rb_write_ptr,
                'start_ptr':         rb_start_ptr,
                'insert_ptr':        rb_insert_ptr,
                'memo_enabled':      memo_enabled,
                'storage_mode':      storage_mode,
                'frame_size':        frame_sz,
                'bytes_used':        used,
                'first_roll_number': first_roll_number,
                'first_roll_length': first_roll_length,
            }
            self.memo_info = result
            self.response.emit(F90Response.MEMORY_INFO, result)
            return result
        
        except Exception as e:
            logger.error(f"Error querying roll data: {e}")
            self.error.emit(F90Error.NO_RESPONSE, str(e))
            return None


    @pyqtSlot()
    def query_roll_data(self) -> Dict[str, Any]:
        logger.debug(f"Reading shooting data at pointer")

        if not self.is_connected:
            logger.error("Camera not connected")
            self.error.emit(F90Error.NO_RESPONSE, "Camera not connected")
            return None
        
        if self.memo_info is None:
            self.query_roll_data_info()
    
    
        # Aggregate roll payloads to capture all frames exactly
        content   = bytearray()
        ptr       = self.memo_info['start_ptr']
        used      = self.memo_info['bytes_used']
        rb_start  = self.memo_info['ring_start']
        rb_end    = self.memo_info['ring_end']
        chunk_idx = 0
        consumed  = 0
        
        # Continue until we've consumed all bytes in the ring buffer
        start = time.time()
        while consumed < used:        
            length = min(0x20, used - consumed)
            logger.debug(f"Roll data chunk #{chunk_idx}, length={length}")

            # Read roll data
            try:
                content.extend(self.read_data(1, ptr, length))
            except Exception as e:
                logger.error(f"Error reading roll data: {e}")
                return None

            # Advance pointer with wrap and account consumed
            consumed += length
            ptr = rb_start + ((ptr - rb_start + length) % (rb_end - rb_start))
            chunk_idx += 1

            self.progress.emit(int(100 * consumed / used))
        logger.info(f"Time to read ring data: {time.time() - start:.3f} seconds for {len(content)} bytes")

        # prepend missing header bytes if necessary
        if content[0] != 0x58 or content[1] != 0x5A:
          content = b'\x58\x5A\0\0' + content
        
        # Split roll data into individual frames and decode
        result = []
        rolls = split_rolls(content)
        for roll in rolls:
            try:
                result.append(decode_roll_data(
                    roll, 
                    model    = self.model,
                    frame_sz = self.memo_info['frame_size'],
                  ))
            except Exception as e:
              continue
        self.response.emit(F90Response.ROLL_DATA, result)

        logger.debug(f"Received {len(content)} bytes of roll data")
        return content
        


    #  --- low level commands ---

    @pyqtSlot()
    def set_9600_baud(self) -> bool:
        self.serial.reset_input_buffer()
        self.serial.write(bytes([0x01, 0x20, 0x87, 0x05, 0, 0, 0, 0, END_BYTE]))
        resp = self.serial.read(2)
        if resp != b'\x06\x00':
            logger.error("Failed to switch baud rate to 9600")
            # raise RuntimeError("Failed to switch baud rate to 9600")
        # if not resp or resp[1] != b'\x06':
        #     logger.error("Failed to switch baud rate to 9600")
        #     return False
        # else:
        #     logger.info("Baud rate switched successfully to 9600")
        time.sleep(0.2)
        self.serial.reset_input_buffer()
        self.serial.baudrate = 9600


    def set_1200_baud(self) -> bool:
        self.serial.reset_input_buffer()
        self.serial.write(b"\x04\x04")
        resp = self.serial.read(2)
        # if not resp or resp[0] != b'\x04' and resp[1] != b'\x04':
        #     logger.error("Failed to switch baud rate to 1200")
        #     return False
        # else:
        #     logger.info("Baud rate switched successfully to 1200")
        time.sleep(0.2)
        self.serial.reset_input_buffer()
        self.serial.baudrate = 1200








    # Build read-memory command
    def read_cmd(self, space, addr, length):
        hi, lo = (addr >> 8) & 0xFF, addr & 0xFF
        cmd = bytes([0x01, 0x20, 0x80, space, hi, lo, 0x00, length, 0x03])
        # tlogging.debug(f"TX read: space=0x{space:02X}, addr=0x{addr:06X}, len={length}")
        return cmd

    # Read arbitrary-length data by chunking
    def read_data(self, space, addr, length):
        # tlogging.debug(f"Read_data start: addr=0x{addr:06X}, len={length}")
        offset = 0
        result = bytearray()
        start  = time.time()

        while offset < length:
            self.serial.reset_input_buffer()
            chunk = min(0x80, length - offset)
            cmd = self.read_cmd(space, addr + offset, chunk)
            self.serial.write(cmd)
            packet = self.read_packet()
            result.extend(packet)
            # tlogging.debug(f"  chunk {offset}-{offset+chunk} read, {len(packet)} bytes")
            offset += chunk
            
            if time.time() - start > self.timeout:
                logger.error("Timeout waiting for data")
                self.error.emit(F90Error.NO_RESPONSE, "Timeout waiting for data")
                raise TimeoutError("Timeout waiting for data")
        return bytes(result)

    # Read one packet
    def read_packet(self):
        start = time.time()
        # wait STX
        while True:
            b = self.serial.read(1)
            if b and b[0] == STX: 
                break
            if time.time() - start > self.timeout:
                logger.error("Timeout waiting for STX")
                self.error.emit(F90Error.NO_RESPONSE, "Timeout waiting for STX")
                raise TimeoutError("Timeout waiting for STX")
        
        # read until ETX
        buf = bytearray()
        start = time.time()
        while True:
            b = self.serial.read(1)
            if not b: 
                continue
            if b[0] == ETX: 
                break
            buf.append(b[0])
            if time.time() - start > self.timeout:
                logger.error("Timeout waiting for ETX")
                self.error.emit(F90Error.NO_RESPONSE, "Timeout waiting for ETX")
                raise TimeoutError("Timeout waiting for ETX")

        payload, chk = buf[:-1], buf[-1]
        if checksum(payload) != chk:
            logger.error(f"Checksum mismatch {checksum(payload):02X} vs {chk:02X}")
            self.error.emit(F90Error.INVALID_CHECKSUM, "Checksum mismatch")
            raise ValueError(f"Checksum mismatch {checksum(payload):02X} vs {chk:02X}")

        # tlogging.debug(f"RX payload len={len(payload)}")
        return payload

    def read_register(self, addr):
        return self.read_data(0x00, addr, 1)[0]

    def read_le16(self, addr):
        d = self.read_data(0x00, addr, 2)
        return d[0] | (d[1] << 8)





def split_rolls(raw: bytes) -> List[bytes]:
    """
    Split raw concatenated payloads into individual roll blobs
    by finding each 0xFF terminator plus its ISO byte.
    """
    rolls = []
    idx = 0
    # rolls start with 0x58 0x5a end with 0xFF <iso_code>
    while idx < len(raw):
        # Find the start of a roll (0x58 0x5A)
        start = raw.find(b'\x58\x5A', idx)
        if start == -1:
            break
        # Find the end of the roll (0xFF <iso_code>)
        end = raw.find(b'\xFF', start + 2)
        if end == -1:
            roll_data = raw[start:]
            rolls.append(roll_data)
            break
        # Extract the roll data
        roll_data = raw[start:end + 2]
        rolls.append(roll_data)
        idx = end + 2
    return rolls



def decode_roll_data(raw: bytes, frame_sz:int, model="F90x") -> RollData:
    """
    Decode one intermediate-mode roll blob (4-byte frames).

    Args:
      raw          - bytes of one roll including header (8), frames, FF, ISO.
      roll_number  - the human-assigned roll ID.

    Returns:
      dict with 'roll_number', 'iso_code', 'frames' list of dicts.
    """
    iso = parse_iso(raw[-1])
    payload = raw[6:-2]
    frames = []
    # get Roll number (binary-coded decimal)
    roll_number = bcd_to_int(raw[4]) + bcd_to_int(raw[5]) * 100

    for i in range(0, len(payload), frame_sz):
        frame = payload[i:i+frame_sz]
        if len(frame) < 2:
            break
        frames.append({
            ExifTagNames.ImageNumber: len(frames) + 1,
            ExifTagNames.Shutter:     parse_shutter(frame[0]),
            ExifTagNames.Aperture:    parse_aperture(frame[1]),
            ExifTagNames.ISO:         iso,
            ExifTagNames.Make:        "Nikon",
            ExifTagNames.Model:       model,
        })
        if frame_sz >= 4:
            frames[-1].update({
                ExifTagNames.FocalLength:  parse_focal_length(frame[3]),
                ExifTagNames.ExposureMode: parse_exposure_mode(frame[2] & 0b00001111),
                ExifTagNames.MeteringMode: parse_metering_mode((frame[2] & 0b00110000) >> 4),
                ExifTagNames.Flash:        parse_flash_mode((frame[2] & 0b11000000) >> 6)
            })
        if frame_sz >= 6:
            frames[-1].update({
                ExifTagNames.ExposureCompensation: parse_exposure_compensation(frame[4]),
                # ExifTagNames.FlashCompensation: parse_flash_compensation(frame[5])
            })
    
    return RollData(roll_number, iso, frames)
