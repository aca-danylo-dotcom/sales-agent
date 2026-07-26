// Follow-up Agent — інтерактивність мокапу (без бекенду, дані фіктивні)

const deals = {
  0: {
    title: 'ТОВ «БудПроект»',
    priorityLabel: 'Високий пріоритет',
    priorityClass: 'priority-high',
    stage: 'КП надіслано',
    amount: '450 000 ₴',
    owner: 'Олексій Смирнов',
    lastContact: '2 дні тому',
    why: 'Клієнт запросив комерційну пропозицію 2 дні тому. Зазвичай клієнти на цьому етапі приймають рішення протягом 1–2 днів. Є ризик втрати угоди.',
    action: 'Написати клієнту та уточнити, чи є питання щодо пропозиції.',
    draft: 'Олексію, доброго дня!\n\nМинулого тижня ми надіслали вам комерційну пропозицію за вашим запитом.\n\nПідкажіть, чи вдалося її переглянути? Готовий відповісти на запитання або надати додаткову інформацію.\n\nБуду радий допомогти!'
  },
  1: {
    title: 'ТОВ «ПромТех»',
    priorityLabel: 'Середній пріоритет',
    priorityClass: 'priority-mid',
    stage: 'Переговори',
    amount: '320 000 ₴',
    owner: 'Марина Ковальчук',
    lastContact: '5 днів тому',
    why: 'Переговори з клієнтом призупинились 5 днів тому без явної причини. Це другий за сумою активний контакт менеджера — втрата уваги тут особливо ризикована.',
    action: 'Зателефонувати клієнту та з\'ясувати, чи є додаткові питання або заперечення.',
    draft: 'Доброго дня, Марино!\n\nМи призупинили спілкування щодо співпраці 5 днів тому. Чи залишились у вас запитання, на які я можу відповісти?\n\nГотовий обговорити деталі у зручний для вас час.'
  },
  2: {
    title: 'ТОВ «МегаПласт»',
    priorityLabel: 'Середній пріоритет',
    priorityClass: 'priority-mid',
    stage: 'КП надіслано',
    amount: '280 000 ₴',
    owner: 'Дмитро Іванов',
    lastContact: '4 дні тому',
    why: 'Клієнт запросив комерційну пропозицію 4 дні тому і досі не відповів. Пауза наближається до критичної — ризик втрати угоди зростає.',
    action: 'Написати клієнту та уточнити, чи є питання щодо пропозиції.',
    draft: 'Доброго дня!\n\nЧотири дні тому ми надіслали комерційну пропозицію за вашим запитом.\n\nПідкажіть, чи вдалося її розглянути? Готовий відповісти на будь-які запитання.'
  },
  3: {
    title: 'ТОВ «БудКомплект»',
    priorityLabel: 'Низький пріоритет',
    priorityClass: 'priority-low',
    stage: 'Новий лід',
    amount: '150 000 ₴',
    owner: 'Марина Ковальчук',
    lastContact: '6 годин тому',
    why: 'Новий лід перебуває без відповіді 6 годин. Швидка перша відповідь суттєво підвищує шанс конверсії в угоду.',
    action: 'Написати першому клієнту, представитися та запропонувати зручний час для дзвінка.',
    draft: 'Доброго дня!\n\nДякую за звернення. Мене звати Марина, я допоможу підібрати оптимальне рішення під ваш запит.\n\nКоли вам буде зручно коротко поговорити по телефону?'
  },
  4: {
    title: 'ТОВ «Інтер\'єр+»',
    priorityLabel: 'Низький пріоритет',
    priorityClass: 'priority-low',
    stage: 'Зустріч проведена',
    amount: '210 000 ₴',
    owner: 'Дмитро Іванов',
    lastContact: '7 днів тому',
    why: 'Після зустрічі минуло 7 днів без наступного контакту. Клієнт міг втратити інтерес або чекає на ваш крок.',
    action: 'Надіслати підсумок зустрічі та запропонувати наступний крок.',
    draft: 'Доброго дня!\n\nДякую за зустріч минулого тижня. Надсилаю короткий підсумок домовленостей.\n\nПропоную обговорити наступні кроки — коли вам зручно?'
  },
  5: {
    title: 'ТОВ «Вектор»',
    priorityLabel: 'Низький пріоритет',
    priorityClass: 'priority-low',
    stage: 'Переговори',
    amount: '95 000 ₴',
    owner: 'Марина Ковальчук',
    lastContact: '12 днів тому',
    why: '12 днів без будь-якої активності по угоді — найдовша пауза в поточному списку. Висока ймовірність, що угода "зависла".',
    action: 'Зв\'язатися з клієнтом і уточнити актуальність угоди.',
    draft: 'Доброго дня!\n\nДавно не спілкувались щодо нашої співпраці. Чи актуальне ще питання для вас?\n\nБуду радий продовжити, якщо це ще в планах.'
  },
  6: {
    title: 'ФОП Смирнов О.О.',
    priorityLabel: 'Низький пріоритет',
    priorityClass: 'priority-low',
    stage: 'КП надіслано',
    amount: '75 000 ₴',
    owner: 'Дмитро Іванов',
    lastContact: '8 днів тому',
    why: 'Комерційну пропозицію надіслано 8 днів тому, відповіді немає. Сума невелика, але угода досі відкрита.',
    action: 'Написати клієнту та уточнити, чи є питання щодо пропозиції.',
    draft: 'Доброго дня!\n\nТиждень тому ми надіслали комерційну пропозицію.\n\nПідкажіть, чи актуальна ще співпраця? Готовий відповісти на запитання.'
  }
};

