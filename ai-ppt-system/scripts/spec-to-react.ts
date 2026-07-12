import { escapeHtml, readSpec, writeText } from "./shared.ts";

const spec = readSpec();

const kickerLabels: Record<string, string> = {
  cover: "PRODUCT VISION",
  agenda: "CONVERSATION MAP",
  section: "SECTION",
  problem: "WHY CHANGE",
  insight: "PRODUCT POSITIONING",
  solution: "CORE CAPABILITY",
  process: "BUSINESS LOOP",
  comparison: "BOUNDARY & EVOLUTION",
  timeline: "MILESTONE",
  data_card: "VALUE",
  architecture: "CAPABILITY ARCHITECTURE",
  case: "PILOT",
  roadmap: "ROADMAP",
  summary: "NEXT STEP"
};

function pointList(points: string[], className = "points") {
  return `<ul class="${className}">${points
    .map((point, index) => `<li class="layout-item fit-check"><span>${String(index + 1).padStart(2, "0")}</span>${escapeHtml(point)}</li>`)
    .join("")}</ul>`;
}

function numbered(points: string[]) {
  return `<div class="steps">${points
    .map(
      (point, index) => `<div class="step layout-item fit-check">
        <b>${String(index + 1).padStart(2, "0")}</b>
        <span>${escapeHtml(point)}</span>
      </div>`
    )
    .join('<div class="step-line" aria-hidden="true"></div>')}</div>`;
}

function cards(points: string[], kind = "cards") {
  return `<div class="${kind}">${points
    .map(
      (point, index) => `<div class="card layout-item fit-check">
        <i>${String(index + 1).padStart(2, "0")}</i>
        <span>${escapeHtml(point)}</span>
      </div>`
    )
    .join("")}</div>`;
}

function bodyFor(slide: (typeof spec.slides)[number]) {
  if (slide.type === "cover") {
    return `<div class="cover-values">${slide.points
      .map((point) => `<span class="layout-item fit-check">${escapeHtml(point)}</span>`)
      .join("")}</div>`;
  }
  if (["process", "timeline", "roadmap", "agenda"].includes(slide.type)) {
    return numbered(slide.points);
  }
  if (slide.type === "problem") {
    return cards(slide.points, "cards problem-cards");
  }
  if (slide.type === "architecture") {
    return cards(slide.points, "cards architecture-cards");
  }
  if (["solution", "data_card", "comparison", "case", "summary"].includes(slide.type)) {
    return cards(slide.points);
  }
  return pointList(slide.points);
}

const slides = spec.slides
  .map(
    (slide, index) => `<section class="slide ${slide.type}${index === 0 ? " active" : ""}" data-page="${slide.page}" aria-hidden="${index === 0 ? "false" : "true"}">
  <div class="ambient ambient-a" aria-hidden="true"></div>
  <div class="ambient ambient-b" aria-hidden="true"></div>
  <div class="slide-grid" aria-hidden="true"></div>
  <div class="content-shell">
    <div class="slide-kicker">${escapeHtml(kickerLabels[slide.type] ?? slide.type.toUpperCase())}</div>
    <h1 class="layout-item fit-check">${escapeHtml(slide.title)}</h1>
    <p class="message layout-item fit-check">${escapeHtml(slide.message)}</p>
    ${bodyFor(slide)}
  </div>
  <div class="brand-mark"><span></span>智能计划管控中枢</div>
  <footer>${slide.page.toString().padStart(2, "0")}</footer>
</section>`
  )
  .join("\n");

