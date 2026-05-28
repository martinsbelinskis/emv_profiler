"""Core parsing logic for MC profiles."""

import csv
import io
import re
import zipfile
from dataclasses import dataclass, fields
from pathlib import Path
from xml.etree import ElementTree as ET


PROFILE_XML = "profile.xml"


@dataclass
class DataElementRow:
    interface: str
    section: str
    id: str
    name: str
    type: str
    output_type: str
    tag: str
    value: str
    encrypt: str
    commentary: str


# Fields compared during diffing — all except the composite key parts
_COMPARE_FIELDS = [f.name for f in fields(DataElementRow) if f.name != "id"]


@dataclass
class ComparisonRow:
    status: str        # identical | different | only_in_1 | only_in_2
    id: str
    name: str
    interface: str     # from profile 1 when present, else profile 2
    section: str
    tag: str
    value_1: str
    value_2: str
    changed_fields: str  # comma-sep list of fields that differ (for "different" status)


def _text(element, tag: str) -> str:
    child = element.find(tag)
    return (child.text or "").strip() if child is not None else ""


def parse_profile(profile_path: str, *, include_empty: bool = False) -> list[DataElementRow]:
    """Open a .profile ZIP, parse profile.xml, return dataElement rows.

    Args:
        profile_path: Path to the .profile ZIP file.
        include_empty: When True, rows with an empty <value> are included
                       (needed for accurate comparison between two profiles).
    """
    path = Path(profile_path)
    if not path.exists():
        raise FileNotFoundError(f"Profile not found: {profile_path}")

    with zipfile.ZipFile(path) as zf:
        if PROFILE_XML not in zf.namelist():
            raise ValueError(f"{PROFILE_XML} not found inside {profile_path}")
        xml_bytes = zf.read(PROFILE_XML)

    root = ET.fromstring(xml_bytes)

    rows: list[DataElementRow] = []
    for app in root.iter("application"):
        for interface in app:
            iface_id = interface.get("id", "")
            for section in interface:
                section_name = section.tag
                for de in section.findall("dataElement"):
                    value = _text(de, "value")
                    if not include_empty and not value:
                        continue
                    rows.append(DataElementRow(
                        interface=iface_id,
                        section=section_name,
                        id=de.get("id", ""),
                        name=_text(de, "name"),
                        type=_text(de, "type"),
                        output_type=_text(de, "outputType"),
                        tag=_text(de, "tag"),
                        value=value,
                        encrypt=_text(de, "encrypt"),
                        commentary=_text(de, "commentary"),
                    ))
    return rows


def compare_profiles(
    rows_1: list[DataElementRow],
    rows_2: list[DataElementRow],
) -> list[ComparisonRow]:
    """Compare two parsed profiles and return a list of comparison rows.

    Elements are matched by their ``id`` attribute. When the same id appears
    multiple times in one profile (different interface/section), each occurrence
    is treated independently using a ``(interface, id)`` composite key.
    """
    def _keyed(rows: list[DataElementRow]) -> dict[tuple[str, str], DataElementRow]:
        result: dict[tuple[str, str], DataElementRow] = {}
        for row in rows:
            key = (row.interface, row.id)
            result[key] = row  # last-write wins for genuine duplicates
        return result

    map_1 = _keyed(rows_1)
    map_2 = _keyed(rows_2)
    all_keys = sorted(set(map_1) | set(map_2), key=lambda k: (k[0], k[1]))

    result: list[ComparisonRow] = []
    for key in all_keys:
        r1 = map_1.get(key)
        r2 = map_2.get(key)

        if r1 and r2:
            changed = [
                f for f in _COMPARE_FIELDS
                if getattr(r1, f) != getattr(r2, f)
            ]
            result.append(ComparisonRow(
                status="different" if changed else "identical",
                id=r1.id,
                name=r1.name,
                interface=r1.interface,
                section=r1.section,
                tag=r1.tag,
                value_1=r1.value,
                value_2=r2.value,
                changed_fields=", ".join(changed),
            ))
        elif r1:
            result.append(ComparisonRow(
                status="only_in_1",
                id=r1.id,
                name=r1.name,
                interface=r1.interface,
                section=r1.section,
                tag=r1.tag,
                value_1=r1.value,
                value_2="",
                changed_fields="",
            ))
        else:
            assert r2
            result.append(ComparisonRow(
                status="only_in_2",
                id=r2.id,
                name=r2.name,
                interface=r2.interface,
                section=r2.section,
                tag=r2.tag,
                value_1="",
                value_2=r2.value,
                changed_fields="",
            ))
    return result


def export_csv(rows: list[DataElementRow], output: io.TextIOBase) -> None:
    """Write DataElementRow list to a CSV file-like object."""
    _write_csv(output, [f.name for f in fields(DataElementRow)],
               [{f.name: getattr(r, f.name) for f in fields(DataElementRow)} for r in rows])


