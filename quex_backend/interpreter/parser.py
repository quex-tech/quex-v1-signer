from .tree import Node
from .lexer import tokens, literals
import ply.yacc as yacc

precedence = (
    ('left', '|'),
    ('left', '+', '-'),
    ('left', '*', '/', '%'),
    ('left', '.'),
)

def p_exp(p):
    '''
    exp : atomic
        | object
        | '(' exp ')'
    '''
    if len(p) == 2:
        p[0] = p[1]
    else:
        p[0] = p[2]

def p_atomic(p):
    '''
    atomic : STRING 
        | INT
        | FLOAT
    '''
    p[0] = Node('atomic', [p[1]])

def p_object(p):
    '''
    object : select
        | slice
        | '.'
        | array_construction
        | function_call
        | binary_exp
        | unary_exp
        | pipe
        | root_select
        | comparison
        | value
    '''
    if p[1] == '.':
        p[0] = Node('.', [])
    else:
        p[0] = p[1]

def p_binary_exp(p):
    '''
    binary_exp : exp '+' exp
        | exp '-' exp
        | exp '*' exp
        | exp '/' exp
        | exp '%' exp
    '''
    p[0] = Node(p[2], [p[1],p[3]])

def p_select(p):
    '''
    select : object '.' IDENT
           | object '[' STRING ']'
           | object '[' exp ']'
    '''
    if len(p) == 4:
        p[0] = Node('select', [p[1], Node('ident', [p[3]])])
    elif type(p[3]) == str:
        p[0] = Node('select', [p[1], Node('ident', [p[3]])])
    else:
        p[0] = Node('select', [p[1], p[3]])

def p_root_select(p):
    '''
    root_select  : '.' IDENT
    '''
    p[0] = Node('select', [Node('.', []), Node('ident', [p[2]])])

def p_unary_exp(p):
    '''
    unary_exp : '-' exp
    '''
    p[0] = Node('neg', [p[2]])


def p_slice(p):
    '''
    slice : object '[' exp ':' exp ']'
        | object '[' ':' exp ']'
        | object '[' exp ':' ']'
    '''
    if len(p) == 6:
        if p[3] == ':':
            p[0] = Node('slice', [p[1], Node('atomic', [0]), p[4]])
        else:
            p[0] = Node('slice', [p[1], p[3]])
    else:
        p[0] = Node('slice', [p[1], p[3], p[5]])

def p_array_construction(p):
    '''
    array_construction : '[' array_entries ']'
    '''
    p[0] = p[2]

def p_array_entries(p):
    '''
    array_entries : 
        | exp 
        | exp ',' array_entries
    '''
    if len(p) == 1:
        p[0] = Node('array', [[]])
    elif len(p) == 2:
        p[0] = Node('array', [p[1]])
    else:
        p[0] = Node('array', [p[1]] + p[3].children)


def p_function_call(p):
    '''
    function_call : FUNCTION_NO_ARGS 
        | FUNCTION_WITH_ARGS '(' exp ')'
    '''
    p[0] = Node(p[1], [])
    if len(p) > 2:
        p[0].children += [p[3]]

def p_pipe(p):
    '''
    pipe : exp '|' exp
    '''
    p[0] = Node('pipe', [p[1], p[3]])

def p_comparison(p):
    '''
    comparison : exp COMPARISON_OPERATOR exp
    '''
    p[0] = Node(p[2], [p[1], p[3]])

def p_value(p):
    '''
    value : VALUE
    '''
    p[0] = Node(p[1], [])

parser = yacc.yacc()
