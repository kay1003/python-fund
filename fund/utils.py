from __future__ import annotations

import datetime as _dt
from dataclasses import dataclass
from typing import Iterable

import pandas as pd


@dataclass(frozen=True)
class IntervalSummary:
    upper: float
    lower: float
    days: int
    total_invest: float
    subset: pd.DataFrame
    per_day_amount: float | None = None


def get_yesterday_str(today: _dt.date | None = None) -> str:
    if today is None:
        today = _dt.date.today()
    return (today - _dt.timedelta(days=1)).strftime("%Y%m%d")


def prepare_hist_df(df: pd.DataFrame, date_col: str = "日期", change_col: str = "涨跌幅") -> pd.DataFrame:
    df = df.copy()
    df[date_col] = pd.to_datetime(df[date_col])
    df = df.sort_values(date_col).reset_index(drop=True)
    if change_col in df.columns:
        df[change_col] = df[change_col].astype(float)
    return df


def resolve_analysis_year(df: pd.DataFrame, date_col: str, year: int | None) -> int:
    if year is not None:
        return year
    return int(df[date_col].dt.year.max())


def summarize_intervals(
    df_down: pd.DataFrame,
    intervals: Iterable[tuple[float, float]],
    *,
    change_col: str = "涨跌幅",
    strategy: str = "fixed",
    fixed_amounts: list[float] | None = None,
    proportional_scale: float = 1000.0,
) -> list[IntervalSummary]:
    results: list[IntervalSummary] = []
    intervals = list(intervals)
    if strategy == "fixed" and (not fixed_amounts or len(fixed_amounts) != len(intervals)):
        raise ValueError("fixed_amounts must be provided and match intervals length.")

    for i, (upper, lower) in enumerate(intervals):
        mask = (df_down[change_col] <= upper) & (df_down[change_col] > lower)
        subset = df_down.loc[mask].copy()
        if strategy == "proportional":
            subset["投资金额"] = subset[change_col].abs() * proportional_scale
            total_invest = float(subset["投资金额"].sum())
            per_day_amount = None
        else:
            per_day_amount = float(fixed_amounts[i])
            total_invest = float(len(subset) * per_day_amount)
        results.append(
            IntervalSummary(
                upper=upper,
                lower=lower,
                days=len(subset),
                total_invest=total_invest,
                subset=subset,
                per_day_amount=per_day_amount,
            )
        )

    return results
