# -*- coding: utf-8 -*-
"""
AI 리더스북 데이터 ETL
- 입력: 학생 명단, 조별 피드백(팩트체크), 웹앱 목록, 사전/사후 설문 3종
- 출력: web/data.js  (window.RB = {students, agg, meta})
모든 데이터는 학번(4자리)을 기준 키로 통합한다.
"""
import warnings; warnings.filterwarnings("ignore")
import os, json, re
import openpyxl

RC = r"C:\Users\user\Downloads\연구대회"
DK = r"C:\Users\user\OneDrive\Desktop"
OUT = r"D:\project_clone\alb\web\data.js"

ROSTER_X   = os.path.join(RC, "학생 명단.xlsx")
FEEDBACK_X = os.path.join(RC, "AI 시대 팩트 체크 조별 피드백.xlsx")
APPS_X     = os.path.join(RC, "웹앱 목록.xlsx")
# 설문 파일은 연구대회 폴더로 이동됨(과거: 데스크탑). 데스크탑에도 있으면 그쪽 우선.
def _survey(fname):
    dk = os.path.join(DK, fname)
    return dk if os.path.exists(dk) else os.path.join(RC, fname)
PRE_X      = _survey("(2026) 정보 수업 사전 설문조사(응답).xlsx")
FC_POST_X  = _survey("(2026) AI 시대 팩트 체크 수행평가 후 설문조사(응답).xlsx")
WA_POST_X  = _survey("(2026) AI 기반 웹앱 개발 수행평가 후 설문조사(응답).xlsx")
ENRICH_J   = r"D:\project_clone\alb\etl\enrich.json"  # 드라이브 크롤 결과(워크플로우 산출)
WA_SCORE_X = r"C:\Users\user\Documents\Codex\2026-06-25\rkr\outputs\AI기반웹앱개발_채점결과(일부).xlsx"

log = []
def L(*a): log.append(" ".join(str(x) for x in a)); print(*a)

# ---------- helpers ----------
def norm_id(v):
    """학번 4자리 문자열로 정규화"""
    if v is None: return None
    s = re.sub(r"[^0-9]", "", str(v))
    if len(s) == 4: return s
    return None

def norm_name(v):
    if v is None: return ""
    return re.sub(r"\s+", "", str(v)).strip()

def to_int(v):
    try:
        f = float(v)
        if 0 <= f <= 10: return int(round(f))
    except (TypeError, ValueError):
        pass
    return None

def load_rows(path, sheet=None):
    wb = openpyxl.load_workbook(path, read_only=True, data_only=True)
    res = []
    for ws in wb.worksheets:
        if sheet and ws.title != sheet: continue
        rows = list(ws.iter_rows(values_only=True))
        res.append((ws.title, rows))
    wb.close()
    return res

def find_col(header, *keywords):
    """헤더에서 keyword를 모두 포함하는 첫 컬럼 인덱스"""
    for i, h in enumerate(header):
        hs = str(h or "")
        if all(k in hs for k in keywords):
            return i
    return None

def detect_likert_block(header, rows):
    """값이 대부분 1~10 정수인 연속 10개 컬럼(=리커트 문항)을 순서대로 반환"""
    ncol = len(header)
    numeric_ratio = []
    sample = [r for r in rows[:60]]
    for c in range(ncol):
        ok = tot = 0
        for r in sample:
            if c < len(r) and r[c] is not None:
                tot += 1
                if to_int(r[c]) is not None: ok += 1
        numeric_ratio.append(ok / tot if tot else 0.0)
    cols = [c for c in range(ncol) if numeric_ratio[c] >= 0.7]
    # 리커트는 보통 뒤쪽 연속 블록 -> 가장 긴 연속 구간 선택
    best = []
    cur = []
    for c in range(ncol):
        if c in cols:
            cur.append(c)
        else:
            if len(cur) > len(best): best = cur
            cur = []
    if len(cur) > len(best): best = cur
    return best  # list of column indices in order

# ---------- 1) 로스터 ----------
def load_roster():
    (_, rows) = load_rows(ROSTER_X)[0]
    header = rows[0]
    ci_cls  = find_col(header, "반")
    ci_id   = find_col(header, "학번")
    ci_name = find_col(header, "이름")
    students = {}
    name2id = {}
    for r in rows[1:]:
        sid = norm_id(r[ci_id]) if ci_id is not None else None
        if not sid: continue
        nm = str(r[ci_name]).strip() if ci_name is not None and r[ci_name] else ""
        cls = str(r[ci_cls]).strip() if ci_cls is not None and r[ci_cls] is not None else ""
        students[sid] = {
            "id": sid, "name": nm, "cls": cls,
            "num": int(sid[2:]) if sid[2:].isdigit() else None,
        }
        name2id[norm_name(nm)] = sid
    L("[roster] students:", len(students))
    return students, name2id

