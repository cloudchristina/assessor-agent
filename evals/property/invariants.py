"""Hypothesis strategies for generating valid UARRow instances + invariant predicates.

Exports:
    uar_row_strategy  -- @st.composite strategy producing valid UARRow instances
    _RULE_IDS         -- frozenset of known rule IDs {"R1",...,"R6"}
"""
from __future__ import annotations

from datetime import datetime

from hypothesis import strategies as st

from src.shared.models import UARRow

_LOGIN_TYPES = st.sampled_from(["SQL_LOGIN", "WINDOWS_LOGIN", "WINDOWS_GROUP"])
_ACCESS_LEVELS = st.sampled_from(["Admin", "Write", "ReadOnly", "Unknown"])
_RULE_IDS: frozenset[str] = frozenset({"R1", "R2", "R3", "R4", "R5", "R6"})

# Safe alphabets that won't trip pydantic or SQL-name edge cases.
_ALPHA = st.characters(min_codepoint=ord("a"), max_codepoint=ord("z"))
_ALNUM = st.characters(
    whitelist_categories=("Ll", "Lu", "Nd"),
    whitelist_characters="_",
)


def _datetimes_naive() -> st.SearchStrategy[datetime]:
    """Bounded naive datetimes — avoids pydantic TZ edge cases."""
    return st.datetimes(
        min_value=datetime(2010, 1, 1),
        max_value=datetime(2030, 12, 31),
    )


@st.composite
def uar_row_strategy(draw: st.DrawFn) -> UARRow:  # type: ignore[type-arg]
    """Produce a valid, fully-populated UARRow instance."""
    return UARRow.model_validate(
        {
            "login_name": draw(
                st.text(alphabet=_ALPHA, min_size=1, max_size=20)
            ),
            "login_type": draw(_LOGIN_TYPES),
            "login_create_date": draw(_datetimes_naive()),
            "last_active_date": draw(st.one_of(st.none(), _datetimes_naive())),
            "server_roles": draw(
                st.lists(
                    st.text(alphabet=_ALNUM, min_size=1, max_size=10),
                    max_size=3,
                )
            ),
            "database": draw(st.text(alphabet=_ALNUM, min_size=1, max_size=30)),
            "mapped_user_name": draw(
                st.one_of(
                    st.none(),
                    st.text(alphabet=_ALNUM, min_size=1, max_size=20),
                )
            ),
            "user_type": draw(
                st.one_of(
                    st.none(),
                    st.text(alphabet=_ALPHA, min_size=1, max_size=10),
                )
            ),
            "default_schema": draw(
                st.one_of(
                    st.none(),
                    st.text(alphabet=_ALNUM, min_size=1, max_size=20),
                )
            ),
            "db_roles": draw(
                st.lists(
                    st.text(alphabet=_ALNUM, min_size=1, max_size=20),
                    max_size=4,
                )
            ),
            "explicit_read": draw(st.booleans()),
            "explicit_write": draw(st.booleans()),
            "explicit_exec": draw(st.booleans()),
            "explicit_admin": draw(st.booleans()),
            "access_level": draw(_ACCESS_LEVELS),
            "grant_counts": draw(
                st.dictionaries(
                    st.sampled_from(["SELECT", "INSERT", "UPDATE"]),
                    st.integers(min_value=0, max_value=100),
                    max_size=3,
                )
            ),
            "deny_counts": draw(
                st.dictionaries(
                    st.sampled_from(["SELECT", "INSERT"]),
                    st.integers(min_value=0, max_value=100),
                    max_size=2,
                )
            ),
        }
    )
