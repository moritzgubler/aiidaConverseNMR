"""
Helper that reconstructs a ``qe-efg.x`` stdout from the exact Fortran formats in
``QE-CONVERSE/src/efg.f90``.  Used by the parser unit tests so the parser is
validated against the real on-disk layout (fixed-width fields, blank-line atom
separators, the two header variants, etc.) without needing a QE run.
"""


def _tensor_row(elem, na, row):
    # Fortran '(5X,A,I3,2X,3(F14.6,2X))' with atm a length-3 character.
    s = '     ' + elem.ljust(3) + f'{na:3d}' + '  '
    for v in row:
        s += f'{v:14.6f}' + '  '
    return s.rstrip()


def _tensor_block(header, atoms):
    """atoms: list of (elem, na, 3x3). Returns list of lines."""
    lines = ['     ' + header]
    for elem, na, tensor in atoms:
        for row in tensor:
            lines.append(_tensor_row(elem, na, row))
        lines.append('')  # blank line between atoms
    return lines


def _principal_lines(elem, na, principal, axes):
    # Fortran '(5X,A,I3,4X,A,F10.4,4X,A,3F10.6,A)'
    out = []
    for which in ('Vxx', 'Vyy', 'Vzz'):
        axis = axes[which]
        s = ('     ' + elem.ljust(3) + f'{na:3d}' + '    '
             + f'{which}=' + f'{principal[which]:10.4f}' + '    '
             + 'axis=(' + ''.join(f'{e:10.6f}' for e in axis) + ')')
        out.append(s)
    return out


def build_sample_output(atoms):
    """Build a full qe-efg stdout.

    Args:
        atoms: list of dicts with keys
            elem, na, tensor(3x3), principal{Vxx,Vyy,Vzz}, axes{Vxx,Vyy,Vzz->[3]},
            Q, I, Cq, eta, nu_Q  (Q==0 -> summary prints Vzz/eta only).
    """
    lines = []
    lines.append('     Computing EFG tensors ...')
    lines.append('')

    # an earlier 'total EFG' (non-symmetrized) block to make sure the parser
    # locks onto the *symmetrized* one.
    tot = [(a['elem'], a['na'], a['tensor']) for a in atoms]
    lines += _tensor_block('----- total EFG (Ha/bohr^2) -----', tot)
    lines += _tensor_block('----- total EFG symmetrized (Ha/bohr^2) -----', tot)

    # per-atom principal-axis block
    lines.append('     NMR/NQR QUADRUPOLAR PARAMETERS:')
    lines.append('     Vxx, Vyy, Vzz: EFG principal values (Ha/bohr^2)')
    lines.append('')
    for a in atoms:
        lines += _principal_lines(a['elem'], a['na'], a['principal'], a['axes'])
        if a['Q'] != 0.0:
            lines.append('     ' + a['elem'].ljust(3) + f'{a["na"]:3d}' + '  '
                         + 'Q=' + f'{a["Q"]:10.4f}' + ' 1e-30 m^2'
                         + '  ' + 'Cq=' + f'{a["Cq"]:12.4f}' + ' MHz'
                         + '  ' + 'eta=' + f'{a["eta"]:8.5f}')
            if a['I'] >= 1.0:
                lines.append('     ' + a['elem'].ljust(3) + f'{a["na"]:3d}' + '  '
                             + 'I=' + f'{a["I"]:6.1f}' + '    '
                             + 'nu_Q=' + f'{a["nu_Q"]:12.4f}' + ' MHz')
        else:
            lines.append('     ' + a['elem'].ljust(3) + f'{a["na"]:3d}' + '  '
                         + 'eta=' + f'{a["eta"]:8.5f}')
        lines.append('')

    # final summary block
    lines.append('     =========== NMR/NQR QUADRUPOLAR PARAMETERS ===========')
    lines.append('     Cq = e*Q*Phi_zz/h (MHz),  eta = (Vxx-Vyy)/Vzz')
    lines.append('     nu_Q = 3*Cq / (2I(2I-1))  (MHz)')
    lines.append('')
    for a in atoms:
        if a['Q'] != 0.0:
            if a['I'] >= 1.0:
                lines.append('     ' + a['elem'].ljust(3) + f'{a["na"]:3d}' + '  '
                             + 'Q=' + f'{a["Q"]:10.4f}' + ' 1e-30 m^2'
                             + '  ' + 'Cq=' + f'{a["Cq"]:12.4f}' + ' MHz'
                             + '  ' + 'eta=' + f'{a["eta"]:8.5f}'
                             + '  ' + 'I=' + f'{a["I"]:6.1f}'
                             + '  ' + 'nu_Q=' + f'{a["nu_Q"]:12.4f}' + ' MHz')
            else:
                lines.append('     ' + a['elem'].ljust(3) + f'{a["na"]:3d}' + '  '
                             + 'Q=' + f'{a["Q"]:10.4f}' + ' 1e-30 m^2'
                             + '  ' + 'Cq=' + f'{a["Cq"]:12.4f}' + ' MHz'
                             + '  ' + 'eta=' + f'{a["eta"]:8.5f}')
        else:
            lines.append('     ' + a['elem'].ljust(3) + f'{a["na"]:3d}' + '  '
                         + 'Vzz=' + f'{a["principal"]["Vzz"]:10.4f}'
                         + '    ' + 'eta=' + f'{a["eta"]:8.5f}')
    lines.append('')
    lines.append('     QE-EFG      :     1.23s CPU      1.50s WALL')
    return '\n'.join(lines)
