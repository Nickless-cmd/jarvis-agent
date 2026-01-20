from jarvis.triage.pytest_triage import parse_pytest_output, triage_pytest_output


def test_triage_assertion_error():
    output = (
        "=================================== FAILURES ===================================\n"
        "_______________________________ test_example _______________________________\n"
        "tests/test_example.py::test_example FAILED\n"
        "E   AssertionError: expected 1 == 2\n"
        "E   assert 1 == 2\n"
        "E   +  where 1 = <function at 0x...>\n"
        "src/jarvis/agent.py:123: in run_agent\n"
        "    assert False\n"
    )
    triage = triage_pytest_output(output, ui_lang="en")
    assert triage["title"] == "Tests failed (1)"
    assert "test_example" in triage["body"]
    assert "AssertionError" in triage["query_terms"]
    assert "src/jarvis/agent.py" in triage["query_terms"]
    assert "run_agent" in triage["query_terms"]


def test_triage_key_error():
    output = (
        "=================================== FAILURES ===================================\n"
        "_______________________________ test_dict_access _______________________________\n"
        "tests/test_dict.py::test_dict_access FAILED\n"
        "E   KeyError: 'missing_key'\n"
        "E   def test_dict_access():\n"
        "E       d = {}\n"
        "E       return d['missing_key']\n"
        "src/jarvis/utils.py:45: in get_value\n"
        "    return data[key]\n"
    )
    triage = triage_pytest_output(output, ui_lang="da")
    assert triage["title"] == "Tests fejlede (1)"
    assert "test_dict_access" in triage["body"]
    assert "KeyError" in triage["query_terms"]
    assert "src/jarvis/utils.py" in triage["query_terms"]
    assert "get_value" in triage["query_terms"]


def test_parse_module_not_found():
    output = (
        "=================================== FAILURES ===================================\n"
        "__________________________ test_imports __________________________\n"
        "E   ModuleNotFoundError: No module named 'jarvis'\n"
        "tests/test_imports.py:5: in <module>\n"
        "    import jarvis\n"
    )
    parsed = parse_pytest_output(output)
    assert parsed["error_type"] == "ModuleNotFoundError"
    assert "tests/test_imports.py" in parsed["file_paths"]


def test_parse_assertion():
    output = (
        "FAILED tests/test_example.py::test_run - AssertionError: expected 1 == 2\n"
        "E   AssertionError: expected 1 == 2\n"
        "tests/test_example.py:10: in test_run\n"
        "    assert 1 == 2\n"
    )
    parsed = parse_pytest_output(output)
    assert parsed["error_type"] == "AssertionError"
    assert "tests/test_example.py" in parsed["file_paths"]
    assert 10 in parsed["line_numbers"]


def test_parse_indentation_error():
    output = (
        "E   IndentationError: unexpected indent\n"
        "src/jarvis/bad.py:3: in <module>\n"
        "    def broken():\n"
    )
    parsed = parse_pytest_output(output)
    assert parsed["error_type"] == "IndentationError"
    assert "src/jarvis/bad.py" in parsed["file_paths"]
