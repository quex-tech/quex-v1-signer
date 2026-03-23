import struct
import unittest
from dataclasses import dataclass
from enum import IntEnum

from quex_backend.ride.mixins import (
    RideDecodable,
    RideEncodable,
    read_ride_bytes,
    write_ride_bytes,
)


class MyEnum(IntEnum):
    A = 0
    B = 1


@dataclass
class MyClass(RideEncodable, RideDecodable):
    a: int
    b: str


class TestWriteRideBytes(unittest.TestCase):
    def test_write_ride_bytes(self):
        cases = [
            (1, b"\x00\x00\x00\x00\x00\x00\x00\x01"),
            ("Hello", b"\x00\x00\x00\x00\x00\x00\x00\x05Hello"),
            (b"Hello", b"\x00\x00\x00\x00\x00\x00\x00\x05Hello"),
            (
                [1, 2, 3],
                b"\x00\x00\x00\x00\x00\x00\x00\x03\x00\x00\x00\x00\x00\x00\x00\x01\x00\x00\x00\x00\x00\x00\x00\x02\x00\x00\x00\x00\x00\x00\x00\x03",
            ),
            (MyEnum.A, b"\x00\x00\x00\x00\x00\x00\x00\x00"),
            (MyEnum.B, b"\x00\x00\x00\x00\x00\x00\x00\x01"),
            (
                MyClass(1, "Hello"),
                b"\x00\x00\x00\x00\x00\x00\x00\x01\x00\x00\x00\x00\x00\x00\x00\x05Hello",
            ),
        ]

        for input_value, expected in cases:
            with self.subTest(input_value=input_value, expected=expected):
                buf = bytearray()
                write_ride_bytes(input_value, buf)
                self.assertEqual(bytes(buf), expected)


class TestReadRideBytes(unittest.TestCase):
    def test_read_ride_bytes(self):
        cases = [
            (b"\x00\x00\x00\x00\x00\x00\x00\x05Hello", bytes, b"Hello"),
            (b"\x00\x00\x00\x00\x00\x00\x00\x05Hello", str, "Hello"),
            (
                b"\x00\x00\x00\x00\x00\x00\x00\x02\x00\x00\x00\x00\x00\x00\x00\x01\x00\x00\x00\x00\x00\x00\x00\x02",
                list[int],
                [1, 2],
            ),
            (b"\x00\x00\x00\x00\x00\x00\x00\x01", MyEnum, MyEnum.B),
            (
                b"\x00\x00\x00\x00\x00\x00\x00\x01\x00\x00\x00\x00\x00\x00\x00\x05Hello",
                MyClass,
                MyClass(1, "Hello"),
            ),
        ]

        for value, target_type, expected in cases:
            with self.subTest(input_value=value, target_type=target_type, expected=expected):
                actual, _ = read_ride_bytes(value, 0, target_type)
                self.assertEqual(actual, expected)

    def test_read_ride_bytes_invalid(self):
        cases = [
            (b"", int),
            (b"\x00\x00\x00\x01", int),
            (b"", str),
            (b"", bytes),
            (b"", bool),
            (b"", list[int]),
            (b"", MyEnum),
            (b"", MyClass),
            (b"\x00\x00\x00\x00\x00\x00\x00\x01", bytes),
            (b"\x00\x00\x00\x00\x00\x00\x00\x02\x00", bytes),
            (b"\x00\x00\x00\x00\x00\x00\x00\x01", str),
            (b"\x00\x00\x00\x00\x00\x00\x00\x02\x00", str),
        ]

        for value, target_type in cases:
            with self.subTest(input_value=value, target_type=target_type), self.assertRaises((ValueError, struct.error)):
                read_ride_bytes(value, 0, target_type)


if __name__ == "__main__":
    unittest.main()