let currentIndex = '0';
let sortByAmount = false;
let currentPage = 1;

function showToast(message) {
  const toast = document.getElementById('toast');
  toast.textContent = message;
  toast.hidden = false;
  requestAnimationFrame(() => toast.classList.add('show'));
  clearTimeout(showToast._t);
  showToast._t = setTimeout(() => {
    toast.classList.remove('show');
    setTimeout(() => { toast.hidden = true; }, 200);
  }, 2200);
}

// --- Навігація по сайдбару ---
function switchView(target) {
  ['today', 'deals', 'placeholder'].forEach(name => {
    document.getElementById('view-' + name).hidden = name !== target;
  });
}

document.getElementById('nav').addEventListener('click', (e) => {
  const item = e.target.closest('.nav-item');
  if (!item) return;
  document.querySelectorAll('.nav-item').forEach(el => el.classList.remove('active'));
  item.classList.add('active');

  const target = item.dataset.target;
  switchView(target);

  if (target === 'placeholder') {
    document.getElementById('placeholder-title').textContent = `Розділ «${item.dataset.label}»`;
    showToast(`Розділ «${item.dataset.label}» ще в розробці`);
  }
});

document.getElementById('back-to-today').addEventListener('click', () => {
  document.querySelectorAll('.nav-item').forEach(el => el.classList.remove('active'));
  document.querySelector('.nav-item[data-target="today"]').classList.add('active');
  switchView('today');
});

// --- Вибір угоди зі списку ---
function renderDetail(index) {
  const deal = deals[index];
  if (!deal) return;
  currentIndex = index;

  document.getElementById('detail-panel').hidden = false;
  document.getElementById('detail-empty').hidden = true;

  const priorityEl = document.getElementById('detail-priority');
  priorityEl.textContent = deal.priorityLabel;
  priorityEl.className = 'priority ' + deal.priorityClass;

  document.getElementById('detail-title').textContent = deal.title;
  document.getElementById('detail-stage').textContent = deal.stage;
  document.getElementById('detail-amount').textContent = deal.amount;
  document.getElementById('detail-owner').textContent = deal.owner;
  document.getElementById('detail-lastcontact').textContent = deal.lastContact;
  document.getElementById('detail-why').textContent = deal.why;
  document.getElementById('detail-action').textContent = deal.action;

  const draftEl = document.getElementById('draft-text');
  draftEl.innerHTML = deal.draft.split('\n\n').join('<br><br>');
  updateCharCount();
}

