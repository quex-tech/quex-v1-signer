import ply.lex as lex
import re

tokens = [
    'STRING', 
    'IDENT',
    'INT',
    'FLOAT',
    'TRUE',
    'FALSE',
    'NULL',
    'FUNCTION_NO_ARGS',
    'FUNCTION_WITH_ARGS',
    'OR',
    'AND',
    'NOT',
    'EQ',
    'NEQ',
    'LT',
    'LE',
    'GT',
    'GE',
    'ALT',
    'ITERATOR',
]

literals = "+-*/%()[]().,|:"

t_EQ = r'=='
t_NEQ = r'!='
t_LE = r'<='
t_GE = r'>='
t_LT = r'<'
t_GT = r'>'
t_ALT = r'//'

t_ITERATOR = r'\.\[]'

def t_FUNCTION_NO_ARGS(t):
    r'(abs|ceil|floor|round|sqrt|length|min|max|todate|fromdate|tonumber|add|any|all|not)'
    return t

def t_FUNCTION_WITH_ARGS(t):
    r'(split|join|map)'
    return t

def t_IDENT(t):
    r'[a-zA-Z_]\w*'
    t.type = 'IDENT'
    if t.value == 'and':
        t.type = 'AND'
    elif t.value == 'or':
        t.type = 'OR'
    elif t.value == 'null':
        t.type = 'NULL'
        t.value = None
    elif t.value == 'true':
        t.type = 'TRUE'
        t.value = True
    elif t.value == 'false':
        t.type = 'FALSE'
        t.value = False
    return t

def t_INT(t):
    r'\d+'
    t.value = int(t.value)
    return t

def t_FLOAT(t):
    r'\d+\.\d*'
    t.value = float(t.value)
    return t

def t_STRING(t):
    r'"(\\.|[^"])*"'
    t.value = t.value[1:-1]
    return t

t_ignore = ' \r\n\t\f'

def t_error(t):
    raise SyntaxError(f"Illegal character '{t.value[0]}' at position {t.lexpos}")


lexer = lex.lex(reflags=re.UNICODE | re.DOTALL)
