# FMCG Inventory & Supply Chain — Dataform Project (GCS → BigQuery)

Transformasi dari data mentah (CSV di GCS) sampai mart layer siap analisis (ABC, RFM, Safety Stock, ROP, Dynamic Replenishment, Supplier Performance), menggunakan **Dataform Core 3.0** di BigQuery.

## 1. Struktur project

```
fmcg_dataform/
├── workflow_settings.yaml        # project id, dataset names, GCS bucket, vars
├── package.json
├── includes/
│   └── constants.js              # Z-score service level, ABC cutoffs
└── definitions/
    ├── sources/
    │   ├── load_raw_from_gcs.sqlx    # type: operations — LOAD DATA dari GCS
    │   ├── src_master_product.sqlx   # type: declaration (raw_fmcg.*)
    │   ├── src_supplier_master.sqlx
    │   ├── src_customer_master.sqlx
    │   ├── src_inventory_transactions.sqlx
    │   ├── src_purchase_orders.sqlx
    │   ├── src_sales_transactions.sqlx
    │   └── src_current_inventory.sqlx
    ├── staging/                  # stg_* : typing, trim, dedup, null-handling
    │   ├── stg_master_product.sqlx
    │   ├── stg_supplier_master.sqlx
    │   ├── stg_customer_master.sqlx
    │   ├── stg_inventory_transactions.sqlx
    │   ├── stg_purchase_orders.sqlx
    │   ├── stg_sales_transactions.sqlx
    │   └── stg_current_inventory.sqlx
    ├── intermediate/             # int_* : reusable aggregations
    │   ├── int_daily_demand.sqlx
    │   ├── int_demand_stats.sqlx
    │   ├── int_po_performance.sqlx
    │   ├── int_sku_annual_value.sqlx
    │   └── int_customer_sales_agg.sqlx
    └── marts/                    # dim_* / fact_* / mart_*
        ├── dim_product.sqlx
        ├── dim_supplier.sqlx
        ├── dim_customer.sqlx
        ├── fact_inventory_transactions.sqlx
        ├── fact_sales.sqlx
        ├── fact_purchase_orders.sqlx
        ├── mart_current_inventory.sqlx
        ├── mart_abc_analysis.sqlx
        ├── mart_rfm_analysis.sqlx
        ├── mart_safety_stock_rop.sqlx
        ├── mart_replenishment_recommendation.sqlx
        └── mart_supplier_performance.sqlx
```

## 2. Alur data

```
GCS (7 CSV)
   │  LOAD DATA (definitions/sources/load_raw_from_gcs.sqlx, tag "load")
   ▼
raw_fmcg.*  (declared via src_*.sqlx)
   │
   ▼
stg_fmcg.stg_*        <- cleaning: cast type, trim, dedup, null backfill
   │
   ▼
int_fmcg.int_*        <- daily demand calendar, demand stats, PO performance,
   │                      annual SKU value, customer RFM base
   ▼
mart_fmcg.dim_*/fact_*/mart_*   <- siap dipakai BI tool (Looker Studio/Power BI/Tableau)
```

## 3. Setup

1. **Buat dataset & bucket**
   ```bash
   bq mk --location=asia-southeast2 raw_fmcg
   bq mk --location=asia-southeast2 stg_fmcg
   bq mk --location=asia-southeast2 int_fmcg
   bq mk --location=asia-southeast2 mart_fmcg
   gsutil mb -l asia-southeast2 gs://your-bucket-name
   gsutil cp 0*.csv gs://your-bucket-name/fmcg/
   ```
2. Edit `workflow_settings.yaml` → isi `defaultProject`, `defaultLocation`, dan `vars.gcs_bucket` sesuai project/bucket kamu. **`vars.gcs_bucket` harus full URI dengan skema `gs://`**, contoh `gs://gcs-raw-dev/fmcg_data` — bukan `gcs-raw-dev/fmcg_data`, karena `LOAD DATA ... FROM FILES(uris=[...])` butuh URI lengkap.
   > Catatan penting: properti di `workflow_settings.yaml` **tidak** diakses dengan nama yang sama persis di kode sqlx. Mapping resminya: `defaultProject` → `dataform.projectConfig.defaultDatabase`, `defaultDataset` → `dataform.projectConfig.defaultSchema`, `defaultAssertionDataset` → `dataform.projectConfig.assertionSchema`. `vars.*` tetap diakses sebagai `dataform.projectConfig.vars.*`.
3. **Install dependencies** (dari root project):
   ```bash
   npm install
   ```
4. **Load raw data dari GCS** (jalankan operations dulu, terpisah dari DAG transform):
   ```bash
   dataform run --tags load
   ```
   Jadwalkan step ini sebelum full run — misalnya via Cloud Composer/Workflows yang trigger setelah file baru landing di GCS (Cloud Storage notification → Pub/Sub → Cloud Function/Workflow → `dataform run --tags load`).
5. **Jalankan transformasi staging → mart**:
   ```bash
   dataform run --tags staging,intermediate,mart
   ```
   atau cukup `dataform run` untuk full DAG (Dataform otomatis skip operations "load" di run biasa kalau tidak ditag, tergantung orkestrasi — disarankan pisahkan load sebagai step tersendiri seperti di atas).
6. **Compile check** sebelum deploy:
   ```bash
   dataform compile
   ```

## 4. Catatan desain

- **Idempotent**: `LOAD DATA OVERWRITE` di raw layer + `type: table` (full refresh) di staging/intermediate/mart membuat pipeline aman dijalankan berulang.
- **Data quality**: dedup dan null-handling terjadi di staging layer (`stg_inventory_transactions`, `stg_sales_transactions`, dst.) — lihat kolom `is_backfilled_cost` untuk audit trail baris yang di-backfill.
- **Assertions**: setiap tabel dim/fact punya `uniqueKey`/`nonNull` assertion bawaan Dataform (`dwh_fmcg_assertions` dataset) — jalankan `dataform run --actions <table> --include-dependencies` untuk validasi.
- **ABC & RFM tidak di-hardcode**: dihitung ulang di `mart_abc_analysis` dan `mart_rfm_analysis` langsung dari transaksi, sesuai prinsip di dataset awal.
- **Safety Stock** pakai formula combined-variability (memperhitungkan variabilitas demand *dan* lead time), plus kolom `safety_stock_simple` untuk versi buku teks dasar. Ubah target service level di `includes/constants.js` (`default_service_level`).
- Untuk scale up ke production: pertimbangkan `type: "incremental"` pada `fact_inventory_transactions`/`fact_sales` begitu volume harian sudah jelas, dengan `uniqueKey` sebagai merge key.

## 5. Contoh query dari mart layer

```sql
-- SKU yang butuh reorder segera, urut berdasarkan nilai ABC
SELECT sku_id, warehouse_id, abc_class, current_stock, reorder_point,
       projected_stock, recommended_order_qty, replenishment_status
FROM `your-project.mart_fmcg.mart_replenishment_recommendation`
WHERE replenishment_status IN ('REORDER_NOW','STOCKOUT')
ORDER BY abc_class, projected_stock;

-- Customer champions untuk campaign retensi
SELECT customer_id, rfm_segment, recency_days, frequency_orders, monetary_total
FROM `your-project.mart_fmcg.mart_rfm_analysis`
WHERE rfm_segment = 'Champions';
```
