import numpy as np
from itertools import cycle
from datetime import date, timedelta
from bokeh.plotting import figure as bokeh_figure
from bokeh.models import (
    NumeralTickFormatter,
    DatetimeTickFormatter,
    Span,
    ColumnDataSource,
)
from bokeh.models.tools import HoverTool
from bokeh.palettes import Dark2

BAR_COLOUR = "#D5DFED"
LINE_COLOUR = ["#3D6CB3", "#B33D43"]


nhs_region_pops = {
    "North West": 7012947,
    "North East and Yorkshire": 8566925,
    "Midlands": 10537679,
    "East of England": 6493188,
    "London": 8908081,
    "South East": 8852361,
    "South West": 5605997,
}

england_interventions = [
    (date(2020, 3, 23), "Lockdown", "#CC5450"),
    (date(2020, 5, 10), "Stay Alert", "#50CCA5"),
    (date(2020, 6, 1), "Schools Open", "#50CCA5"),
    (date(2020, 6, 15), "Non-essential shops open", "#50CCA5"),
    (date(2020, 7, 4), "1m plus distancing, pubs open", "#50CCA5")
]


def region_hover_tool():
    return HoverTool(
        tooltips=[
            ("Region", "$name"),
            ("Value per 100,000", "$y{0.00}"),
            ("Date", "$x{%d %b}"),
        ],
        formatters={"$x": "datetime"},
    )


def intervention(fig, date, label, colour="red"):
    span = Span(
        location=date,
        dimension="height",
        line_color=colour,
        line_width=1,
        line_dash="dashed",
    )
    fig.add_layout(span)

    # span_label = Label(
    #    text=label,
    #    text_font="Noto Sans",
    #    text_font_size="10px",
    #    x=date,
    #    y=0,
    #    x_offset=-20,
    #    y_offset=-10,
    #    background_fill_color="white",
    # )
    # fig.add_layout(span_label)


def add_interventions(fig):
    for when, label, colour in england_interventions:
        intervention(fig, when, label, colour)


def figure(**kwargs):
    fig = bokeh_figure(
        width=1200,
        height=500,
        toolbar_location=None,
        x_range=(
            np.datetime64(date(2020, 3, 1)),
            np.datetime64(date.today() + timedelta(days=1)),
        ),
        sizing_mode="scale_width",
        tools="",
        **kwargs
    )
    add_interventions(fig)
    fig.xaxis.formatter = DatetimeTickFormatter(days="%d %b")
    fig.xgrid.visible = False
    fig.y_range.start = 0
    return fig


def stack_datasource(source, series):
    data = {}
    for i in range(0, len(series)):
        y = sum(source.sel(location=loc) for loc in series[0 : i + 1]).values
        data[series[i]] = y

    data["date"] = source["date"].values
    return ColumnDataSource(data)


def uk_cases_graph(uk_cases, ecdc_cases):
    provisional_days = 4
    bar_width = 8640 * 10e3 * 0.7

    fig = figure(title="New cases")

    uk_cases = uk_cases.ffill("date").diff("date")

    rolling = (
        uk_cases[:, :-provisional_days]
        .rolling({"date": 7}, center=True)
        .mean()
        .dropna("date")
    )

    layers = ["England", "Scotland", "Wales"]
    colours = {"England": "#E6A6A1", "Scotland": "#A1A3E6", "Wales": "#A6C78B"}

    cases_ds = stack_datasource(uk_cases, layers)
    rolling_ds = stack_datasource(rolling, layers)

    lower = 0
    for layer in layers:
        label = layer
        fig.vbar(
            source=cases_ds,
            x='date',
            bottom=lower,
            top=layer,
            width=bar_width,
            line_width=0,
            fill_color=colours[layer],
            fill_alpha=0.3
        )
        fig.line(
            source=rolling_ds,
            x="date",
            y=layer,
            line_color=colours[layer],
            line_width=1.5,
            legend_label=label
        )
        lower = layer

    if ecdc_cases:
        total_cases = (
            ecdc_cases.sel(location="United Kingdom")["cases"]
            .dropna("date")
            .diff("date")
            .rolling({"date": 7}, center=True)
            .mean()
        )

        fig.line(
            x=total_cases["date"].values,
            y=total_cases.values,
            name="UK Cases",
            legend_label="UK cases (date of report)",
            line_width=2,
            line_color=LINE_COLOUR[1],
        )
    fig.yaxis.formatter = NumeralTickFormatter(format="0,0")
    return fig