function updateCharCount() {
  const draftEl = document.getElementById('draft-text');
  const len = draftEl.innerText.trim().length;
  const word = ukrainianCharWord(len);
  document.getElementById('char-count').textContent = `${len} ${word}`;
}

function ukrainianCharWord(n) {
  const mod100 = n % 100;
  const mod10 = n % 10;
  if (mod100 >= 11 && mod100 <= 14) return 'символів';
  if (mod10 === 1) return 'символ';
  if (mod10 >= 2 && mod10 <= 4) return 'символи';
  return 'символів';
}

document.getElementById('action-list').addEventListener('click', (e) => {
  const li = e.target.closest('.action-item');
  if (!li) return;
  document.querySelectorAll('.action-item').forEach(el => el.classList.remove('selected'));
  li.classList.add('selected');
  renderDetail(li.dataset.index);
});

// --- Закриття деталей ---
document.getElementById('detail-close').addEventListener('click', () => {
  document.getElementById('detail-panel').hidden = true;
  document.getElementById('detail-empty').hidden = false;
  document.querySelectorAll('.action-item').forEach(el => el.classList.remove('selected'));
});

document.getElementById('detail-more').addEventListener('click', () => {
  showToast('Додаткові дії ще в розробці');
});

// --- Копіювання чернетки ---
document.getElementById('copy-btn').addEventListener('click', async (e) => {
  const text = document.getElementById('draft-text').innerText.trim();
  try {
    await navigator.clipboard.writeText(text);
  } catch (err) {
    // clipboard API недоступний (напр. без HTTPS) — ігноруємо, кнопка все одно дасть відгук
  }
  const btn = e.currentTarget;
  const original = btn.textContent;
  btn.textContent = '✓ Скопійовано';
  setTimeout(() => { btn.textContent = original; }, 1500);
});

// --- Редагування чернетки ---
document.getElementById('edit-btn').addEventListener('click', (e) => {
  const draftEl = document.getElementById('draft-text');
  const btn = e.currentTarget;
  const editing = draftEl.getAttribute('contenteditable') === 'true';

  if (editing) {
    draftEl.removeAttribute('contenteditable');
    btn.textContent = '✎ Редагувати';
  } else {
    draftEl.setAttribute('contenteditable', 'true');
    draftEl.focus();
    btn.textContent = '✓ Зберегти';
  }
});

document.getElementById('draft-text').addEventListener('input', updateCharCount);

// --- Дії з угодою ---
function resolveCurrentDeal(message) {
  const li = document.querySelector(`.action-item[data-index="${currentIndex}"]`);
  if (!li) return;
  li.classList.add('dismissing');
  showToast(message);
  setTimeout(() => {
    li.remove();
    delete deals[currentIndex];
    const next = document.querySelector('.action-item:not(.page-empty-state)');
    if (next) {
      document.querySelectorAll('.action-item').forEach(el => el.classList.remove('selected'));
      next.classList.add('selected');
      renderDetail(next.dataset.index);
    } else {
      document.getElementById('detail-panel').hidden = true;
      document.getElementById('detail-empty').hidden = false;
    }
  }, 220);
}

document.getElementById('confirm-btn').addEventListener('click', () => {
  resolveCurrentDeal('Завдання створено в CRM (демо)');
});

document.getElementById('snooze-btn').addEventListener('click', () => {
  resolveCurrentDeal('Угоду відкладено (демо)');
});

document.getElementById('dismiss-btn').addEventListener('click', () => {
  resolveCurrentDeal('Позначено як неактуальне (демо)');
});

// --- Сортування ---
document.getElementById('sort-btn').addEventListener('click', (e) => {
  sortByAmount = !sortByAmount;
  const btn = e.currentTarget;
  btn.innerHTML = (sortByAmount ? 'За сумою' : 'За пріоритетом') + ' <span class="caret">⌄</span>';

  const priorityRank = { high: 3, mid: 2, low: 1 };
  const list = document.getElementById('action-list');
  const items = Array.from(list.querySelectorAll('.action-item'));

  items.sort((a, b) => {
    if (sortByAmount) {
      return Number(b.dataset.amount) - Number(a.dataset.amount);
    }
    return priorityRank[b.dataset.priority] - priorityRank[a.dataset.priority];
  });

  items.forEach(item => list.insertBefore(item, document.getElementById('page-empty')));
});

