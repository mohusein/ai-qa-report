"""Local test for QAEngine.evaluate_call using a mocked AI client.
Run with: python test_engine.py
"""
import sys
import types

# Provide dummy modules to avoid requiring external SDKs during this local test
deepgram_mod = types.ModuleType("deepgram")
class DummyDeepgramClient:
    def __init__(self, *args, **kwargs):
        pass
def PrerecordedOptions(*args, **kwargs):
    return None
deepgram_mod.DeepgramClient = DummyDeepgramClient
deepgram_mod.PrerecordedOptions = PrerecordedOptions
sys.modules["deepgram"] = deepgram_mod

openai_mod = types.ModuleType("openai")
class OpenAI:
    def __init__(self, *args, **kwargs):
        pass
openai_mod.OpenAI = OpenAI
sys.modules["openai"] = openai_mod

from engine import QAEngine


class DummyResponse:
    def __init__(self, content):
        class Choice:
            def __init__(self, content):
                self.message = type("M", (), {"content": content})

        self.choices = [Choice(content)]


class DummyCompletions:
    @staticmethod
    def create(*args, **kwargs):
        # Simulate model JSON output including agent_name
        content = '{"loan_type":"Mortgage","score":88,"reasoning":"Good call","agent_name":"Test Agent"}'
        return DummyResponse(content)


class DummyChat:
    completions = DummyCompletions()


class DummyAI:
    chat = DummyChat()


def main():
    import engine

    # Monkeypatch the ai_client used by engine
    engine.ai_client = DummyAI()

    qe = QAEngine()
    result = qe.evaluate_call(
        "Agent: Hello, I'm Test Agent. This call is about a mortgage.",
        {"duration": 120, "hangup": "Customer", "transfer_ext": None},
    )

    print("Evaluation result:")
    print(result)


if __name__ == "__main__":
    main()
