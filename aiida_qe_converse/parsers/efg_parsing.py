"""
Pure-Python parsing of ``qe-efg.x`` stdout.

This module has **no AiiDA dependency** so the parsing logic can be unit-tested
on its own.  The aiida ``QeEfgParser`` (in ``qeefg.py``) is a thin wrapper that
calls :func:`parse_efg_output` and stores the result as an ``orm.Dict``.

The exact stdout formats are defined in ``QE-CONVERSE/src/efg.f90``:

* tensor blocks, header e.g. ``----- total EFG symmetrized (Ha/bohr^2) -----``;
  each atom is 3 rows ``<elem> <na>  <c1> <c2> <c3>`` (Fortran
  ``'(5X,A,I3,2X,3(F14.6,2X))'``), blank line between atoms.
* a per-atom principal-axis block (header ``NMR/NQR QUADRUPOLAR PARAMETERS:``)
  with ``Vxx=/Vyy=/Vzz=`` lines carrying value + ``axis=( ex ey ez )``.
* a final summary block (header ``=========== NMR/NQR QUADRUPOLAR PARAMETERS
  ===========``), one line per atom with ``Cq``/``eta``/``nu_Q`` (or
  ``Vzz``/``eta`` when ``Q == 0``).

Atoms are keyed by their **1-based sequential index** (``"1"``, ``"2"``, ...)
as printed in the ``do na = 1, nat`` loops; this is robust against the rare
case where a custom 3-character kind name ending in a digit merges with the
atom index in the fixed-width Fortran field.
"""

import re

# A tensor row: a label prefix followed by exactly three contiguous floats at
# end-of-line.  The "three contiguous floats" anchor excludes the summary /
# axis lines (which interleave non-numeric tokens such as ``eta=`` or end in
# ``)``).
_TENSOR_ROW_RE = re.compile(
    r'^\s*(?P<label>.+?)\s+(?P<c1>-?\d+\.\d+)\s+(?P<c2>-?\d+\.\d+)\s+(?P<c3>-?\d+\.\d+)\s*$'
)

# A principal-value line: ``Vxx= <val>   axis=( ex ey ez )``.
_PRINC_RE = re.compile(
    r'(?P<which>V[xyz][xyz])=\s*(?P<val>-?\d+\.\d+).*?'
    r'axis=\(\s*(?P<e1>-?\d+\.\d+)\s+(?P<e2>-?\d+\.\d+)\s+(?P<e3>-?\d+\.\d+)\s*\)'
)

# Summary markers.  Fortran writes them as literals with no space around ``=``
# (the descriptive header lines use ``Cq = ...`` *with* spaces, so they do not
# match these patterns).  ``Q=``/``I=`` use a negative lookbehind so the ``Q=``
# inside ``nu_Q=`` is not mistaken for the standalone quadrupole moment.
_Q_RE = re.compile(r'(?<![A-Za-z_])Q=\s*(-?\d+\.\d+)')
_CQ_RE = re.compile(r'Cq=\s*(-?\d+\.\d+)')
_ETA_RE = re.compile(r'eta=\s*(-?\d+\.\d+)')
_NUQ_RE = re.compile(r'nu_Q=\s*(-?\d+\.\d+)')
_I_RE = re.compile(r'(?<![A-Za-z_])I=\s*(-?\d+\.\d+)')
_VZZ_RE = re.compile(r'Vzz=\s*(-?\d+\.\d+)')

# A summary data line starts with an element label + integer index and carries
# an ``eta=`` token (true for every summary case).
_SUMMARY_DATA_RE = re.compile(r'^\s*[A-Za-z]\S*\s+\d+\b.*eta=')


def _find_line(lines, needle, start=0):
    """Return the index of the first line containing ``needle`` (or None)."""
    for i in range(start, len(lines)):
        if needle in lines[i]:
            return i
    return None


def _label_to_element(label):
    """Best-effort element symbol from a printed ``<elem> <na>`` label prefix."""
    tokens = label.split()
    if tokens:
        return tokens[0]
    return label.strip()


def _collect_tensor_block(lines, start):
    """Collect consecutive 3-row tensor groups starting at line ``start``.

    Stops at the first non-blank line that is not a tensor row (e.g. the next
    section header).  Returns ``(tensors, labels)`` where ``tensors`` is a list
    of 3x3 lists and ``labels`` the element label of each atom.
    """
    tensors, labels = [], []
    rows, label = [], None
    i = start
    while i < len(lines):
        line = lines[i]
        match = _TENSOR_ROW_RE.match(line)
        if match:
            if not rows:
                label = _label_to_element(match.group('label'))
            rows.append([float(match.group('c1')),
                         float(match.group('c2')),
                         float(match.group('c3'))])
            if len(rows) == 3:
                tensors.append(rows)
                labels.append(label)
                rows = []
        elif line.strip() == '':
            pass  # blank line separates atoms; keep scanning
        else:
            break  # next section header -> end of tensor block
        i += 1
    return tensors, labels