// --- Фільтри ---
document.getElementById('filter-btn').addEventListener('click', () => {
  const dropdown = document.getElementById('filter-dropdown');
  dropdown.hidden = !dropdown.hidden;
});

document.addEventListener('click', (e) => {
  const dropdown = document.getElementById('filter-dropdown');
  if (dropdown.hidden) return;
  if (!dropdown.contains(e.target) && e.target.id !== 'filter-btn') {
    dropdown.hidden = true;
  }
});

document.querySelectorAll('.filter-check').forEach(checkbox => {
  checkbox.addEventListener('change', () => {
    const active = Array.from(document.querySelectorAll('.filter-check'))
      .filter(c => c.checked).map(c => c.value);
    document.querySelectorAll('.action-item[data-priority]').forEach(li => {
      li.style.display = active.includes(li.dataset.priority) ? '' : 'none';
    });
  });
});

// --- Пагінація (демо: реальні дані лише для перших 7 угод) ---
function goToPage(page) {
  currentPage = Math.min(3, Math.max(1, page));
  const realItems = document.querySelectorAll('.action-item[data-index]');
  const emptyState = document.getElementById('page-empty');

  document.querySelectorAll('.page-btn[data-page]').forEach(btn => {
    btn.classList.toggle('active', Number(btn.dataset.page) === currentPage);
  });

  if (currentPage === 1) {
    realItems.forEach(li => { li.style.display = ''; });
    emptyState.hidden = true;
    document.getElementById('pagination-info').textContent = 'Показано 1–7 з 18';
  } else {
    realItems.forEach(li => { li.style.display = 'none'; });
    emptyState.hidden = false;
    const from = currentPage === 2 ? 8 : 15;
    const to = currentPage === 2 ? 14 : 18;
    document.getElementById('pagination-info').textContent = `Показано ${from}–${to} з 18`;
  }
}

document.querySelectorAll('.page-btn[data-page]').forEach(btn => {
  btn.addEventListener('click', () => goToPage(Number(btn.dataset.page)));
});
document.getElementById('page-prev').addEventListener('click', () => goToPage(currentPage - 1));
document.getElementById('page-next').addEventListener('click', () => goToPage(currentPage + 1));

// --- Оновити ---
document.getElementById('refresh-btn').addEventListener('click', (e) => {
  const btn = e.currentTarget;
  btn.classList.add('spinning');
  setTimeout(() => btn.classList.remove('spinning'), 600);
  showToast('Дані оновлено (демо)');
});

// =====================================================================
// Розділ «Угоди»
// =====================================================================

