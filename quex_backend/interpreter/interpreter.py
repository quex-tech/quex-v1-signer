from math import ceil, floor, sqrt
from datetime import datetime, timezone

def primitive_to_str(x):
    if type(x) == bool:
        return 'true' if x else 'false'
    elif type(x) == int or type(x) == float:
        return str(x)
    elif type(x) == str:
        return x
    elif x is None:
        return ""
    else:
        raise ValueError

def jq_eval(obj, ast):
    if ast.type == 'atomic':
        return ast.children[0]
    elif ast.type == 'ident':
        return ast.children[0]
    elif ast.type == 'true':
        return True
    elif ast.type == 'false':
        return False
    elif ast.type == 'null':
        return None
    elif ast.type == '.':
        return obj
    elif ast.type == '+':
        first = jq_eval(obj, ast.children[0])
        second = jq_eval(obj, ast.children[1])
        if first is None:
            return second
        if second is None:
            return first
        return first + second
    elif ast.type == '-':
        return jq_eval(obj, ast.children[0]) - jq_eval(obj, ast.children[1])
    elif ast.type == '*':
        return jq_eval(obj, ast.children[0]) * jq_eval(obj, ast.children[1])
    elif ast.type == '/':
        return jq_eval(obj, ast.children[0]) / jq_eval(obj, ast.children[1])
    elif ast.type == '%':
        return jq_eval(obj, ast.children[0]) % jq_eval(obj, ast.children[1])
    elif ast.type == 'select':
        obj = jq_eval(obj, ast.children[0])
        selector = jq_eval(obj, ast.children[1])
        if type(obj) == list:
            if -len(obj) <= selector < len(obj):
                return obj[selector]
            return None
        if selector in obj:
            return obj[selector]
        return None
    elif ast.type == 'slice':
        if len(ast.children) == 2:
            return jq_eval(obj, ast.children[0])[jq_eval(obj, ast.children[1]) : ]
        return jq_eval(obj, ast.children[0])[jq_eval(obj, ast.children[1]) : jq_eval(obj, ast.children[2])]
    elif ast.type == 'pipe':
        return jq_eval(jq_eval(obj, ast.children[0]), ast.children[1])
    elif ast.type == 'array':
        return [jq_eval(obj, x) for x in ast.children]
    elif ast.type == 'map':
        return [jq_eval(x, ast.children[0]) for x in obj]
    elif ast.type == 'tonumber':
        return float(obj)
    elif ast.type == 'floor':
        return floor(obj)
    elif ast.type == 'ceil':
        return ceil(obj)
    elif ast.type == 'round':
        return round(obj)
    elif ast.type == 'abs':
        return abs(obj)
    elif ast.type == 'sqrt':
        return sqrt(obj)
    elif ast.type == 'split':
        return obj.split(jq_eval(obj, ast.children[0]))
    elif ast.type == 'join':
        return jq_eval(obj, ast.children[0]).join([primitive_to_str(x) for x in obj])
    elif ast.type == 'fromdate':
        return int(datetime.fromisoformat(obj).timestamp())
    elif ast.type == 'todate':
        return datetime.fromtimestamp(obj, tz=timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')
    elif ast.type == 'add':
        return sum(obj)
    elif ast.type == 'any':
        return any(obj)
    elif ast.type == 'all':
        return all(obj)
    elif ast.type == 'length':
        return len(obj)
    elif ast.type == 'min':
        return min(obj)
    elif ast.type == 'max':
        return max(obj)
    elif ast.type == 'neg':
        return -jq_eval(obj, ast.children[0])
    elif ast.type == 'round':
        return round(obj)
    elif ast.type == '==':
        return jq_eval(obj, ast.children[0]) == jq_eval(obj, ast.children[1])
    elif ast.type == '!=':
        return jq_eval(obj, ast.children[0]) != jq_eval(obj, ast.children[1])
    elif ast.type == '>=':
        return jq_eval(obj, ast.children[0]) >= jq_eval(obj, ast.children[1])
    elif ast.type == '<=':
        return jq_eval(obj, ast.children[0]) <= jq_eval(obj, ast.children[1])
    elif ast.type == '>':
        return jq_eval(obj, ast.children[0]) > jq_eval(obj, ast.children[1])
    elif ast.type == '<':
        return jq_eval(obj, ast.children[0]) < jq_eval(obj, ast.children[1])
