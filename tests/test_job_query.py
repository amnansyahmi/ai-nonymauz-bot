from handlers.jobs import build_job_query


def test_title_only():
    assert build_job_query("software engineer") == "software engineer"


def test_title_and_location():
    assert build_job_query("data analyst", "Selangor") == "data analyst in Selangor"


def test_all_fields():
    assert build_job_query("nurse", "Johor", "3000") == "nurse in Johor salary 3000"


def test_blank_optional_fields_ignored():
    assert build_job_query("chef", "", "") == "chef"
    assert build_job_query("chef", "  ", "  ") == "chef"
