"""
CLI entrypoint for the FMCG ML project.

Usage:
    python main.py forecast [--limit N] [--horizon 30]
    python main.py classify
    python main.py cluster            # runs both RFM and demand clustering
    python main.py optimize [--budget 200000000]
    python main.py all                # runs everything in the recommended order
"""
import argparse


def main():
    parser = argparse.ArgumentParser(description="FMCG inventory ML pipeline")
    sub = parser.add_subparsers(dest="command", required=True)

    p_forecast = sub.add_parser("forecast", help="Demand forecasting (SARIMA/Holt-Winters vs naive baseline)")
    p_forecast.add_argument("--limit", type=int, default=None)
    p_forecast.add_argument("--horizon", type=int, default=30)
    p_forecast.add_argument("--test-days", type=int, default=30)

    sub.add_parser("classify", help="Stockout/reorder risk classification")

    sub.add_parser("cluster", help="RFM customer clustering + SKU demand-pattern clustering")

    p_opt = sub.add_parser("optimize", help="Budget-constrained replenishment optimization (LP/IP)")
    p_opt.add_argument("--budget", type=float, default=200_000_000)
    p_opt.add_argument("--capacity-units", type=float, default=None)

    sub.add_parser("all", help="Run forecast -> classify -> cluster -> optimize, in that order")

    args = parser.parse_args()

    if args.command == "forecast":
        from src.forecasting.train import run
        run(horizon=args.horizon, test_days=args.test_days, limit=args.limit)

    elif args.command == "classify":
        from src.classification.train import run
        run()

    elif args.command == "cluster":
        from src.clustering.rfm_clustering import run as run_rfm
        from src.clustering.demand_clustering import run as run_demand
        print("=" * 70, "\nRFM CUSTOMER CLUSTERING\n", "=" * 70, sep="")
        run_rfm()
        print("\n" + "=" * 70, "\nSKU DEMAND-PATTERN CLUSTERING\n", "=" * 70, sep="")
        run_demand()

    elif args.command == "optimize":
        from src.optimization.replenishment_lp import run
        run(budget=args.budget, capacity_units=args.capacity_units)

    elif args.command == "all":
        from src.forecasting.train import run as run_forecast
        from src.classification.train import run as run_classify
        from src.clustering.rfm_clustering import run as run_rfm
        from src.clustering.demand_clustering import run as run_demand
        from src.optimization.replenishment_lp import run as run_opt

        print("### 1/4 FORECASTING ###")
        run_forecast(limit=15)  # keep 'all' fast; run forecast alone for full run
        print("\n### 2/4 CLASSIFICATION ###")
        run_classify()
        print("\n### 3/4 CLUSTERING ###")
        run_rfm()
        run_demand()
        print("\n### 4/4 OPTIMIZATION ###")
        run_opt(budget=200_000_000)


if __name__ == "__main__":
    main()
