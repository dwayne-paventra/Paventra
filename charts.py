import plotly.express as px


def create_budget_chart(budget_df):
    fig = px.pie(
        budget_df,
        names="Category",
        values="Cost ($)",
        hole=0.55,
        title="Project Budget Allocation"
    )

    fig.update_traces(textposition="inside", textinfo="percent+label")

    fig.update_layout(
        template="plotly_white",
        title_x=0.5
    )

    return fig


def create_capital_chart(capital_df):
    fig = px.line(
        capital_df,
        x="Fiscal Year",
        y="Recommended Budget",
        markers=True,
        title="Three-Year Capital Investment"
    )

    fig.update_traces(
        line=dict(width=5),
        marker=dict(size=10)
    )

    fig.update_layout(
        template="plotly_white",
        title_x=0.5,
        xaxis_title="Fiscal Year",
        yaxis_title="Budget ($)"
    )

    fig.update_yaxes(
        tickprefix="$",
        separatethousands=True
    )

    return fig