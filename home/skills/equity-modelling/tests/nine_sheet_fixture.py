"""Small synthetic nine-sheet project proving the shared historical rendering path."""
from __future__ import annotations

from engine import NINE_SHEET_ORDER


class SyntheticCompany:
    """A deliberately small revenue-to-EPS chain with an independent revenue tie."""

    def workbook_rows(self, actuals, drivers, periods):
        operating = {
            "revenue": {
                "_meta": {"label": "Revenue", "format": "money", "section": "Operating results", "order": 1},
                "2025Q1": "=em_actual_revenue_2025Q1",
                "2026Q1": "=em_actual_revenue_2026Q1",
            },
            "revenue_yoy": {
                "_meta": {"label": "Revenue YoY", "format": "percent", "order": 2},
                "2025Q1": None,
                "2026Q1": '=IFERROR(em_actual_revenue_2026Q1/em_actual_revenue_2025Q1-1,"")',
            },
            "net_income": {
                "_meta": {"label": "Net Income", "format": "money", "section": "Earnings", "order": 3},
                "2025Q1": "=em_actual_net_income_2025Q1",
                "2026Q1": "=em_actual_net_income_2026Q1",
            },
            "diluted_eps": {
                "_meta": {"label": "GAAP Diluted EPS — Calculated", "format": "eps", "order": 4},
                "2025Q1": '=IFERROR(em_actual_net_income_2025Q1/em_actual_diluted_shares_2025Q1,"")',
                "2026Q1": '=IFERROR(em_actual_net_income_2026Q1/em_actual_diluted_shares_2026Q1,"")',
            },
        }
        bridge = {
            "base_revenue": {
                "_meta": {"label": "Revenue — Same Quarter Last Year", "format": "money", "order": 1},
                "2025Q1": None,
                "2026Q1": "=em_actual_revenue_2025Q1",
            },
            "revenue_growth": {
                "_meta": {"label": "Revenue Growth", "format": "percent", "order": 2},
                "2025Q1": None,
                "2026Q1": '=IFERROR(em_actual_revenue_2026Q1/em_actual_revenue_2025Q1-1,"")',
            },
            "bridged_revenue": {
                "_meta": {"label": "Bridged Revenue", "format": "money", "order": 3},
                "2025Q1": "=em_actual_revenue_2025Q1",
                "2026Q1": "=em_model_Bridge_Model_base_revenue_2026Q1*(1+em_model_Bridge_Model_revenue_growth_2026Q1)",
            },
            "revenue_check": {
                "_meta": {"label": "Independent Consolidated Revenue Check", "format": "money", "order": 4},
                "2025Q1": '=IF(OR(em_model_Bridge_Model_bridged_revenue_2025Q1="",em_actual_consolidated_revenue_2025Q1=""),"Unavailable",IF(ABS(em_model_Bridge_Model_bridged_revenue_2025Q1-em_actual_consolidated_revenue_2025Q1)<0.05,"Pass","Fail"))',
                "2026Q1": '=IF(OR(em_model_Bridge_Model_bridged_revenue_2026Q1="",em_actual_consolidated_revenue_2026Q1=""),"Unavailable",IF(ABS(em_model_Bridge_Model_bridged_revenue_2026Q1-em_actual_consolidated_revenue_2026Q1)<0.05,"Pass","Fail"))',
            },
        }
        statements = {
            "revenue": {"_meta": {"label": "Revenue", "format": "money"},
                        "2025Q1": "=em_model_Operating_Model_revenue_2025Q1",
                        "2026Q1": "=em_model_Operating_Model_revenue_2026Q1"},
            "net_income": {"_meta": {"label": "GAAP Net Income", "format": "money"},
                           "2025Q1": "=em_model_Operating_Model_net_income_2025Q1",
                           "2026Q1": "=em_model_Operating_Model_net_income_2026Q1"},
            "diluted_eps": {"_meta": {"label": "GAAP Diluted EPS", "format": "eps"},
                            "2025Q1": "=em_model_Operating_Model_diluted_eps_2025Q1",
                            "2026Q1": "=em_model_Operating_Model_diluted_eps_2026Q1"},
        }
        valuation = {
            "dated_price": {"_meta": {"label": "Dated Share Price", "format": "price"},
                            "2025Q1": "=em_benchmark_price_dated", "2026Q1": "=em_benchmark_price_dated"},
            "equity_value": {"_meta": {"label": "Equity Value", "format": "money"},
                             "2025Q1": "=em_benchmark_price_dated*em_actual_diluted_shares_2025Q1",
                             "2026Q1": "=em_benchmark_price_dated*em_actual_diluted_shares_2026Q1"},
            "price_earnings": {"_meta": {"label": "Price / GAAP Earnings", "format": "multiple"},
                               "2025Q1": '=IFERROR(em_model_Valuation_equity_value_2025Q1/em_model_Operating_Model_net_income_2025Q1,"")',
                               "2026Q1": '=IFERROR(em_model_Valuation_equity_value_2026Q1/em_model_Operating_Model_net_income_2026Q1,"")'},
        }
        outlook = {
            "example_scope": {"_meta": {"label": "Scope", "format": "text", "section": "Historical synthetic example"},
                              "2025Q1": "No investment recommendation; historical fixture only.",
                              "2026Q1": "No investment recommendation; historical fixture only."},
            "latest_revenue": {"_meta": {"label": "Latest Revenue", "format": "money"},
                               "2025Q1": "=em_model_Operating_Model_revenue_2025Q1",
                               "2026Q1": "=em_model_Operating_Model_revenue_2026Q1"},
            "latest_eps": {"_meta": {"label": "Latest GAAP EPS", "format": "eps"},
                           "2025Q1": "=em_model_Operating_Model_diluted_eps_2025Q1",
                           "2026Q1": "=em_model_Operating_Model_diluted_eps_2026Q1"},
            "check_status": {"_meta": {"label": "Revenue Check Status", "format": "text"},
                             "2025Q1": "=em_model_Checks_revenue_check_2025Q1",
                             "2026Q1": "=em_model_Checks_revenue_check_2026Q1"},
        }
        consensus = {
            "revenue_consensus": {"_meta": {"label": "Revenue Consensus — Unavailable (not supplied)", "format": "money"}},
            "eps_consensus": {"_meta": {"label": "EPS Consensus — Unavailable (not supplied)", "format": "eps"}},
        }
        checks = {
            "revenue_check": {
                "_meta": {"label": "Bridge to Independently Sourced Consolidated Revenue", "format": "text", "section": "Independent reconciliation"},
                "2025Q1": "=em_model_Bridge_Model_revenue_check_2025Q1",
                "2026Q1": "=em_model_Bridge_Model_revenue_check_2026Q1",
            },
        }
        return {
            "Outlook": outlook,
            "Operating Model": operating,
            "Bridge Model": bridge,
            "Financial Statements": statements,
            "Valuation": valuation,
            "Consensus": consensus,
            "Checks": checks,
        }


