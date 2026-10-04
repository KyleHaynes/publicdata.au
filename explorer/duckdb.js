// The one vendored module that needs bundling: DuckDB-WASM imports apache-arrow by bare name.
export { AsyncDuckDB, ConsoleLogger, LogLevel } from '@duckdb/duckdb-wasm';
export { DuckDBHandler } from '@perspective-dev/client/dist/esm/virtual_servers/duckdb.js';
