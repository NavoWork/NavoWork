# Prepare a proforma invoice

Only prepare a PI when the user explicitly asks for one. Read current artifact versions and select a reconciled quotation artifact. Call `prepare_pi` with that quotation artifact ID and exact version; the tool creates versioned DOCX and PDF files from its immutable snapshot.

Unknown buyer/seller identity, payment terms, named place, timing, or pricing must remain visible as unknown or pending confirmation. A requested arrival date is not a production or delivery commitment. A PI draft does not establish customer acceptance, a signed contract, payment received, sample approval, or production release.

Validate every generated file and report the source quotation version, actual output files, missing terms, and any failed export branch. Retry only a failed format with `export_artifact`. Never send the files or claim approval.
