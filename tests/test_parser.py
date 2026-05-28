"""Tests for mc_profile_parser."""

import io
import zipfile

import pytest

from mc_profile_parser.parser import (
    ComparisonRow,
    DataElementRow,
    EnvCompareRow,
    compare_profiles,
    compare_env_files,
    export_comparison_csv,
    export_csv,
    export_env_comparison_csv,
    parse_env_file,
    parse_profile,
)

# ── fixtures / helpers ────────────────────────────────────────────────────────

def _make_xml(elements: list[dict]) -> bytes:
    """Build a minimal profile.xml with given dataElement dicts."""
    items = []
    for e in elements:
        val = e.get("value", "")
        items.append(f"""
        <dataElement id="{e['id']}">
          <name>{e.get('name', e['id'])}</name>
          <type>var</type>
          <outputType>h</outputType>
          <tag>{e.get('tag', '00')}</tag>
          <value>{val}</value>
          <encrypt>False</encrypt>
          <commentary>{e.get('commentary', '')}</commentary>
        </dataElement>""")
    body = "\n".join(items)
    xml = f"""<?xml version="1.0" encoding="utf-8"?>
<profile>
  <application id="profile" name="Test">
    <interface id="fci">
      <profile_data>{body}
      </profile_data>
    </interface>
  </application>
</profile>"""
    return xml.encode()


def _make_profile(tmp_path, name: str, elements: list[dict]) -> str:
    path = tmp_path / name
    with zipfile.ZipFile(path, "w") as zf:
        zf.writestr("profile.xml", _make_xml(elements))
    return str(path)


# ── parse_profile tests ───────────────────────────────────────────────────────

def test_parse_returns_only_non_empty_values(tmp_path):
    p = _make_profile(tmp_path, "t.profile", [
        {"id": "a", "value": "AABB"},
        {"id": "b", "value": ""},
    ])
    rows = parse_profile(p)
    assert len(rows) == 1
    assert rows[0].id == "a"


def test_parse_include_empty(tmp_path):
    p = _make_profile(tmp_path, "t.profile", [
        {"id": "a", "value": "AABB"},
        {"id": "b", "value": ""},
    ])
    rows = parse_profile(p, include_empty=True)
    assert len(rows) == 2


def test_parse_row_fields(tmp_path):
    p = _make_profile(tmp_path, "t.profile", [
        {"id": "emv.fci.applabel", "name": "App Label", "tag": "50", "value": "4D"},
    ])
    row = parse_profile(p)[0]
    assert row.interface == "fci"
    assert row.section == "profile_data"
    assert row.name == "App Label"
    assert row.tag == "50"


def test_file_not_found():
    with pytest.raises(FileNotFoundError):
        parse_profile("/nonexistent/path.profile")


def test_missing_profile_xml(tmp_path):
    path = tmp_path / "empty.profile"
    with zipfile.ZipFile(path, "w") as zf:
        zf.writestr("other.xml", b"<root/>")
    with pytest.raises(ValueError, match="profile.xml"):
        parse_profile(str(path))


# ── compare_profiles tests ────────────────────────────────────────────────────

def _rows(*specs: tuple) -> list[DataElementRow]:
    """Build DataElementRow list from (id, value, [tag]) tuples."""
    result = []
    for spec in specs:
        elem_id, value = spec[0], spec[1]
        tag = spec[2] if len(spec) > 2 else "00"
        result.append(DataElementRow(
            interface="fci", section="profile_data",
            id=elem_id, name=elem_id, type="var",
            output_type="h", tag=tag,
            value=value, encrypt="False", commentary="",
        ))
    return result


def test_compare_identical():
    r = _rows(("a", "AA"), ("b", "BB"))
    cmp = compare_profiles(r, r)
    assert all(c.status == "identical" for c in cmp)


def test_compare_only_in_1():
    r1 = _rows(("a", "AA"), ("b", "BB"))
    r2 = _rows(("a", "AA"))
    cmp = compare_profiles(r1, r2)
    statuses = {c.id: c.status for c in cmp}
    assert statuses["a"] == "identical"
    assert statuses["b"] == "only_in_1"


def test_compare_only_in_2():
    r1 = _rows(("a", "AA"))
    r2 = _rows(("a", "AA"), ("c", "CC"))
    cmp = compare_profiles(r1, r2)
    statuses = {c.id: c.status for c in cmp}
    assert statuses["c"] == "only_in_2"