def england_deaths(uk_cases, excess_deaths):
    fig = figure(title="Deaths in England & Wales")

    deaths_england = uk_cases["deaths"].sel(location="England").diff("date").fillna(0)
    deaths_wales = uk_cases["deaths"].sel(location="Wales").diff("date").fillna(0)
    deaths = deaths_england + deaths_wales
    deaths_mean = deaths.rolling(date=7, center=True).mean().dropna("date")

    bar_width = 8640 * 10e3 * 0.7
    fig.vbar(
        x=deaths["date"].values,
        top=deaths.values,
        width=bar_width,
        legend_label="Reported COVID-19 deaths",
        line_width=0,
        fill_color=BAR_COLOUR,
    )
    fig.line(
        x=deaths_mean["date"].values,
        y=deaths_mean.values,
        line_width=2,
        legend_label="7 day average",
        line_color=LINE_COLOUR[0],
    )

    excess = excess_deaths["deaths"].interpolate() / 7
    fig.line(
        x=excess.index,
        y=excess.values,
        line_width=2,
        line_color=LINE_COLOUR[1],
        legend_label="Excess deaths (weekly)",
    )

    fig.xaxis.axis_label = "Date of report"
    fig.yaxis.formatter = NumeralTickFormatter(format="0,0")
    return fig


def regional_cases(regions):
    fig = figure(title="New cases by region")

    fig.add_tools(region_hover_tool())

    colours = cycle(Dark2[7])

    for loc in sorted([str(loc.data) for loc in regions["location"]]):
        s = regions.sel(location=loc)
        color = next(colours)
        fig.line(
            x=s["date"].values,
            y=s["cases_rolling"].values / nhs_region_pops[loc] * 100000,
            legend_label=loc,
            name=loc,
            color=color,
            line_width=1,
        )
        fig.line(
            x=s["date"].values,
            y=s["cases_rolling_provisional"].values / nhs_region_pops[loc] * 100000,
            legend_label=loc,
            name=loc,
            color=color,
            line_width=1,
            line_alpha=0.4,
        )

    fig.legend.location = "top_right"
    fig.yaxis.axis_label = "Cases per 100,000 population"
    return fig


def regional_deaths(nhs_deaths):
    fig = figure(title="Deaths in hospital")

    fig.add_tools(region_hover_tool())

    colours = cycle(Dark2[7])

    for loc in sorted([str(loc.data) for loc in nhs_deaths["location"]]):
        s = nhs_deaths.sel(location=loc)
        color = next(colours)
        fig.line(
            x=s["date"].values,
            y=s["deaths_rolling"].values / nhs_region_pops[loc] * 100000,
            legend_label=loc,
            name=loc,
            color=color,
            line_width=1,
        )
        fig.line(
            x=s["date"].values,
            y=s["deaths_rolling_provisional"].values / nhs_region_pops[loc] * 100000,
            legend_label=loc,
            name=loc,
            color=color,
            line_width=1,
            line_alpha=0.4,
        )

    fig.legend.location = "top_right"
    fig.xaxis.axis_label = "Date of death"
    fig.yaxis.axis_label = "Deaths per 100,000 population"
    return fig


def triage_graph(triage_online, title=""):
    fig = figure(title=title)
    fig.add_tools(region_hover_tool())

    colours = cycle(Dark2[7])
    for loc in sorted([str(loc.item()) for loc in triage_online["region"]]):
        s = triage_online.sel(region=loc)
        color = next(colours)
        fig.line(
            x=s["date"].values,
            y=s["count_rolling_7"].values / nhs_region_pops[loc] * 100000,
            legend_label=loc,
            name=loc,
            color=color,
            line_width=1,
        )

    fig.legend.location = "top_right"
    fig.yaxis.axis_label = "Instances per 100,000 population"
    return fig


def patients_in_hospital_graph(hosp):
    fig = figure(title="Patients in hospital",)
    fig.add_tools(region_hover_tool())

    colours = cycle(Dark2[7])

    locations = sorted(
        set(str(loc.item()) for loc in hosp["location"])
        - {"Scotland", "Wales", "Northern Ireland"}
    )

    for loc in locations:
        s = hosp.sel(location=loc)
        color = next(colours)
        fig.line(
            x=s["date"].values,
            y=s["patients_rolling_3"].values / nhs_region_pops[loc] * 100000,
            legend_label=loc,
            name=loc,
            color=color,
            line_width=1,
        )

    fig.legend.location = "top_right"
    fig.yaxis.axis_label = "Patients per 100,000 population"
    return fig
