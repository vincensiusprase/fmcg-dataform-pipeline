# FMCG Inventory ML — Forecasting, Classification, Clustering, Optimization

Lanjutan dari [dataset sintetis + Dataform pipeline](../fmcg_dataform) FMCG 2 tahun. Project ini menambahkan 4 model ML di atas mart/consumption layer, sesuai urutan prioritas: **Forecasting → Classification → Clustering → Optimization**.

## Struktur

```
fmcg_ml/
├── config.py                      # BigQuery vs local-mode switch, constants
├── requirements.txt
├── main.py                        # CLI: python main.py {forecast|classify|cluster|optimize|all}
├── data/raw/                      # 7 CSV mentah (copy dari project dataset)
├── outputs/                       # hasil run (gitignored, di-generate ulang tiap run)
└── src/
    ├── data/
    │   ├── local_recompute.py     # replikasi logic Dataform (int_*/mart_*) di pandas
    │   └── loader.py              # entry point tunggal: BigQuery view ATAU local recompute
    ├── forecasting/                # 1. Demand forecasting
    │   ├── data_prep.py
    │   ├── models.py               # naive / Holt-Winters / SARIMA + auto-select
    │   ├── evaluate.py
    │   └── train.py
    ├── classification/             # 2. Stockout/reorder risk
    │   ├── feature_engineering.py
    │   └── train.py
    ├── clustering/                 # 3. RFM & demand pattern clustering
    │   ├── rfm_clustering.py
    │   └── demand_clustering.py
    └── optimization/               # 4. Budget-constrained replenishment (LP/IP)
        └── replenishment_lp.py
```

## Kenapa ada `local_recompute.py`

Supaya project ini bisa dijalankan dan didemokan **tanpa kredensial GCP** (penting untuk portfolio yang dibuka orang lain). `local_recompute.py` mereplikasi logika `.sqlx` di `int_daily_demand`, `int_demand_stats`, `mart_abc_analysis`, `mart_rfm_analysis`, `mart_replenishment_recommendation` — 1:1 di pandas dari 7 CSV mentah di `data/raw/`.

`config.USE_BIGQUERY = True` mengalihkan semua modul untuk query langsung ke `consumption_fmcg`/`mart_fmcg` di BigQuery (butuh `gcloud auth application-default login` dan project ID yang benar). Semua modul ML memanggil `src/data/loader.py`, tidak pernah baca CSV atau BigQuery langsung — jadi tinggal ganti 1 flag untuk pindah mode.

**Catatan konsistensi:** kalau kamu ubah formula di `.sqlx` (misal ganti service level di `includes/constants.js`), update juga `local_recompute.py` supaya kedua mode tetap sinkron.