# ---------- 2) 조별 피드백 (팩트체크) ----------
def load_feedback(roster):
    (_, rows) = load_rows(FEEDBACK_X)[0]
    header = rows[0]
    # 멤버 학번/이름 컬럼 쌍 찾기
    pair_cols = []
    for i, h in enumerate(header):
        if str(h or "").strip() == "학번":
            # 다음 컬럼이 이름인지
            if i+1 < len(header) and str(header[i+1] or "").strip() == "이름":
                pair_cols.append((i, i+1))
    ci_team  = find_col(header, "팀명")
    ci_topic = find_col(header, "주제")  # 첫 '주제' = 실제 주제 텍스트
    # 점수 3개: '주제/검증', 'AI활용', '결과'
    ci_s1 = find_col(header, "검증", "방법") or find_col(header, "주제/검증")
    ci_s2 = find_col(header, "AI활용") or find_col(header, "AI", "검증")
    ci_s3 = find_col(header, "결과")
    ci_cmt = find_col(header, "코멘트")
    # fallback by known layout
    if ci_s1 is None: ci_s1 = 11
    if ci_s2 is None: ci_s2 = 12
    if ci_s3 is None: ci_s3 = 13

    fc = {}
    teams = 0
    for r in rows[1:]:
        if r is None: continue
        team = str(r[ci_team]).strip() if ci_team is not None and r[ci_team] else ""
        topic = str(r[ci_topic]).strip() if ci_topic is not None and r[ci_topic] else ""
        if not team and not topic: continue
        members = []
        for (ci, cn) in pair_cols:
            mid = norm_id(r[ci]) if ci < len(r) else None
            if mid:
                mname = str(r[cn]).strip() if cn < len(r) and r[cn] else roster.get(mid, {}).get("name", "")
                members.append({"id": mid, "name": mname})
        if not members: continue
        teams += 1
        s1, s2, s3 = to_int(r[ci_s1]) if ci_s1 < len(r) else None, \
                     to_int(r[ci_s2]) if ci_s2 < len(r) else None, \
                     to_int(r[ci_s3]) if ci_s3 < len(r) else None
        total = sum(x for x in (s1, s2, s3) if x is not None) if any(x is not None for x in (s1,s2,s3)) else None
        cmt = str(r[ci_cmt]).strip() if ci_cmt is not None and ci_cmt < len(r) and r[ci_cmt] else ""
        rec = {
            "team": team, "topic": topic,
            "scores": {"주제·검증 설계": s1, "정보검증·AI활용": s2, "결과 분석·표현": s3},
            "total": total, "totalMax": 30,
            "comment": cmt,
            "members": members,
        }
        for m in members:
            fc[m["id"]] = rec
    L("[feedback] teams:", teams, "students mapped:", len(fc))
    return fc

# ---------- 3) 웹앱 목록 ----------
def load_apps(roster, name2id):
    (_, rows) = load_rows(APPS_X)[0]
    header = rows[0]
    ci_id   = find_col(header, "학번")
    ci_name = find_col(header, "이름")
    ci_title= find_col(header, "제목")
    ci_desc = find_col(header, "설명")
    ci_url  = find_col(header, "appUrl") or find_col(header, "URL") or find_col(header, "url")
    apps = {}
    for r in rows[1:]:
        if r is None: continue
        sid = norm_id(r[ci_id]) if ci_id is not None and ci_id < len(r) else None
        if not sid and ci_name is not None:
            sid = name2id.get(norm_name(r[ci_name]))
        if not sid: continue
        title = str(r[ci_title]).strip() if ci_title is not None and r[ci_title] else ""
        desc  = str(r[ci_desc]).strip() if ci_desc is not None and r[ci_desc] else ""
        url   = str(r[ci_url]).strip() if ci_url is not None and r[ci_url] else ""
        if not (title or desc or url): continue
        apps[sid] = {"title": title, "desc": desc, "url": url}
    L("[apps] students mapped:", len(apps))
    return apps

