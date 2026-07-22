from circleback.pipeline.text_utils import strip_quoted_content


def test_strip_standard_quotes():
    text = "Sounds good to me.\n> I'll send it by Friday.\n> Thanks!"
    assert strip_quoted_content(text) == "Sounds good to me."

def test_strip_on_wrote():
    text = "I will handle this.\n\nOn Oct 14, 2025, at 10:00 AM, John Doe wrote:\nI need the report by Friday."
    assert strip_quoted_content(text) == "I will handle this."

def test_strip_forwarded_message():
    text = "FYI, see below.\n---------- Forwarded message ---------\nFrom: Sarah\nDate: Mon\nI'll get this done."
    assert strip_quoted_content(text) == "FYI, see below."

def test_strip_from_block():
    text = "Got it.\n\nFrom: Alice\nDate: Tuesday\nSubject: Update\nTo: Bob\nHere is the thing."
    assert strip_quoted_content(text) == "Got it."

def test_no_quotes():
    text = "Just a normal email without quotes."
    assert strip_quoted_content(text) == text

def test_empty_string():
    assert strip_quoted_content("") == ""
