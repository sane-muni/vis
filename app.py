import base64
import io

import dash
import matplotlib.pyplot as plt
import pandas as pd
import plotly.graph_objects as go
from dash import dcc, html
from dash.dependencies import Input, Output
from mpl_toolkits.basemap import Basemap
from PIL import Image

# Load the data
mortality_data = pd.read_csv("data/Mortality.csv", skip_blank_lines=True)
incidence_data = pd.read_csv("data/Incidence.csv", skip_blank_lines=True)

# Clean the data by converting "Suppressed" to NaN
mortality_data["Deaths"] = pd.to_numeric(mortality_data["Deaths"], errors="coerce")
incidence_data["Count"] = pd.to_numeric(incidence_data["Count"], errors="coerce")


# Clean and standardize age group labels
def clean_age_group(age_group):
    if "years" in age_group:
        age_group = age_group.replace(" years", "").strip()
    if age_group == "< 1":
        return "0-19"
    elif "1-4" <= age_group <= "19" or "15-19" in age_group:
        return "0-19"
    elif "20-24" <= age_group <= "39":
        return "20-39"
    elif "40-44" <= age_group <= "59":
        return "40-59"
    elif "60-64" <= age_group <= "79":
        return "60-79"
    else:
        return "80+"


# Apply the function to clean the 'Age Group' in both datasets
mortality_data["Age Range"] = mortality_data["Age Group"].apply(clean_age_group)
incidence_data["Age Range"] = incidence_data["Age Groups"].apply(clean_age_group)

# Find min and max years
min_year = min(mortality_data["Year"].min(), incidence_data["Year"].min())
max_year = max(mortality_data["Year"].max(), incidence_data["Year"].max())

# Initialize the Dash app
app = dash.Dash(__name__)


# Function to create a U.S. map
def create_us_map():
    # Create a Basemap instance for the U.S.
    fig, ax = plt.subplots(figsize=(8, 6))
    m = Basemap(
        projection="merc",
        llcrnrlat=24,
        urcrnrlat=50,
        llcrnrlon=-125,
        urcrnrlon=-66,
        resolution="i",
    )

    # Draw coastlines and country boundaries
    m.drawcoastlines()
    m.drawcountries()
    m.drawstates()

    # Save the map as an image in a BytesIO buffer
    buf = io.BytesIO()
    plt.savefig(buf, format="png")
    buf.seek(0)

    # Convert the image to base64
    img_b64 = base64.b64encode(buf.getvalue()).decode("utf-8")

    return img_b64


# Define the layout of the app
app.layout = html.Div(
    [
        html.H1("Cancer Mortality and Incidence Data by Age Range"),
        # Year Slider
        dcc.Slider(
            id="year-slider",
            min=min_year,
            max=max_year,
            step=2,  # Set step to 2
            value=min_year,  # Default value
            marks={year: str(year) for year in range(min_year, max_year + 1, 2)},
            tooltip={"placement": "bottom", "always_visible": True},
        ),
        # Create a two-column layout using Flexbox
        html.Div(
            [
                # US Map (Matplotlib image)
                html.Div(
                    html.Img(
                        id="us-map", src=f"data:image/png;base64,{create_us_map()}"
                    ),
                    style={"width": "48%", "display": "inline-block"},
                ),
                # Graph for bar chart
                html.Div(
                    dcc.Graph(id="bar-chart"),
                    style={"width": "48%", "display": "inline-block", "float": "right"},
                ),
            ],
            style={"display": "flex", "justify-content": "space-between"},
        ),
    ],
    style={"backgroundColor": "#ffffff"},  # Change background web
)


# Define callback to update the bar chart based on the selected year
@app.callback(Output("bar-chart", "figure"), [Input("year-slider", "value")])
def update_chart(selected_year):
    # Filter data based on the selected year
    filtered_mortality_data = mortality_data[mortality_data["Year"] == selected_year]
    filtered_incidence_data = incidence_data[incidence_data["Year"] == selected_year]

    # Group the data by age range and calculate the sum of deaths and incidences
    mortality_by_age = (
        filtered_mortality_data.groupby("Age Range")
        .agg({"Deaths": "sum"})
        .reset_index()
    )
    incidence_by_age = (
        filtered_incidence_data.groupby("Age Range").agg({"Count": "sum"}).reset_index()
    )

    # Merge the mortality and incidence data
    combined_data = pd.merge(
        mortality_by_age, incidence_by_age, on="Age Range", how="outer"
    ).fillna(0)

    # Create the bar chart
    fig = go.Figure()

    # Add bars for incidence and death counts
    fig.add_trace(
        go.Bar(
            x=combined_data["Age Range"],
            y=combined_data["Count"],
            name="Incidence",
            marker_color="#ff7f0e",
        )
    )

    fig.add_trace(
        go.Bar(
            x=combined_data["Age Range"],
            y=combined_data["Deaths"],
            name="Deaths",
            marker_color="gray",
        )
    )

    # Update layout
    fig.update_layout(
        barmode="group",
        title=f"Cancer Mortality and Incidence in {selected_year}",
        xaxis_title="Age Range",
        yaxis_title="Count",
        xaxis={
            "categoryorder": "array",
            "categoryarray": ["0-19", "20-39", "40-59", "60-79", "80+"],
        },
        plot_bgcolor="white",  # Set the plot area background
        paper_bgcolor="#f0f0f0",  # Set the overall figure background
        template="plotly_dark",
        font=dict(color="black"),
    )

    return fig


# Run the app
if __name__ == "__main__":
    app.run_server(debug=True)
