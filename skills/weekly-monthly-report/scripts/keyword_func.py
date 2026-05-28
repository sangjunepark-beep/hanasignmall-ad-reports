
import re

CATEGORIES = [('오뚜기', '오뚜기'), ('A형 입간판', 'A형 입간판'), ('A형입간판', 'A형 입간판'), ('A형', 'A형'), ('주차스티커', '주차스티커'), ('주차증', '주차증'), ('주차금지', '주차금지'), ('피난안내도', '피난안내도'), ('게시판', '게시판'), ('안내판', '안내판'), ('입간판', '입간판'), ('현수막', '현수막'), ('배너', '배너'), ('명판', '명판'), ('표지판', '표지판'), ('시트지', '시트지'), ('포맥스', '포맥스'), ('페트', '페트'), ('폼보드', '폼보드'), ('명찰', '명찰'), ('실사출력', '실사출력'), ('스티커', '스티커'), ('간판', '간판'), ('표지', '표지')]

MODIFIERS = ['슬림디자인', '슬림', '미니', '대형', '소형', '중형', '아크릴', '야광', '홀로그램', '모양재단', '가로형', '세로형', '옥외', '옥내', '엘리베이터', '아파트', '병원', '학교', '사무실', '음식점', '방화문', '화재', '비상구', '블랙', '화이트', '백색', '투명']

SIZE_PATTERNS = [('\\d+x\\d+(?:x\\d+)?(?:mm|cm)?', 'dim'), ('\\d+(?:T|장|cm|mm|구|파이|개)', 'spec')]

def extract_keyword(name):
    if not name: return ''
    masked = name
    sizes = []
    for pat, _ in SIZE_PATTERNS:
        for m in re.finditer(pat, masked):
            sizes.append(m.group(0))
        masked = re.sub(pat, ' ', masked)
    seen = set()
    sizes = [s for s in sizes if not (s in seen or seen.add(s))][:2]
    category_label = None
    category_kw = None
    for kw, label in CATEGORIES:
        if kw in name:
            category_label = label; category_kw = kw; break
    modifier = None
    for m in MODIFIERS:
        if m in name:
            if category_kw and m in category_kw: continue
            modifier = m; break
    parts = []
    if modifier: parts.append(modifier)
    if category_label: parts.append(category_label)
    if sizes: parts.extend(sizes)
    if parts: return ' '.join(parts)
    return ' '.join(name.split()[:3])
