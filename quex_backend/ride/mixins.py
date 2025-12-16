import struct
from abc import ABC
from dataclasses import fields
from enum import IntEnum
from typing import get_origin, get_args


class RideEncodable(ABC):
    def to_ride_bytes(self) -> bytes:
        buf = bytearray()
        self.write_ride_bytes(buf)
        return bytes(buf)

    def write_ride_bytes(self, buf):
        for f in fields(self):
            write_ride_bytes(getattr(self, f.name), buf)


class RideDecodable(ABC):
    @classmethod
    def from_ride_bytes(cls, buf):
        v, _ = cls.read_ride_bytes(buf, 0)
        return v

    @classmethod
    def read_ride_bytes(cls, buf, off):
        kwargs = {}
        newoff = off
        for f in fields(cls):
            v, newoff = read_ride_bytes(buf, newoff, f.type)
            kwargs[f.name] = v
        return cls(**kwargs), newoff


class UnsupportedRideTypeError(BaseException):
    pass


def write_ride_bytes(value, buf):
    if isinstance(value, int):
        buf.extend(struct.pack(">q", value))
        return
    if isinstance(value, bool):
        buf.extend(struct.pack(">q", 1 if value else 0))
        return
    if isinstance(value, bytes):
        buf.extend(struct.pack(">q", len(value)))
        buf.extend(value)
        return
    if isinstance(value, str):
        bytestr = value.encode()
        buf.extend(struct.pack(">q", len(bytestr)))
        buf.extend(bytestr)
        return
    if isinstance(value, list):
        buf.extend(struct.pack(">q", len(value)))
        for item in value:
            write_ride_bytes(item, buf)
        return
    if isinstance(value, IntEnum):
        buf.extend(struct.pack(">q", value.value))
        return
    if isinstance(value, RideEncodable):
        value.write_ride_bytes(buf)
        return
    raise UnsupportedRideTypeError


def read_ride_bytes(buf, off, target_type):
    if target_type is int:
        return struct.unpack_from(">q", buf, off)[0], off + 8
    if target_type is bool:
        return struct.unpack_from(">q", buf, off)[0] != 0, off + 8
    if target_type is bytes:
        end = off + 8 + struct.unpack_from(">q", buf, off)[0]
        if end > len(buf):
            raise ValueError("not enough bytes")
        return buf[off + 8 : end], end
    if target_type is str:
        end = off + 8 + struct.unpack_from(">q", buf, off)[0]
        if end > len(buf):
            raise ValueError("not enough bytes")
        return buf[off + 8 : end].decode(), end
    if get_origin(target_type) is list:
        inner_type = get_args(target_type)[0]
        count = struct.unpack_from(">q", buf, off)[0]
        newoff = off + 8
        res = list()
        for i in range(count):
            v, newoff = read_ride_bytes(buf, newoff, inner_type)
            res.append(v)
        return res, newoff
    if isinstance(target_type, type) and issubclass(target_type, IntEnum):
        return target_type(struct.unpack_from(">q", buf, off)[0]), off + 8
    if isinstance(target_type, type) and issubclass(target_type, RideDecodable):
        return target_type.read_ride_bytes(buf, off)
    raise UnsupportedRideTypeError
