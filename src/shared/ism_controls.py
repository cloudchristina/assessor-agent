"""Static ISM control catalogue. Source: official ISM (current at time of writing)."""
from dataclasses import dataclass


@dataclass(frozen=True)
class ISMControlSpec:
    control_id: str
    title: str
    intent: str
    classification: str  # OFFICIAL/PROTECTED/SECRET applicability


_CATALOGUE: dict[str, ISMControlSpec] = {
    "ISM-1546": ISMControlSpec(
        "ISM-1546",
        "MFA for privileged accounts",
        "Privileged accounts must authenticate using multi-factor authentication.",
        "OFFICIAL",
    ),
    "ISM-1509": ISMControlSpec(
        "ISM-1509",
        "Privileged access revoked",
        "Privileged access is revoked when no longer required for an individual's duties.",
        "OFFICIAL",
    ),
    "ISM-1555": ISMControlSpec(
        "ISM-1555",
        "Inactive accounts disabled",
        "Inactive accounts are disabled after a defined period.",
        "OFFICIAL",
    ),
    "ISM-1175": ISMControlSpec(
        "ISM-1175",
        "Segregation of duties for privileged operations",
        "Privileged operations are subject to segregation of duties.",
        "OFFICIAL",
    ),
    "ISM-0445": ISMControlSpec(
        "ISM-0445",
        "Least privilege",
        "Users are granted the minimum privileges required to perform their duties.",
        "OFFICIAL",
    ),
    "ISM-1545": ISMControlSpec(
        "ISM-1545",
        "No shared accounts",
        "Shared and generic accounts are not used.",
        "OFFICIAL",
    ),
    "ISM-1507": ISMControlSpec(
        "ISM-1507",
        "Privileged access justified",
        "Privileged access is justified and authorised.",
        "OFFICIAL",
    ),
    "ISM-1508": ISMControlSpec(
        "ISM-1508",
        "Privileged access reviewed",
        "Privileged access is reviewed at least annually.",
        "OFFICIAL",
    ),
    "ISM-0430": ISMControlSpec(
        "ISM-0430",
        "Periodic access review",
        "Access to systems is reviewed periodically.",
        "OFFICIAL",
    ),
}


def get_ism_control(control_id: str) -> ISMControlSpec:
    if control_id not in _CATALOGUE:
        raise KeyError(f"unknown control: {control_id}")
    return _CATALOGUE[control_id]
