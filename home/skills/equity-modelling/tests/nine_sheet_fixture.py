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


class FiscalAnnualCompany:
    """Synthetic company-owned fiscal trend and annual formulas for renderer contracts."""

    @staticmethod
    def _row(label, semantic_format, order, **values):
        return {"_meta": {"label": label, "format": semantic_format, "order": order}, **values}

    def workbook_rows(self, actuals, drivers, periods):
        quarterly = periods.periods
        annuals = periods.annual_periods
        revenue = {}
        operating_profit = {}
        net_income = {}
        diluted_shares = {}
        revenue_yoy = {}
        revenue_qoq = {}
        revenue_two_year = {}
        operating_margin = {}
        margin_yoy = {}
        margin_qoq = {}
        annual_eps = {}
        annual_revenue_yoy = {}
        year_end_cash = {}

        for period in quarterly:
            if period.endswith("E"):
                continue
            for metric, row in (("revenue", revenue), ("operating_profit", operating_profit),
                                ("net_income", net_income), ("diluted_shares", diluted_shares)):
                source = f"em_actual_{metric}_{period}"
                row[period] = f'=IF({source}="","",{source})'
            current_revenue = f"em_model_Operating_Model_revenue_{period}"
            prior_yoy = periods.comparable_period(period, years_back=1)
            prior_qoq = periods.comparable_period(period, quarters_back=1)
            prior_two_year = periods.comparable_period(period, years_back=2)
            for row, prior in ((revenue_yoy, prior_yoy), (revenue_qoq, prior_qoq),
                               (revenue_two_year, prior_two_year)):
                base = f"em_model_Operating_Model_revenue_{prior}" if prior else None
                if base:
                    row[period] = f'=IF(OR({current_revenue}="",{base}="",{current_revenue}<=0,{base}<=0),"",{current_revenue}/{base}-1)'
                else:
                    row[period] = None
            profit = f"em_actual_operating_profit_{period}"
            sales = f"em_actual_revenue_{period}"
            operating_margin[period] = f'=IF(OR({profit}="",{sales}="",{sales}<=0),"",{profit}/{sales})'
            for row, prior in ((margin_yoy, prior_yoy), (margin_qoq, prior_qoq)):
                if prior:
                    row[period] = f'=IF(OR(em_actual_operating_profit_{period}="",em_actual_revenue_{period}="",em_actual_revenue_{period}<=0,em_actual_operating_profit_{prior}="",em_actual_revenue_{prior}="",em_actual_revenue_{prior}<=0),"",(em_actual_operating_profit_{period}/em_actual_revenue_{period}-em_actual_operating_profit_{prior}/em_actual_revenue_{prior})*100)'
                else:
                    row[period] = None

        for annual in annuals:
            members = periods.annual_members(annual)
            refs = lambda metric: [f"em_model_Operating_Model_{metric}_{period}" for period in members]
            def complete(metric, aggregate):
                quarter_refs = ",".join(refs(metric))
                return f'=IF(COUNT({quarter_refs})<>4,"",{aggregate}({quarter_refs}))'
            revenue[annual] = complete("revenue", "SUM")
            operating_profit[annual] = complete("operating_profit", "SUM")
            net_income[annual] = complete("net_income", "SUM")
            diluted_shares[annual] = complete("diluted_shares", "AVERAGE")
            annual_profit = f"em_model_Operating_Model_operating_profit_{annual}"
            annual_revenue = f"em_model_Operating_Model_revenue_{annual}"
            operating_margin[annual] = f'=IF(OR({annual_profit}="",{annual_revenue}="",{annual_revenue}<=0),"",{annual_profit}/{annual_revenue})'
            annual_net = f"em_model_Operating_Model_net_income_{annual}"
            annual_shares = f"em_model_Operating_Model_diluted_shares_{annual}"
            annual_eps[annual] = f'=IF(OR({annual_net}="",{annual_shares}="",{annual_shares}<=0),"",{annual_net}/{annual_shares})'
            prior_annual = f"FY{int(annual[2:6]) - 1}A"
            if prior_annual in annuals:
                margin_yoy[annual] = f'=IF(OR(em_model_Operating_Model_operating_margin_{annual}="",em_model_Operating_Model_operating_margin_{prior_annual}=""),"",(em_model_Operating_Model_operating_margin_{annual}-em_model_Operating_Model_operating_margin_{prior_annual})*100)'
            q4_cash = f"em_actual_cash_{members[-1]}"
            year_end_cash[annual] = f'=IF({q4_cash}="","",{q4_cash})'
            if prior_annual in annuals:
                revenue_yoy[annual] = f'=IF(OR(em_model_Operating_Model_revenue_{annual}="",em_model_Operating_Model_revenue_{prior_annual}="",em_model_Operating_Model_revenue_{annual}<=0,em_model_Operating_Model_revenue_{prior_annual}<=0),"",em_model_Operating_Model_revenue_{annual}/em_model_Operating_Model_revenue_{prior_annual}-1)'
            else:
                revenue_yoy[annual] = None

        operating = {
            "revenue": self._row("Revenue", "money", 1, **revenue),
            "revenue_yoy": self._row("Revenue YoY", "percent", 2, **revenue_yoy),
            "revenue_qoq": self._row("Revenue QoQ", "percent", 3, **revenue_qoq),
            "revenue_two_year_stack": self._row("Revenue 2yr Stack", "percent", 4, **revenue_two_year),
            "operating_profit": self._row("Operating Profit", "money", 5, **operating_profit),
            "operating_margin": self._row("Operating Margin", "percent", 6, **operating_margin),
            "operating_margin_yoy": self._row("Operating Margin YoY", "percentage_points", 7, **margin_yoy),
            "operating_margin_qoq": self._row("Operating Margin QoQ", "percentage_points", 8, **margin_qoq),
            "net_income": self._row("Net Income", "money", 9, **net_income),
            "diluted_shares": self._row("Diluted Shares", "shares", 10, **diluted_shares),
            "diluted_eps": self._row("Diluted EPS — Calculated", "eps", 11, **annual_eps),
        }
        empty = {"_meta": {"label": "Historical Fixture", "format": "text"}}
        return {
            "Outlook": {"fixture": empty},
            "Operating Model": operating,
            "Bridge Model": {"fixture": empty},
            "Financial Statements": {
                "year_end_cash": self._row("Cash — Year End", "money", 1, **year_end_cash),
            },
            "Valuation": {"fixture": empty},
            "Consensus": {"fixture": empty},
            "Checks": {"fixture": empty},
        }


