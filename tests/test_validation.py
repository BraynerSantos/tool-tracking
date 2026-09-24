import math

from app.validation import validate_attributes, validate_schema

SCHEMA = [
    {"key": "diameter_mm", "label": "Diameter (mm)", "type": "number"},
    {"key": "coating", "label": "Coating", "type": "text"},
]


class TestValidateSchema:
    def test_accepts_valid_schema(self):
        assert validate_schema(SCHEMA) is None

    def test_rejects_non_array(self):
        err = validate_schema("nope")
        assert isinstance(err, str) and "array" in err.lower()
        assert validate_schema({"key": "a"}) and "array" in validate_schema({"key": "a"}).lower()
        assert validate_schema(None) and "array" in validate_schema(None).lower()

    def test_rejects_non_dict_entries(self):
        assert validate_schema([None])
        assert validate_schema(["nope"])
        assert validate_schema([42])

    def test_rejects_empty_key(self):
        assert validate_schema([{"key": "", "label": "L", "type": "number"}])
        assert validate_schema([{"key": "   ", "label": "L", "type": "number"}])
        assert validate_schema([{"label": "L", "type": "number"}])

    def test_rejects_empty_label(self):
        assert validate_schema([{"key": "a", "label": "", "type": "number"}])
        assert validate_schema([{"key": "a", "label": "  ", "type": "number"}])
        assert validate_schema([{"key": "a", "type": "number"}])

    def test_rejects_invalid_type(self):
        assert validate_schema([{"key": "a", "label": "L", "type": "date"}])
        assert validate_schema([{"key": "a", "label": "L", "type": "TEXT"}])
        assert validate_schema([{"key": "a", "label": "L"}])

    def test_duplicate_keys_rejected(self):
        schema = [
            {"key": "a", "label": "A", "type": "number"},
            {"key": "a", "label": "B", "type": "text"},
        ]
        assert validate_schema(schema)

    def test_empty_schema_is_valid(self):
        assert validate_schema([]) is None


class TestValidateAttributesNumbers:
    def test_decimal_values_accepted(self):
        r = validate_attributes(SCHEMA, {"diameter_mm": "0.250"})
        assert r == {"ok": True, "clean": {"diameter_mm": 0.25}}

        r = validate_attributes(SCHEMA, {"diameter_mm": " 6.35 "})
        assert r == {"ok": True, "clean": {"diameter_mm": 6.35}}
        assert r["clean"]["diameter_mm"] == 6.35

        r = validate_attributes(SCHEMA, {"diameter_mm": 0.5})
        assert r == {"ok": True, "clean": {"diameter_mm": 0.5}}
        assert r["clean"]["diameter_mm"] == 0.5

    def test_numeric_types_accepted(self):
        r = validate_attributes(SCHEMA, {"diameter_mm": 6})
        assert r["ok"] is True and r["clean"]["diameter_mm"] == 6

        r = validate_attributes(SCHEMA, {"diameter_mm": 6.5})
        assert r["clean"]["diameter_mm"] == 6.5

        r = validate_attributes(SCHEMA, {"diameter_mm": -1.25})
        assert r["clean"]["diameter_mm"] == -1.25

        r = validate_attributes(SCHEMA, {"diameter_mm": 0})
        assert r["ok"] is True and r["clean"]["diameter_mm"] == 0

    def test_numeric_strings_accepted(self):
        r = validate_attributes(SCHEMA, {"diameter_mm": "6.35"})
        assert r["clean"]["diameter_mm"] == 6.35

        r = validate_attributes(SCHEMA, {"diameter_mm": " 0.5 "})
        assert r["clean"]["diameter_mm"] == 0.5

        r = validate_attributes(SCHEMA, {"diameter_mm": "6"})
        assert r["ok"] is True and r["clean"]["diameter_mm"] == 6.0

        r = validate_attributes(SCHEMA, {"diameter_mm": "-3.5"})
        assert r["clean"]["diameter_mm"] == -3.5

    def test_junk_rejected(self):
        for junk in ["", "   ", "wide", [], {}, None, math.nan, math.inf, True]:
            r = validate_attributes(SCHEMA, {"diameter_mm": junk})
            assert r["ok"] is False, f"expected rejection for {junk!r}"
            assert "number" in r["errors"]["diameter_mm"].lower()

    def test_nan_and_infinity_rejected(self):
        assert validate_attributes(SCHEMA, {"diameter_mm": math.nan})["ok"] is False
        assert validate_attributes(SCHEMA, {"diameter_mm": math.inf})["ok"] is False
        assert validate_attributes(SCHEMA, {"diameter_mm": -math.inf})["ok"] is False
        assert validate_attributes(SCHEMA, {"diameter_mm": "NaN"})["ok"] is False
        assert validate_attributes(SCHEMA, {"diameter_mm": "Infinity"})["ok"] is False

    def test_bools_rejected(self):
        assert validate_attributes(SCHEMA, {"diameter_mm": True})["ok"] is False
        assert validate_attributes(SCHEMA, {"diameter_mm": False})["ok"] is False

    def test_huge_integer_rejected_not_crash(self):
        # a huge JSON integer overflows float() -> must be a validation error
        r = validate_attributes(SCHEMA, {"diameter_mm": 10**400})
        assert r["ok"] is False
        assert "number" in r["errors"]["diameter_mm"].lower()


class TestValidateAttributesText:
    def test_text_coerced_via_str(self):
        r = validate_attributes(SCHEMA, {"coating": "TiAlN"})
        assert r["clean"]["coating"] == "TiAlN"

        r = validate_attributes(SCHEMA, {"coating": 42})
        assert r["clean"]["coating"] == "42"

        r = validate_attributes(SCHEMA, {"coating": 6.35})
        assert r["clean"]["coating"] == "6.35"

    def test_blank_text_allowed(self):
        r = validate_attributes(SCHEMA, {"coating": ""})
        assert r["ok"] is True and r["clean"]["coating"] == ""

    def test_none_text_becomes_empty_string(self):
        r = validate_attributes(SCHEMA, {"coating": None})
        assert r["ok"] is True and r["clean"]["coating"] == ""


class TestValidateAttributesShape:
    def test_unknown_keys_stripped_and_text_coerced(self):
        r = validate_attributes(SCHEMA, {"coating": "TiAlN", "hack": "x", "diameter_mm": "6"})
        assert r == {"ok": True, "clean": {"diameter_mm": 6.0, "coating": "TiAlN"}}

    def test_missing_fields_skipped(self):
        assert validate_attributes(SCHEMA, {}) == {"ok": True, "clean": {}}
        assert validate_attributes(SCHEMA, {})["ok"] is True

    def test_non_dict_attrs_treated_as_empty(self):
        assert validate_attributes(SCHEMA, None) == {"ok": True, "clean": {}}
        assert validate_attributes(SCHEMA, "nope") == {"ok": True, "clean": {}}
        assert validate_attributes(SCHEMA, [1, 2]) == {"ok": True, "clean": {}}

    def test_mixed_valid_and_invalid_reports_errors(self):
        r = validate_attributes(SCHEMA, {"diameter_mm": "wide", "coating": "TiAlN"})
        assert r["ok"] is False
        assert "coating" not in r.get("clean", {})
        assert "number" in r["errors"]["diameter_mm"].lower()