const allDeals = [
  { id: 'd1', company: 'ТОВ «БудПроект»', amount: 450000, stage: 'КП надіслано', priority: 'high', idleDays: 2, owner: 'Олексій Смирнов', ownerIcon: '👨', created: '12 липня 2024', probability: '60%',
    noteType: 'warn', noteTitle: '⚠️ Ризик втрати', note: 'Клієнт запросив комерційну пропозицію 2 дні тому і не відповідає. На цьому етапі рішення зазвичай ухвалюють за 1–2 дні.',
    timeline: [{ stage: 'Новий лід', date: '12 липня' }, { stage: 'Кваліфікація', date: '15 липня' }, { stage: 'КП надіслано', date: '23 липня' }] },

  { id: 'd2', company: 'ТОВ «ПромТех»', amount: 320000, stage: 'Переговори', priority: 'mid', idleDays: 5, owner: 'Марина Ковальчук', ownerIcon: '👩', created: '2 липня 2024', probability: '45%',
    noteType: 'warn', noteTitle: '⚠️ Ризик втрати', note: 'Переговори призупинились 5 днів тому без явної причини. Варто уточнити наявність заперечень.',
    timeline: [{ stage: 'Новий лід', date: '2 липня' }, { stage: 'КП надіслано', date: '10 липня' }, { stage: 'Переговори', date: '18 липня' }] },

  { id: 'd3', company: 'ТОВ «МегаПласт»', amount: 280000, stage: 'КП надіслано', priority: 'mid', idleDays: 4, owner: 'Дмитро Іванов', ownerIcon: '👨', created: '8 липня 2024', probability: '50%',
    noteType: 'neutral', noteTitle: 'Статус угоди', note: 'Пропозицію надіслано 4 дні тому. Пауза наближається до критичної — потрібне нагадування.',
    timeline: [{ stage: 'Новий лід', date: '8 липня' }, { stage: 'Кваліфікація', date: '14 липня' }, { stage: 'КП надіслано', date: '21 липня' }] },

  { id: 'd4', company: 'ТОВ «БудКомплект»', amount: 150000, stage: 'Новий лід', priority: 'low', idleDays: 0, owner: 'Марина Ковальчук', ownerIcon: '👩', created: '25 липня 2024', probability: '20%',
    noteType: 'success', noteTitle: '✅ Все за планом', note: 'Свіжий лід у роботі. Перша відповідь протягом дня суттєво підвищує шанс конверсії.',
    timeline: [{ stage: 'Новий лід', date: '25 липня' }] },

  { id: 'd5', company: 'ТОВ «Інтер\'єр+»', amount: 210000, stage: 'Зустріч проведена', priority: 'low', idleDays: 7, owner: 'Дмитро Іванов', ownerIcon: '👨', created: '28 червня 2024', probability: '55%',
    noteType: 'warn', noteTitle: '⚠️ Потребує уваги', note: 'Після зустрічі минуло 7 днів без наступного контакту. Клієнт може чекати на ваш крок.',
    timeline: [{ stage: 'Новий лід', date: '28 червня' }, { stage: 'Кваліфікація', date: '4 липня' }, { stage: 'Зустріч проведена', date: '18 липня' }] },

  { id: 'd6', company: 'ТОВ «Вектор»', amount: 95000, stage: 'Переговори', priority: 'low', idleDays: 12, owner: 'Марина Ковальчук', ownerIcon: '👩', created: '10 червня 2024', probability: '30%',
    noteType: 'warn', noteTitle: '⚠️ Угода зависла', note: '12 днів без активності — найдовша пауза у воронці. Висока ймовірність, що угода втрачена.',
    timeline: [{ stage: 'Новий лід', date: '10 червня' }, { stage: 'КП надіслано', date: '25 червня' }, { stage: 'Переговори', date: '13 липня' }] },

  { id: 'd7', company: 'ФОП Смирнов О.О.', amount: 75000, stage: 'КП надіслано', priority: 'low', idleDays: 8, owner: 'Дмитро Іванов', ownerIcon: '👨', created: '1 липня 2024', probability: '35%',
    noteType: 'neutral', noteTitle: 'Статус угоди', note: 'Пропозицію надіслано 8 днів тому, відповіді немає. Сума невелика, але угода досі відкрита.',
    timeline: [{ stage: 'Новий лід', date: '1 липня' }, { stage: 'КП надіслано', date: '17 липня' }] },

  { id: 'd8', company: 'ТОВ «Агротрейд»', amount: 620000, stage: 'Договір', priority: 'high', idleDays: 1, owner: 'Олексій Смирнов', ownerIcon: '👨', created: '20 травня 2024', probability: '85%',
    noteType: 'success', noteTitle: '✅ Все за планом', note: 'Найбільша угода у воронці на фінальному етапі. Договір на погодженні у юристів клієнта.',
    timeline: [{ stage: 'Новий лід', date: '20 травня' }, { stage: 'КП надіслано', date: '3 червня' }, { stage: 'Переговори', date: '28 червня' }, { stage: 'Договір', date: '24 липня' }] },

  { id: 'd9', company: 'ТОВ «Логістик Плюс»', amount: 385000, stage: 'Переговори', priority: 'high', idleDays: 9, owner: 'Олексій Смирнов', ownerIcon: '👨', created: '18 червня 2024', probability: '40%',
    noteType: 'warn', noteTitle: '⚠️ Угода зависла', note: 'Велика сума і 9 днів тиші на етапі переговорів. Потрібен дзвінок особисто, не лист.',
    timeline: [{ stage: 'Новий лід', date: '18 червня' }, { stage: 'Кваліфікація', date: '24 червня' }, { stage: 'Переговори', date: '16 липня' }] },

  { id: 'd10', company: 'ТОВ «Стальконструкція»', amount: 540000, stage: 'Зустріч проведена', priority: 'high', idleDays: 3, owner: 'Марина Ковальчук', ownerIcon: '👩', created: '5 липня 2024', probability: '65%',
    noteType: 'neutral', noteTitle: 'Статус угоди', note: 'Зустріч пройшла успішно, клієнт запросив розрахунок під власні обсяги.',
    timeline: [{ stage: 'Новий лід', date: '5 липня' }, { stage: 'Кваліфікація', date: '11 липня' }, { stage: 'Зустріч проведена', date: '22 липня' }] },

  { id: 'd11', company: 'ФОП Гриценко І.В.', amount: 48000, stage: 'Кваліфікація', priority: 'low', idleDays: 6, owner: 'Дмитро Іванов', ownerIcon: '👨', created: '14 липня 2024', probability: '25%',
    noteType: 'neutral', noteTitle: 'Статус угоди', note: 'Бюджет клієнта ще не підтверджено. Потрібно уточнити терміни та обсяг замовлення.',
    timeline: [{ stage: 'Новий лід', date: '14 липня' }, { stage: 'Кваліфікація', date: '19 липня' }] },

  { id: 'd12', company: 'ТОВ «Енергосервіс»', amount: 295000, stage: 'КП надіслано', priority: 'mid', idleDays: 14, owner: 'Марина Ковальчук', ownerIcon: '👩', created: '3 червня 2024', probability: '20%',
    noteType: 'warn', noteTitle: '⚠️ Угода зависла', note: '14 днів без реакції на пропозицію. Варто зробити останню спробу або перевести в архів.',
    timeline: [{ stage: 'Новий лід', date: '3 червня' }, { stage: 'Кваліфікація', date: '17 червня' }, { stage: 'КП надіслано', date: '11 липня' }] }
];

