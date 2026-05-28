"""ENV export template — defines the ordered list of ENV variables for .env output."""

from __future__ import annotations

import re
from dataclasses import dataclass, field

_HEX_RE = re.compile(r'^[0-9A-Fa-f]{2,4}$')
_TYPE_RE = re.compile(r'^(x\d*|a)$', re.IGNORECASE)


@dataclass
class EnvEntry:
    var_name: str        # e.g. "ApplicationLabel_50_a"
    tags: list[str]      # all hex tags found in name (uppercase), e.g. ["50"]
    type_hint: str       # "a" = ASCII (hex→latin-1), "x"/"xN" = raw hex, "" = raw hex
    default_value: str = ""  # pre-filled fixed value (overrides profile mapping when set)

    @property
    def primary_tag(self) -> str:
        return self.tags[0] if self.tags else ""


def _parse_entry(var_name: str, default_value: str = "") -> EnvEntry:
    parts = var_name.split("_")
    tags: list[str] = [p.upper() for p in parts if _HEX_RE.match(p)]
    type_hint = next((p for p in reversed(parts) if _TYPE_RE.match(p)), "")
    return EnvEntry(var_name=var_name, tags=tags, type_hint=type_hint, default_value=default_value)


# ---------------------------------------------------------------------------
# Each entry: (var_name, default_value)
# default_value is pre-filled in the Override column; empty means auto-map from profile.
# ---------------------------------------------------------------------------
_TEMPLATE_DEFS: list[tuple[str, str]] = [
    # ── Profile data elements ──────────────────────────────────────────────
    ("ApplicationLabel_50_a",                               ""),
    ("ApplicationPreferredName_9F12_a",                     ""),
    ("LanguagePreference_5F2D_a",                           ""),
    ("IFR_9F0A",                                            ""),
    ("ACSessionKeyCounterLimitContact_DF3A_x2",             ""),
    ("Accumulator1ControlContact_DF11_x1",                  ""),
    ("Accumulator1CurrencyConversionTable_D1_x25",          ""),
    ("Accumulator1CVRDependencyDataContact_DF28_x3",        ""),
    ("Accumulator1LowerLimit_CA_x6",                        ""),
    ("Accumulator1UpperLimit_CB_x6",                        ""),
    ("Accumulator2ControlContact_DF14_x1",                  ""),
    ("Accumulator2CurrencyCode_DF16_x2",                    ""),
    ("Accumulator2CurrencyConversionTable_DF17_x25",        ""),
    ("Accumulator2CVRDependencyDataContact_DF2A_x3",        ""),
    ("Accumulator2LowerLimit_DF18_x6",                      ""),
    ("Accumulator2UpperLimit_DF19_x6",                      ""),
    ("AdditionalCheckTable_D3_x18",                         ""),
    ("ApplicationControlContact_D5_x6",                     ""),
    ("CIACDeclineContact_C3_x3",                            ""),
    ("CIACDefaultContact_C4_x3",                            ""),
    ("CIACOnlineContact_C5_x3",                             ""),
    ("Cdol1L_C7_x",                                         ""),
    ("Counter1ControlContact_DF1A_x1",                      ""),
    ("Counter1CVRDependencyDataContact_DF2C_x3",            ""),
    ("Counter1LowerLimit_9F14_x1",                          ""),
    ("Counter1UpperLimit_9F23_x1",                          ""),
    ("Counter2ControlContact_DF1D_x1",                      ""),
    ("Counter2CVRDependencyDataContact_DF2E_x3",            ""),
    ("Counter2LowerLimit_DF1F_x1",                          ""),
    ("Counter2UpperLimit_DF21_x1",                          ""),
    ("CryptogramVersionNumberV2x_DF63_x1",                  ""),
    ("CVRIssuerDiscretionaryDataContact_DF3C_x1",           ""),
    ("DefaultARPCResponseCode_D6_x2",                       ""),
    ("DS_Management_Control_DF41_x2",                       ""),
    ("LogFormat_9F4F_x",                                    ""),
    ("MaximumTransactionAmountCurrencyCode_DF24_x2",        ""),
    ("MaximumTransactionAmountCVMContact_DF22_x6",          ""),
    ("MaximumTransactionAmountNoCVMContact_DF25_x6",        ""),
    ("NumberOfDaysOfflineLimit_DF27_x2",                    ""),
    ("PINDeciphermentsErrorCounterLimit_DF36_x2",           ""),
    ("PTL_C6_x2",                                           ""),
    ("PIN_TryCounter_9F17_x1",                              ""),
    ("LogDataTable_DE_x9",                                  ""),
    ("ReadRecordFilterContact_DF3F_x",                      ""),
    ("SMISessionKeyCounterLimitContact_DF32_x2",            ""),
    ("ApplicationVersionNumber_9F08_x2",                    ""),
    ("SDA_TagList_9F4A_x1",                                 ""),
    ("DDOL_9F49_x",                                         ""),
    ("IAC_Contact_Default_9F0D_x5",                         ""),
    ("IAC_Contact_Denial_9F0E_x5",                          ""),
    ("IAC_Contact_Online_9F0F_x5",                          ""),
    ("CDOL1_Contact_8C_x",                                  ""),
    ("CDOL2_Contact_8D_x",                                  ""),
    ("CVMC_ontact_List_8E_x",                               ""),
    ("AUC_Contact_9F07_x2",                                 ""),
    ("Accumulator1CurrencyCode_9F42_C9_x2",                 ""),
    ("Issuer_Country_Code_5F28_x2_CRMCountryCode_C8_x2",   ""),
    ("ApplicationInterchangeProfileContact_82_x2",          ""),
    ("ApplicationCurrencyExponent_9F44_x1",                 ""),
    ("ACSessionKeyCounterLimitContactless_DF34_x2",         ""),
    ("Accumulator1ControlContactless_DF12_x1",              ""),
    ("Accumulator1CVRDependencyDataContactless_DF29_x3",    ""),
    ("Accumulator2ControlContactless_DF15_x1",              ""),
    ("Accumulator2CVRDependencyDataContactless_DF2B_x3",    ""),
    ("ApplicationControlContactless_D7_x6",                 ""),
    ("ApplicationInterchangeProfileContactless_D8_x2",      ""),
    ("CIACDeclineContactless_CF_x3",                        ""),
    ("CIACDefaultContactless_CD_x3",                        ""),
    ("CIACOnlineContactless_CE_x3",                         ""),
    ("Counter1ControlContactless_DF1B_x1",                  ""),
    ("Counter1CVRDependencyDataContactless_DF2D_x3",        ""),
    ("Counter2ControlContactless_DF1E_x1",                  ""),
    ("Counter2CVRDependencyDataContactless_DF2F_x3",        ""),
    ("CVRIssuerDiscretionaryDataContactless_DF3D_x1",       ""),
    ("MaximumTransactionAmountCVMContactless_DF23_x6",      ""),
    ("MaximumTransactionAmountNoCVMContactless_DF26_x6",    ""),
    ("ReadRecordFilterContactless_DF40_x",                  ""),
    ("SMISessionKeyCounterLimitContactless_DF33_x2",        ""),
    ("AUC_Contactless_9F07_x2",                             ""),
    ("CDOL1_Contactless_8C_x",                              ""),
    ("CDOL2_Contactless_8D_x",                              ""),
    ("CVM_List_Contactless_8E_x",                           ""),
    ("IAC_Contactless_Default_9F0D_x5",                     ""),
    ("IAC_Contactless_Denial_9F0E_x5",                      ""),
    ("IAC_Contactless_Online_9F0F_x5",                      ""),

    # ── Data not used, defined in echip profile ────────────────────────────
    ("ApplicationFileLocatorContact_94_x",                  "1801020120020300"),
    ("ApplicationFileLocatorContactless_D9_x",              "1001010120010200"),
    ("eCARD_IcPersonalizer",                                "1673"),
    ("eCARD_MachineId",                                     "01007000"),
    ("ApplicationLifeCycleData_9F7E_Alcd_Ver",              "04"),
    ("ApplicationLifeCycleData_9F7E_Alcd_TypApprvId",       "100F1700020000"),
    ("ApplicationLifeCycleData_9F7E_AppIssrId",             "4445435441202020202020202020202020202020"),
    ("ApplicationLifeCycleData_9F7EAlcd_AppCodeId",         "5441472051564A313244495F5376312E30202020"),
    ("PTH_x1",                                              "00"),

    # ── General data ───────────────────────────────────────────────────────
    ("eMCHIP_GenPkSiz",                                     "1408"),
    ("eMCHIP_GenPkExp",                                     "03"),
    ("ICC_PK_CertificateSerialNumber_x3",                   "512345"),
    ("FCI_BF0C_tlv",                                        "9F4D020B0A9F6E0705780000323000"),
    ("ApplicationPriorityIndicator_87_x1",                  "01"),
    ("IssuerCodeTableIndex_9F11_x1",                        "01"),
    ("PDOL_9F38",                                           "BLANK"),
    ("ATCLimit_x2",                                         "4E20"),
    ("KeyDerivationIndexContactContactless_DF68_x1",        "01"),
    ("InterfaceEnablingSwitch_DF30_x1",                     "03"),
    ("MCHIPInterfaceIdentifierContact_x1",                  "00"),
    ("MCHIPInterfaceIdentifierContactless_x1",              "01"),
    ("IVCVC3Track1Contact_DF38_x2",                         "0000"),
    ("IVCVC3Track2Contact_DF39_x2",                         "0000"),
    ("Application_Effective_Date_5F25",                     "CALCULATE_2"),
    ("FCI_list",                                            "84,50,9F12,87,9F11,5F2D,BF0C"),
    ("PsePerso",                                            "1"),
    ("AID_4F_x",                                            "A0000000041010"),
    ("PAN_SequenceNumber_5F34_x1",                          "01"),
    ("ServiceCode_5F30_x2",                                 "0201"),
    ("DRDOL_9F51_x",                                        "9F3704"),
]

ENV_TEMPLATE: list[EnvEntry] = [_parse_entry(n, d) for n, d in _TEMPLATE_DEFS]

