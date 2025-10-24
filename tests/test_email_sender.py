import pytest
import logging
from unittest.mock import MagicMock
from azure.core.exceptions import HttpResponseError
from azfunc.helpers import email_sender


#================================= Test format_text_for_html() =================================

@pytest.mark.parametrize("text, expected, use_substring", [
    ("", "No description provided.", False),                            # no text provided
    ("8 < 10 & 10 > 8", "8 &lt; 10 &amp; 10 &gt; 8", False),            # escape unsafe characters
    ("ok\n\nok", "ok</p><p>ok", False),                                 # replace double newlines
    ("ok\nok", "ok<br/>ok", False),                                     # replace single newlines
    ("Danger: 5 < 10 & 20 > 15\n\nLine2\nLine3",
     ["5 &lt; 10 &amp; 20 &gt; 15", "</p><p>Line2<br/>Line3"],          # mixed case: escaping + newlines
     True)
])
def test_format_text_for_html(text, expected, use_substring):

    result = email_sender.format_text_for_html(text)

    # Assertions
    if not use_substring:
        assert result == expected                                       # exact match for simple cases
    else:
        for substring in expected:
            assert substring in result                                  # check all substrings appear in the result


#================================= Test format_email() =================================
'''
Successful case also includes unsafe characters in the description and instruction fields
so it shows that they get escaped and newlines get replaced by format_text_for_html()
'''

@pytest.mark.parametrize("alert, expected_subject, plain_snippets, html_snippets", [
    # successful case
    ({                                                                  # alert
        "user_id": "user1",
        "email": "user1@example.com",
        "alert_id": "123",
        "zone_id": "FLC127",
        "areaDesc": "Lake, FL; Volusia, FL",
        "created_at": "2025-10-22T00:00:00Z",
        "effective_at": "2025-10-22T00:00:00Z",
        "severity": "Severe",
        "certainty": "Likely",
        "urgency": "Immediate",
        "event": "Flood Warning",
        "senderName": "NWS Melbourne FL",
        "headline": "Flood Warning in Effect",
        "description": "* WHAT...Minor flooding is occurring and minor flooding is forecast.\n\n"
                       "* WHERE...St Johns River near Astor.\n\n* WHEN...Until further notice.",
        "instruction": "Stay tuned to further developments by listening to your local radio & television,\n or "
                       "NOAA Weather Radio for further information.",
        "response": "Avoid",
        "link": "http://www.weather.gov"
    },
    "Weather Alert: Flood Warning",                                     # expected_subject
    ["Area: Lake, FL; Volusia, FL",                                     # plain_snippets
     "Severity: Severe | Certainty: Likely | Urgency: Immediate",
     "Headline: Flood Warning in Effect"],
    ["<h3>Headline</h3>",                                               # html_snippets
     "<p><strong>Area:</strong> Lake, FL; Volusia, FL</p>",
     "<p>* WHAT...Minor flooding is occurring and minor flooding is forecast.</p><p>* WHERE...St Johns "
     "River near Astor.</p><p>* WHEN...Until further notice.</p>",
     "<p>Stay tuned to further developments by listening to your local radio &amp; television,<br/> or "
     "NOAA Weather Radio for further information.</p>"]),
    # empty case
    ({},                                                                # alert
     "Weather Alert: Unknown Event",                                    # expected_subject
    ["Area: Unknown area",                                              # plain_snippets
     "Severity: N/A | Certainty: N/A | Urgency: N/A",
     "Headline: No headline provided.",
     "Description: No description provided."],
    ["<h3>Headline</h3>",                                               # html_snippets
     "<p>No instructions provided. Stay alert and follow official guidance.</p>",
     "<p><a href='#'>More Information</a></p>"]),
])
def test_format_email(alert, expected_subject, plain_snippets, html_snippets):

    subject, plain_body, html_body = email_sender.format_email(alert)

    # Assertions
    assert subject == expected_subject
    for snippet in plain_snippets:
        assert snippet in plain_body
    for snippet in html_snippets:
        assert snippet in html_body


#================================= Test send_email_via_acs() =================================

@pytest.mark.parametrize("side_effect, expected_log, log_level", [
    # Successful case where everything works like it's supposed to
    (None, "ACS email send status: Succeeded", logging.INFO),
    # Case where HttpResponseError is raised
    (HttpResponseError("Service down"), "ACS error:", logging.ERROR),
    # Case where a generic Exception is raised
    (Exception("general exception"), "Unexpected error: general exception", logging.ERROR)
])
def test_send_email_via_acs_(monkeypatch, caplog, side_effect, expected_log, log_level):

    mock_poller = MagicMock()
    mock_poller.result.return_value = {"status": "Succeeded"}

    mock_client = MagicMock()
    if not side_effect:
        mock_client.begin_send.return_value = mock_poller
    else:
        mock_client.begin_send.side_effect = side_effect

    monkeypatch.setattr(email_sender, "email_client", mock_client)

    with caplog.at_level(log_level):
        email_sender.send_email_via_acs("user@example.com", "Subject",
                                        "Plain email", "<p>HTML email</p>")

    # Assertions
    mock_client.begin_send.assert_called_once()
    if not side_effect:
        args, kwargs = mock_client.begin_send.call_args
        message = args[0]
        assert message["recipients"]["to"][0]["address"] == "user@example.com"
        assert message["content"]["subject"] == "Subject"
        assert message["content"]["plainText"] == "Plain email"
        assert message["content"]["html"] == "<p>HTML email</p>"
    assert expected_log in caplog.text