def fiscal_annual_project():
    historical = [f"{year}Q{quarter}" for year in (2024, 2025) for quarter in range(1, 5)] + ["2026Q1"]
    forecasts = ["2026Q2", "2026Q3", "2026Q4", "2027Q1", "2027Q2", "2027Q3", "2027Q4", "2028Q1"]
    actuals = []
    for period in historical:
        year, quarter = int(period[:4]), int(period[-1])
        revenue = {(2024, 1): 100.0, (2025, 1): 110.0, (2026, 1): 132.0,
                   (2024, 2): 100.0, (2025, 2): 125.0}.get((year, quarter), 100.0)
        op_margin = {(2024, 1): 0.20, (2025, 1): 0.24, (2026, 1): 0.25}.get((year, quarter), 0.20)
        for metric, value in (
            ("revenue", revenue),
            ("operating_profit", revenue * op_margin),
            ("net_income", revenue * 0.10),
            ("diluted_shares", 10.0),
            ("cash", 50.0 + quarter),
        ):
            actuals.append({"metric": metric, "period": period, "value": value})
    spec = {
        "periods": {"historical_quarters": historical, "forecast_quarters": forecasts},
        "forecast_gate": {"approved": False},
        "workbook": {"sheets": list(NINE_SHEET_ORDER)},
    }
    drivers = [{"driver_id": "growth", "driver_name": "Revenue Growth", "status": "proposed",
                **{period: 0.10 for period in forecasts}}]
    return spec, actuals, drivers, FiscalAnnualCompany()


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
