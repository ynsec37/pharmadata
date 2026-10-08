# Export pharmaverseadam to data-raw/raw/pharmaverseadam/; labels and roles from
# the ADaM spec. Run after 01_fetch_sources.py: Rscript data-raw/02_03_export_pharmaverseadam.R

source(here::here("data-raw", "02_01_export_common.R"))

suppressPackageStartupMessages(library(jsonlite))

# Dataset name to spec sheet via study-name suffix (mirrors suffixes_dict in
# pharmaverseadam/data-raw/create_adams_data.R).
SUFFIXES <- c(
  ophtha = "_P",
  onco = "_O",
  vaccine = "_V",
  peds = "_E",
  metabolic = "_M",
  neuro = "_N"
)

spec_dataset <- function(name) {
  suffix <- str_extract(name, "[^_]+$")
  if (!suffix %in% names(SUFFIXES)) {
    return(toupper(name))
  }
  name |>
    str_remove(paste0("_", suffix, "$")) |>
    toupper() |>
    paste0(SUFFIXES[[suffix]])
}

# One dataset_spec() per dataset, keyed and variable-ordered by the spec.
read_adam_specs <- function(file) {
  json <- fromJSON(file, simplifyVector = TRUE)
  # A null Dataset becomes NA and would crash row$Label[[1]]; drop them.
  datasets <- tibble(json$Datasets) |> filter(!is.na(Dataset))
  variables <- tibble(json$Variables)

  map(set_names(unique(datasets$Dataset)), function(dataset) {
    row <- datasets |> filter(Dataset == dataset)
    columns <- variables |>
      filter(Dataset == dataset) |>
      arrange(as.numeric(Order))
    dataset_spec(
      label = clean_label(row$Label[[1]]),
      structure = clean_label(row$Structure[[1]]),
      columns = spec_columns(
        column_name = columns$Variable,
        column_label = columns$Label,
        mandatory = columns$Mandatory,
        role = columns$Role
      )
    )
  })
}

export_pharmaverseadam <- function() {
  dir <- require_source("pharmaverseadam")
  out <- raw_dir("pharmaverseadam")
  specs <- read_adam_specs(path(dir, "inst", "extdata", "adams-specs.json"))

  walk(rda_files(dir), function(file) {
    name <- as.character(path_ext_remove(path_file(file)))
    df <- load_rda(file)
    spec <- specs[[spec_dataset(name)]]
    if (is.null(spec)) {
      # No sheet for this dataset: only the data describes its columns.
      spec <- dataset_spec()
    }

    # Report a specified variable the delivered data lacks, not drop it.
    absent <- setdiff(spec$columns$column_name, names(df))
    if (length(absent) > 0) {
      cli_warn("{name}: spec variables not in data: {absent}")
    }

    # Column order: the specification's variables first, then the rest.
    ordered <- intersect(spec$columns$column_name, names(df))
    df <- df[c(ordered, setdiff(names(df), ordered))]

    # Source spells "Hys Law"; canonical CDISC spelling is "Hy's Law".
    spec$label <- str_replace(
      first_label(c(spec$label, rd_title(dir, name)), name),
      fixed("Hys Law"),
      "Hy's Law"
    )
    export_one(name, df, out, spec)
  })
}

# Run only as a script; sourcing defines functions only.
if (sys.nframe() == 0L) {
  export_pharmaverseadam()
}
