import pytest

from quex_backend.interpreter import jq_eval, parser
from quex_backend.interpreter.iterator import JqIterator


def perform_jq_filter_test(jq, input_data, expected_output):
    """
    Test JQ filter operations.

    Args:
        jq: JQ filter to apply
        input_data: input data
        expected_output: expected output
    """
    ast = parser.parse(jq)
    result = jq_eval(input_data, ast)
    assert result == expected_output, f"Failed test case:\nJq filter: {jq}\nInput: {input_data}\nExpected: {expected_output}\nGot: {result}"

jq_primitive_test_cases = [
    pytest.param(
        "42", None, 42,
        id="Integer literal"
    ),
    pytest.param(
        "3.14", None, 3.14,
        id="Float literal"
    ),
    pytest.param(
        "\"hello\"", None, "hello", 
        id="String literal"
    ),
    pytest.param(
        "true", None, True,
        id="Boolean true literal"
    ),
    pytest.param(
        "false", None, False,
        id="Boolean false literal"
    ),
    pytest.param(
        "null", None, None,
        id="Null literal"
    ),
    pytest.param(
        "(42)", None, 42,
        id="Parenthesized integer"
    ),
    pytest.param(
        "(\"hello\")", None, "hello",
        id="Parenthesized string"
    ),
    pytest.param(
        "(true)", None, True,
        id="Parenthesized boolean"
    ),
    pytest.param(
        "(null)", None, None,
        id="Parenthesized null"
    )
]

@pytest.mark.parametrize("jq,input_data,expected_output", jq_primitive_test_cases)
def test_jq_primitives(jq, input_data, expected_output):
    perform_jq_filter_test(jq, input_data, expected_output)


jq_index_identifier_test_cases = [
    pytest.param(
        ".", "Hello, world!", "Hello, world!",
        id="Root identifier"
    ),
    pytest.param(
        ".foo", {"foo": 42, "bar": "less interesting data"}, 42,
        id="Object Identifier-Index, depth 1"
    ),
    pytest.param(
        ".foo.bar", {"foo": {"bar": 42}, "bar": "less interesting data"}, 42,
        id="Object Identifier-Index, depth 2"
    ),
    pytest.param(
        ".foo", {"notfoo": True, "alsonotfoo": False}, None,
        id="Object Identifier-Index, non-existing field"
    ),
    pytest.param(
        ".\"foo\"", {"foo": 42}, 42,
        id="Object index with string literal"
    ),
    pytest.param(
        ".[\"foo\"]", {"foo": 42}, 42,
        id="Object index with bracket notation"
    ),
    pytest.param(
        ".[0]", [{"name": "JSON", "good": True}, {"name": "XML", "good": False}], {"name": "JSON", "good": True},
        id="Array index"
    ),
    pytest.param(
        ".[-2]", [{"name": "JSON", "good": True}, {"name": "XML", "good": False}], {"name": "JSON", "good": True},
        id="Array index, negative index"
    ),
    pytest.param(
        ".[2]", [{"name": "JSON", "good": True}, {"name": "XML", "good": False}], None,
        id="Array index, out of range"),
    pytest.param(
        ".[-3]", [{"name": "JSON", "good": True}, {"name": "XML", "good": False}], None,
        id="Array index, negative index, out of range"),
    pytest.param(
        ".foo.bar.baz", {"foo": {"bar": {"baz": 42}}}, 42,
        id="Object index chain with dot notation"
    ),
    pytest.param(
        ".[\"foo\"][\"bar\"][\"baz\"]", {"foo": {"bar": {"baz": 42}}}, 42,
        id="Object index chain with bracket notation"
    ),
    pytest.param(
        ".[\"foo\"].[\"bar\"].[\"baz\"]", {"foo": {"bar": {"baz": 42}}}, 42,
        id="Object index chain with bracket notation with dot notation"
    ),
    pytest.param(
        ".foo.\"bar\".[\"baz\"][\"qux\"]", {"foo": {"bar": {"baz": {"qux": 42}}}}, 42,
        id="Object index chain with mixed notation"
    ),
]


