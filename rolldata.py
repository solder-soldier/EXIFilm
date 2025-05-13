# -*- coding: utf-8 -*-
#

import csv
import json
from typing import Any, Dict

from util import *
from f90.constants import *

COLUMNS = [
    ExifTagNames.ImageNumber,
    ExifTagNames.Shutter,
    ExifTagNames.Aperture,
    ExifTagNames.FocalLength,
    ExifTagNames.ISO,
    ExifTagNames.ExposureMode,
    ExifTagNames.MeteringMode,
    ExifTagNames.Flash,
]




def split_binary_roll_data(raw: bytes, mode: int=0x4E) -> Dict[str, Any]:
    roll_num = int.from_bytes(raw[0:2], 'little')
    print(f"Roll #{roll_num} header parsed.")
    sdf = raw[-1]
    payload_len = FRAME_SIZES.get(raw[-1])
    if payload_len is None:
        raise ValueError(f"Invalid storage mode: {mode}")

    frames: List[bytes] = []
    idx = 2
    while idx < len(raw) and raw[idx] != 0xFF:
        chunk = raw[idx: idx + payload_len]
        if len(chunk) < payload_len:
            print("Truncated frame payload")
            break
        frames.append(chunk)
        idx += payload_len

    if idx > len(raw) or raw[-3] != 0xFF:
        print("Terminator 0xFF or ISO byte missing")
        iso = None
    else:
        iso = raw[-2]
        print(f"ISO: {parse_iso(iso)} (0x{iso:02X})")

    print(f"{idx} bytes read, {len(frames)} frames found")
    return frames, roll_num, iso



def decode_binary_roll_data(frames:List, iso:int, roll:int):
    iso = parse_iso(iso)
    decoded_frames = []

    for i, frame in enumerate(frames):
        decoded_frame = {
            ExifTagNames.ImageNumber: i + 1,
            ExifTagNames.Shutter:     parse_shutter(frame[0]),
            ExifTagNames.Aperture:    parse_aperture(frame[1]),
            ExifTagNames.ISO:         iso,
            ExifTagNames.Make:        "Nikon",
            ExifTagNames.Model:       "F90_X",
        }

        if len(frame) >= 4:
            decoded_frame[ExifTagNames.FocalLength] = parse_focal_length(frame[3])
            decoded_frame[ExifTagNames.ExposureMode] = parse_exposure_mode(frame[2] & 0b00001111)
            decoded_frame[ExifTagNames.MeteringMode] = parse_metering_mode((frame[2] & 0b00110000) >> 4)
            decoded_frame[ExifTagNames.Flash] = parse_flash_mode((frame[2] & 0b11000000) >> 6)
            
        # if len(payload) >= 6:
        #     decoded_frame[ExifTagNames.ExposureCompensation] = payload[4]
        #     decoded_frame[ExifTagNames.FlashCompensation]    = payload[5]
        decoded_frames.append(decoded_frame)
    return decoded_frames, roll, iso



class RollData:
    def __init__(self, roll_number: int, iso: int, frames: List=[], desc: str=""):
        self.roll_number = roll_number
        self.iso         = iso
        self.desc        = desc
        self.frames      = frames


    def __str__(self):
        return f"Roll {self.roll_number} ({self.iso}) - {len(self.frames)} frames"


    def save_csv(self, filename: str):
        with open(filename, 'w') as f:
            # print heeader: roll number, iso
            f.write(f"# Roll Number,{self.roll_number}\n")
            f.write(f"# ISO,{self.iso}\n")
            f.write(f"# Frames,{len(self.frames)}\n")
            f.write(f"# Description,{len(self.desc)}\n")

            f.write(f"{', '.join([col.string for col in COLUMNS])}\n")
            for i, frame in enumerate(self.frames):
                for col in COLUMNS:
                    if col in frame:
                        # format aperture and shutter
                        if col == ExifTagNames.Shutter:
                            f.write(f"{format_exposure_time(frame[col])},")
                        elif col == ExifTagNames.Aperture:
                            f.write(f"{format_aperture(frame[col])},")
                        elif col == ExifTagNames.FocalLength:
                            f.write(f"{frame[col]} mm,")
                        else:
                            f.write(f"{frame[col]},")
                    else:
                        continue
                        # f.write("Unknown,")
                f.write("\n")
        logger.debug(f"Saved {len(self.frames)} frames to {filename}")


    def save_json(self, filename: str):
        # convert value exiftagenames (keys of frames) to hex numbers
        frames = []
        for frame in self.frames:
            frame_dict = {}

            for key, value in frame.items():
                _key = f"{key.value:#04x}"
                frame_dict[_key] = value
            frames.append(frame_dict)

        data = {
            'roll_number': self.roll_number,
            'iso':         self.iso,
            'description': self.desc,
            'frames':      frames,
        }
        
        # save the roll data
        with open(filename, 'w') as f:
            json.dump(data, f, indent=4)
        logger.debug(f"Saved {len(self.frames)} frames to {filename}")


    @classmethod
    def from_json(cls, filename: str):
        with open(filename, 'r') as f:
            data = json.load(f)
        
        # get the roll data
        roll = data['roll_number']
        iso = data['iso']
        desc = data['description']
        frames = data['frames']
        
        # convert hex numbers to ExifTagNames
        _frames = []
        for frame in frames:
            frame_dict = {}
            for key, value in frame.items():
                _key = ExifTagNames(int(key, 16))
                frame_dict[_key] = value
            _frames.append(frame_dict)

        # create the class instance
        return cls(roll, iso, _frames, desc)


    @classmethod
    def from_csv(cls, path):
        frames = []
        return cls(roll=42, iso=1337, frames=frames)
    
        with open(path, newline='') as f:
            reader = csv.DictReader(f)
            frames = list(reader)
        # assume first row contains roll and iso as columns, or modify as needed:
        roll_num = frames[0].get('roll_number', 'Unknown')
        iso      = frames[0].get('iso', 'Unknown')
        desc     = frames[0].get('description', '')
        return cls(roll=roll_num, iso=iso, frames=frames, desc=desc)



