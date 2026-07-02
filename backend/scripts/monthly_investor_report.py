"""Monthly Investor Report — auto-generated PDF for stakeholders."""
import sys, os, json, io, textwrap
from datetime import date, timedelta
from collections import defaultdict

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
os.environ['DISABLE_BAYESIAN'] = '1'

import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import matplotlib.dates as mdates

from app.db.database import SessionLocal
from app.models.portfolio_metrics import PortfolioMetrics
from app.models.portfolio_position import PortfolioPosition
from app.models.rebalance_history import RebalanceHistory
from app.models.stock import Stock
from sqlalchemy import text

REPORT_DIR = os.path.join(os.path.dirname(__file__), '..', 'reports')


def _query_metrics(session, months=3):
    cutoff = date.today() - timedelta(days=months * 31)
    rows = session.query(PortfolioMetrics).filter(
        PortfolioMetrics.date >= cutoff
    ).order_by(PortfolioMetrics.date).all()
    return rows


def _query_positions(session, as_of):
    rows = session.query(PortfolioPosition).filter(
        PortfolioPosition.date == as_of
    ).all()
    return rows


def _query_rebalances(session, months=3):
    cutoff = date.today() - timedelta(days=months * 31)
    rows = session.query(RebalanceHistory).filter(
        RebalanceHistory.date >= cutoff
    ).order_by(RebalanceHistory.date).all()
    return rows


def _query_sector_map(session):
    stock_map = {}
    for s in session.query(Stock).all():
        stock_map[s.symbol] = s.sector or "Unknown"
    return stock_map


def _get_fiscal_month(d):
    return f"{d.year}-{d.month:02d}"


def _compute_monthly_returns(metrics):
    monthly = defaultdict(list)
    for m in metrics:
        if m.daily_return is not None:
            monthly[_get_fiscal_month(m.date)].append(m.daily_return)
    result = {}
    for month, rets in monthly.items():
        result[month] = float(np.prod([1 + r for r in rets]) - 1)
    return result


def _compute_monthly_benchmark(metrics):
    monthly = defaultdict(list)
    for m in metrics:
        if m.benchmark_return is not None:
            monthly[_get_fiscal_month(m.date)].append(m.benchmark_return)
    result = {}
    for month, rets in monthly.items():
        result[month] = float(np.prod([1 + r for r in rets]) - 1)
    return result


def _top_contributors(positions, sector_map, n=5):
    sorted_pos = sorted(positions, key=lambda p: (p.pnl_pct or 0) * (p.allocation or 0), reverse=True)
    return [
        {"symbol": p.symbol, "sector": sector_map.get(p.symbol, "Unknown"),
         "pnl_pct": round(p.pnl_pct or 0, 2), "weight": round((p.allocation or 0) * 100, 1)}
        for p in sorted_pos[:n]
    ]


def _worst_performers(positions, sector_map, n=5):
    sorted_pos = sorted(positions, key=lambda p: (p.pnl_pct or 0) * (p.allocation or 0))
    return [
        {"symbol": p.symbol, "sector": sector_map.get(p.symbol, "Unknown"),
         "pnl_pct": round(p.pnl_pct or 0, 2), "weight": round((p.allocation or 0) * 100, 1)}
        for p in sorted_pos[:n]
    ]


def _sector_exposure(positions, sector_map):
    sectors = defaultdict(float)
    for p in positions:
        sec = sector_map.get(p.symbol, "Unknown")
        sectors[sec] += p.allocation or 0
    return {s: round(w * 100, 1) for s, w in sorted(sectors.items(), key=lambda x: -x[1])}


def _generate_nav_chart(metrics, path):
    dates = [m.date for m in metrics]
    navs = [m.nav for m in metrics if m.nav is not None]
    ben = [m.benchmark_nav for m in metrics if m.benchmark_nav is not None]

    fig, ax = plt.subplots(figsize=(10, 4))
    if navs:
        norm_nav = [n / navs[0] * 100 for n in navs]
        ax.plot(dates[:len(norm_nav)], norm_nav, label='Portfolio', linewidth=2, color='#1f77b4')
    if ben:
        norm_ben = [b / ben[0] * 100 for b in ben]
        ax.plot(dates[:len(norm_ben)], norm_ben, label='Nifty 50', linewidth=2, color='#ff7f0e', linestyle='--')
    ax.set_ylabel('Normalized NAV (Base=100)')
    ax.set_title('NAV Growth')
    ax.legend(loc='upper left')
    ax.grid(True, alpha=0.3)
    ax.xaxis.set_major_formatter(mdates.DateFormatter('%b %d'))
    fig.tight_layout()
    fig.savefig(path, dpi=150, bbox_inches='tight')
    plt.close(fig)


