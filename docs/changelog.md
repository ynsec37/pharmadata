# Changelog

## 0.2.2

Refresh the shipped ``pharmaverseadam`` datasets from upstream: ADSL gains two
columns. Dataset tests now derive their expectations from the shipped data, so
future refreshes need no test edits.

## 0.2.1

Record ``parquet_size_bytes`` and ``hash_alg`` alongside ``parquet_hash`` in
``_meta.json``, and ``size_bytes`` alongside source ``sha256`` in
``_collection.json``, enabling full integrity verification of shipped data.

## 0.2.0

Hash-based incremental data refresh: source and parquet hashes drive rebuilds.
Only datasets whose upstream source changed are re-exported and repackaged;
upstream deletions are kept in the library.

## 0.1.0

Initial release.
