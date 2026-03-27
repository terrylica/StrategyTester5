
def PeriodSeconds(period: int) -> int:
    """
    Convert MT5 timeframe to seconds.
    Correctly decodes MetaTrader 5 bit flags.
    """

    # Months (0xC000)
    if (period & 0xC000) == 0xC000:
        value = period & 0x3FFF
        return value * 30 * 24 * 3600

    # Weeks (0x8000)
    if (period & 0x8000) == 0x8000:
        value = period & 0x7FFF
        return value * 7 * 24 * 3600

    # Hours / Days (0x4000)
    if (period & 0x4000) == 0x4000:
        value = period & 0x3FFF
        return value * 3600

    # Minutes
    return period * 60