def _generate_monthly_returns_chart(monthly_returns, monthly_benchmark, path):
    months = sorted(set(list(monthly_returns.keys()) + list(monthly_benchmark.keys())))
    if not months:
        return
    x = np.arange(len(months))
    w = 0.35

    fig, ax = plt.subplots(figsize=(10, 4))
    p_vals = [monthly_returns.get(m, 0) * 100 for m in months]
    b_vals = [monthly_benchmark.get(m, 0) * 100 for m in months]
    ax.bar(x - w / 2, p_vals, w, label='Portfolio', color='#1f77b4')
    ax.bar(x + w / 2, b_vals, w, label='Nifty 50', color='#ff7f0e')
    ax.axhline(y=0, color='black', linewidth=0.5)
    ax.set_ylabel('Return %')
    ax.set_title('Monthly Returns')
    ax.set_xticks(x)
    ax.set_xticklabels(months, rotation=45, ha='right')
    ax.legend()
    ax.grid(True, alpha=0.3)
    fig.tight_layout()
    fig.savefig(path, dpi=150, bbox_inches='tight')
    plt.close(fig)


def _generate_sector_chart(exposure, path):
    labels = list(exposure.keys())
    values = list(exposure.values())
    if not labels:
        return
    fig, ax = plt.subplots(figsize=(8, 5))
    colors = plt.cm.Set3(np.linspace(0, 1, len(labels)))
    wedges, texts, autotexts = ax.pie(
        values, labels=None, autopct='%1.1f%%', colors=colors,
        startangle=90, pctdistance=0.85
    )
    ax.set_title('Sector Exposure')
    ax.axis('equal')
    if labels:
        ax.legend(wedges, [f"{l} ({v}%)" for l, v in zip(labels, values)],
                  loc='center left', bbox_to_anchor=(1, 0.5), fontsize=8)
    fig.tight_layout()
    fig.savefig(path, dpi=150, bbox_inches='tight')
    plt.close(fig)


def _generate_drawdown_chart(metrics, path):
    dates = [m.date for m in metrics]
    navs = [m.nav for m in metrics if m.nav is not None]
    if len(navs) < 5:
        return
    peak = np.maximum.accumulate(navs)
    dd = [(p - n) / p * 100 for p, n in zip(peak, navs)]
    fig, ax = plt.subplots(figsize=(10, 3))
    ax.fill_between(dates[:len(dd)], dd, 0, color='#d62728', alpha=0.5)
    ax.set_ylabel('Drawdown %')
    ax.set_title('Portfolio Drawdown')
    ax.grid(True, alpha=0.3)
    ax.xaxis.set_major_formatter(mdates.DateFormatter('%b %d'))
    fig.tight_layout()
    fig.savefig(path, dpi=150, bbox_inches='tight')
    plt.close(fig)


def _compute_metrics_summary(metrics):
    if not metrics:
        return {}
    returns = [m.daily_return for m in metrics if m.daily_return is not None]
    bench_returns = [m.benchmark_return for m in metrics if m.benchmark_return is not None]
    navs = [m.nav for m in metrics if m.nav is not None]
    alphas = [m.alpha for m in metrics if m.alpha is not None]

    total_return = float(np.prod([1 + r for r in returns]) - 1) if returns else 0
    bench_return = float(np.prod([1 + r for r in bench_returns]) - 1) if bench_returns else 0
    alpha = total_return - bench_return
    volatility = float(np.std(returns) * np.sqrt(252) * 100) if len(returns) > 5 else 0
    sharpe = float(np.mean(returns) / max(np.std(returns), 1e-9) * np.sqrt(252)) if len(returns) > 5 else 0
    peak = max(navs) if navs else 1
    current = navs[-1] if navs else 1
    drawdown = (peak - current) / peak * 100

    return {
        "total_return_pct": round(total_return * 100, 2),
        "benchmark_return_pct": round(bench_return * 100, 2),
        "alpha_pct": round(alpha * 100, 2),
        "volatility_annual_pct": round(volatility, 2),
        "sharpe_ratio": round(sharpe, 2),
        "current_drawdown_pct": round(drawdown, 2),
        "n_trading_days": len(returns),
        "positive_days_pct": round(sum(1 for r in returns if r > 0) / len(returns) * 100, 1) if returns else 0,
    }


