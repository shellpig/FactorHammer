"""Tearsheet report builder."""

from __future__ import annotations

from pathlib import Path
from typing import Any

try:
    import plotly.graph_objects as go
    from plotly.subplots import make_subplots
except ModuleNotFoundError:
    class _FallbackFigure:
        def __init__(self, data: list[dict[str, Any]] | None = None):
            self.data: list[dict[str, Any]] = list(data or [])
            self.layout: dict[str, Any] = {}

        def add_trace(self, trace: dict[str, Any], row: int | None = None, col: int | None = None) -> None:
            _ = (row, col)
            self.data.append(trace)

        def update_layout(self, **kwargs: Any) -> None:
            self.layout.update(kwargs)

        def write_html(self, filepath: str) -> None:
            Path(filepath).write_text(
                "<html><body><h1>Tearsheet</h1></body></html>",
                encoding="utf-8",
            )

    class _FallbackGo:
        Figure = _FallbackFigure

        @staticmethod
        def Scatter(**kwargs: Any) -> dict[str, Any]:
            return {"type": "scatter", **kwargs}

        @staticmethod
        def Heatmap(**kwargs: Any) -> dict[str, Any]:
            return {"type": "heatmap", **kwargs}

        @staticmethod
        def Table(**kwargs: Any) -> dict[str, Any]:
            return {"type": "table", **kwargs}

    def make_subplots(**kwargs: Any) -> _FallbackFigure:
        _ = kwargs
        return _FallbackFigure()

    go = _FallbackGo()

from src.backtest.metrics import BacktestResult, calculate_monthly_returns


