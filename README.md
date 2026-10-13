# FMCG End-to-End Data Architecture

A Dataform project that loads FMCG master and transaction data from Google Cloud Storage (GCS) into BigQuery, transforms it into warehouse models, and publishes business-friendly views for inventory, sales, customers, and suppliers.

## Architecture

```text
GCS CSV extracts
      |
      v
BigQuery raw_fmcg
      |
      v
stg_fmcg  ->  int_fmcg  ->  mart_fmcg  ->  consumption_fmcg
                                  |
                                  +-- dimensions and facts
                                  +-- inventory and replenishment analytics
                                  +-- ABC and RFM analysis
                                  +-- supplier and purchase-order performance
```

The project is organized into Dataform actions under `definitions/`:

| Layer | Directory | Purpose |
| --- | --- | --- |
| Sources | `definitions/sources/` | Declares raw BigQuery tables and loads the CSV extracts from GCS. |
| Staging | `definitions/staging/` | Cleans, casts, and deduplicates raw records. |
| Intermediate | `definitions/intermediate/` | Builds reusable aggregates such as daily demand, demand statistics, customer sales, and purchase-order performance. |
| Marts | `definitions/marts/` | Creates fact and dimension tables, inventory and replenishment models, ABC classification, and RFM analysis. |
| Consumption | `definitions/consumption/` | Publishes views with business-friendly fields for reporting and analysis. |

Shared business parameters, including the default 95% service level and ABC class cutoffs, are in `includes/constants.js`.

## Data inputs

The load operation expects these seven CSV files in the configured GCS directory:

| GCS object | BigQuery raw table |
| --- | --- |
| `01_master_product.csv` | `master_product` |
| `02_supplier_master.csv` | `supplier_master` |
| `03_customer_master.csv` | `customer_master` |
| `04_inventory_transactions.csv` | `inventory_transactions` |
| `05_purchase_orders.csv` | `purchase_orders` |
| `06_sales_transactions.csv` | `sales_transactions` |
| `07_current_inventory.csv` | `current_inventory` |

Each CSV should have a header row and columns matching the schema in `definitions/sources/load_raw_from_gcs.sqlx`. The load uses `LOAD DATA OVERWRITE`, replacing the corresponding raw table contents on each run; it is not an incremental append.

## Prerequisites

- A Google Cloud project with BigQuery and Dataform APIs enabled.
- A GCS bucket containing the seven CSV extracts.
- A Dataform repository connected to this project, or the Dataform CLI.
- A Google identity or service account with permission to read the GCS objects and create or update BigQuery datasets, tables, views, and assertions.

## Configure the project

Edit `workflow_settings.yaml` before compiling or running the project:

```yaml
dataformCoreVersion: 3.0.52
defaultProject: "YOUR_GCP_PROJECT_ID"
defaultLocation: "US"
defaultDataset: "dwh_fmcg"
defaultAssertionDataset: "dwh_fmcg_assertions"
vars:
  raw_dataset: "raw_fmcg"
  staging_dataset: "stg_fmcg"
  intermediate_dataset: "int_fmcg"
  mart_dataset: "mart_fmcg"
  consumption_dataset: "consumption_fmcg"
  gcs_bucket: "gs://YOUR_BUCKET/fmcg_data"
  snapshot_date: "YYYY-MM-DD"
```

Use a GCS URI that points to the directory containing the input files. Keep the `gs://` prefix. The `snapshot_date` variable is available to the models that need a reporting snapshot date; set it to the date relevant to your source data.

The project uses `@dataform/core` as its declared dependency. Install dependencies from the project directory:

```bash
npm install
```

For a local CLI workflow, install the Dataform CLI if it is not already available:

```bash
npm install --global @dataform/cli
```

## Run the workflow

First compile the project to check the Dataform definitions:

```bash
dataform compile
```

Run the raw load operation separately before the transformation models. This operation reads the files from GCS and overwrites the seven raw tables:

```bash
dataform run --tags load
```

After the raw load succeeds, run the transformation DAG:

```bash
dataform run --exclude-tags load
```

The same sequence can be run from the connected Dataform repository in Google Cloud: compile, execute the `load`-tagged operation, then execute the remaining actions. Keep the load and transformation executions separate so the raw data is available before dependent models run.

## Key outputs

The `consumption_fmcg` dataset contains reporting views, including:

- `vw_inventory_health` — stock, projected inventory, reorder status, and recommended order quantities by SKU and warehouse.
- `vw_sales_trend_monthly` and `vw_product_sales_performance` — monthly trends and product sales metrics.
- `vw_customer_value` — customer value analysis.
- `vw_supplier_scorecard` — supplier performance indicators.
- `vw_inventory_value_summary` — inventory value summaries.

The mart layer also produces dimensions, facts, ABC and RFM analyses, safety-stock and reorder-point calculations, and replenishment recommendations. Dataform assertions are defined on selected models and run with their corresponding workflow actions.

## Customization

- Change dataset names, project, location, GCS URI, and snapshot date in `workflow_settings.yaml`.
- Adjust service-level Z scores and the default service level in `includes/constants.js`.
- Adjust ABC cumulative-value cutoffs in `includes/constants.js`.
- Review the schema and load statements in `definitions/sources/load_raw_from_gcs.sqlx` whenever the source CSV layouts change.

## Notes

- BigQuery storage and query costs, as well as GCS storage and access, depend on usage and region.
- Confirm that the configured BigQuery location is compatible with the GCS bucket and your organization's data residency requirements.
- Do not commit service-account credentials or other secrets. Use Google Cloud authentication and IAM rather than storing credentials in this repository.
