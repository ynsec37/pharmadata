# Export the CDISC pilot ADaM datasets to data-raw/raw/cdiscpilotadam/ as parquet.
# Run after 01_fetch_sources.py: Rscript data-raw/02_05_export_cdiscpilotadam.R

source(here::here("data-raw", "02_02_export_define.R"))

export_cdiscpilotadam <- function() {
  export_pilot("cdiscpilotadam")
}

# Run only when executed as a script; sourcing defines functions only.
if (sys.nframe() == 0L) {
  export_cdiscpilotadam()
}
