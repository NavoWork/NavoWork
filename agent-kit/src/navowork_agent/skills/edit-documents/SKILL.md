# Edit managed business files

When the user explicitly asks to modify an uploaded DOCX or XLSX, first read the file and identify exact paragraph, table, sheet, and cell locations. Load this Skill, call `create_working_copy` with the authorized `file_id`, then use the returned artifact ID, version baseline, and working file ID for `edit_file`. Never pass a physical path or attempt to modify the original.

DOCX supports paragraph text, table-cell text, image insertion, and replacing an inline picture by its zero-based image index. Basic paragraph/cell formatting is available. XLSX supports cell values, supported formulas, number format, bold/italic, fill and alignment, range copy/paste within one sheet, and row/column insertion or deletion in formula-free workbooks. Formula-bearing workbooks reject structural changes because reference shifts cannot be guaranteed.

Apply edits in small batches, validate the resulting version, and report each changed location and any unsupported operation. Every save creates a new immutable working-copy version. Structural validation does not replace visual review in Word or Excel.
