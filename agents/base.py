from utils.llm import complete, is_live


class BaseAgent:
    name = "Agent"
    system_prompt = ""

    def _ask(self, user_prompt: str, max_tokens: int = 800):
        """Returns (narrative_or_None, is_live_bool)."""
        reply = complete(self.system_prompt, user_prompt, max_tokens=max_tokens)
        return reply, is_live()