@pytest.mark.parametrize("jq,input_data,expected_output", jq_index_identifier_test_cases)
def test_jq_index_identifier(jq, input_data, expected_output):
    perform_jq_filter_test(jq, input_data, expected_output)


jq_slice_test_cases = [
    pytest.param(
        ".[2:4]", ["a", "b", "c", "d", "e"], ["c", "d"],
        id="Array slice with positive indices"
    ),
    pytest.param(
        ".[2:4]", "abcdefghi", "cd",
        id="String slice with positive indices"
    ),
    pytest.param(
        ".[:3]", ["a", "b", "c", "d", "e"], ["a", "b", "c"],
        id="Array slice with omitted start"
    ),
    pytest.param(
        ".[-2:]", ["a", "b", "c", "d", "e"], ["d", "e"],
        id="Array slice with negative start"
    ),
    pytest.param(
        ".[-3:-1]", ["a", "b", "c", "d", "e"], ["c", "d"],
        id="Array slice with negative indices"
    ),
    pytest.param(
        ".[1:]", ["a", "b", "c", "d", "e"], ["b", "c", "d", "e"],
        id="Array slice with omitted end"
    ),
    pytest.param(
        ".[5:7]", ["a", "b", "c", "d", "e"], [],
        id="Array slice with out of range indices"
    ),
    pytest.param(
        ".[-7:-5]", ["a", "b", "c", "d", "e"], [],
        id="Array slice with out of range negative indices"
    ),
]


@pytest.mark.parametrize("jq,input_data,expected_output", jq_slice_test_cases)
def test_jq_slice(jq, input_data, expected_output):
    perform_jq_filter_test(jq, input_data, expected_output)


jq_arithmetic_test_cases = [
    pytest.param(
        ". + 2", 3, 5,
        id="Simple addition"
    ),
    pytest.param(
        ". - 2", 5, 3,
        id="Simple subtraction"
    ),
    pytest.param(
        ". * 2", 3, 6,
        id="Simple multiplication"
    ),
    pytest.param(
        ". / 2", 6, 3,
        id="Simple division"
    ),
    pytest.param(
        "(. + 2) * 5", 1, 15,
        id="Combined addition and multiplication"
    ),
    pytest.param(
        ".a + 1", {"a": 7}, 8,
        id="Addition with object field"
    ),
    pytest.param(
        "4 - .a", {"a": 3}, 1,
        id="Subtraction with object field"
    ),
    pytest.param(
        "10 / . * 3", 5, 6,
        id="Combined division and multiplication"
    ),
    pytest.param(
        ".a + .b", {"a": 5, "b": 3}, 8,
        id="Addition of two object fields"
    ),
    pytest.param(
        ".a * .b", {"a": 4, "b": 3}, 12,
        id="Multiplication of two object fields"
    ),
    pytest.param(
        "(.a + .b) * .c", {"a": 2, "b": 3, "c": 4}, 20,
        id="Complex arithmetic with multiple fields"
    ),
    pytest.param(
        ".a / .b", {"a": 10, "b": 2}, 5,
        id="Division of two object fields"
    ),
    pytest.param(
        ".a - .b", {"a": 10, "b": 3}, 7,
        id="Subtraction of two object fields"
    ),
    pytest.param(
        "(.a + .b) / .c", {"a": 10, "b": 20, "c": 5}, 6,
        id="Combined addition and division"
    ),
    pytest.param(
        ".a + null", {"a": 1}, 1,
        id="Addition with null"
    ),
    pytest.param(
        ".a + 1", {}, 1,
        id="Addition with missing field"
    ),
]


@pytest.mark.parametrize("jq,input_data,expected_output", jq_arithmetic_test_cases)
def test_jq_arithmetic(jq, input_data, expected_output):
    perform_jq_filter_test(jq, input_data, expected_output)


