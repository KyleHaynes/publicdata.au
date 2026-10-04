## Resubmission

This resubmits 0.4.0, which failed the incoming pre-test on Debian: the
`pd_read()` example read a zstd-compressed Parquet file with an 'arrow' built
without zstd. The example now also requires `arrow::codec_is_available("zstd")`,
and `pd_read()` stops with an explanatory error when the codec is missing.

## R CMD check results

0 errors | 0 warnings | 1 note

* This is a new submission.

## Web access

Every function reads https://publicdata.au/. Examples that need the site run
only when `pd_available()` finds it, so they are skipped rather than failing
when it cannot be reached; when it cannot, every function stops with a message
naming the site. Tests use mocked responses, and the one test that reads the
live site is skipped on CRAN.

## File system

Nothing is written outside the session's temporary directory unless the user
asks. `pd_download()` saves to `tempdir()` unless given a path, and
`pd_connect()` keeps 'DuckDB''s 'httpfs' extension in the temporary directory
unless `shared_home = TRUE`; its example and `pd_tbl()`'s run only in an
interactive session, since they download that extension. The examples of
`pd_boundaries()` and `pd_join_boundaries()` also run only interactively,
because a boundary file is tens of megabytes. The download cache
in `tools::R_user_dir("publicdataau", "cache")` is used only when the user
passes `cache = TRUE` or sets `options(publicdataau.cache = TRUE)`; the
examples and tests never turn it on.

## Vignette

The vignette is precomputed: it is knitted from `vignettes/publicdataau.Rmd.orig`
against the live site before release, so building it needs no network.

## Test environments

* Local Linux, R 4.4.3: R CMD check --as-cran --run-donttest, online, with
  the site unreachable, and with an empty HOME.
* win-builder, R-devel, Windows Server 2022 x64.
