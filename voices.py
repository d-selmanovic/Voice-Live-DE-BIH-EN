VOICES = ('marin', 'cedar', 'alloy', 'ash', 'ballad', 'coral', 'echo', 'sage',
          'shimmer', 'verse', 'quartz', 'ripple', 'vesper', 'willow', 'stone',
          'gleam', 'meridian', 'bossa', 'tempo', 'beacon', 'delta', 'cinder')
LANGUAGES = {'de': 'Deutsch', 'bs': 'Bosanski', 'en': 'English'}
VERSION = 'voice-study-v1'


def selection(body):
    if not isinstance(body, dict):
        raise ValueError('Ungültige Auswahl')
    voice, language = body.get('voice', 'marin'), body.get('language', 'de')
    if not isinstance(voice, str) or not isinstance(language, str) or voice not in VOICES or language not in LANGUAGES:
        raise ValueError('Unbekannte Stimme oder Testsprache')
    code = body.get('tester_code', '')
    if not isinstance(code, str) or len(code.strip()) > 64:
        raise ValueError('Testcode darf höchstens 64 Zeichen enthalten')
    if code.strip() and len(code.strip()) < 3:
        raise ValueError('Testcode muss mindestens 3 Zeichen enthalten')
    return voice, language, code.strip().casefold()


def language_prompt(language):
    return {'de': 'Beginne dieses Testgespräch auf Deutsch mit natürlicher deutscher Aussprache.',
            'bs': 'Započni ovaj testni razgovor na bosanskom jeziku.',
            'en': 'Start this test conversation in English with natural English pronunciation.'}[language]
