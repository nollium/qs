import re
from urllib.parse import unquote, quote_plus
from typing import Mapping, Any, cast
import unittest


def merge(source: Any, destination: Any):
    """
    taken from: http://stackoverflow.com/a/20666342

    """
    for key, value in source.items():
        if isinstance(value, dict):
            # get node or create one
            node = destination.setdefault(key, {})
            merge(value, node)
        else:
            if (
                isinstance(value, list) or isinstance(value, tuple)
            ) and key in destination:
                value = destination[key] + value
            destination[key] = value

    return destination


def qs_parse(qs: str, keep_blank_values: bool = False, strict_parsing: bool = False):
    tokens = {}
    pairs = [s2 for s1 in qs.split("&") for s2 in s1.split(";")]

    def get_name_value(name: str, value: str):
        name = unquote(name.replace("+", " "))
        value = unquote(value.replace("+", " "))
        matches = re.findall(r"([\s\w]+|\[\]|\[\w+\])", name)

        new_value: str | list | dict = value
        for i, match in enumerate(matches[::-1]):
            if match == "[]":
                if i == 0:
                    new_value = [new_value]
                else:
                    new_value += new_value
            elif re.match(r"\[\w+\]", match):
                name = re.sub(r"[\[\]]", "", match)
                new_value = {name: new_value}
            else:
                is_list = isinstance(new_value, list) or isinstance(new_value, tuple)
                is_dict = isinstance(new_value, dict)

                if is_list:
                    match = match + "[]"

                if match not in tokens:
                    tokens[match] = [] if not is_dict else {}

                if i == 0:
                    tokens[match] = [new_value]
                elif is_dict:
                    tokens[match] = merge(new_value, tokens[match])
                elif is_list:
                    tokens[match] = tokens[match] + list(new_value)
                else:
                    tokens[match].append(new_value)

    for name_val in pairs:
        if not name_val and not strict_parsing:
            continue
        nv = name_val.split("=")

        if len(nv) != 2:
            if strict_parsing:
                raise ValueError(f"Bad query field: {name_val}")
            # Handle case of a control-name with no equal sign
            if keep_blank_values:
                nv.append("")
            else:
                continue

        if len(nv[1]) or keep_blank_values:
            get_name_value(nv[0], nv[1])

    return tokens


def build_qs(query: Mapping) -> str:
    def dict_generator(indict, pre=None):
        pre = pre[:] if pre else []
        if isinstance(indict, dict):
            for key, value in indict.items():
                if isinstance(value, dict):
                    for d in dict_generator(value, pre + [key]):
                        yield d
                else:
                    yield pre + [key, value]
        else:
            yield indict

    paths = [i for i in dict_generator(query)]
    qs = []

    for path in paths:
        names = path[:-1]
        value = path[-1]
        s: list[str] = []
        for i, n in enumerate(names):
            n = f"[{n}]" if i > 0 else str(n)
            s.append(n)

        match value:
            case list() | tuple():
                for v in value:
                    multi = s[:]
                    if not s[-1].endswith("[]"):
                        multi.append("[]")
                    multi.append("=")
                    multi.append(str(v))
                    qs.append("".join(multi))
            case _:
                s.append("=")
                s.append(str(value))
                qs.append("".join(s))

    return "&".join(qs)


class TestURLParsing(unittest.TestCase):
    def test_merge(self):
        source = {"a": 1, "b": {"c": 2}}
        destination = {"a": 3, "b": {"d": 4}}
        expected = {"a": 1, "b": {"c": 2, "d": 4}}
        self.assertEqual(merge(source, destination), expected)

    def test_qs_parse_no_strict_no_blanks(self):
        qs = "a=1&b=2&c=3"
        expected = {"a": ["1"], "b": ["2"], "c": ["3"]}
        self.assertEqual(qs_parse(qs), expected)

    def test_qs_parse_with_strict(self):
        qs = "a=1&b=2&c"
        with self.assertRaises(ValueError):
            qs_parse(qs, strict_parsing=True)

    def test_qs_parse_keep_blanks(self):
        qs = "a=1&b=2&c"
        expected = {"a": ["1"], "b": ["2"], "c": [""]}
        self.assertEqual(qs_parse(qs, keep_blank_values=True), expected)

    def test_build_qs(self):
        query = {"a": 1, "b": 2, "c": 3}
        expected = "a=1&b=2&c=3"
        self.assertEqual(build_qs(query), expected)

    def test_build_qs_nested_dict(self):
        query = {"a": 1, "b": {"c": 2, "d": 3}}
        expected = "a=1&b[c]=2&b[d]=3"
        self.assertEqual(build_qs(query), expected)

    def test_build_qs_with_list(self):
        query = {"a": 1, "b": [2, 3]}
        expected = "a=1&b[]=2&b[]=3"
        self.assertEqual(build_qs(query), expected)


if __name__ == "__main__":
    unittest.main()
