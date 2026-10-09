# Changelog

## 0.2.0

Hash-based incremental data refresh: source and parquet hashes drive rebuilds.
Only datasets whose upstream source changed are re-exported and repackaged;
upstream deletions are kept in the library.

## 0.1.0

Initial release.
