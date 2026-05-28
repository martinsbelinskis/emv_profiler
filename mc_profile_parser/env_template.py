"""ENV export template — defines the ordered list of ENV variables for .env output."""

from __future__ import annotations

import re
from dataclasses import dataclass, field

_HEX_RE = re.compile(r'^[0-9A-Fa-f]{2,4}$')
_TYPE_RE = re.compile(r'^(x\d*|a)$', re.IGNORECASE)


@dataclass
class EnvEntry:
    var_name: str       # e.g. "ApplicationLabel_50_a"
    tags: list[str]     # all hex tags found in name (uppercase), e.g. ["50"]
    type_hint: str      # "a" = ASCII (hex→latin-1), "x"/"xN" = raw hex, "" = raw hex

    @property
    def primary_tag(self) -> str:
        return self.tags[0] if self.tags else ""


def _parse_entry(var_name: str) -> EnvEntry:
    parts = var_name.split("_")
    tags: list[str] = [p.upper() for p in parts if _HEX_RE.match(p)]
    type_hint = next((p for p in reversed(parts) if _TYPE_RE.match(p)), "")
    return EnvEntry(var_name=var_name, tags=tags, type_hint=type_hint)


# Ordered list of ENV variable names matching the standard template output format.
_TEMPLATE_NAMES: list[str] = [
    "ApplicationLabel_50_a",
    "ApplicationPreferredName_9F12_a",
    "LanguagePreference_5F2D_a",
    "IFR_9F0A",
    "ACSessionKeyCounterLimitContact_DF3A_x2",
    "Accumulator1ControlContact_DF11_x1",
    "Accumulator1CurrencyConversionTable_D1_x25",
    "Accumulator1CVRDependencyDataContact_DF28_x3",
    "Accumulator1LowerLimit_CA_x6",
    "Accumulator1UpperLimit_CB_x6",
    "Accumulator2ControlContact_DF14_x1",
    "Accumulator2CurrencyCode_DF16_x2",
    "Accumulator2CurrencyConversionTable_DF17_x25",
    "Accumulator2CVRDependencyDataContact_DF2A_x3",
    "Accumulator2LowerLimit_DF18_x6",
    "Accumulator2UpperLimit_DF19_x6",
    "AdditionalCheckTable_D3_x18",
    "ApplicationControlContact_D5_x6",
    "CIACDeclineContact_C3_x3",
    "CIACDefaultContact_C4_x3",
    "CIACOnlineContact_C5_x3",
    "Cdol1L_C7_x",
    "Counter1ControlContact_DF1A_x1",
    "Counter1CVRDependencyDataContact_DF2C_x3",
    "Counter1LowerLimit_9F14_x1",
    "Counter1UpperLimit_9F23_x1",
    "Counter2ControlContact_DF1D_x1",
    "Counter2CVRDependencyDataContact_DF2E_x3",
    "Counter2LowerLimit_DF1F_x1",
    "Counter2UpperLimit_DF21_x1",
    "CryptogramVersionNumberV2x_DF63_x1",
    "CVRIssuerDiscretionaryDataContact_DF3C_x1",
    "DefaultARPCResponseCode_D6_x2",
    "DS_Management_Control_DF41_x2",
    "LogFormat_9F4F_x",
    "MaximumTransactionAmountCurrencyCode_DF24_x2",
    "MaximumTransactionAmountCVMContact_DF22_x6",
    "MaximumTransactionAmountNoCVMContact_DF25_x6",
    "NumberOfDaysOfflineLimit_DF27_x2",
    "PINDeciphermentsErrorCounterLimit_DF36_x2",
    "PTL_C6_x2",
    "PIN_TryCounter_9F17_x1",
    "LogDataTable_DE_x9",
    "ReadRecordFilterContact_DF3F_x",
    "SMISessionKeyCounterLimitContact_DF32_x2",
    "ApplicationVersionNumber_9F08_x2",
    "SDA_TagList_9F4A_x1",
    "DDOL_9F49_x",
    "IAC_Contact_Default_9F0D_x5",
    "IAC_Contact_Denial_9F0E_x5",
    "IAC_Contact_Online_9F0F_x5",
    "CDOL1_Contact_8C_x",
    "CDOL2_Contact_8D_x",
    "CVMC_ontact_List_8E_x",
    "AUC_Contact_9F07_x2",
    "Accumulator1CurrencyCode_9F42_C9_x2",
    "Issuer_Country_Code_5F28_x2_CRMCountryCode_C8_x2",
    "ApplicationInterchangeProfileContact_82_x2",
    "ApplicationCurrencyExponent_9F44_x1",
    "ACSessionKeyCounterLimitContactless_DF34_x2",
    "Accumulator1ControlContactless_DF12_x1",
    "Accumulator1CVRDependencyDataContactless_DF29_x3",
    "Accumulator2ControlContactless_DF15_x1",
    "Accumulator2CVRDependencyDataContactless_DF2B_x3",
    "ApplicationControlContactless_D7_x6",
    "ApplicationInterchangeProfileContactless_D8_x2",
    "CIACDeclineContactless_CF_x3",
    "CIACDefaultContactless_CD_x3",
    "CIACOnlineContactless_CE_x3",
    "Counter1ControlContactless_DF1B_x1",
    "Counter1CVRDependencyDataContactless_DF2D_x3",
    "Counter2ControlContactless_DF1E_x1",
    "Counter2CVRDependencyDataContactless_DF2F_x3",
    "CVRIssuerDiscretionaryDataContactless_DF3D_x1",
    "MaximumTransactionAmountCVMContactless_DF23_x6",
    "MaximumTransactionAmountNoCVMContactless_DF26_x6",
    "ReadRecordFilterContactless_DF40_x",
    "SMISessionKeyCounterLimitContactless_DF33_x2",
    "AUC_Contactless_9F07_x2",
    "CDOL1_Contactless_8C_x",
    "CDOL2_Contactless_8D_x",
    "CVM_List_Contactless_8E_x",
    "IAC_Contactless_Default_9F0D_x5",
    "IAC_Contactless_Denial_9F0E_x5",
    "IAC_Contactless_Online_9F0F_x5",
]

ENV_TEMPLATE: list[EnvEntry] = [_parse_entry(n) for n in _TEMPLATE_NAMES]