def synthetic_project():
    periods = ("2025Q1", "2026Q1")
    forecasts = ("2026Q2", "2026Q3", "2026Q4", "2027Q1",
                 "2027Q2", "2027Q3", "2027Q4", "2028Q1")
    actuals = [
        {"metric": "revenue", "period": "2025Q1", "value": 100.0},
        {"metric": "revenue", "period": "2026Q1", "value": 125.0},
        {"metric": "consolidated_revenue", "period": "2025Q1", "value": 100.0},
        {"metric": "consolidated_revenue", "period": "2026Q1", "value": 125.0},
        {"metric": "net_income", "period": "2025Q1", "value": 10.0},
        {"metric": "net_income", "period": "2026Q1", "value": 15.0},
        {"metric": "diluted_shares", "period": "2025Q1", "value": 10.0},
        {"metric": "diluted_shares", "period": "2026Q1", "value": 10.0},
    ]
    drivers = [{"driver_id": "revenue_growth", "driver_name": "Revenue Growth Assumption",
                "status": "proposed", **{period: 0.1 for period in forecasts}}]
    spec = {
        "periods": {"historical_quarters": list(periods), "forecast_quarters": list(forecasts)},
        "price": {"value": 20.0, "date": "2026-09-18"},
        "forecast_gate": {"approved": False},
        "workbook": {"sheets": list(NINE_SHEET_ORDER)},
    }
    return spec, actuals, drivers, SyntheticCompany()
