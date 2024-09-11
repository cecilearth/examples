# Plot AOI Time Series Mean AGB

This subdirectory contains a Jupyter notebook that shows how to use Python to connect to Cecil's database, use SQL to fetch mean aboveground biomass (AGB) data from three providers for an AOI and different years, and plot a time series chart for each provider mean AGB and total mean AGB.

## Requirements
- Python version 3.8 or later.

## Install Packages
Run the following command to install the Python packages:
```
pip install -r requirements.txt
```
The Jupyter package will be installed as part of the requirements.

## Set Environment Variables
```
export SNOWFLAKE_ACCOUNT=<<account_identifier>>
export SNOWFLAKE_WAREHOUSE=<<warehouse>>
export SNOWFLAKE_DATABASE=<<database>>
export SNOWFLAKE_USER=<<user>>
export SNOWFLAKE_PASSWORD=<<password>>
```
If you don't have the database credentials, click [here](https://cecil.earth/get-in-touch) to get in touch and request the credentials.

## Start Jupyter Server
Start a Jupyter server:
```
jupyter notebook
```
The Jupyter UI will be opened in your browser. You can also access the UI using this url:

<http://localhost:8888/>

## Run Notebook
 - Double-click on [plot-aoi-times-series-mean-agb.ipynb](plot-aoi-times-series-mean-agb.ipynb) file to open and run the notebook.