def export_comparison_csv(rows: list[ComparisonRow], output: io.TextIOBase) -> None:
    """Write ComparisonRow list to a CSV file-like object."""
    _write_csv(output, [f.name for f in fields(ComparisonRow)],
               [{f.name: getattr(r, f.name) for f in fields(ComparisonRow)} for r in rows])


def _write_csv(output: io.TextIOBase, fieldnames: list[str], rows: list[dict]) -> None:
    writer = csv.DictWriter(output, fieldnames=fieldnames, lineterminator="\n")
    writer.writeheader()
    writer.writerows(rows)


def _hex_to_display(hex_val: str, type_hint: str) -> str:
    """Convert a hex profile value to the string used in the .env output."""
    hex_val = hex_val.strip()
    if not hex_val:
        return ""
    # Validate: must be even-length hex
    if len(hex_val) % 2 != 0 or not all(c in "0123456789ABCDEFabcdef" for c in hex_val):
        return hex_val  # pass through as-is if not valid hex
    if type_hint.lower() == "a":
        try:
            return bytes.fromhex(hex_val).decode("latin-1")
        except Exception:
            return hex_val
    return hex_val


def export_env(
    entries: "list[EnvEntry]",
    mapping: dict[str, str],       # {var_name -> element_id}
    overrides: dict[str, str],     # {var_name -> manual override value (takes priority)}
    id_to_row: dict[str, DataElementRow],  # {element_id -> row}
    output: io.TextIOBase,
) -> None:
    """Write a .env file from the template, mapping, overrides and profile data.

    Priority: override value > profile-mapped value > empty.
    """
    for entry in entries:
        override = overrides.get(entry.var_name, "").strip()
        if override:
            display_val = override
        else:
            elem_id = mapping.get(entry.var_name, "")
            row = id_to_row.get(elem_id)
            hex_val = row.value if row else ""
            display_val = _hex_to_display(hex_val, entry.type_hint) if hex_val else ""
        safe_val = display_val.replace("\\", "\\\\").replace('"', '\\"')
        output.write(f'{entry.var_name} = "{safe_val}"\n')


# ── .env file comparison ──────────────────────────────────────────────────────

@dataclass
class EnvCompareRow:
    variable: str
    value_1: str
    value_2: str
    status: str  # identical | different | only_in_1 | only_in_2


# Matches: KEY = "VALUE", KEY = 'VALUE', KEY = VALUE  (with optional spaces)
_ENV_LINE_RE = re.compile(r'^([A-Za-z_][A-Za-z0-9_]*)\s*=\s*(.*)')


def parse_env_file(path: str | Path) -> dict[str, str]:
    """Parse a .env file into {variable_name: value}.

    Handles quoted values (single or double quotes), inline comments starting
    with ``//`` or ``#`` after the value are stripped.  Lines that start with
    ``//`` or ``#`` (comments) and blank lines are skipped.

    Encoding is auto-detected: UTF-8-with-BOM → UTF-8 → cp1252 → latin-1.
    """
    path = Path(path)
    raw = path.read_bytes()
    # Try encodings in order; latin-1 always succeeds (every byte is valid)
    for enc in ("utf-8-sig", "utf-8", "cp1252", "latin-1"):
        try:
            text = raw.decode(enc)
            break
        except (UnicodeDecodeError, LookupError):
            continue

    result: dict[str, str] = {}
    for line in text.splitlines():
        line = line.strip()
        if not line or line.startswith("//") or line.startswith("#"):
            continue
        m = _ENV_LINE_RE.match(line)
        if not m:
            continue
        key = m.group(1).strip()
        val = m.group(2).strip()
        # Strip surrounding quotes
        if len(val) >= 2 and val[0] in ('"', "'") and val[-1] == val[0]:
            val = val[1:-1]
        result[key] = val
    return result


def compare_env_files(
    env1: dict[str, str],
    env2: dict[str, str],
) -> list[EnvCompareRow]:
    """Compare two parsed .env dicts and return a sorted list of EnvCompareRows."""
    all_keys = sorted(set(env1) | set(env2), key=str.casefold)
    rows: list[EnvCompareRow] = []
    for key in all_keys:
        v1 = env1.get(key)
        v2 = env2.get(key)
        if v1 is None:
            status = "only_in_2"
            v1 = ""
        elif v2 is None:
            status = "only_in_1"
            v2 = ""
        elif v1 == v2:
            status = "identical"
        else:
            status = "different"
        rows.append(EnvCompareRow(variable=key, value_1=v1, value_2=v2, status=status))
    return rows


def export_env_comparison_csv(rows: list[EnvCompareRow], output: io.TextIOBase) -> None:
    """Write EnvCompareRow list to a CSV file-like object."""
    _write_csv(output, [f.name for f in fields(EnvCompareRow)],
               [{f.name: getattr(r, f.name) for f in fields(EnvCompareRow)} for r in rows])
