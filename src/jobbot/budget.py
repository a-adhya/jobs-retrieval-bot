from __future__ import annotations

from dataclasses import dataclass

from jobbot.errors import BudgetExceeded


@dataclass
class Budget:
    """Per-run caps. Every AI call and every paid API lookup must go through this object."""

    llm_limit_usd: float
    paid_lookup_limit: int
    llm_spent_usd: float = 0.0
    paid_lookups_used: int = 0

    def charge_llm(self, usd: float) -> None:
        self.llm_spent_usd += usd
        if self.llm_spent_usd > self.llm_limit_usd:
            raise BudgetExceeded(
                f"AI spend ${self.llm_spent_usd:.4f} is over this run's cap of ${self.llm_limit_usd:.2f}"
            )

    def take_paid_lookup(self) -> None:
        if self.paid_lookups_used >= self.paid_lookup_limit:
            raise BudgetExceeded(f"Paid lookup cap of {self.paid_lookup_limit} reached for this run")
        self.paid_lookups_used += 1
