"""The decision page is generated from the committed result tables; these tests check it builds and carries no template leftovers."""
import re

import pandas as pd

import build_site


def test_page_builds_from_result_tables(tmp_path):
    out = tmp_path / "index.html"
    build_site.build(out)
    html = out.read_text()
    assert "<title>" in html and "const DATA" in html
    visible = html.split("<body>")[1].split("<script>")[0]
    for bad in ("nan", "None", "undefined", "{{", "}}"):
        assert not re.search(r"(?<![A-Za-z])" + re.escape(bad) + r"(?![A-Za-z])", visible), bad


def test_page_numbers_come_from_the_tables(tmp_path):
    out = tmp_path / "index.html"
    build_site.build(out)
    html = out.read_text()
    pareto = pd.read_csv(build_site.TABLES / "r10_slow_request_pareto.csv")
    assert f"{int(pareto.slow_requests.sum()):,}" in html
    drivers = pd.read_csv(build_site.TABLES / "r14_slow_drivers.csv").set_index("predictors")
    assert f"{drivers.loc['Complaint type', 'pct_of_variation_explained']:.0f}%" in html
