def create_label(stock_return, benchmark_return):
    alpha = stock_return - benchmark_return
    if alpha > 100:
        return 1
    return 0