jq_comparison_test_cases = [
    pytest.param(
        ". == 5", 5, True,
        id="Equality comparison with number"
    ),
    pytest.param(
        ". == 5", 6, False,
        id="Equality comparison with different number"
    ),
    pytest.param(
        ". == \"hello\"", "hello", True,
        id="Equality comparison with string"
    ),
    pytest.param(
        ". == true", True, True,
        id="Equality comparison with boolean"
    ),
    pytest.param(
        ". == null", None, True,
        id="Equality comparison with null"
    ),
    pytest.param(
        ". != 5", 6, True,
        id="Inequality comparison"
    ),
    pytest.param(
        ". < 5", 3, True,
        id="Less than comparison"
    ),
    pytest.param(
        ". <= 5", 5, True,
        id="Less than or equal comparison"
    ),
    pytest.param(
        ". > 5", 7, True,
        id="Greater than comparison"
    ),
    pytest.param(
        ". >= 5", 5, True,
        id="Greater than or equal comparison"
    ),
    pytest.param(
        ".a == .b", {"a": 5, "b": 5}, True,
        id="Equality comparison of object fields"
    ),
    pytest.param(
        ".a < .b", {"a": 3, "b": 5}, True,
        id="Less than comparison of object fields"
    ),
    pytest.param(
        ".a > .b", {"a": 7, "b": 5}, True,
        id="Greater than comparison of object fields"
    ),
    pytest.param(
        ".a <= .b", {"a": 5, "b": 5}, True,
        id="Less than or equal comparison of object fields"
    ),
    pytest.param(
        ".a >= .b", {"a": 5, "b": 5}, True,
        id="Greater than or equal comparison of object fields"
    ),
    pytest.param(
        ".a != .b", {"a": 5, "b": 6}, True,
        id="Inequality comparison of object fields"
    ),
    pytest.param(
        ".a // 42", {"a": 19}, 19,
        id="Alternative operator with existing field"
    ),
    pytest.param(
        ".a // 42", {}, 42,
        id="Alternative operator with missing field"
    ),
    pytest.param(
        ".a // .b // 42", {"b": 19}, 19,
        id="Chained alternative operator"
    ),
    pytest.param(
        ".a // .b // 42", {}, 42,
        id="Chained alternative operator with all missing"
    ),
    pytest.param(
        ".a == .b and .c == .d", {"a": 5, "b": 5, "c": 3, "d": 3}, True,
        id="Combined equality comparisons with and"
    ),
    pytest.param(
        ".a == .b or .c == .d", {"a": 5, "b": 6, "c": 3, "d": 3}, True,
        id="Combined equality comparisons with or"
    ),
    pytest.param(
        ".a == .b and .c == .d", {"a": 5, "b": 6, "c": 3, "d": 4}, False,
        id="Combined equality comparisons with and (false case)"
    ),
    pytest.param(
        ".a == .b or .c == .d", {"a": 5, "b": 6, "c": 3, "d": 4}, False,
        id="Combined equality comparisons with or (false case)"
    ),
    pytest.param(
        "not", True, False,
        id="not operator with true value"
    ),
    pytest.param(
        "not", False, True,
        id="not operator with false value"
    ),
    pytest.param(
        "not", None, True,
        id="not operator with null value"
    ),
    pytest.param(
        "not", 0, True,
        id="not operator with zero"
    ),
    pytest.param(
        "not", 1, False,
        id="not operator with non-zero number"
    ),
    pytest.param(
        "not", "", True,
        id="not operator with empty string"
    ),
    pytest.param(
        "not", "hello", False,
        id="not operator with non-empty string"
    ),
    pytest.param(
        "not", [], True,
        id="not operator with empty array"
    ),
    pytest.param(
        "not", [1,2,3], False,
        id="not operator with non-empty array"
    ),
    pytest.param(
        "not", {}, True,
        id="not operator with empty object"
    ),
    pytest.param(
        "not", {"a": 1}, False,
        id="not operator with non-empty object"
    ),
    pytest.param(
        "not | not", True, True,
        id="not operator with pipe"
    )
]

