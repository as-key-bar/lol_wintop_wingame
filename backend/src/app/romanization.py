import re
import unicodedata

_KANA = {
    "あ": "a", "い": "i", "う": "u", "え": "e", "お": "o",
    "か": "ka", "き": "ki", "く": "ku", "け": "ke", "こ": "ko",
    "さ": "sa", "し": "shi", "す": "su", "せ": "se", "そ": "so",
    "た": "ta", "ち": "chi", "つ": "tsu", "て": "te", "と": "to",
    "な": "na", "に": "ni", "ぬ": "nu", "ね": "ne", "の": "no",
    "は": "ha", "ひ": "hi", "ふ": "fu", "へ": "he", "ほ": "ho",
    "ま": "ma", "み": "mi", "む": "mu", "め": "me", "も": "mo",
    "や": "ya", "ゆ": "yu", "よ": "yo",
    "ら": "ra", "り": "ri", "る": "ru", "れ": "re", "ろ": "ro",
    "わ": "wa", "ゐ": "wi", "ゑ": "we", "を": "o", "ん": "n",
    "が": "ga", "ぎ": "gi", "ぐ": "gu", "げ": "ge", "ご": "go",
    "ざ": "za", "じ": "ji", "ず": "zu", "ぜ": "ze", "ぞ": "zo",
    "だ": "da", "ぢ": "ji", "づ": "zu", "で": "de", "ど": "do",
    "ば": "ba", "び": "bi", "ぶ": "bu", "べ": "be", "ぼ": "bo",
    "ぱ": "pa", "ぴ": "pi", "ぷ": "pu", "ぺ": "pe", "ぽ": "po",
    "ぁ": "a", "ぃ": "i", "ぅ": "u", "ぇ": "e", "ぉ": "o",
    "ゃ": "ya", "ゅ": "yu", "ょ": "yo", "ゎ": "wa",
    "ゔ": "vu",
}

_COMBINATIONS = {
    ("き", "ゃ"): "kya", ("き", "ゅ"): "kyu", ("き", "ょ"): "kyo",
    ("ぎ", "ゃ"): "gya", ("ぎ", "ゅ"): "gyu", ("ぎ", "ょ"): "gyo",
    ("し", "ゃ"): "sha", ("し", "ゅ"): "shu", ("し", "ょ"): "sho",
    ("じ", "ゃ"): "ja", ("じ", "ゅ"): "ju", ("じ", "ょ"): "jo",
    ("ち", "ゃ"): "cha", ("ち", "ゅ"): "chu", ("ち", "ょ"): "cho",
    ("ぢ", "ゃ"): "ja", ("ぢ", "ゅ"): "ju", ("ぢ", "ょ"): "jo",
    ("に", "ゃ"): "nya", ("に", "ゅ"): "nyu", ("に", "ょ"): "nyo",
    ("ひ", "ゃ"): "hya", ("ひ", "ゅ"): "hyu", ("ひ", "ょ"): "hyo",
    ("び", "ゃ"): "bya", ("び", "ゅ"): "byu", ("び", "ょ"): "byo",
    ("ぴ", "ゃ"): "pya", ("ぴ", "ゅ"): "pyu", ("ぴ", "ょ"): "pyo",
    ("み", "ゃ"): "mya", ("み", "ゅ"): "myu", ("み", "ょ"): "myo",
    ("り", "ゃ"): "rya", ("り", "ゅ"): "ryu", ("り", "ょ"): "ryo",
    ("う", "ぃ"): "wi", ("う", "ぇ"): "we", ("う", "ぉ"): "wo",
    ("き", "ぇ"): "kye", ("ぎ", "ぇ"): "gye",
    ("し", "ぇ"): "she", ("じ", "ぇ"): "je", ("ち", "ぇ"): "che",
    ("に", "ぇ"): "nye", ("ひ", "ぇ"): "hye", ("び", "ぇ"): "bye",
    ("ぴ", "ぇ"): "pye", ("み", "ぇ"): "mye", ("り", "ぇ"): "rye",
    ("ふ", "ぁ"): "fa", ("ふ", "ぃ"): "fi", ("ふ", "ぇ"): "fe",
    ("ふ", "ぉ"): "fo", ("ふ", "ゅ"): "fyu",
    ("つ", "ぁ"): "tsa", ("つ", "ぃ"): "tsi", ("つ", "ぇ"): "tse",
    ("つ", "ぉ"): "tso",
    ("て", "ぃ"): "ti", ("て", "ゅ"): "tyu", ("て", "ぇ"): "tye",
    ("で", "ぃ"): "di", ("で", "ゅ"): "dyu", ("で", "ぇ"): "dye",
    ("と", "ぅ"): "tu", ("ど", "ぅ"): "du",
    ("ゔ", "ぁ"): "va", ("ゔ", "ぃ"): "vi", ("ゔ", "ぇ"): "ve",
    ("ゔ", "ぉ"): "vo", ("ゔ", "ゅ"): "vyu",
}

_VOWELS = frozenset("aeiou")


def _to_hiragana(character: str) -> str:
    codepoint = ord(character)
    if 0x30A1 <= codepoint <= 0x30F6:
        return chr(codepoint - 0x60)
    return character


def romanize_japanese(value: str) -> str:
    text = unicodedata.normalize("NFKC", value).casefold()
    kana = "".join(_to_hiragana(character) for character in text)
    result: list[str] = []
    geminate = False
    repeat_vowel = False
    index = 0

    while index < len(kana):
        character = kana[index]
        if character == "っ":
            geminate = True
            index += 1
            continue
        if character == "ー":
            repeat_vowel = True
            index += 1
            continue

        syllable = ""
        if index + 1 < len(kana):
            syllable = _COMBINATIONS.get((character, kana[index + 1]), "")
        if syllable:
            index += 2
        else:
            syllable = _KANA.get(character, character if character.isascii() else "")
            index += 1

        if repeat_vowel:
            previous_vowels = [letter for letter in reversed("".join(result)) if letter in _VOWELS]
            if previous_vowels:
                result.append(previous_vowels[0])
            repeat_vowel = False

        if geminate:
            if syllable and syllable[0] not in _VOWELS:
                result.append(syllable[0])
            geminate = False
        result.append(syllable)

    return "".join(result)


def normalize_romaji(value: str) -> str:
    normalized = unicodedata.normalize("NFKC", value).casefold()
    compact = re.sub(r"[^a-z0-9]", "", normalized).replace("v", "b")
    return re.sub(r"([aeiou])\1+", r"\1", compact)
