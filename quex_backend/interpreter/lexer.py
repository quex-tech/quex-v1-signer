import ply.lex as lex
import re

tokens = [
    'STRING', 
    'IDENT',
    'INT',
    'FLOAT',
    'FUNCTION_NO_ARGS',
    'FUNCTION_WITH_ARGS',
    'VALUE',
    'OR',
    'AND',
    'NOT',
    'EQ',
    'NEQ',
    'LT',
    'LE',
    'GT',
    'GE',
    'ALT'
]

literals = "+-*/%()[]().,|:"

t_VALUE = r'(true|false|null)'
t_FUNCTION_NO_ARGS = r'(abs|ceil|floor|round|sqrt|length|min|max|todate|fromdate|tonumber|add|any|all)'
t_FUNCTION_WITH_ARGS = r'(split|join|map)'

t_OR = r'or'
t_AND = r'and'
t_NOT = r'not'

t_EQ = r'=='
t_NEQ = r'!='
t_LE = r'<='
t_GE = r'>='
t_LT = r'<'
t_GT = r'>'
t_ALT = r'//'

t_IDENT = r'[a-zA-Z_]\w*'

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
    print(f"Illegal character: {t.value[0]}")
    t.lexer.skip(1)

lexer = lex.lex(reflags=re.UNICODE | re.DOTALL)
