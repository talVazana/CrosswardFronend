from app import special_users


def test_special_users_are_registered_by_email():
    assert special_users.SPECIAL_USERS == {
        "tal.vazanas@gmail.com": "god",
        "shachar383838@gmail.com": "admin",
    }


def test_god_email_resolves_to_god_role():
    assert special_users.website_role_for_email("tal.vazanas@gmail.com") == "god"
    assert special_users.is_god("tal.vazanas@gmail.com") is True
    assert special_users.has_game_admin_role("tal.vazanas@gmail.com") is False


def test_admin_email_resolves_to_admin_role():
    assert (
        special_users.website_role_for_email("shachar383838@gmail.com") == "admin"
    )
    assert special_users.has_game_admin_role("shachar383838@gmail.com") is True
    assert special_users.is_god("shachar383838@gmail.com") is False


def test_email_matching_is_case_and_space_insensitive():
    assert special_users.website_role_for_email("  Tal.Vazanas@Gmail.com ") == "god"
    assert (
        special_users.website_role_for_email(" SHACHAR383838@gmail.com ") == "admin"
    )


def test_unknown_emails_have_no_role():
    assert special_users.website_role_for_email("someone@example.com") is None
    assert special_users.website_role_for_email("") is None
    assert special_users.website_role_for_email(None) is None
    assert special_users.is_god("someone@example.com") is False
    assert special_users.has_game_admin_role("someone@example.com") is False
