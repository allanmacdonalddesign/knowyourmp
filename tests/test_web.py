from civic import web


def test_home_escapes_user_input():
    html = web.home("<script>x</script>", '"><img src=x>').decode()
    assert "<script>x</script>" not in html and '"><img' not in html


def test_home_has_only_the_postal_code_step():
    html = web.home().decode()
    text = html.split("</style>")[1].lower()  # visible page, not the CSS
    assert 'action="/mp"' in html and "meet" in text
    assert "opportunit" not in text and "draft" not in text and "petition" not in text


def test_no_third_party_resources_are_loaded():
    html = web.home().decode()
    assert "googleapis" not in html and "<script src" not in html and "@import" not in html
