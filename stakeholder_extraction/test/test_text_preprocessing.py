from stakeholder_extraction import stakeholdertext_processing as processing

def test_prepare_stakeholder_text(monkeypatch):

    # Mocking the prepared stakeholder text and the StakeholderView result to reduce the OpenAI API calls.
    def mock_correct_language(
            stakeholder: str,
            source_text: str,
    ) -> str:
        assert stakeholder == "Customer Service"
        assert source_text == "I recieved a complain."

        return "I received a complaint."

    def mock_normalize_process_text(
            stakeholder: str,
            corrected_text: str,
    ) -> str:
        assert stakeholder == "Customer Service"
        assert corrected_text == "I received a complaint."

        return "Customer Service receives a complaint."

    # Making sure to return the mocked results when the functions are called.
    monkeypatch.setattr(processing, "correct_language", mock_correct_language,)
    monkeypatch.setattr(processing, "normalize_process_text", mock_normalize_process_text,)

    # Tested function.
    corrected_text, prepared_text = (
        processing.prepare_stakeholder_text(
            stakeholder="Customer Service",
            source_text="I recieved a complain.", )
    )

    # Assertions.
    assert corrected_text == "I received a complaint."
    assert (
        prepared_text == "Customer Service receives a complaint."
    )
