"""Natural language time parsing for task input."""
import re
from datetime import datetime, timedelta


def parse_due_time(text):
    now = datetime.now()
    text = text.strip()
    if text.startswith("明天"):
        time_str = text[2:].strip()
        target_date = now.date() + timedelta(days=1)
    elif text.startswith("后天"):
        time_str = text[2:].strip()
        target_date = now.date() + timedelta(days=2)
    elif text.startswith("今天"):
        time_str = text[2:].strip()
        target_date = now.date()
    else:
        try:
            dt = datetime.strptime(text, "%Y-%m-%d %H:%M")
            return dt.isoformat()
        except ValueError:
            pass
        time_str = text
        target_date = now.date()
    time_str = time_str.strip()
    try:
        hour, minute = map(int, time_str.split(":"))
    except Exception:
        raise ValueError("无法解析时间: " + text)
    target_dt = datetime(target_date.year, target_date.month, target_date.day,
                         hour, minute)
    return target_dt.isoformat()


def _cn_to_digits(text):
    """Convert Chinese number words in text to digits for parsing."""
    cn = [
        ("五十九", "59"), ("五十八", "58"), ("五十七", "57"), ("五十六", "56"),
        ("五十五", "55"), ("五十四", "54"), ("五十三", "53"), ("五十二", "52"),
        ("五十一", "51"),
        ("四十九", "49"), ("四十八", "48"), ("四十七", "47"), ("四十六", "46"),
        ("四十五", "45"), ("四十四", "44"), ("四十三", "43"), ("四十二", "42"),
        ("四十一", "41"),
        ("三十九", "39"), ("三十八", "38"), ("三十七", "37"), ("三十六", "36"),
        ("三十五", "35"), ("三十四", "34"), ("三十三", "33"), ("三十二", "32"),
        ("三十一", "31"),
        ("二十九", "29"), ("二十八", "28"), ("二十七", "27"), ("二十六", "26"),
        ("二十五", "25"), ("二十四", "24"), ("二十三", "23"), ("二十二", "22"),
        ("二十一", "21"),
        ("二十", "20"),
        ("十九", "19"), ("十八", "18"), ("十七", "17"), ("十六", "16"),
        ("十五", "15"), ("十四", "14"), ("十三", "13"), ("十二", "12"),
        ("十一", "11"), ("十", "10"),
        ("九", "9"), ("八", "8"), ("七", "7"), ("六", "6"),
        ("五", "5"), ("四", "4"), ("三", "3"), ("二", "2"),
        ("两", "2"), ("一", "1"), ("零", "0"),
        ("五十", "50"), ("四十", "40"), ("三十", "30"),
    ]
    result = text
    for word, digit in cn:
        result = result.replace(word, digit)
    return result


def _normalize_time_expr(text):
    """Expand combined time expressions so the parser can see them.

    "今晚" -> "今天晚上", "明早" -> "明天早上", etc.
    """
    mapping = [
        ("今晚", "今天晚上"),
        ("今早", "今天早上"),
        ("今晨", "今天早晨"),
        ("今上午", "今天上午"),
        ("今下午", "今天下午"),
        ("今中午", "今天中午"),
        ("明晚", "明天晚上"),
        ("明早", "明天早上"),
        ("明晨", "明天早晨"),
        ("明上午", "明天上午"),
        ("明下午", "明天下午"),
        ("明中午", "明天中午"),
        ("后晚", "后天晚上"),
        ("后早", "后天早上"),
        ("后晨", "后天早晨"),
        ("后上午", "后天上午"),
        ("后下午", "后天下午"),
        ("后中午", "后天中午"),
    ]
    result = text
    for short, full in mapping:
        result = result.replace(short, full)
    return result


def _parse_relative_time(text):
    """Parse relative time expressions like '5分钟后提醒我喝水', '10秒后休息'.
    Returns (content, due_iso) or None if no relative time found."""
    now = datetime.now()
    normalized = _cn_to_digits(text)

    connector = r'(?:提醒我|提醒|叫我|通知我|记住|记得|要|定个|设置|帮我|给我|请)'

    time_units = [
        (r'(\d+)\s*分(?:钟)?后', 'minutes'),
        (r'(\d+)\s*秒(?:钟)?后', 'seconds'),
        (r'(\d+)\s*小?时后', 'hours'),
        (r'半(?:个)?小?时后', 'half_hour'),
    ]

    for pattern, unit in time_units:
        m = re.search(pattern, normalized)
        if not m:
            continue

        if unit == 'half_hour':
            delta = timedelta(minutes=30)
        elif unit == 'minutes':
            delta = timedelta(minutes=int(m.group(1)))
        elif unit == 'seconds':
            delta = timedelta(seconds=int(m.group(1)))
        elif unit == 'hours':
            delta = timedelta(hours=int(m.group(1)))
        else:
            continue

        due_iso = (now + delta).isoformat()

        content = normalized
        content = re.sub(r'\d+\s*分(?:钟)?后', '', content)
        content = re.sub(r'\d+\s*秒(?:钟)?后', '', content)
        content = re.sub(r'\d+\s*小?时后', '', content)
        content = re.sub(r'半(?:个)?小?时后', '', content)
        content = re.sub(connector, '', content)
        content = re.sub(r'\s+', '', content)

        if not content:
            return (text, due_iso)
        return (content, due_iso)

    return None


