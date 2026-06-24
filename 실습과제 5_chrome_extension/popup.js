const RSS_URL = "https://www.mois.go.kr/gpms/view/jsp/rss/rss.jsp?ctxCd=1012";
const MAX_ITEMS = 30;

const statusEl = document.getElementById("status");
const listEl = document.getElementById("newsList");
const ministryListEl = document.getElementById("ministryList");
const refreshBtn = document.getElementById("refreshBtn");
const selectAllBtn = document.getElementById("selectAllBtn");
const clearAllBtn = document.getElementById("clearAllBtn");

let allItems = [];
let allMinistries = [];
let selectedMinistries = new Set();

function parsePubDate(pubDate = "") {
  const raw = pubDate.trim();
  if (!raw) {
    return 0;
  }

  const parsed = Date.parse(raw);
  if (!Number.isNaN(parsed)) {
    return parsed;
  }

  const koMatch = raw.match(
    /(?:[가-힣]{1,2},\s*)?(\d{1,2})\s*(\d{1,2})월\s*(\d{4})\s*(\d{1,2}):(\d{2}):(\d{2})\s*([A-Z]{3,4})?/i
  );

  if (!koMatch) {
    return 0;
  }

  const day = Number(koMatch[1]);
  const month = Number(koMatch[2]);
  const year = Number(koMatch[3]);
  const hour = Number(koMatch[4]);
  const minute = Number(koMatch[5]);
  const second = Number(koMatch[6]);
  const tz = (koMatch[7] || "KST").toUpperCase();
  const offsetHours = tz === "KST" ? 9 : 0;

  return Date.UTC(year, month - 1, day, hour - offsetHours, minute, second);
}

function decodeHtml(input = "") {
  const textarea = document.createElement("textarea");
  textarea.innerHTML = input;
  return textarea.value;
}

function stripHtml(input = "") {
  return decodeHtml(input.replace(/<[^>]*>/g, " "))
    .replace(/\s+/g, " ")
    .trim();
}

function extractTag(itemXml, tagNames) {
  for (const tag of tagNames) {
    const re = new RegExp(`<${tag}[^>]*>([\\s\\S]*?)<\\/${tag}>`, "i");
    const match = itemXml.match(re);
    if (!match) {
      continue;
    }

    const raw = match[1]
      .replace(/<!\[CDATA\[([\s\S]*?)\]\]>/g, "$1")
      .trim();

    if (raw) {
      return raw;
    }
  }

  return "";
}

function parseRssItems(xmlText) {
  const itemBlocks = xmlText.match(/<item\b[\s\S]*?<\/item>/gi) || [];

  return itemBlocks
    .map((itemXml) => {
      const title = decodeHtml(stripHtml(extractTag(itemXml, ["title"])));
      const link = extractTag(itemXml, ["link"]);
      const descriptionHtml = extractTag(itemXml, ["description"]);
      const creator = decodeHtml(stripHtml(extractTag(itemXml, ["dc:creator", "author"])));
      const pubDate = extractTag(itemXml, ["pubDate"]);
      const guid = extractTag(itemXml, ["guid"]);
      const snippet = stripHtml(descriptionHtml).slice(0, 140);

      return {
        title: title || "(제목 없음)",
        link,
        description: snippet,
        creator: creator || "미분류",
        pubDate,
        guid,
        timestamp: parsePubDate(pubDate)
      };
    })
    .filter((item) => item.link)
    .sort((a, b) => b.timestamp - a.timestamp)
    .slice(0, MAX_ITEMS);
}

function toSortedMinistries(items) {
  return Array.from(new Set(items.map((item) => item.creator))).sort((a, b) => a.localeCompare(b, "ko"));
}

function toOrderedSelectedArray() {
  return allMinistries.filter((name) => selectedMinistries.has(name));
}

function sameArray(a, b) {
  if (a.length !== b.length) {
    return false;
  }

  for (let i = 0; i < a.length; i += 1) {
    if (a[i] !== b[i]) {
      return false;
    }
  }

  return true;
}

function resolveSelectedMinistries(saved, ministries) {
  if (!ministries.length) {
    return [];
  }

  if (!Array.isArray(saved)) {
    return [...ministries];
  }

  const ministrySet = new Set(ministries);
  const filtered = saved.filter((name) => ministrySet.has(name));

  if (saved.length > 0 && filtered.length === 0) {
    return [...ministries];
  }

  return filtered;
}

