# Tests for the Define-XML reader in 02_02_export_define.R: define_text and read_define
# parse a submission's define.xml into dataset_spec() entries.

# A minimal Define-XML 2.0 document: one ItemGroup (domain DM) with two items.
define_xml <- function() {
  '<?xml version="1.0" encoding="UTF-8"?>
<ODM xmlns="http://www.cdisc.org/ns/odm/v1.3"
     xmlns:def="http://www.cdisc.org/ns/def/v2.0">
  <Study>
    <MetaDataVersion>
      <ItemDef OID="IT.USUBJID" Name="USUBJID" SASFieldName="USUBJID">
        <Description><TranslatedText>Unique Subject Identifier</TranslatedText></Description>
      </ItemDef>
      <ItemDef OID="IT.AGE" Name="AGE" SASFieldName="AGE">
        <Description><TranslatedText>Age</TranslatedText></Description>
      </ItemDef>
      <ItemGroupDef OID="IG.DM" Name="dm" Structure="One record per subject">
        <Description><TranslatedText>Demographics</TranslatedText></Description>
        <ItemRef ItemOID="IT.USUBJID" Mandatory="Yes" Role="Identifier"/>
        <ItemRef ItemOID="IT.AGE" Mandatory="No" Role="Analysis"/>
      </ItemGroupDef>
    </MetaDataVersion>
  </Study>
</ODM>'
}

write_define <- function(dir, xml = define_xml()) {
  path <- file.path(dir, "define.xml")
  writeLines(xml, path)
  path
}

test_that("define_text returns the text of the first matching node", {
  doc <- xml2::read_xml(define_xml())
  group <- xml2::xml_find_first(doc, "//*[local-name()='ItemGroupDef']")
  expect_identical(
    define_text(
      group,
      "./*[local-name()='Description']/*[local-name()='TranslatedText']"
    ),
    "Demographics"
  )
})

test_that("define_text returns NA when the node is absent", {
  doc <- xml2::read_xml(define_xml())
  group <- xml2::xml_find_first(doc, "//*[local-name()='ItemGroupDef']")
  expect_identical(
    define_text(group, "./*[local-name()='Missing']"),
    NA_character_
  )
})

test_that("read_define builds one dataset_spec per ItemGroupDef", {
  dir <- withr::local_tempdir()
  file <- write_define(dir)
  define <- read_define(file)

  expect_named(define, "DM") # keyed by upper-case Name
  dm <- define[["DM"]]
  expect_identical(dm$label, "Demographics")
  expect_identical(dm$structure, "One record per subject")
  expect_identical(dm$columns$column_name, c("USUBJID", "AGE"))
  expect_identical(
    dm$columns$column_label,
    c("Unique Subject Identifier", "Age")
  )
  expect_identical(dm$columns$mandatory, c("Yes", "No"))
  expect_identical(dm$columns$role, c("Identifier", "Analysis"))
})

test_that("read_define uses SASFieldName as the column name", {
  # SASFieldName is the XPT column; Name is the OID's label.
  xml <- sub('SASFieldName="AGE"', 'SASFieldName="AGE"', define_xml())
  dir <- withr::local_tempdir()
  file <- write_define(dir, xml)
  define <- read_define(file)
  expect_identical(define[["DM"]]$columns$column_name[[2]], "AGE")
})

test_that("read_define falls back to Name when SASFieldName is absent", {
  xml <- gsub('SASFieldName="USUBJID"', "", define_xml())
  dir <- withr::local_tempdir()
  file <- write_define(dir, xml)
  define <- read_define(file)
  expect_identical(define[["DM"]]$columns$column_name[[1]], "USUBJID")
})