const STAGE_CLASS = {
  'Новий лід': 'stage-new',
  'Кваліфікація': 'stage-qual',
  'КП надіслано': 'stage-offer',
  'Переговори': 'stage-talks',
  'Зустріч проведена': 'stage-meeting',
  'Договір': 'stage-contract'
};

const PRIORITY_LABEL = { high: 'Високий', mid: 'Середній', low: 'Низький' };
const PRIORITY_RANK = { high: 3, mid: 2, low: 1 };
const DEALS_PER_PAGE = 8;

let dealsSort = { key: 'priority', dir: 'desc' };
let dealsPage = 1;
let selectedDealId = null;

function formatMoney(value) {
  return value.toLocaleString('uk-UA').replace(/ /g, ' ') + ' ₴';
}

function dayWord(n) {
  const mod100 = n % 100;
  const mod10 = n % 10;
  if (mod100 >= 11 && mod100 <= 14) return 'днів';
  if (mod10 === 1) return 'день';
  if (mod10 >= 2 && mod10 <= 4) return 'дні';
  return 'днів';
}

function idleLabel(days) {
  return days === 0 ? 'сьогодні' : `${days} ${dayWord(days)} тому`;
}

function getFilteredDeals() {
  const query = document.getElementById('deals-search').value.trim().toLowerCase();
  const stage = document.getElementById('deals-stage').value;
  const priority = document.getElementById('deals-priority').value;

  const filtered = allDeals.filter(deal => {
    if (query && !deal.company.toLowerCase().includes(query)) return false;
    if (stage !== 'all' && deal.stage !== stage) return false;
    if (priority !== 'all' && deal.priority !== priority) return false;
    return true;
  });

  const dir = dealsSort.dir === 'asc' ? 1 : -1;
  filtered.sort((a, b) => {
    switch (dealsSort.key) {
      case 'company': return a.company.localeCompare(b.company, 'uk') * dir;
      case 'amount': return (a.amount - b.amount) * dir;
      case 'idle': return (a.idleDays - b.idleDays) * dir;
      default: return (PRIORITY_RANK[a.priority] - PRIORITY_RANK[b.priority]) * dir;
    }
  });

  return filtered;
}

