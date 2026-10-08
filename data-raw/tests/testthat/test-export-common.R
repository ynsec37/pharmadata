# Tests for 02_01_export_common.R helpers: the label/column cleaners, the rda/Rd
# readers, and the dataset_spec/export_one writers.

test_that("clean_label turns NULL and the string 'null' into NA", {
  expect_identical(clean_label(NULL), NA_character_)
  expect_identical(clean_label("null"), NA_character_)
  expect_identical(clean_label(NA_character_), NA_character_)
  # a real label passes through as a character scalar
  expect_identical(clean_label("Study Identifier"), "Study Identifier")
  # non-character input is coerced
  expect_identical(clean_label(1L), "1")
})

test_that("clean_label is vectorised", {
  expect_identical(
    clean_label(c("a", "null", NA, "b")),
    c("a", NA_character_, NA_character_, "b")
  )
})

test_that("first_label returns the first non-empty candidate or the fallback", {
  expect_identical(first_label(c(NA, "", "a", "b"), "fallback"), "a")
  expect_identical(first_label(c("null", NA), "fallback"), "fallback")
  expect_identical(first_label(character(), "fallback"), "fallback")
  # only zero-length strings are missing: whitespace is a real value
  expect_identical(first_label("   ", "fallback"), "   ")
})

test_that("clean_column turns empty strings into nulls", {
  expect_identical(clean_column(c("a", "", NA)), c("a", NA_character_, NA))
})

test_that("fix_utf8 re-decodes CP1252 bytes marked as UTF-8", {
  # a CP1252 right single quotation mark (0x92) mislabeled as UTF-8
  bad <- "\x92"
  Encoding(bad) <- "UTF-8"
  expect_match(fix_utf8(bad), "\u2019") # U+2019 right single quote
  # valid UTF-8 passes through
  expect_identical(fix_utf8("hello"), "hello")
})

test_that("fix_utf8 does not touch clean strings", {
  plain <- c("a", "b", "c")
  expect_identical(fix_utf8(plain), plain)
})

test_that("load_rda reads the only object of an .rda file", {
  path <- withr::local_tempfile(fileext = ".rda")
  value <- data.frame(x = 1:3)
  save(value, file = path)
  expect_identical(load_rda(path), value)
})

test_that("load_rda aborts on a file with no objects", {
  path <- withr::local_tempfile(fileext = ".rda")
  save(list = character(), file = path)
  expect_error(load_rda(path), "no objects")
})

test_that("load_rda warns on multiple objects and uses the first", {
  path <- withr::local_tempfile(fileext = ".rda")
  aaa <- 1
  bbb <- 2
  save(aaa, bbb, file = path)
  expect_warning(
    result <- load_rda(path),
    "multiple objects"
  )
  expect_identical(result, 1)
})

test_that("rd_title reads the title of a man page", {
  dir <- withr::local_tempdir()
  dir.create(file.path(dir, "man"))
  writeLines(
    c(
      "\\name{adsl}",
      "\\title{Subject-Level Analysis Dataset}",
      "\\description{...}"
    ),
    file.path(dir, "man", "adsl.Rd")
  )
  expect_identical(rd_title(dir, "adsl"), "Subject-Level Analysis Dataset")
})

test_that("rd_title returns NULL when the page is absent", {
  dir <- withr::local_tempdir()
  expect_null(rd_title(dir, "missing"))
})

test_that("spec_columns builds a tibble and drops duplicate names", {
  cols <- spec_columns(
    column_name = c("USUBJID", "AGE", "USUBJID"),
    column_label = c("Subject", "Age", "Subject again"),
    mandatory = c("Yes", "Yes", "Yes"),
    role = c("Identifier", "Analysis", "Identifier")
  )
  expect_s3_class(cols, "tbl_df")
  expect_identical(cols$column_name, c("USUBJID", "AGE"))
  # the first row of a duplicate name wins
  expect_identical(cols$column_label[[1]], "Subject")
})

test_that("dataset_spec wraps its parts into a named list", {
  spec <- dataset_spec(
    label = "ADSL",
    structure = "One record per subject",
    columns = spec_columns(column_name = "USUBJID")
  )
  expect_named(spec, c("label", "structure", "columns"))
  expect_identical(spec$label, "ADSL")
})

test_that("export_one writes a parquet and its metadata table", {
  out <- withr::local_tempdir()
  df <- data.frame(USUBJID = c("01", "02"), AGE = c(30, 40))
  attr(df$USUBJID, "label") <- "Subject ID"
  spec <- dataset_spec(
    label = "Demographics",
    columns = spec_columns(
      column_name = c("USUBJID", "AGE"),
      column_label = c("Subject", "Age"),
      mandatory = c("Yes", ""),
      role = c("Identifier", "")
    )
  )
  meta <- export_one("dm", df, out, spec)

  expect_true(file.exists(file.path(out, "dm.parquet")))
  expect_true(file.exists(file.path(out, "dm_meta.parquet")))

  # the data is written back clean (empty strings became null)
  written <- arrow::read_parquet(file.path(out, "dm.parquet"))
  expect_identical(nrow(written), 2L)

  # data label wins over the spec label (coalesce picks the first non-NA)
  expect_identical(meta$dataset_name[[1]], "dm")
  expect_identical(meta$dataset_label[[1]], "Demographics")
  expect_identical(
    meta$column_label[meta$column_name == "USUBJID"][[1]],
    "Subject ID"
  )
  # AGE has no data label, so the spec label wins
  expect_identical(
    meta$column_label[meta$column_name == "AGE"][[1]],
    "Age"
  )
})

test_that("export_one falls back to the data label when the spec has none", {
  out <- withr::local_tempdir()
  df <- data.frame(USUBJID = "01")
  attr(df$USUBJID, "label") <- "Subject ID"
  meta <- export_one("dm", df, out)
  expect_identical(meta$column_label[[1]], "Subject ID")
})

test_that("export_one uses the placeholder when neither data nor spec labels", {
  out <- withr::local_tempdir()
  df <- data.frame(USUBJID = "01")
  meta <- export_one("dm", df, out)
  expect_identical(meta$column_label[[1]], "undocumented field")
})