def _correct_misrecognition(text):
    """Fix common speech-recognition errors before parsing.

    Offline engines like Vosk often drop the second syllable in two-character
    words, e.g. "提醒" -> "听".  We apply domain-specific corrections here.
    """
    corrections = [
        # "提醒我" variants — keep longer patterns first
        ("听醒我", "提醒我"),
        ("挺醒我", "提醒我"),
        ("体型我", "提醒我"),
        ("体形我", "提醒我"),
        ("提心我", "提醒我"),
        ("听我", "提醒我"),
        # "提醒" (without 我)
        ("请听我", "请提醒我"),
        # "叫我" variants
        ("交我", "叫我"),
        ("教我", "叫我"),
        ("搅我", "叫我"),
        # "通知我" variants
        ("通吃我", "通知我"),
        ("同志我", "通知我"),
        # "记住" variants
        ("寄住", "记住"),
        # "记得" variants
        ("积得", "记得"),
        # "定个" variants
        ("订个", "定个"),
    ]
    result = text
    for wrong, right in corrections:
        result = result.replace(wrong, right)
    return result


def parse_voice_task(text):
    """Extract task content and due time from voice input.
    e.g. "今天下午三点提醒我出去玩" -> ("出去玩", iso_string today 15:00)
    e.g. "明天上午十点开会"       -> ("开会", iso_string tomorrow 10:00)
    Returns (content, due_iso) or (original_text, None) if no time found.
    """
    text = text.strip()
    text = _normalize_time_expr(text)
    text = _correct_misrecognition(text)

    rel = _parse_relative_time(text)
    if rel:
        return rel

    now = datetime.now()

    # normalize Chinese numbers to digits
    normalized = _cn_to_digits(text)

    # figure out target date
    date_offset = 0
    for pattern, offset in [("今天", 0), ("明天", 1), ("后天", 2)]:
        if pattern in text:
            date_offset = offset
            break
    target_date = now.date() + timedelta(days=date_offset)

    # figure out am/pm
    am_pm = None
    for word, offset in [("上午", 0), ("早晨", 0), ("早上", 0),
                         ("中午", 12), ("下午", 12), ("晚上", 12),
                         ("夜里", 0), ("半夜", 0), ("凌晨", 0)]:
        if word in text:
            am_pm = offset
            break

    # extract hour and minute from normalized text
    hour = None
    minute = 0

    # "3点半" / "三点半" — half-past must be checked first
    tm = re.search(r'(\d{1,2})\s*[点:：时]?\s*半', normalized)
    if tm:
        hour = int(tm.group(1))
        minute = 30
    # "3点1刻" / "三点一刻" — quarter
    elif re.search(r'[刻可]', normalized):
        tm = re.search(r'(\d{1,2})\s*[点:：时]\s*(\d{1,2})\s*[刻可]', normalized)
        if tm:
            hour = int(tm.group(1))
            minute = int(tm.group(2)) * 15
        else:
            tm = re.search(r'(\d{1,2})\s*[刻可]', normalized)
            if tm:
                hour = int(tm.group(1))
                minute = 15
    if hour is None:
        # "3点15分", "3:15", "3：15", "3点15", "3时15"
        tm = re.search(r'(\d{1,2})\s*[点:：时]\s*(\d{1,2})?\s*[分]?', normalized)
        if tm:
            hour = int(tm.group(1))
            minute = int(tm.group(2)) if tm.group(2) else 0
        else:
            # "15:30" or "3:30" (pure digits colon)
            tm = re.search(r'(\d{1,2}):(\d{2})', normalized)
            if tm:
                hour = int(tm.group(1))
                minute = int(tm.group(2))
            else:
                # bare "3点" or "3时" with nothing after
                tm = re.search(r'(\d{1,2})\s*[点:：时]', normalized)
                if tm:
                    hour = int(tm.group(1))
                    minute = 0

    if hour is None:
        return (text, None)

    # apply am/pm offset (or heuristic when not specified)
    if am_pm is not None:
        if hour == 12:
            hour = 0 if am_pm == 0 else 12
        elif hour <= 12:
            hour = hour + am_pm
    else:
        # No am/pm specified → heuristic: 1-6 = PM, 7-12 = AM
        if 1 <= hour <= 6:
            hour = hour + 12

    hour = hour % 24
    minute = minute % 60

    try:
        due_dt = datetime(target_date.year, target_date.month, target_date.day,
                          hour, minute)
        due_iso = due_dt.isoformat()
    except ValueError:
        return (text, None)

    # extract content: strip date/time words and connector verbs
    content = text
    content = re.sub(r'(今天|明天|后天)', '', content)
    content = re.sub(r'(上午|下午|中午|晚上|早晨|早上)', '', content)
    cn_num = r'[零一二两三四五六七八九十廿卅]'
    content = re.sub(cn_num + r'+[点:：时]' + cn_num + r'*[分半刻可]?', '', content)
    content = re.sub(r'\d{1,2}\s*[点:：时]\s*\d{0,2}\s*[分]?', '', content)
    content = re.sub(r'\d{1,2}点半', '', content)
    content = re.sub(r'\d{1,2}\s*[点:：时]\s*\d{0,2}\s*[刻可]', '', content)
    content = re.sub(r'\d{1,2}:\d{2}', '', content)
    content = re.sub(r'(提醒我|提醒|叫我|通知我|记住|记得|要|定个|设置|帮我|给我)', '', content)
    content = re.sub(r'^我', '', content)
    content = re.sub(r'\s+', '', content)

    if not content:
        return (text, due_iso)

    return (content, due_iso)
