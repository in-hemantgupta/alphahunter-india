def max_drawdown(equity_curve):

    peak = equity_curve[0]

    dd = 0

    for value in equity_curve:

        if value > peak:

            peak = value

        drawdown = (peak - value) / peak

        dd = max(dd, drawdown)

    return dd
