# renv.lock: one version per R package the sources use, recorded from this library.
# Run: Rscript data-raw/renv_lock.R

suppressPackageStartupMessages(library(here))

# quarto rmarkdown knitr
library(reticulate)
library(rmarkdown)
library(knitr)

repos <- c(CRAN = "https://packagemanager.posit.co/cran/latest")

deps <- renv::dependencies(path = here::here(), quiet = TRUE)

renv::snapshot(
  packages = unique(deps$Package),
  library = NULL,
  project = NULL,
  exclude = "renv",
  repos = repos,
  prompt = FALSE,
  force = TRUE
)
