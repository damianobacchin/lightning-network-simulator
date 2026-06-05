# Submarine swap fee model

swap_fee_rate = 1000  # off-chain swap-provider fee, ppm of the swapped amount
swap_fee_base = 0  # off-chain swap-provider fee, fixed sats per swap

sats_per_vbyte = 10  # on-chain feerate, sats / vbyte
swap_vbytes = 200  # size of the on-chain swap funding tx, vbytes

min_swap_amount = 5000  # skip swaps at or below this size, sats
