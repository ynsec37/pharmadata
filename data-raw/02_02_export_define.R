# Define-XML 2.0 reader for the CDISC pilots: the only source of dataset label,
# mandatory and role; column labels come from the XPT first.

source(here::here("data-raw", "02_01_export_common.R"))

suppressPackageStartupMessages({
  library(haven)
  library(xml2)
})

# The text of the first node matching an XPath, or NA when there is none.
define_text <- function(node, xpath) {
  found <- xml_find_first(node, xpath)
  if (inherits(found, "xml_missing")) NA_character_ else xml_text(found)
}

# Read Define-XML into one dataset_spec() per ItemGroupDef, keyed by upper-case
# dataset name. local-name() XPath keeps the reader namespace-agnostic.
read_define <- function(file) {
  doc <- read_xml(file)
  items <- xml_find_all(doc, "//*[local-name()='ItemDef']")
  item_oid <- xml_attr(items, "OID")
  # One ItemDef's column name is the SAS variable name, i.e. the XPT column.
  sas_name <- xml_attr(items, "SASFieldName")
  item_name <- set_names(
    ifelse(is.na(sas_name), xml_attr(items, "Name"), sas_name),
    item_oid
  )
  item_label <- set_names(
    map_chr(items, ~ define_text(.x, ".//*[local-name()='TranslatedText']")),
    item_oid
  )

  groups <- xml_find_all(doc, "//*[local-name()='ItemGroupDef']")
  map(groups, function(group) {
    refs <- xml_find_all(group, "./*[local-name()='ItemRef']")
    ref_oid <- xml_attr(refs, "ItemOID")
    dataset_spec(
      label = define_text(
        group,
        "./*[local-name()='Description']/*[local-name()='TranslatedText']"
      ),
      structure = xml_attr(group, "Structure"),
      columns = spec_columns(
        column_name = unname(item_name[ref_oid]),
        column_label = unname(item_label[ref_oid]),
        mandatory = xml_attr(refs, "Mandatory"),
        role = xml_attr(refs, "Role")
      )
    )
  }) |>
    set_names(toupper(xml_attr(groups, "Name")))
}

# Export one CDISC pilot collection: every .xpt in data-raw/sources/, described
# by the Define-XML beside it.
export_pilot <- function(collection) {
  dir <- require_source(collection)
  out <- raw_dir(collection)
  xpt <- dir_ls(dir, glob = "*.xpt")
  if (length(xpt) == 0) {
    cli_abort(c(
      "no {.file *.xpt} file in {.file {dir}}",
      "i" = "run {.code data-raw/01_fetch_sources.py} first"
    ))
  }
  define <- read_define(path(dir, "define.xml"))

  walk(xpt, function(xpt_file) {
    name <- as.character(path_ext_remove(path_file(xpt_file)))
    spec <- define[[toupper(name)]]
    if (is.null(spec)) {
      # A domain the Define-XML does not describe: labels from the XPT, named after itself.
      cli_warn(
        "{name}: no ItemGroupDef in define.xml; labels from the XPT only"
      )
      spec <- dataset_spec(label = name)
    } else {
      spec$label <- first_label(spec$label, name)
    }
    export_one(name, read_xpt(xpt_file), out, spec)
  })
}
