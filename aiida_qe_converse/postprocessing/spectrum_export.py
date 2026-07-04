"""Serialize plotted spectrum data to CSV text (pure Python, no AiiDA).

The GUI exports exactly what is plotted: metadata as ``#``-commented header
lines, then one or more data blocks. Each block starts with its column names
as a plain (uncommented) CSV row, so spreadsheets show them aligned over the
data and ``pandas.read_csv(f, comment='#')`` picks them up as the header.
Blocks are separated by two blank lines (gnuplot ``index`` convention).
"""

_TITLE = "EFG quadrupolar NMR spectrum - aiida-qe-converse"


def _fmt_value(value):
    if isinstance(value, bool):
        return "yes" if value else "no"
    if isinstance(value, float):
        return "%.8g" % value
    return str(value)


def spectrum_csv(meta, blocks, title=_TITLE):
    """Build CSV text from metadata and data blocks.

    :param meta: sequence of ``(key, value)`` pairs (or dict) rendered as
        ``# key = value`` header lines, in order.
    :param blocks: sequence of ``(block_title, column_names, columns)`` where
        ``columns`` is a list of equal-length sequences (numbers or strings),
        one per column name.
    :param title: first ``#`` header line.
    :returns: the full CSV file content as a string.
    """
    lines = [f"# {title}"]
    items = meta.items() if hasattr(meta, "items") else meta
    for key, value in items:
        lines.append(f"# {key} = {_fmt_value(value)}")
    for block_title, column_names, columns in blocks:
        lines.append("")
        lines.append("")
        lines.append(f"# {block_title}")
        lines.append(",".join(column_names))
        if len(columns) != len(column_names):
            raise ValueError("column_names and columns length mismatch")
        n_rows = {len(c) for c in columns}
        if len(n_rows) > 1:
            raise ValueError("columns have differing lengths")
        for row in zip(*columns):
            lines.append(",".join(_fmt_value(v) for v in row))
    return "\n".join(lines) + "\n"
