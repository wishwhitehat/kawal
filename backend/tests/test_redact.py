from app.redact import extract_indicators, extract_urls, indicator_from_model, normalise_phone, redact_text


def test_malaysian_mobile_is_normalised_with_country_code():
    assert normalise_phone("012-345 6789", "MY") == "60123456789"
    assert normalise_phone("+65 8123 4567", "MY") == "6581234567"


def test_extracts_phone_domain_and_masks_them():
    inds = extract_indicators("WhatsApp +60 11-2345 6789 or visit https://lhdn-refund-claim.xyz/semak", "MY")
    kinds = {i.kind: i for i in inds}
    assert kinds["domain"].value == "lhdn-refund-claim.xyz"
    assert kinds["phone"].value == "601123456789"
    assert "*" in kinds["phone"].masked and kinds["phone"].masked.endswith("89")


def test_bank_account_is_masked_to_last_four():
    inds = extract_indicators("Transfer to account 7612 3398 1021 today", "MY")
    acct = next(i for i in inds if i.kind == "account")
    assert acct.masked == "acct ****1021"


def test_fingerprint_is_keyed_and_stable():
    ind = extract_indicators("+60 11-2345 6789", "MY")[0]
    assert ind.fingerprint("pepper-a") == ind.fingerprint("pepper-a")
    assert ind.fingerprint("pepper-a") != ind.fingerprint("pepper-b")
    assert "6789" not in ind.fingerprint("pepper-a")


def test_redact_text_removes_contact_details():
    out = redact_text("Call 017-889 2214, email scam@evil.com, pay at poslaju-redeliver.top/pay")
    assert "889" not in out and "scam@evil.com" not in out
    assert "[LINK:poslaju-redeliver.top]" in out


def test_extract_urls_adds_scheme():
    assert extract_urls("go to sf-redelivery-my.top now.") == ["http://sf-redelivery-my.top"]


def test_indicator_from_model_handles_urls_and_phones():
    assert indicator_from_model("url", "https://www.dbs-sg-verify.com/login").value == "dbs-sg-verify.com"
    assert indicator_from_model("phone", "+65 8123 4567").kind == "phone"
    assert indicator_from_model("phone", "") is None
