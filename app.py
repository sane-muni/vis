import matplotlib

matplotlib.use("Agg")  # Set non-GUI backend
import dash
import geopandas as gpd
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from dash import dcc, html
from dash.dependencies import Input, Output

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

# Load the shapefile for the U.S. map
gdf = gpd.read_file("data/us-states-shapefile/ne_110m_admin_1_states_provinces.shp")

# Define the bounding box for the contiguous U.S.
min_long = -125  # West longitude
max_long = -66  # East longitude
min_lat = 24  # South latitude
max_lat = 49  # North latitude

# Clip the shapefile to the bounding box
gdf = gdf.cx[min_long:max_long, min_lat:max_lat]


# Merge mortality data with U.S. shapefile data based on state names
def merge_mortality_with_shapefile():
    # Clean the state names in the mortality data
    mortality_data["State"] = mortality_data["State"].str.strip()
    mortality_data["State"] = mortality_data["State"].str.title()

    # Merge with the shapefile
    merged_data = gdf.merge(
        mortality_data, left_on="name", right_on="State", how="left"
    )

    # Drop rows where 'Deaths' is NaN (states with no mortality data)
    merged_data = merged_data.dropna(subset=["Deaths"])

    return merged_data


# Function to create a U.S. map with colored states based on selected data type (Mortality or Incidence)
# Aggregate data by State and Year, summing the Count or Deaths
def aggregate_data(data, value_column):
    return data.groupby(["State", "Year"])[value_column].sum().reset_index()


# Aggregate both mortality and incidence data
incidence_data_aggregated = aggregate_data(incidence_data, "Count")
mortality_data_aggregated = aggregate_data(mortality_data, "Deaths")


# Merge the aggregated data with the shapefile
def merge_data_with_shapefile(aggregated_data, data_type="incidence"):
    if data_type == "incidence":
        value_column = "Count"
    else:
        value_column = "Deaths"

    # Merge with the shapefile
    merged_data = gdf.merge(
        aggregated_data, left_on="name", right_on="State", how="left"
    )

    # Drop rows where the value column is NaN (states with no data)
    merged_data = merged_data.dropna(subset=[value_column])

    return merged_data


# Example of creating the map with aggregated data
def create_us_map_with_aggregated_data(selected_year, data_type="incidence"):
    # Filter the aggregated data by year
    if data_type == "incidence":
        filtered_data = incidence_data_aggregated[
            incidence_data_aggregated["Year"] == selected_year
        ]
    else:
        filtered_data = mortality_data_aggregated[
            mortality_data_aggregated["Year"] == selected_year
        ]

    # Merge with the shapefile
    merged_data = merge_data_with_shapefile(filtered_data, data_type)

    if data_type == "incidence":
        value_column = "Count"
        color_scale = "Oranges"
    else:
        value_column = "Deaths"
        color_scale = "Greys"

    # Create the choropleth map
    fig = px.choropleth(
        merged_data,
        geojson=merged_data.geometry,
        locations=merged_data.index,
        color=value_column,
        color_continuous_scale=color_scale,
        hover_name="name",
        hover_data={value_column: True},
        title=f"Number of {data_type.title()} by State in {selected_year}",
        labels={value_column: f"{data_type.title()}"},
    )

    # Customize hover to remove index
    fig.update_traces(
        customdata=merged_data[[value_column]].values,
        hovertemplate="<br>".join(
            [
                "<b>%{hovertext}</b>",  # Hover name (state)
                f"{data_type.title()}: %{{customdata[0]:,}}",
            ]
        ),
    )

    fig.update_geos(fitbounds="locations", visible=False)
    fig.update_layout(
        margin={"r": 0, "t": 40, "l": 0, "b": 0},
        geo=dict(showland=True, landcolor="white"),
        template="plotly",
    )

    return fig


# Initialize the Dash app
app = dash.Dash(__name__)

# Layout for the app
app.layout = html.Div(
    [
        html.H1(
            "Cancer Mortality and Incidence Data",
            style={"text-align": "center"},
        ),
        html.Div(
            [
                # US Map (Plotly choropleth map)
                html.Div(
                    [
                        dcc.Graph(id="us-map", style={"width": "100%"}),
                        dcc.RadioItems(
                            id="data-selector",
                            options=[
                                {"label": "Incidence", "value": "incidence"},
                                {"label": "Mortality", "value": "mortality"},
                            ],
                            value="incidence",
                            labelStyle={
                                "display": "inline-block",
                                "margin-right": "10px",
                            },
                            style={"width": "100%"},
                        ),
                    ],
                    style={
                        "width": "48%",
                        "display": "inline-block",
                        "border": "1px solid black",
                    },
                ),
                # Bar chart (Plotly bar chart)
                html.Div(
                    dcc.Graph(id="bar-chart"),
                    style={"width": "48%", "display": "inline-block", "float": "right"},
                ),
            ],
            style={"display": "flex", "justify-content": "space-between"},
        ),
        html.Div(
            [
                html.Br(),
                # Year slider
                dcc.Slider(
                    id="year-slider",
                    min=min_year,
                    max=max_year,
                    step=1,
                    value=min_year,
                    marks={
                        year: str(year) for year in range(min_year, max_year + 1, 2)
                    },
                    tooltip={"placement": "bottom", "always_visible": True},
                ),
            ]
        ),
    ],
    style={"backgroundColor": "#ffffff"},
)


# Callback to update the US map based on the selected year and data type
@app.callback(
    Output("us-map", "figure"),
    [Input("year-slider", "value"), Input("data-selector", "value")],
)
def update_map(selected_year, data_type):
    return create_us_map_with_aggregated_data(selected_year, data_type)


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