def test_compare_different_value():
    r1 = _rows(("a", "AA"))
    r2 = _rows(("a", "BB"))
    cmp = compare_profiles(r1, r2)
    row = cmp[0]
    assert row.status == "different"
    assert row.value_1 == "AA"
    assert row.value_2 == "BB"
    assert "value" in row.changed_fields


def test_compare_changed_fields_lists_all_diffs():
    r1 = _rows(("a", "AA", "50"))
    r2 = _rows(("a", "BB", "51"))
    cmp = compare_profiles(r1, r2)
    assert "value" in cmp[0].changed_fields
    assert "tag" in cmp[0].changed_fields


def test_compare_changed_fields_empty_when_identical():
    r = _rows(("a", "AA"))
    cmp = compare_profiles(r, r)
    assert cmp[0].changed_fields == ""


# ── export tests ──────────────────────────────────────────────────────────────

def test_export_csv(tmp_path):
    p = _make_profile(tmp_path, "t.profile", [{"id": "a", "value": "AABB"}])
    rows = parse_profile(p)
    buf = io.StringIO()
    export_csv(rows, buf)
    text = buf.getvalue()
    assert "interface,section,id" in text
    assert "AABB" in text


def test_export_comparison_csv():
    r1 = _rows(("a", "AA"), ("b", "BB"))
    r2 = _rows(("a", "XX"))
    cmp = compare_profiles(r1, r2)
    buf = io.StringIO()
    export_comparison_csv(cmp, buf)
    text = buf.getvalue()
    assert "status" in text
    assert "only_in_1" in text
    assert "different" in text


# ── parse_env_file tests ──────────────────────────────────────────────────────

def test_parse_env_double_quoted(tmp_path):
    env_file = tmp_path / "test.env"
    env_file.write_text('ApplicationLabel_50_a = "Mastercard"\n', encoding="utf-8")
    result = parse_env_file(env_file)
    assert result == {"ApplicationLabel_50_a": "Mastercard"}


def test_parse_env_single_quoted(tmp_path):
    env_file = tmp_path / "test.env"
    env_file.write_text("KEY = 'value'\n", encoding="utf-8")
    result = parse_env_file(env_file)
    assert result["KEY"] == "value"


def test_parse_env_unquoted(tmp_path):
    env_file = tmp_path / "test.env"
    env_file.write_text("KEY = BLANK\n", encoding="utf-8")
    result = parse_env_file(env_file)
    assert result["KEY"] == "BLANK"


def test_parse_env_skips_comments(tmp_path):
    env_file = tmp_path / "test.env"
    env_file.write_text(
        "// comment\n"
        "# hash comment\n"
        'KEY = "val"\n',
        encoding="utf-8",
    )
    result = parse_env_file(env_file)
    assert list(result.keys()) == ["KEY"]


def test_parse_env_skips_blank_lines(tmp_path):
    env_file = tmp_path / "test.env"
    env_file.write_text('\nKEY = "val"\n\n', encoding="utf-8")
    result = parse_env_file(env_file)
    assert list(result.keys()) == ["KEY"]


# ── compare_env_files tests ───────────────────────────────────────────────────

def test_compare_env_identical():
    env = {"A": "1", "B": "2"}
    rows = compare_env_files(env, env)
    assert all(r.status == "identical" for r in rows)


def test_compare_env_different():
    rows = compare_env_files({"A": "1"}, {"A": "2"})
    assert rows[0].status == "different"
    assert rows[0].value_1 == "1"
    assert rows[0].value_2 == "2"


def test_compare_env_only_in_1():
    rows = compare_env_files({"A": "1", "B": "2"}, {"A": "1"})
    statuses = {r.variable: r.status for r in rows}
    assert statuses["B"] == "only_in_1"
    assert statuses["A"] == "identical"


def test_compare_env_only_in_2():
    rows = compare_env_files({"A": "1"}, {"A": "1", "C": "3"})
    statuses = {r.variable: r.status for r in rows}
    assert statuses["C"] == "only_in_2"


def test_export_env_comparison_csv():
    rows = [
        EnvCompareRow(variable="A", value_1="1", value_2="2", status="different"),
        EnvCompareRow(variable="B", value_1="X", value_2="",  status="only_in_1"),
    ]
    buf = io.StringIO()
    export_env_comparison_csv(rows, buf)
    text = buf.getvalue()
    assert "variable,value_1,value_2,status" in text
    assert "different" in text
    assert "only_in_1" in text
