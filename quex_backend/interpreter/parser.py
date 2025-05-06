from .tree import Node
from .lexer import tokens, literals
import ply.yacc as yacc

precedence = (
    ('right', '|'),
    ('left', ','),
    ('right', 'ALT'),
    ('left', 'OR'),
    ('left', 'AND'),
    ('nonassoc', 'NEQ', 'EQ', 'LT', 'LE', 'GT', 'GE'),
    ('left', '+', '-'),
    ('left', '*', '/', '%'),
    ('right', 'UMINUS'),
    ('left', '.'),
)

def p_exp(p):
    '''
    exp : atomic
        | object
        | '(' exp ')'
        | iterator
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
        | TRUE
        | FALSE
        | NULL
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
    '''
    if p[1] == '.':
        p[0] = Node('.', [])
    else:
        p[0] = p[1]

def p_iterator(p):
    '''
    iterator : object '[' ']'
    '''
    p[0] = Node('func_with_one_arg', ['iterator', p[1]])

def p_unary_exp(p):
    '''
    unary_exp : '-' exp %prec UMINUS
    '''
    p[0] = Node('func_with_one_arg', ['neg', p[2]])

def p_binary_exp(p):
    '''
    binary_exp : exp '+' exp
        | exp '-' exp
        | exp '*' exp
        | exp '/' exp
        | exp '%' exp
        | exp EQ exp
        | exp NEQ exp
        | exp LT exp
        | exp LE exp
        | exp GT exp
        | exp GE exp
        | exp AND exp
        | exp OR exp
        | exp ALT exp
        | exp '|' exp
    '''
    if p[2] == '|':
        p[0] = Node("pipe", [p[1], p[3]])
    else:
        p[0] = Node("binop", [p[2], p[1], p[3]])

def p_select(p):
    '''
    select : '.' IDENT
           | '.' STRING
           | object '.' IDENT
           | object '.' STRING
           | object '[' exp ']'
           | object '.' '[' exp ']'
    '''
    if len(p) == 3:
        p[0] = Node('select', [Node('.', []), Node('ident', [p[2]])])
    elif len(p) == 4:
        p[0] = Node('select', [p[1], Node('ident', [p[3]])])
    elif len(p) == 5:
        p[0] = Node('select', [p[1], p[3]])
    else:
        p[0] = Node('select', [p[1], p[4]])

def p_slice(p):
    '''
    slice : object '[' exp ':' exp ']'
        | object '[' ':' exp ']'
        | object '[' exp ':' ']'
    '''
    if len(p) == 6:
        if p[3] == ':': # [:b]
            p[0] = Node('slice', [p[1], Node('atomic', [None]), p[4]])
        else: # [a:]
            p[0] = Node('slice', [p[1], p[3], Node('atomic', [None])])
    else: # [a:b]
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
        p[0] = Node('array', [])
    elif len(p) == 2:
        p[0] = Node('array', [p[1]])
    else:
        p[0] = Node('array', [p[1]] + p[3].children)


def p_function_call(p):
    '''
    function_call : FUNCTION_NO_ARGS 
        | FUNCTION_WITH_ARGS '(' exp ')'
    '''
    if len(p) == 2:
        p[0] = Node('func_no_args', [p[1]])
    else:
        p[0] = Node('func_with_one_arg', [p[1], p[3]])


def p_error(p):
    raise ValueError(f"Syntax error: {p}")

parser = yacc.yacc()
