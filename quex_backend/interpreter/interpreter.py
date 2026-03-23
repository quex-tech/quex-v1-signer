import base64
import math
from datetime import UTC, datetime

from .iterator import JqIterator


def _primitive_to_str(x):
    if type(x) is bool:
        return "true" if x else "false"
    elif type(x) is int or type(x) is float:
        return str(x)
    elif type(x) is str:
        return x
    elif x is None:
        return ""
    else:
        raise ValueError


def _iterate_values(obj):
    if isinstance(obj, list):
        return obj
    if isinstance(obj, dict):
        return obj.values()
    raise ValueError("Cannot iterate over type", type(obj))


def _object_to_bool(obj):
    return obj is not False and obj is not None


def _binop_add(left, right):
    if left is None:
        return right
    if right is None:
        return left
    if isinstance(left, list) and isinstance(right, list):
        return left + right
    if isinstance(left, str) and isinstance(right, str):
        return left + right
    if isinstance(left, (int, float)) and isinstance(right, (int, float)):
        return left + right
    raise ValueError(f"Cannot add {type(left)} and {type(right)} values")


def _binop_sub(left, right):
    if isinstance(left, (int, float)) and isinstance(right, (int, float)):
        return left - right
    raise ValueError(f"Cannot subtract {type(left)} and {type(right)} values")


def _binop_mul(left, right):
    if isinstance(left, (int, float)) and isinstance(right, (int, float)):
        return left * right
    raise ValueError(f"Cannot multiply {type(left)} and {type(right)} values")


def _binop_div(left, right):
    if isinstance(left, (int, float)) and isinstance(right, (int, float)):
        return left / right
    raise ValueError(f"Cannot divide {type(left)} and {type(right)} values")


def _binop_mod(left, right):
    if isinstance(left, (int, float)) and isinstance(right, (int, float)):
        return left % right
    raise ValueError(f"Cannot modulo {type(left)} and {type(right)} values")


def _binop_eq(left, right):
    return left == right


def _binop_neq(left, right):
    return left != right


def _binop_lt(left, right):
    return left < right


def _binop_le(left, right):
    return left <= right


def _binop_gt(left, right):
    return left > right


def _binop_ge(left, right):
    return left >= right


def _binop_or(left, right):
    return _object_to_bool(left) or _object_to_bool(right)


def _binop_and(left, right):
    return _object_to_bool(left) and _object_to_bool(right)


def _binop_alt(left, right):
    return left or right


def binop(op, left, right):
    operations = {
        "+": _binop_add,
        "-": _binop_sub,
        "*": _binop_mul,
        "/": _binop_div,
        "%": _binop_mod,
        "==": _binop_eq,
        "!=": _binop_neq,
        "<": _binop_lt,
        "<=": _binop_le,
        ">": _binop_gt,
        ">=": _binop_ge,
        "or": _binop_or,
        "and": _binop_and,
        "//": _binop_alt,
    }
    if op not in operations:
        raise ValueError(f"Unsupported operator: {op}")
    operation = operations[op]
    if isinstance(left, JqIterator) and isinstance(right, JqIterator):
        raise ValueError("Cannot perform binary operation on two iterators")
    if isinstance(left, JqIterator):
        return JqIterator([operation(x, right) for x in left])
    if isinstance(right, JqIterator):
        return JqIterator([operation(left, x) for x in right])
    return operation(left, right)


def select(obj, selector):
    if isinstance(obj, JqIterator):
        return JqIterator([select(x, selector) for x in obj])
    if isinstance(obj, dict):
        if selector in obj:
            return obj[selector]
        return None
    if isinstance(obj, list):
        if -len(obj) <= selector < len(obj):
            return obj[selector]
        return None
    raise ValueError(f"Cannot select {type(obj)} with {type(selector)}")


def slice(obj, start, end):
    if isinstance(obj, (str, list)):
        if start is None:
            start = 0
        if end is None:
            end = len(obj)
        return obj[start:end]
    raise ValueError(f"Cannot slice {type(obj)}")


def _func_add(obj: list):
    if len(obj) == 0:
        return None
    result = obj[0]
    for i in range(1, len(obj)):
        result += obj[i]
    return result


