"""Track status decoding.

FastF1 exposes ``Laps.TrackStatus`` as a *concatenated string* of every status
code that was active at any point during that lap — a lap run entirely under
green is ``"1"``, a lap where the VSC was deployed and then ended is ``"167"``.
Codes are therefore tested with substring containment, never with equality.

Confirmed against the 2019 Italian GP, whose race shows codes ``1, 2, 6, 7``.
"""

from __future__ import annotations

from enum import StrEnum

import pandas as pd


class TrackStatusCode(StrEnum):
    """Single-digit track status codes used by the F1 live-timing feed."""

    ALL_CLEAR = "1"
    YELLOW = "2"
    SC_DEPLOYED = "4"
    RED = "5"
    VSC_DEPLOYED = "6"
    VSC_ENDING = "7"


#: Codes that make a pit stop materially cheaper, because the field is neutralised.
NEUTRALISED = (TrackStatusCode.SC_DEPLOYED, TrackStatusCode.VSC_DEPLOYED)


def has_code(status: pd.Series, code: TrackStatusCode) -> pd.Series:
    """Return a boolean Series flagging laps during which ``code`` was active."""
    return status.fillna("").astype(str).str.contains(str(code), regex=False)


def add_flags(laps: pd.DataFrame) -> pd.DataFrame:
    """Append one boolean column per meaningful track status, plus ``is_neutralised``.

    Args:
        laps: A lap-level frame carrying a ``TrackStatus`` column.

    Returns:
        The same frame with ``yellow``, ``sc``, ``red``, ``vsc``, ``vsc_ending`` and
        ``is_neutralised`` columns added.
    """
    out = laps.copy()
    status = out["TrackStatus"]
    out["yellow"] = has_code(status, TrackStatusCode.YELLOW)
    out["sc"] = has_code(status, TrackStatusCode.SC_DEPLOYED)
    out["red"] = has_code(status, TrackStatusCode.RED)
    out["vsc"] = has_code(status, TrackStatusCode.VSC_DEPLOYED)
    out["vsc_ending"] = has_code(status, TrackStatusCode.VSC_ENDING)
    out["is_neutralised"] = out["sc"] | out["vsc"]
    return out
