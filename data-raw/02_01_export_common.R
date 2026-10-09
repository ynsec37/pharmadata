# Shared helpers of the export stage: read sources, write per dataset
# data-raw/raw/<collection>/<name>{,_meta}.parquet via here().

# Attach quietly.
suppressPackageStartupMessages({
  library(arrow)
  library(cli)
  library(dplyr)
  library(fs)
  library(here)
  library(jsonlite)
  library(purrr)
  library(stringr)
  library(tibble)
})

# The two directories of a collection: its upstream sources, and its output.
source_dir <- function(collection) {
  here("data-raw", "sources", collection)
}

raw_dir <- function(collection) {
  dir <- here("data-raw", "raw", collection)
  dir_create(dir)
  dir
}

# The fetched directory of a collection, or a failure that says what to run.
require_source <- function(collection) {
  dir <- source_dir(collection)
  if (!dir_exists(dir)) {
    cli_abort(c(
      "no fetched sources for {.val {collection}",
      "i" = "run {.code data-raw/01_fetch_sources.py} first"
    ))
  }
  dir
}

# A label as the metadata stores it: the string "null" also means missing.
clean_label <- function(x) {
  if (is.null(x)) {
    return(NA_character_)
  }
  x <- as.character(x)
  replace(x, is.na(x) | x == "null", NA_character_)
}

# First candidate that reads as a label, or `fallback`; blank counts as missing.
first_label <- function(x, fallback) {
  x <- clean_label(x)
  x <- x[!is.na(x) & nzchar(x)]
  if (length(x) == 0) fallback else x[[1]]
}

# A character column as the parquet stores it: valid UTF-8, empty strings as null.
clean_column <- function(x) {
  x <- fix_utf8(x)
  replace(x, !is.na(x) & !nzchar(x), NA_character_)
}

# Strings marked UTF-8 but holding CP1252 bytes: re-decode the invalid bytes.
fix_utf8 <- function(x) {
  x <- enc2utf8(x)
  bad <- !is.na(x) &
    is.na(suppressWarnings(iconv(x, from = "UTF-8", to = "UTF-8")))
  if (any(bad)) {
    x[bad] <- iconv(x[bad], from = "CP1252", to = "UTF-8")
  }
  x
}

# Names of datasets whose source changed for *collection*, or NULL when every
# dataset should be exported (no _changed.json or empty change list). Written
# by data-raw/01b_detect_changes.py after the fetch stage.
changed_filter <- function(collection) {
  file <- here("data-raw", "_changed.json")
  if (!file_exists(file)) {
    return(NULL)
  }
  changed <- jsonlite::fromJSON(file, simplifyVector = TRUE)
  if (is.null(changed[[collection]])) {
    return(character())
  }
  as.character(changed[[collection]])
}

# The first object of an .rda file (the pharmaverse packages hold one per file).
load_rda <- function(file) {
  env <- new.env()
  load(file, envir = env)
  objs <- ls(env)
  if (length(objs) == 0) {
    cli_abort("{.file {file}} contains no objects")
  }
  if (length(objs) > 1) {
    cli_warn(
      "{.file {file}} contains multiple objects: {objs}; using {.val {objs[[1]]}}"
    )
  }
  get(objs[[1]], envir = env)
}

# The datasets a fetched pharmaverse package holds, in file order.
rda_files <- function(dir) {
  dir_ls(path(dir, "data"), glob = "*.rda")
}

# Dataset label fallback: the title of a man/*.Rd page.
# Rd_get_metadata was never exported and disappeared in R 4.5, so read the parsed
# tree. \code{}, \link{} and friends are containers; their text is all a label needs.
rd_text <- function(node) {
  if (is.character(node)) {
    return(node)
  }
  paste(vapply(node, rd_text, character(1)), collapse = "")
}

rd_title <- function(dir, name) {
  rd <- path(dir, "man", paste0(name, ".Rd"))
  if (!file_exists(rd)) {
    return(NULL)
  }
  parsed <- tools::parse_Rd(rd)
  section <- Find(
    function(el) identical(attr(el, "Rd_tag"), "\\title"),
    parsed
  )
  if (is.null(section)) {
    return(NULL)
  }
  title <- str_trim(rd_text(section))
  if (!nzchar(title)) {
    return(NULL)
  }
  title
}

# One row per variable. Joined by name; an absent name misses, a duplicate takes first.
spec_columns <- function(
  column_name = character(),
  column_label = character(),
  mandatory = character(),
  role = character()
) {
  tibble(column_name, column_label, mandatory, role) |>
    distinct(column_name, .keep_all = TRUE)
}

# One dataset as the source describes it: label, structure and variables.
dataset_spec <- function(
  label = NA_character_,
  structure = NA_character_,
  columns = spec_columns()
) {
  list(label = label, structure = structure, columns = columns)
}

# Write one dataset and its metadata table. Column label: the data's, then the
# spec's, then a placeholder.
export_one <- function(name, df, out_dir, spec = dataset_spec()) {
  # Read the metadata before cleaning: mutate() drops the label attribute.
  cols <- tibble(
    column_name = names(df),
    data_label = unname(map_chr(df, ~ clean_label(attr(.x, "label")))),
    column_type = unname(map_chr(df, ~ class(.x)[[1]]))
  )
  df <- mutate(df, across(where(is.character), clean_column))

  meta <- cols |>
    left_join(spec$columns, by = "column_name") |>
    mutate(
      dataset_name = name,
      dataset_label = fix_utf8(spec$label),
      structure = fix_utf8(spec$structure),
      column_label = fix_utf8(
        coalesce(data_label, column_label, "undocumented field")
      ),
      .before = "column_name"
    ) |>
    select(
      dataset_name,
      dataset_label,
      structure,
      column_name,
      column_label,
      column_type,
      mandatory,
      role
    )

  write_parquet(df, path(out_dir, paste0(name, ".parquet")))
  write_parquet(meta, path(out_dir, paste0(name, "_meta.parquet")))
  cli_inform("[{basename(out_dir)}] {name}: {nrow(df)} x {ncol(df)}")
  invisible(meta)
}
