from __future__ import annotations
from dataclasses import dataclass, field
from typing import Optional, List, Dict, Any

@dataclass
class PipelineContext:
    """
    Context object passed to process() functions of stages and analysis scripts.
    """
    contract_id: str
    next_contract_id: Optional[str] = None
    extra_args: Dict[str, Any] = field(default_factory=dict)