const html = `<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>${escapeHtml(spec.deck.title)}</title>
  <style>
    :root {
      --navy: #071525;
      --navy-2: #0d2237;
      --ink: #152538;
      --muted: #5f6f80;
      --line: #d7e0e8;
      --paper: #f3f6f8;
      --white: #ffffff;
      --teal: #0f8f83;
      --teal-soft: #d9f0ec;
      --blue: #2d64d8;
      --orange: #f1a33c;
      --orange-soft: #fff0d9;
      --danger: #d95d4f;
      --scale: 1;
    }
    * { box-sizing: border-box; }
    html, body { width: 100%; height: 100%; }
    body {
      margin: 0;
      background: #030b14;
      color: var(--ink);
      font-family: "Microsoft YaHei", "PingFang SC", "Noto Sans SC", Arial, sans-serif;
      overflow: hidden;
    }
    .deck {
      position: relative;
      width: 100vw;
      height: 100vh;
      overflow: hidden;
      background:
        radial-gradient(circle at 20% 20%, rgba(15, 143, 131, .16), transparent 32%),
        radial-gradient(circle at 82% 76%, rgba(45, 100, 216, .18), transparent 34%),
        #030b14;
    }
    .slide {
      position: absolute;
      left: 50%;
      top: 50%;
      width: 1280px;
      height: 720px;
      padding: 58px 70px 54px;
      background: var(--paper);
      overflow: hidden;
      page-break-after: always;
      opacity: 0;
      visibility: hidden;
      pointer-events: none;
      transform: translate(-50%, -48%) scale(calc(var(--scale) * .97));
      transition: opacity .34s ease, transform .42s cubic-bezier(.2,.8,.2,1), visibility .34s;
      box-shadow: 0 30px 90px rgba(0, 0, 0, .35);
    }
    .slide.active {
      opacity: 1;
      visibility: visible;
      pointer-events: auto;
      transform: translate(-50%, -50%) scale(var(--scale));
    }
    .slide::before {
      content: "";
      position: absolute;
      left: 0;
      top: 0;
      width: 12px;
      height: 100%;
      background: linear-gradient(180deg, var(--orange), var(--teal));
      z-index: 3;
    }
    .slide-grid {
      position: absolute;
      inset: 0;
      opacity: .28;
      background-image:
        linear-gradient(rgba(21,37,56,.05) 1px, transparent 1px),
        linear-gradient(90deg, rgba(21,37,56,.05) 1px, transparent 1px);
      background-size: 48px 48px;
      mask-image: linear-gradient(90deg, transparent 0%, #000 40%, #000 100%);
    }
    .ambient { position: absolute; border-radius: 50%; filter: blur(1px); opacity: .5; }
    .ambient-a { width: 360px; height: 360px; right: -160px; top: -180px; background: rgba(15,143,131,.15); }
    .ambient-b { width: 280px; height: 280px; left: -160px; bottom: -170px; background: rgba(45,100,216,.12); }
    .content-shell { position: relative; z-index: 2; }
    .slide-kicker {
      display: inline-flex;
      align-items: center;
      min-height: 28px;
      padding: 5px 12px;
      margin-bottom: 18px;
      border-radius: 999px;
      background: var(--teal-soft);
      color: #076b63;
      font-size: 14px;
      font-weight: 800;
      letter-spacing: 1.5px;
    }
    h1 {
      width: 1020px;
      margin: 0;
      color: var(--ink);
      font-size: 48px;
      line-height: 1.14;
      font-weight: 800;
      letter-spacing: -.8px;
    }
    .message {
      width: 1040px;
      margin: 18px 0 34px;
      color: var(--muted);
      font-size: 27px;
      line-height: 1.36;
      font-weight: 500;
    }
    .cards {
      display: grid;
      grid-template-columns: repeat(3, 1fr);
      gap: 22px;
      width: 1100px;
    }
    .card {
      position: relative;
      min-height: 166px;
      padding: 52px 26px 26px;
      border: 1px solid var(--line);
      border-radius: 18px;
      background: rgba(255,255,255,.88);
      box-shadow: 0 16px 36px rgba(28,55,83,.08);
      color: var(--ink);
      font-size: 26px;
      line-height: 1.34;
      font-weight: 700;
      display: flex;
      align-items: flex-end;
    }
    .card::after {
      content: "";
      position: absolute;
      left: 26px;
      bottom: 22px;
      width: 42px;
      height: 4px;
      background: var(--orange);
      border-radius: 2px;
      transform: translateY(12px);
    }
    .card i {
      position: absolute;
      top: 20px;
      left: 24px;
      color: var(--teal);
      font-size: 18px;
      font-style: normal;
      font-weight: 800;
    }
    .problem-cards .card { border-top: 5px solid var(--danger); }
    .problem-cards .card i { color: var(--danger); }
    .architecture-cards .card { border-top: 5px solid var(--blue); }
    .architecture-cards .card:nth-child(2) { border-top-color: var(--teal); }
    .architecture-cards .card:nth-child(3) { border-top-color: var(--orange); }
    .steps {
      display: flex;
      align-items: stretch;
      width: 1100px;
      gap: 0;
    }
    .step {
      position: relative;
      flex: 1;
      min-height: 174px;
      padding: 30px 26px;
      border: 1px solid var(--line);
      border-radius: 18px;
      background: rgba(255,255,255,.9);
      box-shadow: 0 16px 36px rgba(28,55,83,.08);
    }
    .step b {
      display: block;
      color: var(--orange);
      font-size: 24px;
      line-height: 1;
      margin-bottom: 30px;
    }
    .step span { color: var(--ink); font-size: 26px; line-height: 1.34; font-weight: 700; }
    .step-line {
      position: relative;
      flex: 0 0 42px;
    }
    .step-line::before {
      content: "";
      position: absolute;
      top: 50%;
      left: 6px;
      width: 30px;
      height: 2px;
      background: var(--teal);
    }
    .step-line::after {
      content: "";
      position: absolute;
      top: calc(50% - 5px);
      right: 4px;
      border-left: 8px solid var(--teal);
      border-top: 6px solid transparent;
      border-bottom: 6px solid transparent;
    }
    .points { display: grid; gap: 16px; width: 930px; margin: 0; padding: 0; list-style: none; }
    .points li {
      display: flex;
      align-items: center;
      min-height: 70px;
      padding: 16px 22px;
      border-radius: 14px;
      border: 1px solid var(--line);
      background: rgba(255,255,255,.9);
      font-size: 25px;
      font-weight: 700;
    }
    .points li span { width: 48px; color: var(--teal); font-size: 17px; }
    .brand-mark {
      position: absolute;
      left: 70px;
      bottom: 30px;
      z-index: 2;
      color: #7a8897;
      font-size: 14px;
      font-weight: 700;
      letter-spacing: .5px;
    }
    .brand-mark span {
      display: inline-block;
      width: 8px;
      height: 8px;
      margin-right: 8px;
      border-radius: 50%;
      background: var(--orange);
    }
    footer {
      position: absolute;
      right: 66px;
      bottom: 28px;
      z-index: 2;
      color: #7a8897;
      font-size: 15px;
      font-weight: 700;
    }
    .cover, .summary {
      color: var(--white);
      background:
        linear-gradient(120deg, rgba(7,21,37,.98), rgba(13,34,55,.94)),
        var(--navy);
    }
    .cover::before, .summary::before { width: 14px; }
    .cover .slide-grid, .summary .slide-grid {
      opacity: .5;
      background-image:
        linear-gradient(rgba(255,255,255,.045) 1px, transparent 1px),
        linear-gradient(90deg, rgba(255,255,255,.045) 1px, transparent 1px);
      mask-image: none;
    }
    .cover .ambient-a { width: 520px; height: 520px; right: -100px; top: -210px; background: rgba(15,143,131,.3); }
    .cover .ambient-b { width: 440px; height: 440px; left: 160px; bottom: -360px; background: rgba(241,163,60,.23); }
    .cover .slide-kicker, .summary .slide-kicker { color: #9ee4dc; background: rgba(15,143,131,.22); }
    .cover h1, .summary h1 { color: var(--white); }
    .cover h1 { width: 1040px; font-size: 64px; line-height: 1.1; }
    .cover .message, .summary .message { color: #c8d4df; }
    .cover .message { width: 1030px; font-size: 30px; margin-top: 24px; }
    .cover-values { display: flex; gap: 16px; margin-top: 10px; }
    .cover-values span {
      min-width: 205px;
      padding: 15px 20px;
      border: 1px solid rgba(255,255,255,.16);
      border-radius: 12px;
      background: rgba(255,255,255,.07);
      color: #f5f8fb;
      font-size: 20px;
      font-weight: 700;
    }
    .cover .brand-mark, .cover footer, .summary .brand-mark, .summary footer { color: #8da0b2; }
    .summary .card { background: rgba(255,255,255,.08); border-color: rgba(255,255,255,.14); color: var(--white); }
    .summary .card i { color: #9ee4dc; }
    .comparison .card:nth-child(1) { border-top: 5px solid var(--blue); }
    .comparison .card:nth-child(2) { border-top: 5px solid var(--teal); }
    .comparison .card:nth-child(3) { border-top: 5px solid var(--orange); }
    .page-hud {
      position: fixed;
      left: 50%;
      bottom: 14px;
      z-index: 50;
      width: min(420px, 58vw);
      transform: translateX(-50%);
      color: #d5e0e9;
      font-size: 12px;
      letter-spacing: 1px;
      text-align: center;
      pointer-events: none;
    }
    .progress-track { height: 3px; margin-bottom: 8px; border-radius: 2px; background: rgba(255,255,255,.16); overflow: hidden; }
    .progress-bar { width: 0; height: 100%; background: linear-gradient(90deg, var(--teal), var(--orange)); transition: width .3s ease; }
    @page { size: 1280px 720px; margin: 0; }
    @media print {
      html, body { width: auto; height: auto; overflow: visible; background: white; }
      .deck { width: auto; height: auto; overflow: visible; background: white; }
      .slide {
        position: relative;
        left: auto;
        top: auto;
        display: block;
        opacity: 1;
        visibility: visible;
        pointer-events: auto;
        transform: none !important;
        margin: 0;
        box-shadow: none;
      }
      .page-hud { display: none; }
    }
  </style>
</head>
<body>
<main class="deck" aria-label="${escapeHtml(spec.deck.title)}">
${slides}
</main>
<div class="page-hud" aria-hidden="true">
  <div class="progress-track"><div class="progress-bar"></div></div>
  <span class="page-current">01</span> / <span class="page-total">${String(spec.slides.length).padStart(2, "0")}</span>
</div>
<script>
  const deck = document.querySelector('.deck');
  const slideItems = Array.from(document.querySelectorAll('.slide'));
  const currentLabel = document.querySelector('.page-current');
  const progressBar = document.querySelector('.progress-bar');
  let activeIndex = 0;
  let wheelLocked = false;
  let touchStartY = null;

  function resizeStage() {
    const scale = Math.min(window.innerWidth / 1280, window.innerHeight / 720) * 0.94;
    document.documentElement.style.setProperty('--scale', String(Math.max(0.2, scale)));
  }

  function renderSlide(index) {
    activeIndex = Math.max(0, Math.min(slideItems.length - 1, index));
    slideItems.forEach((slide, slideIndex) => {
      const active = slideIndex === activeIndex;
      slide.classList.toggle('active', active);
      slide.setAttribute('aria-hidden', active ? 'false' : 'true');
    });
    if (currentLabel) currentLabel.textContent = String(activeIndex + 1).padStart(2, '0');
    if (progressBar) progressBar.style.width = String(((activeIndex + 1) / slideItems.length) * 100) + '%';
  }

  function move(direction) {
    renderSlide(activeIndex + direction);
  }

  deck?.addEventListener('wheel', (event) => {
    if (Math.abs(event.deltaY) < 20) return;
    event.preventDefault();
    if (wheelLocked) return;
    wheelLocked = true;
    move(event.deltaY > 0 ? 1 : -1);
    window.setTimeout(() => { wheelLocked = false; }, 620);
  }, { passive: false });

  deck?.addEventListener('touchstart', (event) => {
    touchStartY = event.touches[0]?.clientY ?? null;
  }, { passive: true });

  deck?.addEventListener('touchend', (event) => {
    if (touchStartY === null) return;
    const endY = event.changedTouches[0]?.clientY ?? touchStartY;
    const delta = touchStartY - endY;
    if (Math.abs(delta) > 45) move(delta > 0 ? 1 : -1);
    touchStartY = null;
  }, { passive: true });

  window.addEventListener('resize', resizeStage);
  resizeStage();
  renderSlide(0);
</script>
</body>
</html>
`;

writeText(["output", "react", "index.html"], html);
console.log("Generated output/react/index.html.");
