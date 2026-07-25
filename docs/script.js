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
document.getElementById('nav').addEventListener('click', (e) => {
  const item = e.target.closest('.nav-item');
  if (!item) return;
  document.querySelectorAll('.nav-item').forEach(el => el.classList.remove('active'));
  item.classList.add('active');

  const today = document.getElementById('view-today');
  const placeholder = document.getElementById('view-placeholder');

  if (item.dataset.target === 'today') {
    today.hidden = false;
    placeholder.hidden = true;
  } else {
    today.hidden = true;
    placeholder.hidden = false;
    document.getElementById('placeholder-title').textContent = `Розділ «${item.dataset.label}»`;
    showToast(`Розділ «${item.dataset.label}» ще в розробці`);
  }
});

document.getElementById('back-to-today').addEventListener('click', () => {
  document.querySelectorAll('.nav-item').forEach(el => el.classList.remove('active'));
  document.querySelector('.nav-item[data-target="today"]').classList.add('active');
  document.getElementById('view-today').hidden = false;
  document.getElementById('view-placeholder').hidden = true;
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
