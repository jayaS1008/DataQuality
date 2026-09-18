"""Candidate logic: stricter than v1 - requires every listed country to be
live (authorised, not suspended, not deactivated), not just one of them.

This is an example of the kind of change a PM would want impact analysis for
before rolling out: how many products flip from active to inactive, and in
which categories.
"""

from dataquality.catalog import ProductRecord


def compute(record: ProductRecord) -> bool:
    if not record.countries:
        return False
    return record.rms_approved and all(
        c.get("authorised") and not c.get("suspended") and not c.get("deactivated") for c in record.countries
    )
