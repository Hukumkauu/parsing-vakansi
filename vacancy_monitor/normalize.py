"""Приведение названий должностей к единому виду.

Порядок:
1. Словарь соответствий (вкладка «Словарь должностей»): если в названии
   вакансии встречается фраза из словаря, должность берётся оттуда.
2. Совпадение со списком должностей из «Настроек мониторинга».
3. Подбор похожего названия: слова сравниваются по основам, опечатки
   допускаются. Общие слова («специалист», «отдел», «центр») весят меньше,
   чем слова, которые определяют профессию. Найденные так соответствия
   добавляются в словарь с пометкой «авто (проверить)»: правилами они
   становятся только после проверки человеком.

Руководящие должности («начальник», «заместитель», «директор»),
преподавание и продажи не смешиваются с должностями специалистов, если сама
отслеживаемая должность не руководящая.

Если в словаре напротив названия написать «не учитывать», такие вакансии
попадут во вкладку «Прочее» (например, «Главный бухгалтер» - это другая
должность, чем «Бухгалтер»).
"""
import re
from difflib import SequenceMatcher

# Слова, которые не меняют суть должности
STOP_WORDS = {
    "и", "в", "по", "на", "с", "со", "для", "к", "от", "из", "г", "the", "of", "and",
    "ведущий", "ведущая", "старший", "старшая", "младший", "младшая", "главный", "главная",
    "senior", "middle", "junior", "lead", "sr", "jr", "стажер", "стажерка", "помощник",
    "удаленно", "удаленка", "вахта", "срочно", "работа", "вакансия",
}

# Общие слова: встречаются в названиях разных профессий, поэтому весят меньше
GENERIC = ("специалист", "инженер", "менеджер", "сотрудник", "работник", "эксперт", "консультант",
           "центр", "отдел", "управлен", "групп", "направлен", "сектор", "служб", "компани",
           "категори", "организац", "учрежден")
GENERIC_WEIGHT = 0.3

# Слова, меняющие уровень или род занятий
MANAGEMENT = ("начальник", "руководител", "заместител", "директор", "заведующ", "head", "chief")
TEACHING = ("преподавател", "учител", "доцент", "профессор", "педагог")
MANAGEMENT_REASON = "руководящая должность"
TEACHING_REASON = "преподавание"
SALES = ("продаж", "sales", "продавец")
SALES_REASON = "продажи"

# Окончания, которые отбрасываются при поиске основы слова
_ENDINGS = sorted([
    "ами", "ями", "ых", "их", "ым", "им", "ого", "его", "ому", "ему", "ыми", "ими", "ая", "яя", "ой", "ей", "ый", "ий",
    "ое", "ее", "ую", "юю", "ом", "ем", "ах", "ях", "ов", "ев", "ам", "ям", "а", "я", "ы", "и",
    "у", "ю", "е", "о", "ь",
], key=len, reverse=True)

# Если в словаре вместо должности написано это, вакансия уходит в «Прочее»
SKIP_MARKS = {"-", "не учитывать", "исключить"}
SKIPPED = "исключено словарём"

STRONG = "словарь"
EXACT = "точное"
AUTO = "авто"


def clean(text: str) -> str:
    text = (text or "").lower().replace("ё", "е")
    text = re.sub(r"[^a-zа-я0-9+#]+", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def stem(word: str) -> str:
    if len(word) <= 4 or not re.match(r"[а-я]", word):
        return word
    for end in _ENDINGS:
        if word.endswith(end) and len(word) - len(end) >= 4:
            return word[: -len(end)]
    return word


def stems(text: str):
    return [stem(w) for w in clean(text).split() if w not in STOP_WORDS]


def _word_match(a: str, b: str) -> bool:
    if a == b:
        return True
    if len(a) >= 5 and len(b) >= 5 and (a.startswith(b) or b.startswith(a)):
        return True
    return len(a) >= 5 and SequenceMatcher(None, a, b).ratio() >= 0.85


def _weight(word: str) -> float:
    return GENERIC_WEIGHT if word.startswith(GENERIC) else 1.0


def coverage(title_stems, candidate_stems) -> float:
    """Какая доля слов кандидата (с учётом веса) нашлась в названии вакансии.
    Хотя бы одно слово, определяющее профессию, должно совпасть."""
    if not candidate_stems:
        return 0.0
    total = found = 0.0
    specific_found = not any(_weight(c) == 1.0 for c in candidate_stems)
    for c in candidate_stems:
        weight = _weight(c)
        total += weight
        if any(_word_match(c, t) for t in title_stems):
            found += weight
            if weight == 1.0:
                specific_found = True
    return found / total if specific_found else 0.0


def _has(stems_list, prefixes) -> bool:
    return any(w.startswith(prefixes) for w in stems_list)


class Normalizer:
    def __init__(self, positions, dictionary, threshold=0.75):
        """positions - список эталонных должностей,
        dictionary - список пар (название в вакансиях, должность)."""
        self.positions = list(dict.fromkeys(positions))
        self.threshold = threshold
        self.phrases = []  # (очищенная фраза, должность)
        for synonym, position in dictionary:
            if synonym and position:
                self.phrases.append((clean(synonym), position))
        self.phrases.sort(key=lambda p: len(p[0]), reverse=True)  # длинные фразы точнее
        self.candidates = [(stems(p), p) for p in self.positions]
        for phrase, position in self.phrases:
            if position.strip().lower() not in SKIP_MARKS:
                self.candidates.append((stems(phrase), position))
        self.new_synonyms = {}  # очищенное название -> (название, должность)

    def normalize(self, title: str):
        """Возвращает (должность или None, способ, оценка 0..1)."""
        text = f" {clean(title)} "
        for phrase, position in self.phrases:
            if phrase and f" {phrase} " in text:
                if position.strip().lower() in SKIP_MARKS:
                    return None, SKIPPED, 1.0
                return position, STRONG, 1.0
        title_stems = stems(title)
        best, best_score, best_len = None, 0.0, 0
        role_change = None
        if _has(title_stems, MANAGEMENT):
            role_change = (MANAGEMENT, MANAGEMENT_REASON)
        elif _has(title_stems, TEACHING):
            role_change = (TEACHING, TEACHING_REASON)
        elif _has(title_stems, SALES):
            role_change = (SALES, SALES_REASON)
        for cand_stems, position in self.candidates:
            if role_change and not _has(cand_stems, role_change[0]):
                continue
            score = coverage(title_stems, cand_stems)
            if score > best_score or (score == best_score and len(cand_stems) > best_len):
                best, best_score, best_len = position, score, len(cand_stems)
        if best_score >= 0.999:
            return best, EXACT, best_score
        if best and best_score >= self.threshold:
            key = clean(title)
            if key and key not in self.new_synonyms:
                self.new_synonyms[key] = (title.strip(), best)
            return best, AUTO, best_score
        if role_change:
            return None, role_change[1], 0.0
        return None, "", best_score
