# Run the export-stage testthat suite: Rscript data-raw/tests/testthat.R
# testthat auto-sources helper-export.R, which loads the export scripts.

library(testthat)

testthat::test_dir(
  here::here("data-raw", "tests", "testthat"),
  reporter = "summary"
)