function renderDealsTable() {
  const filtered = getFilteredDeals();
  const totalPages = Math.max(1, Math.ceil(filtered.length / DEALS_PER_PAGE));
  dealsPage = Math.min(dealsPage, totalPages);

  const start = (dealsPage - 1) * DEALS_PER_PAGE;
  const pageItems = filtered.slice(start, start + DEALS_PER_PAGE);

  const tbody = document.getElementById('deals-tbody');
  tbody.innerHTML = pageItems.map(deal => `
    <tr data-id="${deal.id}"${deal.id === selectedDealId ? ' class="selected"' : ''}>
      <td class="cell-company">${deal.company}</td>
      <td class="cell-amount">${formatMoney(deal.amount)}</td>
      <td><span class="stage-badge ${STAGE_CLASS[deal.stage]}">${deal.stage}</span></td>
      <td><span class="priority priority-${deal.priority}">${PRIORITY_LABEL[deal.priority]}</span></td>
      <td class="cell-idle${deal.idleDays > 7 ? ' stale' : ''}">${idleLabel(deal.idleDays)}</td>
      <td><div class="cell-owner"><span class="owner-avatar">${deal.ownerIcon}</span>${deal.owner}</div></td>
    </tr>
  `).join('');

  document.getElementById('deals-empty').hidden = filtered.length > 0;
  document.getElementById('deals-count').textContent = filtered.length;

  document.getElementById('deals-pagination-info').textContent = filtered.length === 0
    ? 'Нічого не знайдено'
    : `Показано ${start + 1}–${start + pageItems.length} з ${filtered.length}`;

  renderDealsPagination(totalPages);
  renderSortArrows();
}

function renderDealsPagination(totalPages) {
  const container = document.getElementById('deals-pages');
  const buttons = ['<button class="page-btn" data-nav="prev" aria-label="Попередня">‹</button>'];
  for (let page = 1; page <= totalPages; page++) {
    buttons.push(`<button class="page-btn${page === dealsPage ? ' active' : ''}" data-page="${page}">${page}</button>`);
  }
  buttons.push('<button class="page-btn" data-nav="next" aria-label="Наступна">›</button>');
  container.innerHTML = buttons.join('');
}

function renderSortArrows() {
  document.querySelectorAll('.deals-table th.sortable').forEach(th => {
    const arrow = th.querySelector('.sort-arrow');
    arrow.textContent = th.dataset.sort === dealsSort.key ? (dealsSort.dir === 'asc' ? '▲' : '▼') : '';
  });
}

function renderDealsKpi() {
  const sum = allDeals.reduce((acc, deal) => acc + deal.amount, 0);
  const stuck = allDeals.filter(deal => deal.idleDays > 7);
  const stuckSum = stuck.reduce((acc, deal) => acc + deal.amount, 0);

  document.getElementById('kpi-total').textContent = allDeals.length;
  document.getElementById('kpi-sum').textContent = formatMoney(sum);
  document.getElementById('kpi-stuck').textContent = stuck.length;
  document.getElementById('kpi-stuck-sum').textContent = 'на суму ' + formatMoney(stuckSum);
  document.getElementById('kpi-avg').textContent = formatMoney(Math.round(sum / allDeals.length));
}

