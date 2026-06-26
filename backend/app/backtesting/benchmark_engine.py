def get_benchmark_returns(benchmark, start, end):

    return get_price(benchmark, end) / get_price(benchmark, start) - 1
