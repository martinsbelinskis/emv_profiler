"""ENV export template for VISA profiles."""

from __future__ import annotations

import re
from dataclasses import dataclass

_HEX_TAG_RE = re.compile(r'^[0-9A-Fa-f]{2,4}$')


@dataclass
class VisaEnvEntry:
    var_name: str
    tag: str           # hex tag (uppercase) or "" for fixed/non-tag entries
    template_tag: str  # hex BFxx templatetag (uppercase) or "" when not applicable
    prefix: str        # "eVsDef", "eQvDef", or "" for fixed entries
    default_value: str
    decode_ascii: bool = False  # if True, hex tagvalue is decoded as latin-1 for export


def _parse_visa_entry(var_name: str, template_tag: str = "",
                      default_value: str = "",
                      decode_ascii: bool = False) -> VisaEnvEntry:
    parts = var_name.split("_")
    prefix = parts[0] if parts else ""
    tag = ""
    if len(parts) >= 2 and _HEX_TAG_RE.match(parts[1]):
        tag = parts[1].upper()
    return VisaEnvEntry(var_name=var_name, tag=tag,
                        template_tag=template_tag.upper() if template_tag else "",
                        prefix=prefix, default_value=default_value,
                        decode_ascii=decode_ascii)


# ---------------------------------------------------------------------------
# (var_name, template_tag, default_value, decode_ascii)
# template_tag   → BFxx templatetag from the XML <templatetag> element;
#                  used to disambiguate tags that appear with multiple
#                  templatetags (e.g. DF21 under BF56/BF57/BF58).
#                  Leave "" when the tag is unique or not in a template.
# decode_ascii   → profile tagvalue (hex) is decoded to ASCII for export
# default_value  → pre-filled in the Override column; takes priority over
#                  profile mapping if non-empty
# ---------------------------------------------------------------------------
_VISA_TEMPLATE_DEFS: list[tuple[str, str, str, bool]] = [
    # var_name                  template_tag  default_value                                    decode_ascii
    ("eVsDef_4F_Aid",           "",           "A0000000031010",                                False),
    ("eVsDef_50_ApLb",          "",           "Visa Debit",                                    True),
    ("eVsDef_9F12_ApNm",        "",           "Visa",                                          True),
    ("eVsDef_87_Api",           "",           "01",                                            False),
    ("eVsDef_9F0A_AppSRPD",     "",           "0001050100000000",                              False),
    ("eVsDef_9F10_Iad",         "",           "06011203000000",                                False),
    ("eQvDef_9F10_Iad",         "",           "06011203000000",                                False),
    ("eVsDef_5F2D_Lng",         "",           "656E6C746465",                                  False),
    ("eQvDef_9F38_Pdol",        "",           "9F66049F02069F03069F1A0295055F2A029A039C019F3704", False),
    ("eVsDef_9F38_Pdol",        "",           "ABABABAB",                                      False),
    ("eQvDef_DF20_ClCap",       "BF63",       "80",                                            False),
    ("eQvDef_9F5A_Apid",        "",           "3109780440",                                    False),
    ("eVsDef_9F73_CrCoP",       "",           "ABABABAB",                                      False),
    ("eVsDef_9F4D_LogEntry",    "",           "ABABABAB",                                      False),
    ("eVsDef_82_Aip",           "",           "3900",                                          False),
    ("eQvDef_82_Aip",           "",           "2020",                                          False),
    ("eVsDef_9F0D_IacDf",       "",           "BC68AC8800",                                    False),
    ("eVsDef_9F0E_IacDn",       "",           "0010000000",                                    False),
    ("eVsDef_9F0F_IacOn",       "",           "BC68BC9800",                                    False),
    ("eVsDef_9F49_Ddol",        "",           "9F3704",                                        False),
    ("eVsDef_9F11_Icti",        "",           "01",                                            False),
    ("eVsDef_8E_Cvm",           "",           "000000000000000042014403010302031E031F00",      False),
    ("eVsDef_5F28_IsCoc",       "",           "0440",                                          False),
    ("eVsDef_9F07_ApUs",        "",           "FF80",                                          False),
    ("eQvDef_9F07_ApUs",        "",           "8200",                                          False),
    ("eVsDef_9F4A_SdaTl",       "",           "82",                                            False),
    ("eVsDef_8C_Cdol1",         "",           "9F02069F03069F1A0295055F2A029A039C019F3704",    False),
    ("eVsDef_8D_Cdol2",         "",           "8A029F02069F03069F1A0295055F2A029A039C019F37049108", False),
    ("eVsDef_9F44_ApCux",       "",           "02",                                            False),
    ("eVsDef_9F69_Ardc",        "",           "01000000000000",                                False),
    ("eVsDef_9F51_ApCuc",       "",           "0978",                                          False),
    ("eVsDef_9F52_Ada",         "",           "FF3800800000",                                  False),
    ("eVsDef_9F56_IsAth",       "",           "80",                                            False),
    ("eVsDef_9F57_IsCoc",       "",           "0440",                                          False),
    ("eVsDef_9F42_ApCuc",       "",           "0978",                                          False),
    ("eVsDef_9F68_Cap",         "",           "0800E000",                                      False),
    ("eVsDef_9F6C_Ctq",         "",           "0600",                                          False),
    ("eVsDef_9F6E_FFI",         "",           "20700000",                                      False),
    ("eVsDef_DF01_AppCap",      "BF5B",       "0000",                                          False),
    ("eVsDef_DF11_CLTC",        "",           "ABABABAB",                                      False),
    ("eVsDef_DF21_CLTCLL",      "",           "ABABABAB",                                      False),
    ("eVsDef_DF31_CLTCUL",      "",           "ABABABAB",                                      False),
    ("eVsDef_DF41_VlpStl",      "",           "ABABABAB",                                      False),
    ("eVsDef_DF51_VlpAvFu",     "",           "ABABABAB",                                      False),
    ("eVsDef_DF61_VlpReTh",     "",           "ABABABAB",                                      False),
    ("eVsDef_DF71_VlpFuLi",     "",           "ABABABAB",                                      False),
    ("eVsDef_DF11_CTC",         "",           "ABABABAB",                                      False),
    ("eVsDef_DF21_CTCL",        "BF56",       "00",                                            False),
    ("eVsDef_DF31_CTCUL",       "BF56",       "32",                                            False),
    ("eVsDef_DF11_CTCI",        "",           "ABABABAB",                                      False),
    ("eVsDef_DF21_CTCIL",       "BF57",       "00",                                            False),
    ("eVsDef_DF31_CTIUL",       "BF57",       "00",                                            False),
    ("eVsDef_DF51_CTCIC",       "",           "ABABABAB",                                      False),
    ("eVsDef_DF61_CTCICL",      "",           "ABABABAB",                                      False),
    ("eVsDef_DF11_CTTA",        "",           "ABABABAB",                                      False),
    ("eVsDef_DF21_CTTAL",       "BF58",       "000000000000",                                  False),
    ("eVsDef_DF31_CTTAUL",      "BF58",       "000000020000",                                  False),
    ("eVsDef_9F17_PinCt",       "",           "03",                                            False),
    ("eVsDef_9F08_ApVr",        "",           "00A0",                                          False),
    ("eVSDC_GenPkSiz",          "",           "1408",                                          False),
    ("eICC_PK_SizeFor9F4B",     "",           "8180",                                          False),
]

VISA_ENV_TEMPLATE: list[VisaEnvEntry] = [
    _parse_visa_entry(n, t, d, a) for n, t, d, a in _VISA_TEMPLATE_DEFS
]
