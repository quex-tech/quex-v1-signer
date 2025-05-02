import ply.lex as lex
import re

tokens = [
        'STRING', 
        'IDENT',
        'INT',
        'FLOAT',
        'FUNCTION_NO_ARGS',
        'FUNCTION_WITH_ARGS',
        'COMPARISON_OPERATOR',
        'VALUE'
        ]

literals = "+-*/%()[]().,|:"

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

def t_FUNCTION_NO_ARGS(t):
    r'(abs|ceil|floor|round|sqrt|length|min|max|todate|fromdate|tonumber|add|any|all)'
    return t

def t_FUNCTION_WITH_ARGS(t):
    r'(split|join)'
    return t

def t_COMPARISON_OPERATOR(t):
    r'(==|!=|>=|<=|>|<)'
    return t

def t_VALUE(t):
    r'(true|false|null)'
    return t

t_ignore = ' \r\n\t\f'

def t_error(t):
    print(f"Illegal character: {t.value[0]}")
    t.lexer.skip(1)

lexer = lex.lex(reflags=re.UNICODE | re.DOTALL)
