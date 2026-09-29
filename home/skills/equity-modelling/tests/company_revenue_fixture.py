"""Company-owned two-category revenue bridge used to test blueprint flexibility."""
from __future__ import annotations

from engine import NINE_SHEET_ORDER


class AsterSystemsCompany:
    """Synthetic issuer with Hardware and Software revenue categories only.

    These categories are intentionally not decomposed into volume, price, mix, or FX because
    the fixture has no evidence for those attributions.
    """

    segments = (
        ("hardware", "Hardware", "hardware_revenue"),
        ("software", "Software", "software_revenue"),
    )

    @staticmethod
    def _row(label, semantic_format, order, section=None, **values):
        metadata = {"label": label, "format": semantic_format, "order": order}
        if section:
            metadata["section"] = section
        return {"_meta": metadata, **values}

    @staticmethod
    def _actual(metric, period):
        return f"em_actual_{metric}_{period}"

    @staticmethod
    def _model(sheet, metric, period):
        return f"em_model_{sheet}_{metric}_{period}"

    def workbook_rows(self, actuals, drivers, periods):
        quarter_periods = periods.periods
        operating = {}
        bridge = {}
        statements = {}
        checks = {}
        outlook = {}

        residual_by_period = {}
        status_by_period = {}

        for segment_index, (key, label, actual_metric) in enumerate(self.segments, start=1):
            operating[f"{key}_revenue"] = self._row(
                f"{label} Revenue", "money", segment_index, "Reported operating segments",
                **{period: f'=IF({self._actual(actual_metric, period)}="","",'
                            f'{self._actual(actual_metric, period)})'
                   for period in quarter_periods if not period.endswith("E")})

        operating_revenue = {}

        for period in quarter_periods:
            if period.endswith("E"):
                continue
            previous = periods.comparable_period(period, years_back=1)
            segment_bridge_refs = []
            for index, (key, segment_label, actual_metric) in enumerate(self.segments, start=1):
                base_key = f"{key}_base_same_quarter_last_year"
                growth_key = f"{key}_revenue_yoy_growth"
                current_key = f"{key}_bridged_revenue"
                if previous:
                    base_formula = f'=IF({self._actual(actual_metric, previous)}="","",{self._actual(actual_metric, previous)})'
                    growth_formula = (
                        f'=IF(OR({self._actual(actual_metric, period)}="",'
                        f'{self._actual(actual_metric, previous)}="",'
                        f'{self._actual(actual_metric, previous)}<=0),"",'
                        f'{self._actual(actual_metric, period)}/{self._actual(actual_metric, previous)}-1)')
                    current_formula = (
                        f'=IF(COUNT({self._model("Bridge_Model", base_key, period)},'
                        f'{self._model("Bridge_Model", growth_key, period)})<>2,"",'
                        f'{self._model("Bridge_Model", base_key, period)}*'
                        f'(1+{self._model("Bridge_Model", growth_key, period)}))')
                else:
                    base_formula = growth_formula = None
                    current_formula = (f'=IF({self._actual(actual_metric, period)}="","",'
                                       f'{self._actual(actual_metric, period)})')
                bridge.setdefault(base_key, self._row(
                    f"{segment_label} Revenue — Same Fiscal Quarter Last Year", "money", index * 3 - 2,
                    "Historical segment bridge" if index == 1 else None))
                bridge.setdefault(growth_key, self._row(
                    f"{segment_label} Revenue YoY Growth", "percent", index * 3 - 1))
                bridge.setdefault(current_key, self._row(
                    f"{segment_label} Revenue — Reported / Bridged", "money", index * 3))
                if base_formula:
                    bridge[base_key][period] = base_formula
                    bridge[growth_key][period] = growth_formula
                bridge[current_key][period] = current_formula
                segment_bridge_refs.append(self._model("Bridge_Model", current_key, period))

            total_key = "bridged_segment_revenue_total"
            consolidated_key = "independent_consolidated_revenue"
            residual_key = "segment_revenue_residual"
            status_key = "segment_to_consolidated_status"
            count = len(segment_bridge_refs)
            bridge.setdefault(total_key, self._row(
                "Segment Revenue Total (Reported / Bridged)", "money", 7,
                "Independent revenue reconciliation"))
            bridge[total_key][period] = (
                f'=IF(COUNT({",".join(segment_bridge_refs)})<>{count},"",'
                f'SUM({",".join(segment_bridge_refs)}))')
            bridge.setdefault(consolidated_key, self._row(
                "Independently Sourced Consolidated Revenue", "money", 8))
            bridge[consolidated_key][period] = (
                f'=IF({self._actual("consolidated_revenue", period)}="","",'
                f'{self._actual("consolidated_revenue", period)})')
            bridge.setdefault(residual_key, self._row("Segment Revenue Residual", "money", 9))
            bridge[residual_key][period] = (
                f'=IF(COUNT({self._model("Bridge_Model", total_key, period)},'
                f'{self._model("Bridge_Model", consolidated_key, period)})<>2,"",'
                f'{self._model("Bridge_Model", total_key, period)}-'
                f'{self._model("Bridge_Model", consolidated_key, period)})')
            bridge.setdefault(status_key, self._row(
                "Segment-to-Consolidated Revenue Check", "text", 10))
            bridge[status_key][period] = (
                f'=IF(COUNT({self._model("Bridge_Model", total_key, period)},'
                f'{self._model("Bridge_Model", consolidated_key, period)})<>2,"Unavailable",'
                f'IF(ABS({self._model("Bridge_Model", residual_key, period)})<0.05,"Pass","Fail"))')
            residual_by_period[period] = self._model("Bridge_Model", residual_key, period)
            status_by_period[period] = self._model("Bridge_Model", status_key, period)
            total_ref = self._model("Bridge_Model", total_key, period)
            operating_revenue[period] = f'=IF({total_ref}="","",{total_ref})'

        operating["revenue"] = self._row(
            "Revenue", "money", 3, "Consolidated operating result", **operating_revenue)
        financial_revenue = {
            period: f'=IF({self._model("Operating_Model", "revenue", period)}="","",'
                    f'{self._model("Operating_Model", "revenue", period)})'
            for period in quarter_periods if not period.endswith("E")
        }
        statements["revenue"] = self._row(
            "Revenue", "money", 1, "Income statement", **financial_revenue)

        checks["segment_revenue_residual"] = self._row(
            "Segment Revenue Residual", "money", 1, "Revenue reconciliation",
            **{period: f'=IF({ref}="","",{ref})' for period, ref in residual_by_period.items()})
        checks["segment_to_consolidated_status"] = self._row(
            "Segment-to-Consolidated Revenue Check", "text", 2,
            **{period: f"={ref}" for period, ref in status_by_period.items()})
        outlook["revenue_check_status"] = self._row(
            "Revenue Reconciliation Status", "text", 1, "Historical synthetic blueprint",
            **{period: f"={ref}" for period, ref in status_by_period.items()})
        outlook["latest_revenue"] = self._row(
            "Revenue", "money", 2,
            **{period: f'=IF({self._model("Operating_Model", "revenue", period)}="","",'
                        f'{self._model("Operating_Model", "revenue", period)})'
               for period in quarter_periods if not period.endswith("E")})

        empty = {"_meta": {"label": "No sourced valuation inputs", "format": "text"}}
        unavailable = {"_meta": {"label": "Consensus — Unavailable (not supplied)", "format": "text"}}
        return {
            "Outlook": outlook,
            "Operating Model": operating,
            "Bridge Model": bridge,
            "Financial Statements": statements,
            "Valuation": {"valuation_unavailable": empty},
            "Consensus": {"consensus_unavailable": unavailable},
            "Checks": checks,
        }


def revenue_bridge_project():
    """A synthetic two-segment issuer and the standard nine-sheet period horizon."""
    historical = ["2025Q1", "2026Q1"]
    forecasts = ["2026Q2", "2026Q3", "2026Q4", "2027Q1",
                 "2027Q2", "2027Q3", "2027Q4", "2028Q1"]
    actuals = [
        {"metric": metric, "period": period, "value": value}
        for metric, period, value in (
            ("hardware_revenue", "2025Q1", 45.0),
            ("hardware_revenue", "2026Q1", 50.0),
            ("software_revenue", "2025Q1", 55.0),
            ("software_revenue", "2026Q1", 75.0),
            ("consolidated_revenue", "2025Q1", 100.0),
            ("consolidated_revenue", "2026Q1", 125.0),
        )
    ]
    drivers = []
    spec = {
        "ticker": "AST",
        "periods": {"historical_quarters": historical, "forecast_quarters": forecasts},
        "forecast_gate": {"approved": False},
        "workbook": {"sheets": list(NINE_SHEET_ORDER)},
    }
    return spec, actuals, drivers, AsterSystemsCompany()