# ---------- 3c) 웹앱 채점 결과 (일부 반) ----------
def load_wa_scores():
    if not os.path.exists(WA_SCORE_X):
        L("[wa_scores] (없음)"); return {}
    (_, rows) = load_rows(WA_SCORE_X)[0]
    header = rows[0]
    ci_id  = find_col(header, "학번")
    c1 = find_col(header, "문제")           # 문제 발견 및 아이디어 설계
    c2 = find_col(header, "구현")           # 웹앱 구현 및 기능
    c3 = find_col(header, "협력")           # 생성AI의 협력적 활용
    ccm = find_col(header, "코멘트")
    out = {}
    for r in rows[1:]:
        if r is None: continue
        sid = norm_id(r[ci_id]) if ci_id is not None and ci_id < len(r) else None
        if not sid: continue
        s1 = to_int(r[c1]) if c1 is not None and c1 < len(r) else None
        s2 = to_int(r[c2]) if c2 is not None and c2 < len(r) else None
        s3 = to_int(r[c3]) if c3 is not None and c3 < len(r) else None
        if s1 is None and s2 is None and s3 is None: continue
        total = sum(x for x in (s1, s2, s3) if x is not None)
        cmt = str(r[ccm]).strip() if ccm is not None and ccm < len(r) and r[ccm] else ""
        out[sid] = {
            "scores": {"문제 발견·설계": s1, "웹앱 구현·기능": s2, "생성AI 협력 활용": s3},
            "total": total, "totalMax": 30, "comment": cmt,
        }
    L("[wa_scores] students scored:", len(out))
    return out

# ---------- 3b) 드라이브 보강 (PDF 임베드 링크 + 문서 링크) ----------
def load_enrich():
    if not os.path.exists(ENRICH_J):
        L("[enrich] (없음) - 드라이브 보강 생략")
        return {}
    data = json.load(open(ENRICH_J, encoding="utf-8"))
    rows = data.get("students", data) if isinstance(data, dict) else data
    out = {}
    for s in rows:
        sid = norm_id(s.get("hakbun") or s.get("id"))
        if not sid: continue
        out[sid] = s
    L("[enrich] students:", len(out),
      "| 임베드링크:", sum(1 for s in out.values() if s.get("embeddedLink")),
      "| 팩트체크문서:", sum(1 for s in out.values() if s.get("factcheckDocId")))
    return out

# ---------- 4) 설문 (사전/사후) ----------
def load_survey(path, roster, name2id, free_map):
    """free_map: {필드명: [헤더 키워드,...]}  -> 자유응답 추출
       반환: {학번: {'likert':[v1..v10], 'free':{...}}}"""
    out = {}
    for (title, rows) in load_rows(path):
        if not rows: continue
        header = rows[0]
        ci_id   = find_col(header, "학번")
        ci_name = find_col(header, "이름")
        if ci_id is None and ci_name is None: continue
        block = detect_likert_block(header, rows[1:])
        free_cols = {}
        for fld, kws in free_map.items():
            for kw in kws:
                c = find_col(header, kw)
                if c is not None:
                    free_cols[fld] = c; break
        for r in rows[1:]:
            if r is None: continue
            sid = norm_id(r[ci_id]) if ci_id is not None and ci_id < len(r) else None
            if not sid and ci_name is not None and ci_name < len(r):
                sid = name2id.get(norm_name(r[ci_name]))
            if not sid or sid not in roster:  # 로스터(2학년)로 한정
                continue
            likert = [to_int(r[c]) if c < len(r) else None for c in block]
            free = {}
            for fld, c in free_cols.items():
                v = r[c] if c < len(r) else None
                if v is not None and str(v).strip():
                    free[fld] = str(v).strip()
            rec = {"likert": likert, "free": free}
            out[sid] = rec  # 중복 시 마지막 응답 사용
    return out

# ---------- 성장 구인(construct) 계산 ----------
# 설문 내 1-based 문항 번호로 매핑
CONSTRUCTS = [
    # name, type, pre(items), post(survey, items)
    {"key":"ai_understand", "name":"AI 원리·한계 이해", "type":"growth",
     "pre":[8], "post":("wa",[1])},
    {"key":"check", "name":"비판적 검증(CHECK)", "type":"growth",
     "pre":[2,3,9], "post":("fc",[1,2,7,8])},
    {"key":"problem", "name":"문제 발견·해결", "type":"growth",
     "pre":[4,5,7], "post":("wa",[2])},
    {"key":"build", "name":"프로그래밍 구현", "type":"growth",
     "pre":[6], "post":("wa",[9])},
    {"key":"mate", "name":"AI 협업(MATE)", "type":"achieve",
     "post":("wa",[6,7,8])},
    {"key":"media", "name":"정보 신뢰성 판단", "type":"achieve",
     "post":("fc",[3,4,5,6])},
    {"key":"motivation", "name":"지속 동기·자기효능감", "type":"achieve",
     "post":("wa",[10])},
]

