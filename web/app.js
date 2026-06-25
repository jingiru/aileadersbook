/* AI 리더스북 - 클라이언트 앱 (외부 의존성 없음) */
(function () {
  "use strict";
  const RB = window.RB || { students: [], agg: {}, meta: {} };
  const app = document.getElementById("app");
  const norm = (s) => (s || "").toString().replace(/\s+/g, "").trim();
  const byId = {};
  RB.students.forEach((s) => (byId[s.id] = s));

  // ---------- helpers ----------
  function h(html) {
    const t = document.createElement("template");
    t.innerHTML = html.trim();
    return t.content.firstChild;
  }
  function esc(s) {
    return (s == null ? "" : String(s)).replace(/[&<>"]/g, (c) =>
      ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c])
    );
  }
  const pct = (v) => Math.max(0, Math.min(100, (Number(v) / 10) * 100));

  // ---------- Drive 미리보기 모달 ----------
  function previewSrc(kind, id) {
    if (kind === "doc") return "https://docs.google.com/document/d/" + id + "/preview";
    return "https://drive.google.com/file/d/" + id + "/preview"; // pdf
  }
  window.__rbView = function (kind, id, title) {
    const src = previewSrc(kind, id);
    const open = kind === "doc"
      ? "https://docs.google.com/document/d/" + id + "/edit"
      : "https://drive.google.com/file/d/" + id + "/view";
    const m = h(`<div class="modal">
      <div class="modal-bar">
        <div class="t">${esc(title || "산출물")}</div>
        <div style="display:flex;gap:8px;align-items:center">
          <a href="${esc(open)}" target="_blank" rel="noopener">↗ 새 탭에서 열기</a>
          <button class="x" title="닫기">✕</button>
        </div>
      </div>
      <iframe src="${esc(src)}" allow="autoplay"></iframe>
    </div>`);
    const close = () => m.remove();
    m.querySelector(".x").onclick = close;
    m.addEventListener("click", (e) => { if (e.target === m) close(); });
    document.body.appendChild(m);
  };

  // ---------- SVG radar ----------
  const SHORT = {
    "AI 원리·한계 이해": "AI 이해",
    "비판적 검증(CHECK)": "비판검증",
    "문제 발견·해결": "문제해결",
    "프로그래밍 구현": "구현력",
    "AI 협업(MATE)": "AI협업",
    "정보 신뢰성 판단": "신뢰성",
    "지속 동기·자기효능감": "동기",
  };
  function radar(axes) {
    // axes: [{name, pre, post}]
    const N = axes.length, R = 92, cx = 150, cy = 122, levels = 5;
    const ang = (i) => -Math.PI / 2 + (i * 2 * Math.PI) / N;
    const pt = (i, r) => [cx + r * Math.cos(ang(i)), cy + r * Math.sin(ang(i))];
    let s = `<svg viewBox="0 0 300 244" width="100%" style="max-width:320px">`;
    // grid rings
    for (let l = 1; l <= levels; l++) {
      const r = (R * l) / levels;
      const p = axes.map((_, i) => pt(i, r).join(",")).join(" ");
      s += `<polygon class="grid-line" points="${p}" />`;
    }
    // spokes + labels
    axes.forEach((a, i) => {
      const [x, y] = pt(i, R);
      s += `<line class="grid-line" x1="${cx}" y1="${cy}" x2="${x}" y2="${y}"/>`;
      const [lx, ly] = pt(i, R + 16);
      const anchor = Math.abs(lx - cx) < 8 ? "middle" : lx > cx ? "start" : "end";
      const label = SHORT[a.name] || a.name;
      s += `<text class="axis-label" x="${lx}" y="${ly + 4}" text-anchor="${anchor}">${esc(label)}</text>`;
    });
    const poly = (key, fill, stroke, dash) => {
      const vals = axes.map((a) => (a[key] == null ? 0 : a[key]));
      const p = axes.map((a, i) => pt(i, (R * (a[key] || 0)) / 10).join(",")).join(" ");
      return `<polygon points="${p}" fill="${fill}" stroke="${stroke}" stroke-width="2" ${dash ? 'stroke-dasharray="4 4"' : ""}/>`;
    };
    const hasPre = axes.some((a) => a.pre != null);
    if (hasPre) s += poly("pre", "rgba(120,140,200,.12)", "#7a89c0", true);
    s += poly("post", "rgba(139,92,246,.30)", "#8b5cf6", false);
    s += `</svg>`;
    return s;
  }

  // ---------- screens ----------
  function renderLogin(msg) {
    app.innerHTML = "";
    const card = h(`
      <div class="login-screen"><div class="login-card">
        <div class="brand">AI · CHECK-MATE</div>
        <h1>AI 리더스북</h1>
        <div class="tag">${esc(RB.meta.subtitle || "")}</div>
        <div class="field"><label>학번 (4자리)</label><input id="in-id" inputmode="numeric" maxlength="4" placeholder="예: 2101"/></div>
        <div class="field"><label>이름</label><input id="in-name" placeholder="예: 가도연"/></div>
        <div class="err" id="err">${esc(msg || "")}</div>
        <button class="btn" id="go">내 리더스북 열기</button>
        <button class="btn ghost" id="agg">📊 전체 성장 현황 (선생님)</button>
      </div></div>`);
    app.appendChild(card);
    const tryLogin = () => {
      const id = norm(card.querySelector("#in-id").value);
      const nm = norm(card.querySelector("#in-name").value);
      const st = byId[id];
      if (!st) return (card.querySelector("#err").textContent = "학번을 찾을 수 없어요. 다시 확인해 주세요.");
      if (norm(st.name) !== nm) return (card.querySelector("#err").textContent = "학번과 이름이 일치하지 않아요.");
      location.hash = "#s/" + id;
    };
    card.querySelector("#go").onclick = tryLogin;
    card.querySelector("#agg").onclick = () => (location.hash = "#agg");
    card.querySelectorAll("input").forEach((i) =>
      i.addEventListener("keydown", (e) => e.key === "Enter" && tryLogin())
    );
    card.querySelector("#in-id").focus();
  }

  function topbar() {
    return `<div class="topbar"><div class="brand">AI · CHECK-MATE 리더스북</div>
      <button class="logout" onclick="location.hash=''">로그아웃</button></div>`;
  }

  function renderBook(st) {
    const growth = st.growth || [];
    const gGrowth = growth.filter((g) => g.type === "growth");
    const gAchieve = growth.filter((g) => g.type === "achieve");
    const radarAxes = gGrowth.map((g) => ({ name: g.name, pre: g.pre, post: g.post }));

    const deltaRows = gGrowth
      .map((g) => {
        const up = g.delta != null && g.delta > 0.05;
        const tag = g.delta == null ? "" : (g.delta >= 0 ? "+" : "") + g.delta.toFixed(1);
        return `<div class="delta-row">
          <div class="nm">${esc(g.name)}</div>
          <div class="bar">
            ${g.pre != null ? `<i class="pre" style="width:${pct(g.pre)}%"></i>` : ""}
            <i class="post" style="width:${pct(g.post)}%"></i>
          </div>
          <div class="delta-tag ${up ? "up" : "flat"}">${g.delta == null ? "사후" : "▲ " + tag}</div>
        </div>`;
      })
      .join("");

    const achRows = gAchieve
      .map(
        (g) => `<div class="ach-row"><div>${esc(g.name)}</div>
        <div class="bar"><i class="post" style="width:${pct(g.post)}%"></i></div>
        <div style="text-align:right;font-weight:700">${g.post == null ? "-" : g.post.toFixed(1)}</div></div>`
      )
      .join("");

    // CHECK card
    const fc = st.factCheck;
    let checkCard;
    if (fc) {
      const sc = fc.scores || {};
      const scorePills = Object.keys(sc)
        .map(
          (k) =>
            `<div class="score-pill"><div class="v">${sc[k] == null ? "-" : sc[k]}</div><div class="k">${esc(k)}</div></div>`
        )
        .join("");
      const members = (fc.members || [])
        .map(
          (m) =>
            `<span class="member ${m.id === st.id ? "me" : ""}">${esc(m.name || m.id)}</span>`
        )
        .join("");
      const hasScores = Object.keys(fc.scores || {}).length > 0;
      checkCard = `<div class="card check">
        <h2>🔍 AI 시대 팩트 체크 <span class="badge check">CHECK</span></h2>
        <div class="lead">AI·정보를 근거 기반으로 비판적으로 검증한 활동 (조별)</div>
        ${fc.team ? `<div class="kv">팀 <b>${esc(fc.team)}</b></div>` : ""}
        ${fc.topic ? `<div class="kv">주제 <b>${esc(fc.topic)}</b></div>` : ""}
        ${
          hasScores
            ? `<div class="scores">${scorePills}
          <div class="score-pill total-pill"><div class="v">${fc.total == null ? "-" : fc.total}<span style="font-size:14px;color:var(--muted)">/${fc.totalMax || 30}</span></div><div class="k">총점</div></div>
        </div>`
            : ""
        }
        ${fc.comment ? `<div class="comment">💬 ${esc(fc.comment)}</div>` : ""}
        ${members ? `<div class="members">${members}</div>` : ""}
        ${
          fc.docId
            ? `<div class="btnrow"><button class="obtn view check" onclick="__rbView('doc','${esc(fc.docId)}','${esc(st.name)} · 팩트체크 활동지')">📝 활동지 보기</button></div>`
            : ""
        }
      </div>`;
    } else {
      checkCard = `<div class="card check"><h2>🔍 AI 시대 팩트 체크 <span class="badge check">CHECK</span></h2>
        <div class="empty">조별 활동 기록을 찾지 못했어요.</div></div>`;
    }

    // MATE card
    const wa = st.webApp;
    let mateCard;
    if (wa) {
      const appBtn = wa.url
        ? `<a class="obtn app" href="${esc(wa.url)}" target="_blank" rel="noopener">▶ 내가 만든 앱 실행하기</a>`
        : "";
      const pdfBtn = wa.pdfId
        ? `<button class="obtn view" onclick="__rbView('pdf','${esc(wa.pdfId)}','${esc(st.name)} · 웹앱 개발 보고서')">📄 보고서 보기</button>`
        : "";
      let mateScore = "";
      if (wa.score) {
        const sc = wa.score.scores || {};
        const pills = Object.keys(sc)
          .map((k) => `<div class="score-pill"><div class="v">${sc[k] == null ? "-" : sc[k]}</div><div class="k">${esc(k)}</div></div>`)
          .join("");
        mateScore = `<div class="scores">${pills}
          <div class="score-pill total-pill"><div class="v">${wa.score.total == null ? "-" : wa.score.total}<span style="font-size:14px;color:var(--muted)">/${wa.score.totalMax || 30}</span></div><div class="k">총점</div></div>
        </div>
        ${wa.score.comment ? `<div class="comment mate">💬 ${esc(wa.score.comment)}</div>` : ""}`;
      } else {
        mateScore = `<div class="grading">⏳ 채점 진행 중</div>`;
      }
      mateCard = `<div class="card mate">
        <h2>🤝 AI 기반 웹앱 개발 <span class="badge mate">MATE</span></h2>
        <div class="lead">AI를 협업 동료로 삼아 직접 만든 웹앱 (개인)</div>
        <div class="kv">앱 이름 <b>${esc(wa.title || "내 웹앱")}</b></div>
        ${wa.desc ? `<div class="kv" style="margin-bottom:10px">${esc(wa.desc)}</div>` : ""}
        ${mateScore}
        ${appBtn || pdfBtn ? `<div class="btnrow">${appBtn}${pdfBtn}</div>` : `<div class="empty">앱 링크가 아직 없어요.</div>`}
      </div>`;
    } else {
      mateCard = `<div class="card mate"><h2>🤝 AI 기반 웹앱 개발 <span class="badge mate">MATE</span></h2>
        <div class="empty">웹앱 제출 기록을 찾지 못했어요.</div></div>`;
    }

    // reflections
    const refl = (st.reflections || [])
      .map(
        (r) =>
          `<div class="tl-item"><div class="tl-phase">${esc(r.phase)}</div><div class="tl-text">${esc(r.text)}</div></div>`
      )
      .join("");

    app.innerHTML = "";
    app.appendChild(
      h(`<div class="wrap">
      ${topbar()}
      <div class="hero">
        <div class="eyebrow">${esc(st.cls)}반 · ${esc(st.id)}</div>
        <h1><b>${esc(st.name)}</b> 님의 AI 리더스북</h1>
        <div class="sub">${esc(RB.meta.subtitle || "")}</div>
        <div class="chips">
          <span class="chip ${st.has.factCheck ? "check on" : ""}">CHECK · 팩트체크 ${st.has.factCheck ? "✓" : "—"}</span>
          <span class="chip ${st.has.webApp ? "mate on" : ""}">MATE · 웹앱개발 ${st.has.webApp ? "✓" : "—"}</span>
        </div>
      </div>

      <div class="section-title">나의 성장 곡선</div>
      <div class="card">
        <div class="growth-wrap">
          <div>
            ${radar(radarAxes)}
            <div class="legend">
              <span><i class="dot" style="background:#7a89c0"></i>수업 전</span>
              <span><i class="dot" style="background:linear-gradient(135deg,#38bdf8,#8b5cf6)"></i>수업 후</span>
            </div>
          </div>
          <div class="delta-list">${deltaRows || '<div class="empty">성장 데이터를 표시할 설문 응답이 부족해요.</div>'}</div>
        </div>
        ${
          achRows
            ? `<div class="section-title" style="margin-top:22px">수업으로 도달한 역량 (사후)</div><div class="ach">${achRows}</div>`
            : ""
        }
      </div>

      <div class="section-title">나의 산출물 · CHECK & MATE</div>
      <div class="grid cols-2">${checkCard}${mateCard}</div>

      <div class="section-title">나의 성찰 기록</div>
      <div class="card">
        ${refl ? `<div class="timeline">${refl}</div>` : '<div class="empty">성찰 기록이 아직 없어요.</div>'}
      </div>

      ${
        st.teacherMsg
          ? `<div class="card teacher" style="margin-top:18px"><h2>💛 선생님에게 한마디</h2><div class="tl-text" style="color:var(--muted)">“${esc(st.teacherMsg)}”</div></div>`
          : ""
      }
      <div class="foot">AI CHECK-MATE · 디지털 포트폴리오 「AI 리더스북」</div>
    </div>`)
    );
  }

  function renderAggregate() {
    const a = RB.agg || {};
    const c = a.counts || {};
    const cons = (a.constructs || []).filter((x) => x.type === "growth");
    const radarAxes = cons.map((x) => ({ name: x.name, pre: x.pre, post: x.post }));
    const rows = (a.constructs || [])
      .map((g) => {
        const tag = g.delta == null ? "사후 도달" : "▲ +" + g.delta.toFixed(2);
        return `<div class="delta-row">
          <div class="nm">${esc(g.name)}</div>
          <div class="bar">
            ${g.pre != null ? `<i class="pre" style="width:${pct(g.pre)}%"></i>` : ""}
            <i class="post" style="width:${pct(g.post)}%"></i>
          </div>
          <div class="delta-tag ${g.delta ? "up" : "flat"}">${tag}</div>
        </div>`;
      })
      .join("");
    app.innerHTML = "";
    app.appendChild(
      h(`<div class="wrap">
      ${topbar()}
      <div class="hero">
        <div class="eyebrow">연구 효과성 · 전체 현황</div>
        <h1><b>AI CHECK-MATE</b> 성장 대시보드</h1>
        <div class="sub">2학년 전체 학생의 사전·사후 자기효능감 변화와 산출물 제출 현황입니다.</div>
      </div>
      <div class="stat-grid">
        <div class="stat"><div class="n">${a.total || 0}</div><div class="l">전체 학생</div></div>
        <div class="stat"><div class="n">${c.factCheck || 0}</div><div class="l">팩트체크(CHECK)</div></div>
        <div class="stat"><div class="n">${c.webApp || 0}</div><div class="l">웹앱(MATE)</div></div>
        <div class="stat"><div class="n">${c.pre || 0}</div><div class="l">사전 설문</div></div>
        <div class="stat"><div class="n">${c.waPost || 0}</div><div class="l">사후 설문</div></div>
      </div>
      <div class="section-title" style="margin-top:24px">역량별 사전 → 사후 변화 (평균, 10점 척도)</div>
      <div class="card"><div class="growth-wrap">
        <div>${radar(radarAxes)}
          <div class="legend"><span><i class="dot" style="background:#7a89c0"></i>사전</span>
          <span><i class="dot" style="background:linear-gradient(135deg,#38bdf8,#8b5cf6)"></i>사후</span></div>
        </div>
        <div class="delta-list">${rows}</div>
      </div></div>
      <div class="foot">개인별 리더스북은 학번·이름으로 로그인하여 확인할 수 있습니다.</div>
    </div>`)
    );
  }

  // ---------- router ----------
  function route() {
    const hash = location.hash || "";
    if (hash.startsWith("#s/")) {
      const id = hash.slice(3);
      if (byId[id]) return renderBook(byId[id]);
      return renderLogin("학생을 찾을 수 없어요.");
    }
    if (hash === "#agg") return renderAggregate();
    renderLogin();
  }
  window.addEventListener("hashchange", route);
  route();
})();