function openDealDetail(id) {
  const deal = allDeals.find(item => item.id === id);
  if (!deal) return;
  selectedDealId = id;

  document.getElementById('dd-panel').hidden = false;
  document.getElementById('deals-workspace').classList.add('with-detail');

  const priorityEl = document.getElementById('dd-priority');
  priorityEl.textContent = PRIORITY_LABEL[deal.priority] + ' пріоритет';
  priorityEl.className = 'priority priority-' + deal.priority;

  document.getElementById('dd-title').textContent = deal.company;
  document.getElementById('dd-stage').textContent = deal.stage;
  document.getElementById('dd-amount').textContent = formatMoney(deal.amount);
  document.getElementById('dd-owner').textContent = deal.owner;
  document.getElementById('dd-created').textContent = deal.created;
  document.getElementById('dd-probability').textContent = deal.probability;

  const idleEl = document.getElementById('dd-idle');
  idleEl.textContent = idleLabel(deal.idleDays);
  idleEl.className = 'field-value' + (deal.idleDays > 7 ? ' warn' : '');

  const noteBox = document.getElementById('dd-note-box');
  noteBox.className = 'info-box ' + (deal.noteType === 'warn' ? 'warn-box' : deal.noteType === 'success' ? 'success-box' : 'neutral-box');
  document.getElementById('dd-note-title').textContent = deal.noteTitle;
  document.getElementById('dd-note').textContent = deal.note;

  document.getElementById('dd-timeline').innerHTML = deal.timeline.map((step, i) => `
    <li${i === deal.timeline.length - 1 ? ' class="current"' : ''}>
      <div class="timeline-stage">${step.stage}</div>
      <div class="timeline-date">${step.date}</div>
    </li>
  `).join('');

  document.querySelectorAll('#deals-tbody tr').forEach(tr => {
    tr.classList.toggle('selected', tr.dataset.id === id);
  });
}

function closeDealDetail() {
  selectedDealId = null;
  document.getElementById('dd-panel').hidden = true;
  document.getElementById('deals-workspace').classList.remove('with-detail');
  document.querySelectorAll('#deals-tbody tr').forEach(tr => tr.classList.remove('selected'));
}

document.getElementById('deals-tbody').addEventListener('click', (e) => {
  const row = e.target.closest('tr');
  if (!row) return;
  openDealDetail(row.dataset.id);
});

document.getElementById('dd-close').addEventListener('click', closeDealDetail);
document.getElementById('dd-more').addEventListener('click', () => showToast('Додаткові дії ще в розробці'));
document.getElementById('dd-open-crm').addEventListener('click', () => showToast('Перехід у CRM (демо)'));
document.getElementById('dd-task').addEventListener('click', () => showToast('Завдання створено в CRM (демо)'));
document.getElementById('dd-archive').addEventListener('click', () => showToast('Угоду переміщено в архів (демо)'));

document.querySelectorAll('.deals-table th.sortable').forEach(th => {
  th.addEventListener('click', () => {
    const key = th.dataset.sort;
    if (dealsSort.key === key) {
      dealsSort.dir = dealsSort.dir === 'asc' ? 'desc' : 'asc';
    } else {
      dealsSort = { key, dir: key === 'company' ? 'asc' : 'desc' };
    }
    dealsPage = 1;
    renderDealsTable();
  });
});

['deals-search', 'deals-stage', 'deals-priority'].forEach(id => {
  const el = document.getElementById(id);
  el.addEventListener(id === 'deals-search' ? 'input' : 'change', () => {
    dealsPage = 1;
    renderDealsTable();
  });
});

document.getElementById('deals-pages').addEventListener('click', (e) => {
  const btn = e.target.closest('.page-btn');
  if (!btn) return;
  const totalPages = Math.max(1, Math.ceil(getFilteredDeals().length / DEALS_PER_PAGE));
  if (btn.dataset.page) {
    dealsPage = Number(btn.dataset.page);
  } else {
    dealsPage = Math.min(totalPages, Math.max(1, dealsPage + (btn.dataset.nav === 'next' ? 1 : -1)));
  }
  renderDealsTable();
});

document.getElementById('deals-refresh').addEventListener('click', (e) => {
  const btn = e.currentTarget;
  btn.classList.add('spinning');
  setTimeout(() => btn.classList.remove('spinning'), 600);
  showToast('Дані оновлено (демо)');
});

document.getElementById('deals-export').addEventListener('click', () => {
  showToast('Експорт у CSV ще в розробці');
});

renderDealsKpi();
renderDealsTable();