function renderMinistryList() {
  ministryListEl.innerHTML = "";

  if (!allMinistries.length) {
    const empty = document.createElement("div");
    empty.className = "empty";
    empty.textContent = "표시할 부처가 없습니다.";
    ministryListEl.appendChild(empty);
    return;
  }

  const frag = document.createDocumentFragment();

  for (const ministry of allMinistries) {
    const label = document.createElement("label");
    label.className = "ministry-option";

    const checkbox = document.createElement("input");
    checkbox.type = "checkbox";
    checkbox.value = ministry;
    checkbox.checked = selectedMinistries.has(ministry);

    checkbox.addEventListener("change", async (event) => {
      if (event.target.checked) {
        selectedMinistries.add(ministry);
      } else {
        selectedMinistries.delete(ministry);
      }

      await persistSelectionAndSync();
      renderList(allItems);
    });

    const text = document.createElement("span");
    text.textContent = ministry;

    label.append(checkbox, text);
    frag.appendChild(label);
  }

  ministryListEl.appendChild(frag);
}

function renderList(items) {
  const visible = items.filter((item) => selectedMinistries.has(item.creator));

  listEl.innerHTML = "";

  if (visible.length === 0) {
    const li = document.createElement("li");
    li.className = "empty";
    li.textContent = "선택한 부처명의 기사가 없습니다.";
    listEl.appendChild(li);
    statusEl.textContent = `0건 · ${selectedMinistries.size}/${allMinistries.length}개 부처 선택`;
    return;
  }

  const frag = document.createDocumentFragment();

  for (const item of visible) {
    const li = document.createElement("li");
    li.className = "news-card";

    const a = document.createElement("a");
    a.className = "news-link";
    a.href = item.link;
    a.title = "새 탭으로 열기";

    a.addEventListener("click", (event) => {
      event.preventDefault();
      chrome.tabs.create({ url: item.link });
    });

    const title = document.createElement("h2");
    title.className = "news-title";
    title.textContent = item.title;

    const meta = document.createElement("p");
    meta.className = "news-meta";
    const dateText = item.timestamp
      ? new Date(item.timestamp).toLocaleString("ko-KR", { timeZone: "Asia/Seoul" })
      : "날짜 정보 없음";
    meta.textContent = `${item.creator} · ${dateText}`;

    const snippet = document.createElement("p");
    snippet.className = "news-snippet";
    snippet.textContent = item.description || "내용 요약 없음";

    a.append(title, meta, snippet);
    li.appendChild(a);
    frag.appendChild(li);
  }

  listEl.appendChild(frag);
  statusEl.textContent = `${visible.length}건 표시 중 · ${selectedMinistries.size}/${allMinistries.length}개 부처 선택`;
}

async function fetchItems() {
  const response = await fetch(RSS_URL, { cache: "no-store" });
  if (!response.ok) {
    throw new Error(`RSS 조회 실패: ${response.status}`);
  }

  const xmlText = await response.text();
  return parseRssItems(xmlText);
}

async function loadSelectedMinistriesRaw() {
  const data = await chrome.storage.sync.get(["selectedMinistries", "selectedMinistry"]);

  if (Array.isArray(data.selectedMinistries)) {
    return data.selectedMinistries;
  }

  if (typeof data.selectedMinistry === "string" && data.selectedMinistry.trim()) {
    return [data.selectedMinistry.trim()];
  }

  return undefined;
}

async function saveSelectedMinistries(ministries) {
  await chrome.storage.sync.set({ selectedMinistries: ministries });
  await chrome.storage.sync.remove("selectedMinistry");
}

async function persistSelectionAndSync() {
  const selected = toOrderedSelectedArray();
  await saveSelectedMinistries(selected);

  chrome.runtime.sendMessage({
    type: "selectedMinistriesChanged",
    ministries: selected
  });
}

async function reloadFeed() {
  statusEl.textContent = "RSS 불러오는 중...";

  try {
    allItems = await fetchItems();
    allMinistries = toSortedMinistries(allItems);

    const rawSaved = await loadSelectedMinistriesRaw();
    const resolved = resolveSelectedMinistries(rawSaved, allMinistries);
    selectedMinistries = new Set(resolved);

    renderMinistryList();
    renderList(allItems);

    const normalizedSaved = Array.isArray(rawSaved)
      ? rawSaved.filter((name) => allMinistries.includes(name))
      : [];

    if (!sameArray(normalizedSaved, toOrderedSelectedArray())) {
      await persistSelectionAndSync();
    }
  } catch (error) {
    listEl.innerHTML = "";
    const li = document.createElement("li");
    li.className = "empty";
    li.textContent = "RSS를 불러오지 못했습니다. 잠시 후 다시 시도해 주세요.";
    listEl.appendChild(li);
    statusEl.textContent = `오류: ${error.message}`;
  }
}

selectAllBtn.addEventListener("click", async () => {
  selectedMinistries = new Set(allMinistries);
  renderMinistryList();
  await persistSelectionAndSync();
  renderList(allItems);
});

clearAllBtn.addEventListener("click", async () => {
  selectedMinistries = new Set();
  renderMinistryList();
  await persistSelectionAndSync();
  renderList(allItems);
});

refreshBtn.addEventListener("click", async () => {
  await reloadFeed();
  chrome.runtime.sendMessage({ type: "manualCheck" });
});

reloadFeed();
