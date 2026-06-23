from pydantic import BaseModel


class ConfigSchema(BaseModel):
    balance_ratio: float


config = ConfigSchema(balance_ratio=0.5)