def avg_items(likert, items):
    if not likert: return None
    vals = [likert[i-1] for i in items if i-1 < len(likert) and likert[i-1] is not None]
    if not vals: return None
    return round(sum(vals)/len(vals), 2)

def compute_growth(pre, fcp, wap):
    res = []
    for c in CONSTRUCTS:
        pv = avg_items(pre["likert"], c["pre"]) if (pre and "pre" in c) else None
        psurv = {"fc": fcp, "wa": wap}.get(c["post"][0]) if "post" in c else None
        ov = avg_items(psurv["likert"], c["post"][1]) if psurv else None
        delta = round(ov - pv, 2) if (pv is not None and ov is not None) else None
        res.append({"key":c["key"], "name":c["name"], "type":c["type"],
                    "pre":pv, "post":ov, "delta":delta})
    return res

# ---------- 빌드 ----------
def main():
    roster, name2id = load_roster()
    fc = load_feedback(roster)
    apps = load_apps(roster, name2id)
    enrich = load_enrich()
    wa_scores = load_wa_scores()

    # 팩트체크는 조별이므로, 팀의 대표 활동지(작성본)를 팀원 전원에게 연결
    team_doc = {}  # team-id(=대표 학번) -> {docUrl, docId}
    for sid, rec in fc.items():
        members = [m["id"] for m in rec.get("members", [])]
        key = "|".join(sorted(members))
        if key in team_doc: continue
        best = None
        for mid in members:
            e = enrich.get(mid)
            if not e or not e.get("factcheckViewUrl"): continue
            score = (1 if e.get("factcheckFilled") else 0)
            if best is None or score > best[0]:
                best = (score, e["factcheckViewUrl"], e.get("factcheckDocId", ""))
        if best:
            for mid in members:
                team_doc[mid] = {"url": best[1], "id": best[2]}

    pre = load_survey(PRE_X, roster, name2id, {
        "바라는점": ["바라는"], "이전경험": ["이전에 정보"], "언어": ["프로그래밍 언어"], "AI경험": ["인공지능을 활용"]})
    fcp = load_survey(FC_POST_X, roster, name2id, {
        "달라진점": ["크게 달라"], "어려운점": ["어려웠던"], "느낀점": ["느낀 점"]})
    wap = load_survey(WA_POST_X, roster, name2id, {
        "달라진점": ["크게 달라"], "어려운점": ["어려웠던"], "깨달은점": ["깨달"], "선생님께": ["선생님"]})
    L("[survey] pre:", len(pre), "fc_post:", len(fcp), "wa_post:", len(wap))

    students = []
    for sid in sorted(roster):
        s = roster[sid]
        p, f, w = pre.get(sid), fcp.get(sid), wap.get(sid)
        # 회고 모음
        reflections = []
        if p and p["free"].get("바라는점"): reflections.append({"phase":"수업 전 다짐","text":p["free"]["바라는점"]})
        if f and f["free"].get("달라진점"): reflections.append({"phase":"팩트체크 후","text":f["free"]["달라진점"]})
        if f and f["free"].get("느낀점"):  reflections.append({"phase":"팩트체크 느낀점","text":f["free"]["느낀점"]})
        if w and w["free"].get("달라진점"): reflections.append({"phase":"웹앱개발 후","text":w["free"]["달라진점"]})
        if w and w["free"].get("깨달은점"): reflections.append({"phase":"웹앱개발 깨달음","text":w["free"]["깨달은점"]})
        teacher_msg = w["free"].get("선생님께") if w else None

        e = enrich.get(sid, {})
        # 팩트체크: 점수/코멘트(조별 피드백) + 활동지 링크(팀 대표 작성본)
        fcr = dict(fc[sid]) if sid in fc else None
        if fcr is not None:
            td = team_doc.get(sid)
            fcr["docUrl"] = (td or {}).get("url") or e.get("factcheckViewUrl") or None
            fcr["docId"] = (td or {}).get("id") or e.get("factcheckDocId") or None
        elif e.get("factcheckViewUrl"):
            fcr = {"team": None, "topic": None, "scores": {}, "total": None,
                   "comment": "", "members": [], "docUrl": e.get("factcheckViewUrl"),
                   "docId": e.get("factcheckDocId") or None}
        # 웹앱: 최신 링크 = PDF 임베드 링크 우선, 없으면 웹앱목록 링크
        a = apps.get(sid)
        wsc = wa_scores.get(sid)
        list_url = (a or {}).get("url") or ""
        latest = e.get("embeddedLink") or list_url or ""
        war = None
        if a or latest or e.get("webappViewUrl") or wsc:  # 점수만 있어도 카드 생성
            war = {
                "title": (a or {}).get("title") or "",
                "desc": (a or {}).get("desc") or "",
                "url": latest,                      # 앱 실행 (최신)
                "listUrl": list_url,                # 웹앱목록.xlsx 링크
                "linkChanged": bool(e.get("embeddedLink") and list_url and e["embeddedLink"] != list_url),
                "pdfUrl": e.get("webappViewUrl") or None,   # 보고서 PDF (드라이브)
                "pdfId": e.get("webappFileId") or None,
                "score": wsc,                       # 채점 결과(일부 반) 또는 None(채점중)
            }

        rec = {
            "id": sid, "name": s["name"], "cls": s["cls"], "num": s["num"],
            "factCheck": fcr,
            "webApp": war,
            "surveys": {
                "pre": p["likert"] if p else None,
                "fcPost": f["likert"] if f else None,
                "waPost": w["likert"] if w else None,
            },
            "growth": compute_growth(p, f, w),
            "reflections": reflections,
            "teacherMsg": teacher_msg,
            "has": {
                "factCheck": fcr is not None, "webApp": war is not None,
                "appLink": bool(war and war.get("url")),
                "fcDoc": bool(fcr and fcr.get("docUrl")),
                "waPdf": bool(war and war.get("pdfUrl")),
                "pre": p is not None, "fcPost": f is not None, "waPost": w is not None,
            },
        }
        students.append(rec)

    # ---------- 집계 ----------
    agg_constructs = []
    for c in CONSTRUCTS:
        pres = [st["growth"][i]["pre"] for st in students for i,cc in enumerate(CONSTRUCTS) if cc["key"]==c["key"]]
        posts= [st["growth"][i]["post"] for st in students for i,cc in enumerate(CONSTRUCTS) if cc["key"]==c["key"]]
        pres = [x for x in pres if x is not None]
        posts= [x for x in posts if x is not None]
        agg_constructs.append({
            "key":c["key"], "name":c["name"], "type":c["type"],
            "pre": round(sum(pres)/len(pres),2) if pres else None,
            "post": round(sum(posts)/len(posts),2) if posts else None,
            "nPre": len(pres), "nPost": len(posts),
            "delta": round(sum(posts)/len(posts) - sum(pres)/len(pres),2) if (pres and posts) else None,
        })

    by_class = {}
    for st in students:
        by_class.setdefault(st["cls"], 0)
        by_class[st["cls"]] += 1

    agg = {
        "total": len(students),
        "byClass": by_class,
        "counts": {
            "factCheck": sum(1 for st in students if st["has"]["factCheck"]),
            "webApp":    sum(1 for st in students if st["has"]["webApp"]),
            "pre":       sum(1 for st in students if st["has"]["pre"]),
            "fcPost":    sum(1 for st in students if st["has"]["fcPost"]),
            "waPost":    sum(1 for st in students if st["has"]["waPost"]),
        },
        "constructs": agg_constructs,
    }
    meta = {
        "project": "AI CHECK-MATE",
        "title": "AI 리더스북",
        "subtitle": "AI를 적극 활용하되 비판적으로 검토하고, 협업하되 책임은 사람이.",
    }

    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    payload = {"students": students, "agg": agg, "meta": meta}
    with open(OUT, "w", encoding="utf-8") as fp:
        fp.write("// 자동 생성됨 (etl/build_data.py). 직접 수정 금지.\n")
        fp.write("window.RB = ")
        json.dump(payload, fp, ensure_ascii=False, indent=1)
        fp.write(";\n")
    L("[out] wrote", OUT)
    L("[out] counts:", json.dumps(agg["counts"], ensure_ascii=False))
    L("[out] construct agg:")
    for c in agg_constructs:
        L("   ", c["name"], "pre=", c["pre"], "post=", c["post"], "Δ=", c["delta"], "(nPost=%d)"%c["nPost"])

if __name__ == "__main__":
    main()
