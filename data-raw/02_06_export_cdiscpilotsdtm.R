# Export the CDISC pilot SDTM datasets to data-raw/raw/cdiscpilotsdtm/ as parquet.
# Run after 01_fetch_sources.py: Rscript data-raw/02_06_export_cdiscpilotsdtm.R

source(here::here("data-raw", "02_02_export_define.R"))

export_cdiscpilotsdtm <- function() {
  export_pilot("cdiscpilotsdtm")
}

# Run only when executed as a script; sourcing defines functions only.
if (sys.nframe() == 0L) {
  export_cdiscpilotsdtm()
}