def _parse_principal_block(lines, nat):
    """Parse per-atom principal values + eigenvectors (in atom order)."""
    principal_values, eigenvectors = {}, {}
    matches = []
    for line in lines:
        m = _PRINC_RE.search(line)
        if m:
            matches.append(m)
    # Matches come as [Vxx, Vyy, Vzz, Vxx, Vyy, Vzz, ...] in atom order.
    for group_idx in range(len(matches) // 3):
        na = str(group_idx + 1)
        pv, ev = {}, {}
        for offset in range(3):
            m = matches[group_idx * 3 + offset]
            which = m.group('which')  # Vxx / Vyy / Vzz
            pv[which] = float(m.group('val'))
            ev[which] = [float(m.group('e1')), float(m.group('e2')), float(m.group('e3'))]
        principal_values[na] = pv
        eigenvectors[na] = ev
    return principal_values, eigenvectors


def _parse_summary_block(lines, nat):
    """Parse the final ``=== NMR/NQR QUADRUPOLAR PARAMETERS ===`` summary."""
    header = None
    for i, line in enumerate(lines):
        if '===========' in line and 'NMR/NQR QUADRUPOLAR PARAMETERS' in line:
            header = i
            break
    quad = {}
    if header is None:
        return quad

    count = 0
    for line in lines[header + 1:]:
        if not _SUMMARY_DATA_RE.match(line):
            continue
        count += 1
        na = str(count)
        params = {}
        m = _Q_RE.search(line)
        if m:
            params['Q'] = float(m.group(1))
        m = _CQ_RE.search(line)
        if m:
            params['Cq'] = float(m.group(1))
        m = _ETA_RE.search(line)
        if m:
            params['eta'] = float(m.group(1))
        m = _I_RE.search(line)
        if m:
            params['I'] = float(m.group(1))
        m = _NUQ_RE.search(line)
        if m:
            params['nu_Q'] = float(m.group(1))
        m = _VZZ_RE.search(line)
        if m:
            params['Vzz'] = float(m.group(1))
        quad[na] = params
        if count >= nat:
            break
    return quad


def parse_efg_output(text):
    """Parse ``qe-efg.x`` stdout into a structured dictionary.

    Returns a dict with:
        ``natoms``: number of atoms parsed from the symmetrized tensor block;
        ``efg_tensors``: ``{na: 3x3}`` symmetrized EFG (Ha/bohr^2);
        ``principal_values``: ``{na: {'Vxx','Vyy','Vzz'}}`` (Ha/bohr^2);
        ``eigenvectors``: ``{na: {'Vxx','Vyy','Vzz': [ex,ey,ez]}}``;
        ``quadrupolar_parameters``: ``{na: {'Q','Cq','eta','I','nu_Q','Vzz'}}``
            (keys present only when printed by the code);
        ``elements``: ``{na: element_label}``;
        ``converged``: True if a symmetrized tensor block with >=1 atom was found;
        ``warnings``: list of strings.

    Atom keys ``na`` are 1-based sequential strings (``"1"``, ``"2"`` ...).
    """
    result = {
        'natoms': 0,
        'efg_tensors': {},
        'principal_values': {},
        'eigenvectors': {},
        'quadrupolar_parameters': {},
        'elements': {},
        'converged': False,
        'warnings': [],
    }

    lines = text.split('\n')

    sym_idx = _find_line(lines, 'total EFG symmetrized')
    if sym_idx is None:
        result['warnings'].append('No "total EFG symmetrized" block found in output')
        return result

    tensors, labels = _collect_tensor_block(lines, sym_idx + 1)
    nat = len(tensors)
    result['natoms'] = nat
    for k, (tensor, label) in enumerate(zip(tensors, labels)):
        na = str(k + 1)
        result['efg_tensors'][na] = tensor
        result['elements'][na] = label

    if nat == 0:
        result['warnings'].append('Symmetrized EFG block found but no atoms parsed')
        return result

    principal_values, eigenvectors = _parse_principal_block(lines, nat)
    result['principal_values'] = principal_values
    result['eigenvectors'] = eigenvectors

    result['quadrupolar_parameters'] = _parse_summary_block(lines, nat)

    if len(result['principal_values']) < nat:
        result['warnings'].append('Principal-axis block missing for some atoms')
    if len(result['quadrupolar_parameters']) < nat:
        result['warnings'].append('Summary block missing for some atoms')

    result['converged'] = True
    return result
