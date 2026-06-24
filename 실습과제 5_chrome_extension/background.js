const RSS_URL = "https://www.mois.go.kr/gpms/view/jsp/rss/rss.jsp?ctxCd=1012";
const ALARM_NAME = "checkMinistryRss";
const CHECK_INTERVAL_MINUTES = 1;

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

function decodeEntities(text = "") {
  return text
    .replace(/&lt;/g, "<")
    .replace(/&gt;/g, ">")
    .replace(/&amp;/g, "&")
    .replace(/&quot;/g, '"')
    .replace(/&#39;/g, "'")
    .replace(/&nbsp;/g, " ");
}

function stripHtml(text = "") {
  return decodeEntities(text.replace(/<[^>]*>/g, " "))
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
      const title = stripHtml(extractTag(itemXml, ["title"]));
      const link = extractTag(itemXml, ["link"]);
      const description = stripHtml(extractTag(itemXml, ["description"]));
      const creator = stripHtml(extractTag(itemXml, ["dc:creator", "author"])) || "미분류";
      const pubDate = extractTag(itemXml, ["pubDate"]);
      const guid = extractTag(itemXml, ["guid"]);

      return {
        title: title || "(제목 없음)",
        link,
        description,
        creator,
        pubDate,
        guid,
        timestamp: parsePubDate(pubDate)
      };
    })
    .filter((item) => item.link)
    .sort((a, b) => b.timestamp - a.timestamp);
}

function toSortedMinistries(items) {
  return Array.from(new Set(items.map((item) => item.creator))).sort((a, b) => a.localeCompare(b, "ko"));
}

function toItemKey(item) {
  return item.guid || item.link || `${item.title}|${item.pubDate}`;
}

function latestByMinistry(items) {
  const map = {};

  for (const item of items) {
    if (!map[item.creator]) {
      map[item.creator] = item;
    }
  }

  return map;
}

function normalizeIncomingMinistries(ministries) {
  if (!Array.isArray(ministries)) {
    return [];
  }

  return Array.from(new Set(ministries.filter((name) => typeof name === "string" && name.trim())));
}

async function fetchItems() {
  const response = await fetch(RSS_URL, { cache: "no-store" });
  if (!response.ok) {
    throw new Error(`RSS 조회 실패: ${response.status}`);
  }

  const xmlText = await response.text();
  return parseRssItems(xmlText);
}

async function loadStoredSelection() {
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

async function resolveSelectedMinistries(items) {
  const available = toSortedMinistries(items);
  const stored = await loadStoredSelection();

  if (!Array.isArray(stored)) {
    await saveSelectedMinistries(available);
    return available;
  }

  const availableSet = new Set(available);
  const filtered = stored.filter((name) => availableSet.has(name));

  if (stored.length > 0 && filtered.length === 0) {
    await saveSelectedMinistries(available);
    return available;
  }

  if (filtered.length !== stored.length) {
    await saveSelectedMinistries(filtered);
  }

  return filtered;
}

async function setLatestBaselineForMinistries(ministries, items) {
  if (!ministries.length) {
    return;
  }

  const latestMap = latestByMinistry(items);
  const data = await chrome.storage.local.get({ lastSeenByMinistry: {} });
  const lastSeenByMinistry = data.lastSeenByMinistry;
  let changed = false;

  for (const ministry of ministries) {
    const latest = latestMap[ministry];
    if (!latest) {
      continue;
    }

    lastSeenByMinistry[ministry] = toItemKey(latest);
    changed = true;
  }

  if (changed) {
    await chrome.storage.local.set({ lastSeenByMinistry });
  }
}

async function notifyIfNewArticles() {
  const items = await fetchItems();
  const selectedMinistries = await resolveSelectedMinistries(items);

  if (!selectedMinistries.length) {
    return;
  }

  const latestMap = latestByMinistry(items);
  const data = await chrome.storage.local.get({ lastSeenByMinistry: {} });
  const lastSeenByMinistry = data.lastSeenByMinistry;
  const notifications = [];
  let changed = false;

  for (const ministry of selectedMinistries) {
    const latest = latestMap[ministry];
    if (!latest) {
      continue;
    }

    const latestKey = toItemKey(latest);
    const previousKey = lastSeenByMinistry[ministry];

    if (!previousKey) {
      lastSeenByMinistry[ministry] = latestKey;
      changed = true;
      continue;
    }

    if (latestKey !== previousKey) {
      lastSeenByMinistry[ministry] = latestKey;
      changed = true;
      notifications.push({ ministry, item: latest });
    }
  }

  if (changed) {
    await chrome.storage.local.set({ lastSeenByMinistry });
  }

  for (const notice of notifications) {
    await chrome.notifications.create(`new-rss-${Date.now()}-${notice.ministry}`, {
      type: "basic",
      iconUrl: "rss.svg",
      title: `[${notice.ministry}] 새 RSS 글 등록`,
      message: notice.item.title,
      priority: 2
    });
  }
}

async function ensureAlarm() {
  const alarm = await chrome.alarms.get(ALARM_NAME);
  if (!alarm) {
    chrome.alarms.create(ALARM_NAME, {
      periodInMinutes: CHECK_INTERVAL_MINUTES,
      delayInMinutes: 0.2
    });
  }
}

chrome.runtime.onInstalled.addListener(async () => {
  try {
    await ensureAlarm();
    const items = await fetchItems();
    const ministries = await resolveSelectedMinistries(items);
    await setLatestBaselineForMinistries(ministries, items);
  } catch (error) {
    console.error("설치 초기화 실패", error);
  }
});

chrome.runtime.onStartup.addListener(async () => {
  await ensureAlarm();
});

chrome.alarms.onAlarm.addListener(async (alarm) => {
  if (alarm.name !== ALARM_NAME) {
    return;
  }

  try {
    await notifyIfNewArticles();
  } catch (error) {
    console.error("RSS 알림 체크 실패", error);
  }
});

chrome.runtime.onMessage.addListener((message, sender, sendResponse) => {
  if (message?.type === "selectedMinistriesChanged") {
    const ministries = normalizeIncomingMinistries(message.ministries);

    saveSelectedMinistries(ministries)
      .then(async () => {
        const items = await fetchItems();
        await setLatestBaselineForMinistries(ministries, items);
        sendResponse({ ok: true });
      })
      .catch((error) => {
        console.error(error);
        sendResponse({ ok: false, error: String(error) });
      });
    return true;
  }

  if (message?.type === "manualCheck") {
    notifyIfNewArticles()
      .then(() => sendResponse({ ok: true }))
      .catch((error) => {
        console.error(error);
        sendResponse({ ok: false, error: String(error) });
      });
    return true;
  }

  return false;
});
