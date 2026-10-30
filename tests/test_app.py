from streamlit.testing.v1 import AppTest


def test_app_loads_with_request_form():
    at = AppTest.from_file("../app.py", default_timeout=30).run()
    assert not at.exception
    assert [t.label for t in at.tabs] == ["Request", "Status", "Review"]
    assert at.selectbox[0].label == "Department" and "Sales" in at.selectbox[0].options
    assert at.text_area[0].label == "What do you need?"
    assert at.number_input[0].label == "Budget (SAR)"