class TearsheetReport:
    """Build Plotly charts and HTML tearsheet from BacktestResult."""

    def __init__(self, result: BacktestResult):
        self.result = result

    def create_equity_chart(self) -> go.Figure:
        fig = go.Figure()
        fig.add_trace(
            go.Scatter(
                x=self.result.equity_curve.index,
                y=self.result.equity_curve.values,
                mode="lines",
                name="Equity",
                line={"color": "#1f77b4", "width": 2},
            )
        )
        fig.update_layout(title="Equity Curve", xaxis_title="Date", yaxis_title="Equity")
        return self._apply_theme(fig)

    def create_drawdown_chart(self) -> go.Figure:
        equity = self.result.equity_curve
        if equity.empty:
            drawdown = equity
        else:
            drawdown = 1.0 - (equity / equity.cummax())

        fig = go.Figure()
        fig.add_trace(
            go.Scatter(
                x=drawdown.index,
                y=-drawdown.values,
                mode="lines",
                name="Drawdown",
                fill="tozeroy",
                line={"color": "#d62728", "width": 1.5},
            )
        )
        fig.update_layout(title="Drawdown", xaxis_title="Date", yaxis_title="Drawdown")
        return self._apply_theme(fig)

    def create_monthly_heatmap(self) -> go.Figure:
        monthly = calculate_monthly_returns(self.result.equity_curve)
        z = monthly.values * 100.0 if not monthly.empty else monthly.values
        text = [[f"{v:.2f}%" if v == v else "" for v in row] for row in z]

        fig = go.Figure()
        fig.add_trace(
            go.Heatmap(
                z=z,
                x=list(range(1, 13)),
                y=monthly.index.tolist(),
                colorscale=[[0.0, "#d62728"], [0.5, "#ffffff"], [1.0, "#2ca02c"]],
                zmid=0.0,
                text=text,
                texttemplate="%{text}",
                hovertemplate="Year %{y}, Month %{x}: %{z:.2f}%<extra></extra>",
                colorbar={"title": "%"},
            )
        )
        fig.update_layout(title="Monthly Returns Heatmap", xaxis_title="Month", yaxis_title="Year")
        return self._apply_theme(fig)

    def create_summary_table(self) -> go.Figure:
        metrics = [
            ("Total Return", self._format_percent(self.result.total_return)),
            ("Annual Return", self._format_percent(self.result.annual_return)),
            ("Max Drawdown", self._format_percent(self.result.max_drawdown)),
            ("Sharpe Ratio", self._format_number(self.result.sharpe_ratio)),
            ("Sortino Ratio", self._format_ratio(self.result.sortino_ratio)),
            ("Calmar Ratio", self._format_ratio(self.result.calmar_ratio)),
            ("Win Rate", self._format_percent(self.result.win_rate)),
            ("Profit Factor", self._format_ratio(self.result.profit_factor)),
            ("Total Trades", str(self.result.total_trades)),
            ("Average Holding Days", self._format_number(self.result.avg_holding_days)),
            ("Max Single Loss", self._format_number(self.result.max_single_loss)),
        ]

        fig = go.Figure(
            data=[
                go.Table(
                    header={
                        "values": ["Metric", "Value"],
                        "fill_color": "#f3f3f3",
                        "align": "left",
                    },
                    cells={
                        "values": [[m[0] for m in metrics], [m[1] for m in metrics]],
                        "align": "left",
                    },
                )
            ]
        )
        fig.update_layout(title="Performance Summary")
        return self._apply_theme(fig)

    def create_full_tearsheet(self) -> go.Figure:
        full = make_subplots(
            rows=4,
            cols=1,
            shared_xaxes=False,
            row_heights=[0.40, 0.20, 0.25, 0.15],
            vertical_spacing=0.06,
            specs=[[{"type": "xy"}], [{"type": "xy"}], [{"type": "heatmap"}], [{"type": "table"}]],
            subplot_titles=("Equity Curve", "Drawdown", "Monthly Returns", "Summary"),
        )

        for trace in self.create_equity_chart().data:
            full.add_trace(trace, row=1, col=1)
        for trace in self.create_drawdown_chart().data:
            full.add_trace(trace, row=2, col=1)
        for trace in self.create_monthly_heatmap().data:
            full.add_trace(trace, row=3, col=1)
        for trace in self.create_summary_table().data:
            full.add_trace(trace, row=4, col=1)

        full.update_layout(height=1200, showlegend=False, title="Backtest Tearsheet")
        return self._apply_theme(full)

    def save_html(self, filepath: str) -> None:
        path = Path(filepath)
        path.parent.mkdir(parents=True, exist_ok=True)
        fig = self.create_full_tearsheet()
        fig.write_html(str(path))

    def get_streamlit_figures(self) -> dict[str, go.Figure]:
        return {
            "equity": self.create_equity_chart(),
            "drawdown": self.create_drawdown_chart(),
            "monthly": self.create_monthly_heatmap(),
            "summary": self.create_summary_table(),
        }

    def _apply_theme(self, fig: go.Figure) -> go.Figure:
        from src.core.config import get_config
        from src.ui.themes import get_theme

        config = get_config()
        ui_section = config.get("ui", {}) if isinstance(config, dict) else {}
        theme_name = str(ui_section.get("theme", "arctic_light"))
        _, palette = get_theme(theme_name)

        fig.update_layout(
            template=palette["plotly_template"],
            paper_bgcolor=palette["surface"],
            plot_bgcolor=palette["surface"],
            font={"color": palette["text"]},
        )

        for trace in fig.data:
            if hasattr(trace, "header") and hasattr(trace.header, "update"):
                trace.header.update(fill_color=palette["surface"])
                trace.header.font.update(color=palette["text"])
                trace.cells.update(fill_color=palette["background"])
                trace.cells.font.update(color=palette["text"])

        return fig

    @staticmethod
    def _format_percent(value: float) -> str:
        return f"{value * 100:.2f}%"

    @staticmethod
    def _format_number(value: float) -> str:
        return f"{value:.2f}"

    @staticmethod
    def _format_ratio(value: float) -> str:
        if value == 999.0:
            return "N/A"
        return f"{value:.2f}"
