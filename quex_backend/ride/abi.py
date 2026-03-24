import struct
from typing import Any

from eth_abi.base import parse_type_str, parse_tuple_type_str
from eth_abi.encoding import BaseEncoder
from eth_abi.exceptions import ValueOutOfBounds
from eth_abi.codec import ABIEncoder
from eth_abi.registry import ABIRegistry, is_base_tuple, has_arrlist, BaseEquals


class IntegerEncoder(BaseEncoder):
    def validate_value(self, value: Any) -> None:
        if not isinstance(value, int):
            type(self).invalidate_value(value, msg="must be an integer")

    def encode(self, value: Any) -> bytes:
        return struct.pack(">q", value)

    @classmethod
    @parse_type_str("int")
    def from_type_str(cls, type_str: Any, registry: Any) -> "IntegerEncoder":
        return cls()


class UnsignedIntegerEncoder(BaseEncoder):
    def validate_value(self, value: Any) -> None:
        if not isinstance(value, int):
            type(self).invalidate_value(value, msg="must be an integer")
        if value < 0:
            type(self).invalidate_value(value, msg="must be non-negative")

    def encode(self, value: Any) -> bytes:
        return struct.pack(">Q", value)

    @classmethod
    @parse_type_str("uint")
    def from_type_str(cls, type_str: Any, registry: Any) -> "UnsignedIntegerEncoder":
        return cls()


class BoolEncoder(BaseEncoder):
    def validate_value(self, value: Any) -> None:
        if not isinstance(value, bool):
            type(self).invalidate_value(value, msg="must be a boolean")

    def encode(self, value: Any) -> bytes:
        return struct.pack(">q", 1 if value else 0)

    @classmethod
    @parse_type_str("bool")
    def from_type_str(cls, type_str: Any, registry: Any) -> "BoolEncoder":
        return cls()


class StringEncoder(BaseEncoder):
    def validate_value(self, value: Any) -> None:
        if not isinstance(value, str):
            type(self).invalidate_value(value, msg="must be a string")

    def encode(self, value: Any) -> bytes:
        bytestr = value.encode()
        length = len(bytestr)
        res = bytearray(8 + length)
        struct.pack_into(">q", res, 0, length)
        res[8:] = bytestr
        return bytes(res)

    @classmethod
    @parse_type_str("string")
    def from_type_str(cls, type_str: Any, registry: Any) -> "StringEncoder":
        return cls()


class TupleEncoder(BaseEncoder):
    def __init__(self, encoders: tuple[BaseEncoder, ...]) -> None:
        super().__init__()
        self.encoders = encoders

    def validate_value(self, value: Any) -> None:
        if not isinstance(value, (tuple, list)):
            type(self).invalidate_value(value, msg="must be a tuple or list")

        if len(value) != len(self.encoders):
            self.invalidate_value(
                value,
                exc=ValueOutOfBounds,
                msg=f"value has {len(value)} items when {len(self.encoders)} were "
                "expected",
            )

        for item, encoder in zip(value, self.encoders):
            encoder.validate_value(item)

    def encode(self, value: Any) -> bytes:
        res = bytearray()
        for field, encoder in zip(value, self.encoders):
            res.extend(encoder.encode(field))
        return bytes(res)

    @classmethod
    @parse_tuple_type_str
    def from_type_str(cls, type_str: Any, registry: Any) -> "TupleEncoder":
        encoders = tuple(
            registry.get_encoder(comp.to_type_str()) for comp in type_str.components
        )
        return cls(encoders=encoders)


class ArrayEncoder(BaseEncoder):
    def __init__(self, item_encoder: BaseEncoder, array_size: int | None = None) -> None:
        super().__init__()
        self.item_encoder = item_encoder
        self.array_size = array_size

    def validate_value(self, value: Any) -> None:
        if not isinstance(value, list):
            type(self).invalidate_value(value, msg="must be a list")

        if self.array_size is not None and len(value) != self.array_size:
            self.invalidate_value(
                value,
                exc=ValueOutOfBounds,
                msg=f"value has {len(value)} items when {self.array_size} were "
                "expected",
            )

        for item in value:
            self.item_encoder.validate_value(item)

    def encode(self, value: Any) -> bytes:
        res = bytearray()
        if not self.array_size:
            res.extend(struct.pack(">q", len(value)))
        for item in value:
            res.extend(self.item_encoder.encode(item))
        return bytes(res)

    @classmethod
    @parse_type_str(with_arrlist=True)
    def from_type_str(cls, type_str: Any, registry: Any) -> "ArrayEncoder":
        item_encoder = registry.get_encoder(type_str.item_type.to_type_str())
        array_spec = type_str.arrlist[-1]

        return cls(
            item_encoder=item_encoder,
            array_size=array_spec[0] if len(array_spec) == 1 else None,
        )


registry = ABIRegistry()
registry.register_encoder(BaseEquals("int"), IntegerEncoder)
registry.register_encoder(BaseEquals("uint"), UnsignedIntegerEncoder)
registry.register_encoder(BaseEquals("bool"), BoolEncoder)
registry.register_encoder(BaseEquals("string"), StringEncoder)
registry.register_encoder(is_base_tuple, TupleEncoder)
registry.register_encoder(has_arrlist, ArrayEncoder)

encoder = ABIEncoder(registry)