def _generate_strategy_commentary(summary, monthly_returns):
    parts = []
    if summary.get("alpha_pct", 0) > 0:
        parts.append(f"The portfolio generated +{summary['alpha_pct']}% alpha over the period.")
    else:
        parts.append(f"The portfolio underperformed the benchmark by {abs(summary['alpha_pct'])}% over the period.")
    if summary.get("sharpe_ratio", 0) > 1:
        parts.append(f"A Sharpe ratio of {summary['sharpe_ratio']} indicates strong risk-adjusted returns.")
    elif summary.get("sharpe_ratio", 0) > 0:
        parts.append(f"A Sharpe ratio of {summary['sharpe_ratio']} indicates marginal positive risk-adjusted returns.")
    else:
        parts.append("Risk-adjusted returns need improvement.")
    if summary.get("volatility_annual_pct", 0) > 25:
        parts.append(f"Portfolio volatility at {summary['volatility_annual_pct']}% is elevated.")
    else:
        parts.append(f"Portfolio volatility at {summary['volatility_annual_pct']}% is within acceptable range.")
    best_month = max(monthly_returns, key=monthly_returns.get) if monthly_returns else None
    worst_month = min(monthly_returns, key=monthly_returns.get) if monthly_returns else None
    if best_month:
        parts.append(f"Best month: {best_month} ({monthly_returns[best_month]*100:+.2f}%).")
    if worst_month:
        parts.append(f"Worst month: {worst_month} ({monthly_returns[worst_month]*100:+.2f}%).")
    return " ".join(parts)


