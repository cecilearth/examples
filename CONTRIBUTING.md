# Contributing

Anyone can [collaborate with pull requests](https://docs.github.com/en/pull-requests/collaborating-with-pull-requests).

Please keep in mind we only allow **rebase merging** for pull requests, so make sure to always use `git pull -r` to update your local repo.

## Security first

***Do not include sensitive information such as API keys or database credentials.***

Use environment variables with clear instructions in the code example README file.

## Directory structure

Create a subdirectory for each code example containing:

- all files required e.g. python scripts, `requirements.txt` etc.
- `README.md` file providing as much detail as possible.
- `.gitignore` file to avoid pushing output files.

## Python modules

Only use approved modules for consistency:

- cecil-sdk (coming soon)
- pandas
- geopandas
- matplotlib

## Python code

When using Jupyter notebooks, break the code into cells to make it more readable. Use markdowns to add comments.

Use the [black code formatter](https://github.com/psf/black) to format the notebook or any other Python files.

```sh
pip install "black[jupyter]"
black <filename>
```

## SQL code

Write statements in full uppercase.

Use line breaks and indentation to make it easier to read. For example:

```sql
SELECT
    BOUNDARY,
    VARIABLE,
    YEAR
FROM PROVIDER.DATASET
WHERE AOI_ID = 'fab12345'
ORDER BY
    VARIABLE,
    YEAR
```

## Data processing

Use Snowflake capabilities as much as possible to fetch and compute the data. Please don't fetch the entire data from the database for in-memory manipulation in Python.

## Publishing

Please include a brief description in your pull request following the standard from other code examples (e.g. Capitalised titles, lowercase-dash-directory-names) in our [documentation](https://docs.cecil.earth).
