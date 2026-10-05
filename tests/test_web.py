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


def test_searching_screen_draws_veins_and_is_hidden_until_a_lookup_starts():
    html = web.home().decode()
    assert html.count('class="vn"') == 10 and 'pathLength="1"' in html
    assert 'id="searching" role="status"' in html and 'aria-hidden="true"' in html  # not shown on load
    assert 'class=on' in web.searching_overlay(on=True) and "spinring" not in html


def test_loading_preview_theme_switch_sets_the_theme_attribute():
    from civic.web import page, searching_overlay

    shown = page("x", searching_overlay(on=True)).decode()
    assert 'id="searching" class=on' in shown
