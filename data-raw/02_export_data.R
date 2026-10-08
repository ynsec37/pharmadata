# Run the collection exporters, one per collection named in PROGRAMS.
# Rscript data-raw/02_export_data.R [collection], after data-raw/01_fetch_sources.py.

# Quiet, as in 02_01_export_common.R: here() prints the root as it attaches.
suppressPackageStartupMessages({
  library(cli)
  library(here)
  library(purrr)
})

PROGRAMS <- c(
  pharmaverseadam = "02_03_export_pharmaverseadam.R",
  pharmaversesdtm = "02_04_export_pharmaversesdtm.R",
  cdiscpilotadam = "02_05_export_cdiscpilotadam.R",
  cdiscpilotsdtm = "02_06_export_cdiscpilotsdtm.R"
)

# Run only as a script; sourcing defines PROGRAMS without running the driver.
if (sys.nframe() == 0L) {
  requested <- commandArgs(trailingOnly = TRUE)
  unknown <- setdiff(requested, names(PROGRAMS))
  if (length(unknown) > 0) {
    cli_abort(c(
      "unknown collection{?s}: {unknown}",
      "i" = "expected one of {.val {names(PROGRAMS)}}"
    ))
  }
  selected <- if (length(requested) == 0) names(PROGRAMS) else requested

  walk(selected, function(collection) {
    cli_inform("== {collection}")
    # Sourcing defines the exporter (its nframe guard stays false here);
    # the call below runs it.
    source(here("data-raw", PROGRAMS[[collection]]))
    get(paste0("export_", collection))()
  })
  cli_inform("done.")
}
