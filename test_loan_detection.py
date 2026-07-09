"""Quick local checks for deterministic loan-type detection."""
from engine import QAEngine
from file_parser import parse_filename


def check(text, expected, metadata=None):
    engine = QAEngine()
    result = engine.detect_loan_type(text, metadata or {})
    actual = result["loan_type"]
    print(f"{expected:8} -> {actual:8} | {result}")
    assert actual == expected


if __name__ == "__main__":
    check(
        "Customer is a veteran asking about a VA mortgage and military benefits.",
        "VA",
    )
    check(
        "Caller needs help with credit card debt consolidation and settlement.",
        "Debt",
    )
    check(
        "Customer wants to refinance their home loan and asks about mortgage rates.",
        "Mortgage",
    )
    check(
        "General greeting with no loan details.",
        "Unknown",
    )
    check(
        "The call is vague.",
        "Debt",
        {"transfer_ext": "Debt_Relief"},
    )

    filename = "20260615-120636_2012298_7576049254_VA_V6151206220002012298_tpenninger-all.mp3"
    parsed = parse_filename(filename)
    assert parsed["loan_hint"] == "VA"
    check("The transcript never says the loan type out loud.", "VA", parsed)
