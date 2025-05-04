import pytest

from quex_backend.interpreter import jq_eval, parser


def perform_jq_filter_test(jq, input_data, expected_output):
    """
    Test JQ filter operations.

    Args:
        jq: JQ filter to apply
        input_data: input data
        expected_output: expected output
    """
    ast = parser.parse(jq)
    print(ast)
    result = jq_eval(input_data, ast)
    assert result == expected_output, f"Failed test case:\nJq filter: {jq}\nInput: {input_data}\nExpected: {expected_output}\nGot: {result}"


# test_cases = [
#     (".", "Hello, world!", "Hello, world!"),
#     (".", 0.12345678901234567890123456789, 0.12345678901234567890123456789),
#     (".foo", {"foo": 42, "bar": "less interesting data"}, 42),
#     (".foo", {"notfoo": True, "alsonotfoo": False}, None),
#     (".[\"foo\"]", {"foo": 42}, 42),
#     (".Foo", {"Foo": 42}, 42),
#     (".Foo", {"foo": 42}, None),
#     (".[\"1\"]", {"1": 42}, 42),
#     (".\"1\"", {"1": 42}, 42),
#     (".[0]", [{"name": "JSON", "good": True}, {"name": "XML", "good": False}], {"name": "JSON", "good": True}),
#     (".[2]", [{"name": "JSON", "good": True}, {"name": "XML", "good": False}], None),
#     (".[-2]", [1, 2, 3], 2),
#     (".[2:4]", ["a", "b", "c", "d", "e"], ["c", "d"]),
#     (".[2:4]", "abcdefghi", "cd"),
#     (".[:3]", ["a", "b", "c", "d", "e"], ["a", "b", "c"]),
#     (".[-2:]", ["a", "b", "c", "d", "e"], ["d", "e"]),
#     ("(. + 2) * 5", 1, 15),
#     (".a + 1", {"a": 7}, 8),
#     (".a + .b", {"a": [1, 2], "b": [3, 4]}, [1, 2, 3, 4]),
#     (".a + null", {"a": 1}, 1),
#     (".a + 1", {}, 1),
#     ("4 - .a", {"a": 3}, 1),
#     ("10 / . * 3", 5, 6),
#     ("map(abs)", [-10, -1.1, -1e-1], [10, 1.1, 1e-1]),
#     ("map(.+1)", [1, 2, 3], [2, 3, 4]),
#     ("floor", 3.14159, 3),
#     ("sqrt", 9, 3),
#     ("split(\", \")", "a, b,c,d, e, ", ["a", "b,c,d", "e", ""]),
#     ("join(\", \")", ["a", "b,c,d", "e"], "a, b,c,d, e"),
#     ("join(\" \")", ["a", 1, 2.3, True, None, False], "a 1 2.3 true  false"),
#     ("tonumber", "1", 1),
#     ("tonumber", 1, 1),
#     (". + .", "a", "aa")
# ]

