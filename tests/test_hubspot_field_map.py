from csv_to_word_forms import (
    FIELD_MAPPING,
    PAYMENT_MONTH_CALC_HEADER,
    PAYMENT_YEAR_CALC_HEADER,
    TYPE_OF_RENTAL_ASSISTANCE_KEYS,
    build_column_map,
    normalize_column_name,
)
from hubspot_field_map import (
    FILTER_CHECK_TYPE_PROPERTY,
    FILTER_CHECK_TYPE_VALUE,
    FILTER_PAID_STATUS_PROPERTY,
    FILTER_PAID_STATUS_VALUE,
    HUBSPOT_TO_ENGINE_HEADER,
)


def test_mapping_is_nonempty():
    assert len(HUBSPOT_TO_ENGINE_HEADER) > 0


def test_mapping_keys_and_values_are_nonempty_strings():
    for key, value in HUBSPOT_TO_ENGINE_HEADER.items():
        assert isinstance(key, str) and key
        assert isinstance(value, str) and value


def test_mapping_covers_every_field_mapping_header():
    column_map = build_column_map(list(HUBSPOT_TO_ENGINE_HEADER.values()))
    for csv_header, template_label in FIELD_MAPPING:
        assert normalize_column_name(csv_header) in column_map, (
            f"No HubSpot property mapped to CSV header {csv_header!r} "
            f"(needed for template label {template_label!r})"
        )


def test_mapping_covers_payment_month_and_year():
    column_map = build_column_map(list(HUBSPOT_TO_ENGINE_HEADER.values()))
    assert PAYMENT_MONTH_CALC_HEADER in column_map
    assert PAYMENT_YEAR_CALC_HEADER in column_map


def test_mapping_covers_type_of_rental_assistance():
    column_map = build_column_map(list(HUBSPOT_TO_ENGINE_HEADER.values()))
    assert any(key in column_map for key in TYPE_OF_RENTAL_ASSISTANCE_KEYS)


def test_filter_constants_are_nonempty_strings():
    for value in (
        FILTER_CHECK_TYPE_PROPERTY,
        FILTER_CHECK_TYPE_VALUE,
        FILTER_PAID_STATUS_PROPERTY,
        FILTER_PAID_STATUS_VALUE,
    ):
        assert isinstance(value, str) and value


def test_no_leftover_placeholder_values():
    for key in HUBSPOT_TO_ENGINE_HEADER:
        assert not key.startswith("REPLACE_WITH_"), f"Unfilled placeholder: {key!r}"
    for value in (
        FILTER_CHECK_TYPE_PROPERTY,
        FILTER_CHECK_TYPE_VALUE,
        FILTER_PAID_STATUS_PROPERTY,
        FILTER_PAID_STATUS_VALUE,
    ):
        assert not value.startswith("REPLACE_WITH_"), f"Unfilled placeholder: {value!r}"
