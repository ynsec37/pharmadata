# Export pharmaversesdtm to data-raw/raw/pharmaversesdtm/. SDTM columns carry their
# own labels, so read only the dataset label, from the package's man page.
# Run after 01_fetch_sources.py: Rscript data-raw/02_04_export_pharmaversesdtm.R

source(here::here("data-raw", "02_01_export_common.R"))

export_pharmaversesdtm <- function() {
  dir <- require_source("pharmaversesdtm")
  out <- raw_dir("pharmaversesdtm")
  only <- changed_filter("pharmaversesdtm")

  files <- rda_files(dir)
  if (!is.null(only)) {
    files <- files[path_ext_remove(path_file(files)) %in% only]
  }

  walk(files, function(file) {
    name <- as.character(path_ext_remove(path_file(file)))
    export_one(
      name,
      load_rda(file),
      out,
      dataset_spec(label = first_label(rd_title(dir, name), name))
    )
  })
}

# Run only when executed as a script; sourcing defines functions only.
if (sys.nframe() == 0L) {
  export_pharmaversesdtm()
}