test_cases = [
    (".", "Hello, world!", "Hello, world!"),
    (".", 0.12345678901234567890123456789, 0.12345678901234567890123456789),
    (". < 0.12345678901234567890123456788", 0.12345678901234567890123456789, False),
    (".a < 2", {"a": 3}, False),
    (".foo", {"foo": 42, "bar": "less interesting data"}, 42),
    (".foo", {"notfoo": True, "alsonotfoo": False}, None),
    (".[\"foo\"]", {"foo": 42}, 42),
    (".[0]", [{"name": "JSON", "good": True}, {"name": "XML", "good": False}], {"name": "JSON", "good": True}),
    (".[2]", [{"name": "JSON", "good": True}, {"name": "XML", "good": False}], None),
    (".[-2]", [1, 2, 3], 2),
    (".[2:4]", ["a", "b", "c", "d", "e"], ["c", "d"]),
    (".[2:4]", "abcdefghi", "cd"),
    (".[:3]", ["a", "b", "c", "d", "e"], ["a", "b", "c"]),
    (".[-2:]", ["a", "b", "c", "d", "e"], ["d", "e"]),
    (".[]", [], None),
    ("(. + 2) * 5", 1, 15),
    ("[.user, .projects[]]", {"user": "stedolan", "projects": ["jq", "wikiflow"]}, ["stedolan", "jq", "wikiflow"]),
    ("[ .[] | . * 2]", [1, 2, 3], [2, 4, 6]),
    ("{(.user): .titles}", {"user": "stedolan", "titles": ["JQ Primer", "More JQ"]},
     {"stedolan": ["JQ Primer", "More JQ"]}),
    (".a + 1", {"a": 7}, 8),
    (".a + .b", {"a": [1, 2], "b": [3, 4]}, [1, 2, 3, 4]),
    (".a + null", {"a": 1}, 1),
    (".a + 1", {}, 1),
    ("4 - .a", {"a": 3}, 1),
    ("10 / . * 3", 5, 6),
    ("map(abs)", [-10, -1.1, -1e-1], [10, 1.1, 1e-1]),
    ("map(has(\"foo\"))", [{"foo": 42}, {}], [True, False]),
    ("map(has(2))", [[0, 1], ["a", "b", "c"]], [False, True]),
    ("map(in([0,1]))", [2, 0], [False, True]),
    ("map(.+1)", [1, 2, 3], [2, 3, 4]),
    ("map(., .)", [1, 2], [1, 1, 2, 2]),
    ("map(select(. >= 2))", [1, 5, 3, 0, 7], [5, 3, 7]),
    (".[] | select(.id == \"second\")", [{"id": "first", "val": 1}, {"id": "second", "val": 2}],
     {"id": "second", "val": 2}),
    ("add", ["a", "b", "c"], "abc"),
    ("add", [1, 2, 3], 6),
    ("add", [], None),
    ("any", [True, False], True),
    ("any", [False, False], False),
    ("any", [], False),
    ("all", [True, False], False),
    ("all", [True, True], True),
    ("all", [], True),
    ("floor", 3.14159, 3),
    ("sqrt", 9, 3),
    ("min", [5, 4, 2, 7], 2),
    ("[.[]|startswith(\"foo\")]", ["fo", "foo", "barfoo", "foobar", "barfoob"], [False, True, False, True, False]),
    ("[.[]|endswith(\"foo\")]", ["foobar", "barfoo"], [False, True]),
    ("split(\", \")", "a, b,c,d, e, ", ["a", "b,c,d", "e", ""]),
    ("join(\", \")", ["a", "b,c,d", "e"], "a, b,c,d, e"),
    ("join(\" \")", ["a", 1, 2.3, True, None, False], "a 1 2.3 true  false"),
    ("\"The input was \(.), which is one less than \(.+1)\"", 42, "The input was 42, which is one less than 43"),
    ("[.[]|tostring]", [1, "foo", ["foo"]], ["1", "foo", "[\"foo\"]"]),
    ("@base64", "This is a message", "VGhpcyBpcyBhIG1lc3NhZ2U="),
    ("@base64d", "VGhpcyBpcyBhIG1lc3NhZ2U=", "This is a message"),
    ("fromdate", "2015-03-05T23:51:47Z", 1425599507),
    ("todate", 1425599507, "2015-03-05T23:51:47Z"),
    (". == false", None, False),
    (". == {\"b\": {\"d\": (4 + 1e-20), \"c\": 3}, \"a\":1}", {"a": 1, "b": {"c": 3, "d": 4}}, True),
    (". < 5", 2, True),
    ("42 and \"a string\"", None, True),
    ("[true, false | not]", None, [False, True]),
    ("empty // 42", None, 42),
    (".foo // 42", {"foo": 19}, 19),
    (".foo // 42", {}, 42),
    ("(false, null, 1) // 42", None, 1),
    ("split(\", *\"; null)", "ab,cd, ef", ["ab", "cd", "ef"]),
    ("isempty(empty)", None, True),
    ("isempty(.[])", [], True),
    ("isempty(.[])", [1, 2, 3], False),
    ("tonumber", "1", 1),
    ("tonumber", 1, 1),
    (". + .", "a", "aa")
]


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
]


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
    )
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
        ".[] | . * 2", [1,2,3], [2,4,6],
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
        ".[] | . > 2", [1,2,3,4], [False,False,True,True],
        id="pipe with comparison"
    ),
    pytest.param(
        ".a | . + 1 | . * 2", {"a": 5}, 12,
        id="multiple pipes"
    ),
    pytest.param(
        ".[] | . | length", ["abc", "defgh"], [3,5],
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