## Setup

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
python main.py all          # smoke test semua stage sekaligus (forecast dibatasi 15 SKU biar cepat)
```

## 1. Forecasting

```bash
python main.py forecast --limit 20 --horizon 30      # subset dulu, cepat
python main.py forecast --horizon 30                 # full run, ~110 series, beberapa menit
```

- Otomatis pilih **Holt-Winters** (SKU stabil) atau **SARIMA** (SKU volatile/seasonal, dideteksi dari coefficient of variation demand — bukan label buatan), dengan fallback ke **naive rolling-90d average** kalau model gagal konvergen.
- Selalu dibandingkan ke baseline naive (== pendekatan yang dipakai `mart_safety_stock_rop.sqlx` sekarang) di `outputs/forecast_evaluation.csv` — kolom `improvement_vs_naive_%` menunjukkan apakah model ML benar-benar lebih baik dari SQL average sederhana yang sudah ada.
- **Next step production**: kalau model forecast ini terbukti konsisten lebih baik, ganti `avg_daily_demand_90d` di `mart_safety_stock_rop.sqlx` dengan forecast dari sini (materialize `outputs/forecast_results.csv` balik ke BigQuery sebagai tabel baru, join ke situ).

## 2. Classification — Stockout/Reorder Risk

```bash
python main.py classify
```

- **Target**: `replenishment_status IN ('STOCKOUT','REORDER_NOW')` dari mart yang sudah ada — jadi ini belajar meniru & menjelaskan rule-based logic yang sekarang, sekaligus menunjukkan **feature importance** (fitur mana yang paling menentukan risiko).
- **Limitasi yang perlu disebut di portfolio**: dataset ini snapshot 1 titik waktu (110 baris: 55 SKU x 2 warehouse), bukan panel historis. Cukup untuk demo pendekatan & feature importance, tapi metriknya (AUC ~0.85-0.90) jangan diklaim sebagai akurasi produksi.
- **Extending**: untuk versi production-grade, bangun panel historis mingguan dari `int_daily_demand` (rekonstruksi stock level tiap minggu mundur dari `current_inventory` + transaksi) → ribuan baris, baru train/test split beneran per waktu (bukan cross-validation snapshot).

## 3. Clustering

```bash
python main.py cluster
```

Dua sub-analisis:
- **`rfm_clustering.py`** — K-Means di atas Recency/Frequency/Monetary (k dipilih otomatis via silhouette score), lalu **cross-tab dibandingkan ke `rfm_segment` rule-based** yang sudah ada di mart. Ini narasi bagus untuk portfolio: "seberapa mirip hasil unsupervised vs aturan quintile manual, dan customer mana yang diklasifikasikan beda oleh keduanya?"
- **`demand_clustering.py`** — Hierarchical clustering (Ward linkage) SKU berdasarkan pola demand (volume, volatilitas/CV, rasio weekend, amplitudo musiman) — lensa berbeda dari ABC yang murni berbasis value. Berguna untuk menemukan SKU dengan perilaku demand mirip meski value-nya beda kelas ABC.

## 4. Optimization

```bash
python main.py optimize --budget 200000000
```

- Mixed-Integer Program (pakai `PuLP` + CBC solver) yang menjawab pertanyaan yang **tidak bisa dijawab rule-based SQL**: kalau budget procurement terbatas dan tidak cukup untuk memenuhi semua rekomendasi reorder, **SKU mana yang harus diprioritaskan?**
- Objective: maksimalkan unit yang di-reorder, di-weight berdasarkan ABC class (A=3x, B=2x, C=1x), dengan constraint budget (dan opsional kapasitas gudang).
- Constraint MOQ & pack size dimodelkan sebagai integer program (bukan sekadar rounding seperti di `mart_replenishment_recommendation.sqlx`).
- Bandingkan `optimized_order_units` vs `gap_units` (rekomendasi rule-based) di `outputs/optimized_replenishment_plan.csv` untuk melihat trade-off yang dibuat optimizer.

## Menjalankan dengan data BigQuery asli

1. `gcloud auth application-default login`
2. Set `config.USE_BIGQUERY = True`, isi `config.BQ_PROJECT` dengan project ID kamu.
3. Pastikan `consumption_fmcg` dan `mart_fmcg` sudah ter-build lewat Dataform (`dataform run`).
4. Jalankan modul seperti biasa — tidak ada perubahan kode lain yang diperlukan.

## Urutan narasi untuk portfolio write-up

1. **Problem**: rule-based Safety Stock/ROP/ABC/RFM di SQL mart layer sudah jalan, tapi statis — tidak belajar dari data, tidak bisa handle trade-off (budget terbatas).
2. **Forecasting**: buktikan (atau bantah) bahwa model time-series mengalahkan asumsi rolling-average yang dipakai rule-based.
3. **Classification**: jelaskan risk driver stockout secara kuantitatif, bukan cuma threshold ROP biner.
4. **Clustering**: tunjukkan sudut pandang segmentasi tambahan yang tidak tertangkap rule quintile/ABC.
5. **Optimization**: tunjukkan skill "beyond descriptive/predictive" — prescriptive analytics untuk keputusan bisnis nyata (alokasi budget).
