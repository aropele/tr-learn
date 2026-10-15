# /// script
# requires-python = ">=3.11"
# dependencies = []
# ///
from add import slugify, date_part, make_id, ID_RE, MAX_SLUG

def test_stopwords():
    assert slugify("The Case for Index-Fund Investing") == "case-index-fund-investing"
    assert slugify("A  Guide -- of  the   Things") == "guide-things"

def test_apostrophes():
    assert slugify("Vanguard's Principles for Investing Success") == "vanguards-principles-investing-success"

def test_unicode_title():
    assert slugify("Vanguard’s Principles for Investing Success") == "vanguards-principles-investing-success"
    assert slugify("Risk—return in Zürich") == "risk-return-in-zurich"

def test_70_char_cut():
    s = slugify("Vanguard Asset Allocation Model: An investment solution for active, passive, and factor portfolios")
    assert s == "vanguard-asset-allocation-model-investment-solution-active-passive"
    assert len(s) <= MAX_SLUG
    assert len(slugify("x" * 80)) == 70          # single over-long word: hard cut

def test_00_padding():
    assert date_part("2022", "2026-10-15") == "2022-00-00"
    assert date_part("2026-09", "2026-10-15") == "2026-09-00"
    assert date_part("2024-03-05", "2026-10-15") == "2024-03-05"
    assert make_id("Vanguard Capital Markets Model", "2026-09", "2026-10-15") == "2026-09-00-vanguard-capital-markets-model"

def test_null_published_uses_fetch_date():
    assert date_part(None, "2026-10-15") == "2026-10-15"
    assert make_id("Some Page", None, "2026-10-15") == "2026-10-15-some-page"

def test_invalid_input_rejected():
    for bad in ("2026-9", "Sept 2026", "2026-09-1"):
        try: date_part(bad, "2026-10-15"); assert False, bad
        except ValueError: pass
    try: slugify("The of a"); assert False
    except ValueError: pass

def test_ids_match_rule():
    assert ID_RE.match(make_id("Vanguard's Principles", "2022", "2026-10-15"))

if __name__ == "__main__":
    for name, fn in list(globals().items()):
        if name.startswith("test_") and callable(fn):
            fn()
            print(name, "ok")
    print("ok")