def function_no_args(func, obj):
    functions = {
        "abs": abs,
        "ceil": math.ceil,
        "floor": math.floor,
        "round": round,
        "sqrt": math.sqrt,
        "length": len,
        "min": min,
        "max": max,
        "todate": lambda x: datetime.fromtimestamp(x, tz=UTC).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "fromdate": lambda x: int(datetime.fromisoformat(x).timestamp()),
        "tonumber": float,
        "any": any,
        "all": all,
        "add": _func_add,
        "not": lambda x: not x,
        "@base64": lambda x: base64.b64encode(x.encode("utf-8")).decode("utf-8"),
        "@base64d": lambda x: base64.b64decode(x.encode("utf-8")).decode("utf-8"),
        "keys": lambda x: sorted(x.keys()),
        "to_entries": lambda x: [{"key": a, "value": b} for a, b in x.items()],
        "to_bytes": lambda x: x.encode("utf8"),
    }
    supported_types = {
        "abs": (int, float),
        "ceil": (int, float),
        "floor": (int, float),
        "round": (int, float),
        "sqrt": (int, float),
        "length": (str, list),
        "min": (list,),
        "max": (list,),
        "todate": (int,),
        "fromdate": (str,),
        "tonumber": (str, int, float),
        "any": (list,),
        "all": (list,),
        "add": (list,),
        "not": (bool,),
        "@base64": (str,),
        "@base64d": (str,),
        "keys": (dict,),
        "to_entries": (dict,),
        "to_bytes": (str,),
    }

    preprocess_functions = {
        "not": _object_to_bool,
    }

    target = obj

    if func not in functions:
        raise ValueError(f"Unsupported function: {func}")

    if isinstance(target, JqIterator):
        return JqIterator([functions[func](x) for x in target])

    if func in preprocess_functions:
        target = preprocess_functions[func](target)

    if not isinstance(target, supported_types[func]):
        raise ValueError(f"Cannot apply {func} to {type(target)}")

    return functions[func](obj)


def function_with_one_arg(func, obj, arg):
    functions = {
        "neg": lambda _, arg: -arg,
        "split": lambda obj, arg: obj.split(arg),
        "join": lambda obj, arg: arg.join([_primitive_to_str(x) for x in _iterate_values(obj)]),
        "map": lambda obj, arg: [jq_eval(x, arg) for x in _iterate_values(obj)],
        "iterator": lambda _, arg: JqIterator(list(arg.values()) if isinstance(arg, dict) else arg),
        "toarray": lambda _, arg: list(arg),
    }

    supported_obj_types = {
        "split": (str,),
        "join": (list,),
        "map": (list, dict),
    }

    need_eval_arg = set(
        [
            "neg",
            "split",
            "join",
            "iterator",
        ]
    )

    supported_arg_types = {
        "neg": (int, float),
        "split": (str,),
        "join": (str,),
        "iterator": (dict, list),
    }
    if func not in functions:
        raise ValueError(f"Unsupported function: {func}")

    if isinstance(obj, JqIterator):
        return JqIterator([functions[func](x, arg) for x in obj])

    if func in need_eval_arg:
        arg = jq_eval(obj, arg)

    if func in supported_obj_types and not isinstance(obj, supported_obj_types[func]):
        raise ValueError(f"Object type {type(obj)} not supported for {func}")

    if func in supported_arg_types and not isinstance(arg, supported_arg_types[func]):
        raise ValueError(f"Argument type {type(arg)} not supported for {func}")

    return functions[func](obj, arg)


def jq_eval(obj, ast):
    if ast.type == "atomic" or ast.type == "ident":
        return ast.children[0]
    elif ast.type == "true":
        return True
    elif ast.type == "false":
        return False
    elif ast.type == "null":
        return None
    elif ast.type == ".":
        return obj
    elif ast.type == "binop":
        operator = ast.children[0]
        left = jq_eval(obj, ast.children[1])
        right = jq_eval(obj, ast.children[2])
        return binop(operator, left, right)
    elif ast.type == "select":
        target = jq_eval(obj, ast.children[0])
        selector = jq_eval(obj, ast.children[1])
        return select(target, selector)
    elif ast.type == "slice":
        target = jq_eval(obj, ast.children[0])
        start = jq_eval(obj, ast.children[1])
        end = jq_eval(obj, ast.children[2])
        return slice(target, start, end)
    elif ast.type == "pipe":
        return jq_eval(jq_eval(obj, ast.children[0]), ast.children[1])
    elif ast.type == "array":
        result = []
        for child in ast.children:
            values = jq_eval(obj, child)
            if isinstance(values, JqIterator):
                result.extend(values)
            else:
                result.append(values)
        return result
    elif ast.type == "func_no_args":
        return function_no_args(ast.children[0], obj)
    elif ast.type == "func_with_one_arg":
        return function_with_one_arg(ast.children[0], obj, ast.children[1])
    else:
        raise ValueError(f"Unknown node type: {ast.type}")