jq_boolean_test_cases = [
    pytest.param(
        "true and true", None, True,
        id="and with two true values"
    ),
    pytest.param(
        "true and false", None, False,
        id="and with true and false"
    ),
    pytest.param(
        "false and true", None, False,
        id="and with false and true"
    ),
    pytest.param(
        "false and false", None, False,
        id="and with two false values"
    ),
    pytest.param(
        "true or true", None, True,
        id="or with two true values"
    ),
    pytest.param(
        "true or false", None, True,
        id="or with true and false"
    ),
    pytest.param(
        "false or true", None, True,
        id="or with false and true"
    ),
    pytest.param(
        "false or false", None, False,
        id="or with two false values"
    ),
    pytest.param(
        "true and (false or true)", None, True,
        id="complex boolean expression 1"
    ),
    pytest.param(
        "(true and false) or true", None, True,
        id="complex boolean expression 2"
    ),
    pytest.param(
        "true and false | not", None, True,
        id="not with and expression"
    ),
    pytest.param(
        "false or false | not", None, True,
        id="not with or expression"
    ),
    pytest.param(
        "42 and \"a string\"", None, True,
        id="and with number and string"
    ),
    pytest.param(
        "42 or \"a string\"", None, True,
        id="or with number and string"
    )
]

@pytest.mark.parametrize("jq,input_data,expected_output", jq_boolean_test_cases)
def test_jq_boolean(jq, input_data, expected_output):
    perform_jq_filter_test(jq, input_data, expected_output)


@pytest.mark.parametrize("jq,input_data,expected_output", jq_comparison_test_cases)
def test_jq_comparison(jq, input_data, expected_output):
    perform_jq_filter_test(jq, input_data, expected_output)

jq_function_test_cases = [
    pytest.param(
        "abs", -42, 42,
        id="abs function with negative number"
    ),
    pytest.param(
        "abs", 42, 42,
        id="abs function with positive number"
    ),
    pytest.param(
        "ceil", 3.14, 4,
        id="ceil function"
    ),
    pytest.param(
        "floor", 3.75, 3,
        id="floor function"
    ),
    pytest.param(
        "round", 3.14, 3,
        id="round function with rounding down"
    ),
    pytest.param(
        "round", 3.75, 4,
        id="round function with rounding up"
    ),
    pytest.param(
        "sqrt", 16, 4,
        id="sqrt function"
    ),
    pytest.param(
        "length", [1,2,3], 3,
        id="length function with array"
    ),
    pytest.param(
        "length", "hello", 5,
        id="length function with string"
    ),
    pytest.param(
        "min", [5,2,8,1], 1,
        id="min function"
    ),
    pytest.param(
        "max", [5,2,8,1], 8,
        id="max function"
    ),
    pytest.param(
        "split(\",\")", "a,b,c", ["a","b","c"],
        id="split function"
    ),
    pytest.param(
        "join(\",\")", ["a","b","c"], "a,b,c",
        id="join function"
    ),
    pytest.param(
        "todate", 1672531200, "2023-01-01T00:00:00Z",
        id="todate function"
    ),
    pytest.param(
        "fromdate", "2023-01-01T00:00:00Z", 1672531200,
        id="fromdate function"
    ),
    pytest.param(
        "tonumber", "42", 42,
        id="tonumber function"
    ),
    pytest.param(
        "add", [1,2,3,4], 10,
        id="add function"
    ),
    pytest.param(
        "add", [], None,
        id="add function with empty array"
    ),
    pytest.param(
        "add", ["a", "b", "c"], "abc",
        id="add function with string array"
    ),
    pytest.param(
        "any", [True, False, True], True,
        id="any function with true result"
    ),
    pytest.param(
        "any", [False, False, False], False,
        id="any function with false result"
    ),
    pytest.param(
        "all", [True, True, True], True,
        id="all function with true result"
    ),
    pytest.param(
        "all", [True, False, True], False,
        id="all function with false result"
    ),
]

@pytest.mark.parametrize("jq,input_data,expected_output", jq_function_test_cases)
def test_jq_functions(jq, input_data, expected_output):
    perform_jq_filter_test(jq, input_data, expected_output)


