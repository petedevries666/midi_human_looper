"""MB catalog metadata only: no engine startup, file IO, JACK or UI imports."""

ENGINE_INFO = {
    'ID': 'mbh-native', 'NAME': 'MIDI Bad Mother Fucker',
    'TITLE': 'MIDI Bad Mother Fucker', 'TYPE': 'MIDI Tool', 'CAT': 'Other',
    'ENABLED': True, 'INDEX': 999, 'URL': '', 'UI': '',
    'DESCR': 'Independent synchronized MIDI phrase looper',
    'QUALITY': 0, 'COMPLEX': 1, 'EDIT': 0,
}


def validate_category(categories):
    if 'Other' not in categories.get('MIDI Tool', ()):
        raise ValueError('MB requires the Oram MIDI Tool / Other category')


def register_standalone_mbh(standalone, categories):
    """Ensure Oram's generator retains MB without replacing any other engine."""
    validate_category(categories)
    expected = [ENGINE_INFO['NAME'], ENGINE_INFO['TITLE'], 'MIDI Tool', 'Other', True]
    if 'MB' in standalone and standalone['MB'] != expected:
        raise ValueError('MB engine code is already used by another registration')
    standalone['MB'] = expected


def register_mbh(engines, categories):
    """Run before every type-index rebuild, including loads from older catalogs.

    Keep MB's user-edited title/ranking/enabled state and every unrelated record.
    Chain manager resolves ENGINE through its existing engine2class mapping.
    """
    validate_category(categories)
    if 'MB' in engines:
        if engines['MB'].get('NAME') != ENGINE_INFO['NAME'] or engines['MB'].get('TYPE') != 'MIDI Tool':
            raise ValueError('MB engine code is already used by another engine')
        entry = engines['MB']
    else:
        entry = engines['MB'] = {}
    for key, value in ENGINE_INFO.items():
        entry.setdefault(key, value)
    if entry['CAT'] not in categories['MIDI Tool']:
        raise ValueError('MB has an invalid MIDI Tool category')
