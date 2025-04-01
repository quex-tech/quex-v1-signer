import ply.lex as lex
import re

tokens = [
        'STRING', 
        'IDENT',
        'INT',
        'FLOAT'
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

t_ignore = ' \r\n\t\f'

def t_error(t):
    print(f"Illegal character: {t.value[0]}")
    t.lexer.skip(1)

lexer = lex.lex(reflags=re.UNICODE | re.DOTALL)