jq_array_test_cases = [
    pytest.param(
        "[1,2,3]", None, [1,2,3],
        id="simple array construction"
    ),
    pytest.param(
        "[1, 2 + 3, 4 * 2]", None, [1,5,8],
        id="array with expressions"
    ),
    pytest.param(
        "[]", None, [],
        id="empty array"
    ),
    pytest.param(
        "[1, [2,3], 4]", None, [1,[2,3],4], 
        id="nested array"
    ),
    pytest.param(
        "[.a, .b, .c]", {"a": 1, "b": 2, "c": 3}, [1,2,3],
        id="array from object fields"
    ),
    pytest.param(
        "[.[0], .[2]]", [10,20,30,40], [10,30],
        id="array from array indices"
    ),
    pytest.param(
        "[.foo, 2, .bar]", {"foo": "a", "bar": "b"}, ["a",2,"b"],
        id="array mixing literals and selections"
    ),
    pytest.param(
        "[.[]|.*2]", [1,2,3], [2,4,6],
        id="array from iterator with transformation"
    )
]

@pytest.mark.parametrize("jq,input_data,expected_output", jq_array_test_cases)
def test_jq_array_construction(jq, input_data, expected_output):
    perform_jq_filter_test(jq, input_data, expected_output)

jq_pipe_test_cases = [
    pytest.param(
        ".[] | . * 2", [1,2,3], JqIterator([2,4,6]),
        id="pipe with iterator and multiplication"
    ),
    pytest.param(
        ".foo | length", {"foo": [1,2,3,4]}, 4,
        id="pipe with object access and length"
    ),
    pytest.param(
        ". | tonumber", "123", 123.0,
        id="pipe with identity and tonumber"
    ),
    pytest.param(
        ".[] | . > 2", [1,2,3,4], JqIterator([False,False,True,True]),
        id="pipe with comparison"
    ),
    pytest.param(
        ".a | . + 1 | . * 2", {"a": 5}, 12,
        id="multiple pipes"
    ),
    pytest.param(
        ".[] | . | length", ["abc", "defgh"], JqIterator([3,5]),
        id="pipe with iterator and nested operations"
    )
]

@pytest.mark.parametrize("jq,input_data,expected_output", jq_pipe_test_cases)
def test_jq_pipe(jq, input_data, expected_output):
    perform_jq_filter_test(jq, input_data, expected_output)

jq_precedence_test_cases = [
    pytest.param(
        "2 + 3 * 4", None, 14,
        id="multiplication before addition"
    ),
    pytest.param(
        "(2 + 3) * 4", None, 20, 
        id="parentheses override precedence"
    ),
    pytest.param(
        "1 + 2 + 3", None, 6,
        id="left associative addition"
    ),
    pytest.param(
        "8 - 4 - 2", None, 2,
        id="left associative subtraction"
    ),
    pytest.param(
        "2 * 3 + 4 * 5", None, 26,
        id="multiplication before addition, multiple terms"
    ),
    pytest.param(
        "1 + 2 == 3", None, True,
        id="arithmetic before comparison"
    ),
    pytest.param(
        "true and false or true", None, True,
        id="and before or"
    ),
    pytest.param(
        "false or true and true", None, True,
        id="and before or, different order"
    ),
    pytest.param(
        ".foo | . + 1 | . * 2", {"foo": 5}, 12,
        id="pipe chains left to right"
    ),
    pytest.param(
        "1 // 2 // 3", None, 1,
        id="alternative operator chains right to left"
    ),
    pytest.param(
        "null // null // 3", None, 3,
        id="alternative operator with nulls"
    )
]

@pytest.mark.parametrize("jq,input_data,expected_output", jq_precedence_test_cases)
def test_jq_precedence(jq, input_data, expected_output):
    perform_jq_filter_test(jq, input_data, expected_output)

jq_map_test_cases = [
    pytest.param(
        "map(.)", [1, 2, 3], [1, 2, 3],
        id="map identity"
    ),
    pytest.param(
        "map(.+1)", [1, 2, 3], [2, 3, 4],
        id="map with arithmetic"
    ),
    pytest.param(
        "map(.*2)", [1, 2, 3], [2, 4, 6], 
        id="map with multiplication"
    ),
    pytest.param(
        "map(.foo)", [{"foo": 1}, {"foo": 2}], [1, 2],
        id="map with object access"
    ),
    pytest.param(
        "map(.foo.bar)", [{"foo": {"bar": 1}}, {"foo": {"bar": 2}}], [1, 2],
        id="map with nested object access"
    ),
    pytest.param(
        "map(.[0])", [[1,2], [3,4]], [1, 3],
        id="map with array access"
    ),
    pytest.param(
        "map(. | . + 1)", [1, 2, 3], [2, 3, 4],
        id="map with pipe"
    ),
    pytest.param(
        "map(abs)", [-2, -1, 0, 1, 2], [2, 1, 0, 1, 2],
        id="map with function"
    ),
    pytest.param(
        "map(.)", {"a": 1, "b": 2}, [1,2],
        id="map on object returns object's values"
    ),
]

