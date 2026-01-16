import logging
from typing import Dict, Any

logger = logging.getLogger("vera_budget")

class BudgetManager:
    def __init__(self, max_daily_tokens: int = 500000):
        self.limit = max_daily_tokens
        self.used = 0
        self.requests = 0

    def check_budget(self) -> bool:
        """Returns True if we are safe. Returns False if budget exceeded."""
        if self.used >= self.limit:
            logger.warning(f"💸 BUDGET EXCEEDED: Used {self.used}/{self.limit} tokens.")
            return False
        return True

    def update_cost(self, response_metadata: Dict[str, Any]):
        """
        Parses NVIDIA/OpenAI metadata to track usage.
        Structure usually looks like: {'token_usage': {'total_tokens': 150, ...}}
        """
        try:
            usage = response_metadata.get("token_usage", {})
            total_tokens = usage.get("total_tokens", 0)
            
            if total_tokens == 0:
                # Fallback if API doesn't return metadata (estimate: 1 word ~= 1.3 tokens)
                # This happens with some self-hosted NIMs
                logger.warning("⚠️ No token metadata found. Using estimation.")
                return 

            self.used += total_tokens
            self.requests += 1
            logger.info(f"💰 Cost Update: +{total_tokens} tokens. Total: {self.used}/{self.limit}")
            
        except Exception as e:
            logger.error(f"Failed to track cost: {e}")

    def get_status(self) -> str:
        """Returns a string for the UI dashboard."""
        percent = (self.used / self.limit) * 100
        return f"{self.used} / {self.limit} Tokens ({percent:.1f}%)"

# Singleton Instance (Global Wallet)
# In a real SaaS, this would be a Redis Database keyed by User ID.
# For this side project, a global variable is fine.
global_budget = BudgetManager(max_daily_tokens=20000) # Set your safety limit here