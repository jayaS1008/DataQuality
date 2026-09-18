"""Current logic: mirrors dataquality.catalog.build_record's is_active.

A product is active if rmsStatus is Approved AND at least one country listing
is live (authorised, not suspended, not deactivated).
"""

from dataquality.catalog import ProductRecord


def compute(record: ProductRecord) -> bool:
    return record.rms_approved and record.any_country_live
