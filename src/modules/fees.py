def calculate_fee(fee_base: int, fee_rate: int, amount: int) -> int:
    return fee_base + round(fee_rate * amount / 1_000_000)
