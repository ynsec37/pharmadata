# Tests for the ADaM spec reader in 02_03_export_pharmaverseadam.R: spec_dataset maps
# a delivered dataset name to its specification sheet, and read_adam_specs turns
# the pharmaverseadam JSON into dataset_spec() entries.

test_that("spec_dataset uppercases a name without a study suffix", {
  expect_identical(spec_dataset("adsl"), "ADSL")
  expect_identical(spec_dataset("adlb"), "ADLB")
})

test_that("spec_dataset maps a study suffix to its spec sheet suffix", {
  # Study-specific datasets are <domain>_<suffix>; the sheet is <DOMAIN><SUFFIX>.
  expect_identical(spec_dataset("adsl_ophtha"), "ADSL_P")
  expect_identical(spec_dataset("adsl_onco"), "ADSL_O")
  expect_identical(spec_dataset("adsl_vaccine"), "ADSL_V")
  expect_identical(spec_dataset("adsl_peds"), "ADSL_E")
  expect_identical(spec_dataset("adsl_metabolic"), "ADSL_M")
  expect_identical(spec_dataset("adsl_neuro"), "ADSL_N")
})

test_that("spec_dataset leaves an unknown suffix uppercased", {
  # a suffix not in SUFFIXES is treated as part of the name
  expect_identical(spec_dataset("adsl_unknown"), "ADSL_UNKNOWN")
})

# A minimal pharmaverseadam adams-specs.json: one dataset, two variables.
adam_specs_json <- function() {
  '{
    "Datasets": [
      {"Dataset": "ADSL", "Label": "Subject-Level Analysis", "Structure": "One per subject"},
      {"Dataset": null, "Label": "ignored", "Structure": "ignored"}
    ],
    "Variables": [
      {"Dataset": "ADSL", "Variable": "USUBJID", "Label": "Subject ID", "Order": "1", "Mandatory": "Yes", "Role": "Identifier"},
      {"Dataset": "ADSL", "Variable": "AGE", "Label": "Age", "Order": "2", "Mandatory": "No", "Role": "Analysis"}
    ]
  }'
}

test_that("read_adam_specs drops datasets with a null Dataset", {
  dir <- withr::local_tempdir()
  file <- file.path(dir, "adams-specs.json")
  writeLines(adam_specs_json(), file)
  specs <- read_adam_specs(file)
  expect_named(specs, "ADSL")
})

test_that("read_adam_specs orders variables by the spec Order", {
  dir <- withr::local_tempdir()
  file <- file.path(dir, "adams-specs.json")
  writeLines(adam_specs_json(), file)
  specs <- read_adam_specs(file)
  cols <- specs[["ADSL"]]$columns
  expect_identical(cols$column_name, c("USUBJID", "AGE"))
  expect_identical(cols$column_label, c("Subject ID", "Age"))
  expect_identical(cols$mandatory, c("Yes", "No"))
  expect_identical(cols$role, c("Identifier", "Analysis"))
})

test_that("read_adam_specs carries the dataset label and structure", {
  dir <- withr::local_tempdir()
  file <- file.path(dir, "adams-specs.json")
  writeLines(adam_specs_json(), file)
  specs <- read_adam_specs(file)
  expect_identical(specs[["ADSL"]]$label, "Subject-Level Analysis")
  expect_identical(specs[["ADSL"]]$structure, "One per subject")
})