@pytest.mark.parametrize("jq,input_data,expected_output", jq_map_test_cases)
def test_jq_map(jq, input_data, expected_output):
    perform_jq_filter_test(jq, input_data, expected_output)

jq_iterator_test_cases = [
    pytest.param(
        ".[]", [1, 2, 3], JqIterator([1, 2, 3]),
        id="iterator on array"
    ),
    pytest.param(
        ".[]", {"a": 1, "b": 2}, JqIterator([1, 2]),
        id="iterator on object returns values"
    ),
    pytest.param(
        ".[]", [], JqIterator([]),
        id="iterator on empty array returns None"
    ),
    pytest.param(
        ".[] | . + 1", [1, 2, 3], JqIterator([2, 3, 4]),
        id="iterator with pipe"
    ),
    pytest.param(
        ".[] | . * 2", [1, 2, 3], JqIterator([2, 4, 6]),
        id="iterator with multiplication"
    ),
    pytest.param(
        ".[] | .foo", [{"foo": 1}, {"foo": 2}], JqIterator([1, 2]),
        id="iterator with object access"
    ),
    pytest.param(
        "[., . + 1, . + 2] | .[]", 1, JqIterator([1, 2, 3]),
        id="iterator with array construction"
    ),
    pytest.param(
        "[., . + 1, . + 2] | .[] + 1", 1, JqIterator([2, 3, 4]),
        id="iterator with array construction and addition"
    ),
    pytest.param(
        ".foo[]", {"foo": {"bar": 1}}, JqIterator([1]),
        id="iterator with object access and object"
    ),
    pytest.param(
        ".foo[]", {"foo":  [1,2,3]}, JqIterator([1,2,3]),
        id="iterator with object access and array"
    ),
]

@pytest.mark.parametrize("jq,input_data,expected_output", jq_iterator_test_cases)
def test_jq_iterator(jq, input_data, expected_output):
    perform_jq_filter_test(jq, input_data, expected_output)


jq_base64_test_cases = [
    pytest.param(
        "@base64", "Hello, World!", "SGVsbG8sIFdvcmxkIQ==",
        id="base64 encode simple string"
    ),
    pytest.param(
        "@base64", "Special chars: !@#$%^&*()", "U3BlY2lhbCBjaGFyczogIUAjJCVeJiooKQ==", 
        id="base64 encode with special characters"
    ),
    pytest.param(
        "@base64", "", "",
        id="base64 encode empty string"
    ),
    pytest.param(
        "@base64d", "SGVsbG8sIFdvcmxkIQ==", "Hello, World!",
        id="base64 decode simple string"
    ),
    pytest.param(
        "@base64d", "U3BlY2lhbCBjaGFyczogIUAjJCVeJiooKQ==", "Special chars: !@#$%^&*()",
        id="base64 decode with special characters"
    ),
    pytest.param(
        "@base64d", "", "",
        id="base64 decode empty string"
    ),
    pytest.param(
        "@base64d | @base64", "SGVsbG8sIFdvcmxkIQ==", "SGVsbG8sIFdvcmxkIQ==",
        id="base64 encode then decode"
    ),
    pytest.param(
        "@base64 | @base64d", "Hello, World!", "Hello, World!",
        id="base64 decode then encode"
    )
]

@pytest.mark.parametrize("jq,input_data,expected_output", jq_base64_test_cases)
def test_jq_base64(jq, input_data, expected_output):
    perform_jq_filter_test(jq, input_data, expected_output)


def test_lexer_unknown_token():
    with pytest.raises(SyntaxError) as exc_info:
        perform_jq_filter_test("$", [], [])
    assert "Illegal character '$' at position 0" in str(exc_info.value)

