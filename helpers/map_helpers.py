import plotly.express as px


def create_network_map(roads):

    if roads.empty:

        return px.scatter_map(
            title="No Road Data Available"
        )

    fig = px.scatter_map(
        roads,
        lat="Latitude",
        lon="Longitude",
        color="Risk Level",
        hover_name="Road Name",
        hover_data={
            "Condition": True,
            "Traffic": True,
            "Age": True,
            "Risk Score": True,
            "Latitude": False,
            "Longitude": False,
        },
        color_discrete_map={
            "High": "#d32f2f",
            "Medium": "#f9a825",
            "Low": "#2e7d32"
        },
        zoom=11,
        height=650,
    )

    fig.update_layout(
        margin=dict(
            l=0,
            r=0,
            t=40,
            b=0
        ),
        legend_title="Risk Level"
    )

    return fig