def generate_report(months_back=3, output_path=None):
    os.makedirs(REPORT_DIR, exist_ok=True)
    session = SessionLocal()
    try:
        metrics = _query_metrics(session, months_back)
        if not metrics:
            print("No metrics data found for report period.")
            return None
        today = date.today()
        positions = _query_positions(session, today)
        sector_map = _query_sector_map(session)
        rebalances = _query_rebalances(session, months_back)

        monthly_returns = _compute_monthly_returns(metrics)
        monthly_benchmark = _compute_monthly_benchmark(metrics)
        exposure = _sector_exposure(positions, sector_map)
        top = _top_contributors(positions, sector_map)
        worst = _worst_performers(positions, sector_map)
        summary = _compute_metrics_summary(metrics)
        commentary = _generate_strategy_commentary(summary, monthly_returns)

        chart_dir = os.path.join(REPORT_DIR, "charts")
        os.makedirs(chart_dir, exist_ok=True)
        nav_chart = os.path.join(chart_dir, "nav.png")
        monthly_chart = os.path.join(chart_dir, "monthly_returns.png")
        sector_chart = os.path.join(chart_dir, "sector_exposure.png")
        dd_chart = os.path.join(chart_dir, "drawdown.png")
        _generate_nav_chart(metrics, nav_chart)
        _generate_monthly_returns_chart(monthly_returns, monthly_benchmark, monthly_chart)
        _generate_sector_chart(exposure, sector_chart)
        _generate_drawdown_chart(metrics, dd_chart)

        from fitz import open as pdf_open
        pdf_path = output_path or os.path.join(REPORT_DIR, f"investor_report_{today.strftime('%Y_%m')}.pdf")
        doc = pdf_open()
        page_width, page_height = 595, 842
        margin = 50

        def add_page():
            return doc.new_page(width=page_width, height=page_height)

        def insert_text(page, text, x, y, size=10, bold=False, color=(0, 0, 0)):
            fontname = "helv" if not bold else "helv"
            page.insert_text((x, y), text, fontsize=size, color=color,
                             fontname=fontname)

        def insert_image(page, img_path, x, y, width):
            if os.path.exists(img_path):
                page.insert_image((x, y - 200, x + width, y), filename=img_path)

        page = add_page()
        insert_text(page, "ALPHAHUNTER — MONTHLY INVESTOR REPORT", margin, 60, size=20, bold=True, color=(0.12, 0.36, 0.62))
        insert_text(page, f"Report Date: {today.strftime('%B %d, %Y')}", margin, 85, size=11)
        insert_text(page, f"Period: {(today - timedelta(days=months_back*31)).strftime('%b %d')} — {today.strftime('%b %d, %Y')}", margin, 102, size=10)
        insert_text(page, "─" * 80, margin, 115, size=8)

        y = 140
        insert_text(page, "PERFORMANCE SUMMARY", margin, y, size=14, bold=True, color=(0.12, 0.36, 0.62))
        y += 25
        items = [
            f"Total Return:       {summary.get('total_return_pct', 0):+.2f}%",
            f"Benchmark Return:   {summary.get('benchmark_return_pct', 0):+.2f}%",
            f"Alpha:              {summary.get('alpha_pct', 0):+.2f}%",
            f"Sharpe Ratio:       {summary.get('sharpe_ratio', 0):.2f}",
            f"Volatility (ann):   {summary.get('volatility_annual_pct', 0):.2f}%",
            f"Drawdown:           {summary.get('current_drawdown_pct', 0):.2f}%",
            f"Positive Days:      {summary.get('positive_days_pct', 0):.1f}%",
            f"Trading Days:       {summary.get('n_trading_days', 0)}",
        ]
        for item in items:
            insert_text(page, item, margin + 20, y, size=10)
            y += 16

        y += 10
        insert_text(page, "STRATEGY COMMENTARY", margin, y, size=14, bold=True, color=(0.12, 0.36, 0.62))
        y += 20
        wrapped = textwrap.wrap(commentary, width=90)
        for line in wrapped:
            insert_text(page, line, margin + 10, y, size=9)
            y += 14

        page = add_page()
        insert_text(page, "NAV GROWTH CHART", margin, 60, size=14, bold=True, color=(0.12, 0.36, 0.62))
        if os.path.exists(nav_chart):
            insert_image(page, nav_chart, margin, 260, page_width - 2 * margin)

        insert_text(page, "DRAWDOWN CHART", margin, 280, size=14, bold=True, color=(0.12, 0.36, 0.62))
        if os.path.exists(dd_chart):
            insert_image(page, dd_chart, margin, 480, page_width - 2 * margin)

        page = add_page()
        insert_text(page, "MONTHLY RETURNS", margin, 60, size=14, bold=True, color=(0.12, 0.36, 0.62))
        if os.path.exists(monthly_chart):
            insert_image(page, monthly_chart, margin, 260, page_width - 2 * margin)

        insert_text(page, "SECTOR EXPOSURE", margin, 280, size=14, bold=True, color=(0.12, 0.36, 0.62))
        if os.path.exists(sector_chart):
            insert_image(page, sector_chart, margin + 60, 520, 300)

        page = add_page()
        insert_text(page, "TOP CONTRIBUTORS", margin, 60, size=14, bold=True, color=(0.12, 0.36, 0.62))
        y = 85
        headers = ["Symbol", "Sector", "PnL%", "Wt%"]
        col_x = [margin, margin + 100, margin + 220, margin + 290]
        for i, h in enumerate(headers):
            insert_text(page, h, col_x[i], y, size=10, bold=True)
        y += 18
        for t in top:
            insert_text(page, t["symbol"], col_x[0], y, size=9)
            insert_text(page, t["sector"], col_x[1], y, size=9)
            insert_text(page, f"{t['pnl_pct']:+.2f}", col_x[2], y, size=9)
            insert_text(page, f"{t['weight']:.1f}", col_x[3], y, size=9)
            y += 14

        y += 20
        insert_text(page, "WORST PERFORMERS", margin, y, size=14, bold=True, color=(0.12, 0.36, 0.62))
        y += 25
        for i, h in enumerate(headers):
            insert_text(page, h, col_x[i], y, size=10, bold=True)
        y += 18
        for w in worst:
            insert_text(page, w["symbol"], col_x[0], y, size=9)
            insert_text(page, w["sector"], col_x[1], y, size=9)
            insert_text(page, f"{w['pnl_pct']:+.2f}", col_x[2], y, size=9)
            insert_text(page, f"{w['weight']:.1f}", col_x[3], y, size=9)
            y += 14

        y = max(y + 40, 500)
        insert_text(page, "SECTOR EXPOSURE DETAIL", margin, y, size=14, bold=True, color=(0.12, 0.36, 0.62))
        y += 25
        sec_headers = ["Sector", "Weight %"]
        sec_x = [margin, margin + 150]
        for i, h in enumerate(sec_headers):
            insert_text(page, h, sec_x[i], y, size=10, bold=True)
        y += 18
        for sec, wt in sorted(exposure.items(), key=lambda x: -x[1]):
            insert_text(page, sec, sec_x[0], y, size=9)
            insert_text(page, f"{wt:.1f}%", sec_x[1], y, size=9)
            y += 14

        doc.save(pdf_path)
        print(f"Report saved to {pdf_path}")
        return pdf_path
    finally:
        session.close()


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Generate monthly investor report")
    parser.add_argument("--months", type=int, default=3, help="Months of data to include")
    parser.add_argument("--output", type=str, default=None, help="Output PDF path")
    args = parser.parse_args()
    generate_report(months_back=args.months, output_path=args.output)
